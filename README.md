# hashget

Hashget is network *deduplication* tool working together with usual compression utilities (such as tar/gz/xz).  

While usual compression tools uses mathematical algorithms for compressing data, hashget finds which files could be 
downloaded from public (e.g. WordPress or Debian servers) or private (e.g. your company internal website) resources and 
excludes it from archive (leaving only very short meta-information about it).

Upon decompressing, hashget downloads these files, verifies hashsum and places it on target system with same 
permissions, ownership, atime and mtime.

Hashget compression is lossless. If some files are changed, it will be kept as-is (not replaced by original vendor 
files). After restored from archive it will have same files and each file will have same content as it was 
before packing.

## Effectiveness
|Data sample            | unpacked size  |.tar.gz         | hashget .tar.gz         | 
|----                   |----            |----            |----                     |
|Wordpress-5.1.1        | 43 Mb          | 11 Mb ( 26% )  | 155 Kb ( **0.3%** )     |
|Linux kernel  5.0.4    | 934 Mb         | 161 Mb ( 20% ) | 4.7 Mb ( **0.5%** )     |
|Debian 9 (LAMP) LXC VM | 724 Mb         | 165 Mb ( 23% ) | 4.1 Mb ( **0.5%** )     |

Unpacked size measured with `du -sh` command. Ratio calculated as `dh -shb compressed.tar.gz` / `du -shb original-dir` 
in percents. Debian filesystem was clean and packed without temporary files (see example below).

## Installation

Pip (recommended):
```shell
pip3 install hashget[plugins]
```

or clone from git:
```shell
git clone https://gitlab.com/yaroslaff/hashget.git
```

## QuickStart

### Compressing (manual indexing)
```shell
# prepare test data
$ mkdir -p /tmp/test/wp
$ cd /tmp
$ wget https://wordpress.org/wordpress-5.1.1.zip 
$ cd /tmp/test/wp
$ unzip -q /tmp/wordpress-5.1.1.zip

# index data
$ hashget --submit https://wordpress.org/wordpress-5.1.1.zip -p my --hashserver

# pack
$ hashget -zf /tmp/wordpress-hashget.tar.gz --pack . --hashserver
STEP 1/3 Indexing...
Indexing done in 0.07s. 0 local + 0 pulled + 0 new = 0 total packages
STEP 2/3 prepare exclude list for packing...
saved: 1373 files, 1 pkgs, size: 37.9M. Download: 11.0M
STEP 3/3 tarring...
. (38.1M) packed into /tmp/wordpress-hashget.tar.gz (154.7K)
```

`-f` to specify filename, `-z` to gzip it, `--pack .` commands which directory to pack and `--hashserver` without value disables 
remote hashservers.

You can check local indexes HashDB with [hashget-admin](https://gitlab.com/yaroslaff/hashget/wikis/hashget-admin) 
utility.

### Decompressing 

Unpack .tar.gz and then `hashget -u` that directory (which has hidden file .hashget-restore.json).

```shell
$ mkdir /tmp/test/wp-unpacked
$ cd /tmp/test/wp-unpacked
$ tar -xzf /tmp/wordpress-hashget.tar.gz
$ hashget -u . --hashserver
Recovered 1373/1373 files 37.9M bytes (0 downloaded, 11.0M cached) in 6.13s
```

You can delete .hashget-restore.json file after this if you want. Now /tmp/test/wp-unpacked restored from tiny 150K 
hashget archive is same as /tmp/test/wp.

> Manual indexing is easy way to optimize packing of individual large packages.

## Advanced


### Debian VM compressing (built-in plugin)
Compressing [test machine](https://gitlab.com/yaroslaff/hashget/wikis/Test-machine): 

(Since it requires access to VM filesystem, run as user root or use sudo)

```shell
hashget --pack /var/lib/lxc/mydebvm/rootfs/ -zf /tmp/mydebvm.tar.gz \
    --exclude var/cache/apt var/lib/apt/lists
STEP 1/3 Indexing debian packages...
Total: 222 packages
Indexing done in 0.02s. 222 local + 0 pulled + 0 new = 222 total.
STEP 2/3 prepare exclude list for packing...
saved: 8515 files, 216 pkgs, size: 445.8M. Download: 98.7M
STEP 3/3 tarring...
/var/lib/lxc/mydebvm/rootfs/ (687.2M) packed into /tmp/mydebian.tar.gz (4.0M)
```

`--exclude` directive tells hashget and tar to skip some directories which are not necessary in backup. 
(You can omit it, backup will be larger)

Built-in debian plugin automatically discovers installed debian packages, downloads index files from hashserver 
(to speed-up indexing) or download packages and index itself (if not found on hashserver). HashPackages (indexes) are 
stored in local hashdb, so next time you will pack this directory, it will not download and index same data again and 
will work much faster.

For each package hashget archive will store link to [snapshot.debian.org](https://snapshot.debian.org) in restore-file.
snapshot links are permanent and works since 2010. Unfortunately, other deb/apt based linux distributions do not have 
such snapshots, so this method is very effective only for Debian. 
You may [disable this heuristic](https://gitlab.com/yaroslaff/hashget/wikis/Disable%20heuristics%20and%20HashDB) 
when packing other OS.

### Hint files
If our package is indexed (like we just did with wordpress) it will be very effectively deduplicated on packing.
But what if it's not indexed? For example, if you cleaned hashdb cache or if you will restored this backup on other 
machine and pack it again. It will take it's full space again. 

We will delete index for this file:
```shell
hashget-admin --purge --hp wordpress-5.1.1-ru_RU.zip
```
(you can get index filename with `hashget-admin --list -p PROJECT` command)

Now, if you will make hashget --pack , it will make huge 22M archive again, our magic is lost...

Now, create special small *hint* file hashget-hint.json (or .hashget-hint.json , 
if you want it to be hidden) in /tmp/test with this content:
```json
{
	"project": "wordpress.org",
	"url": "https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip"
}
```

And now try compress it again:
```shell
$ hashget --pack /tmp/test -zf /tmp/test.tar.gz
STEP 1/3 Indexing...
submitting https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip
STEP 2/3 prepare exclude list for packing...
saved: 1396 files, 1 pkgs, size: 52.2M. Download: 11.7M
STEP 3/3 tarring...
/tmp/test (52.3M) packed into /tmp/test.tar.gz (157.9K)
```

Great! Hashget used hint file and automatically indexed file, so we got our fantastic compression rate again.

> Directories with hint files are packed effectively even if not indexed before. If you are developer, 
you can include hashget-hint file inside your package files to make it backup-friendly. 
This is much more simple way then writing plugin. 

### Heuristic plugins
Heuristics are small plugins (installed when you did `pip3 install hashget[plugins]`, or can be installed separately)
which can auto-detect some non-indexed files which could be indexed. You already know build-in heuristics for Debian 
and hint files, but hashget could be extended with third-party plugins.

Lets try test with linux kernel sources package (100Mb+):

```shell
$ mkdir /tmp/lk 
$ cd /tmp/lk
$ wget -q https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
$ tar -xf linux-5.0.4.tar.xz 
$ du -sh .
1.1G	.
```

If we will pack this machine same way as before we will see this:
```shell
$ hashget --pack /tmp/lk/ -zf /tmp/lk.tar.gz --hashserver
STEP 1/3 Indexing...
submitting https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
Indexing done in 199.27s. 1 local + 0 pulled + 1 new = 2 total packages
STEP 2/3 prepare exclude list for packing...
saved: 50580 files, 1 pkgs, size: 869.3M. Download: 100.4M
STEP 3/3 tarring...
/tmp/lk/ (875.3M) packed into /tmp/lk.tar.gz (4.6M)
```

One very interesting line here is:
```
submitting https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
```

Hashget detected linux kernel sources package, downloaded and indexed it. And we got fantastic result again: almost 200 times! 
Package was not indexed before and was indexed during packing.

This happened because hashget has heuristical plugin which detects linux kernel sources and guesses URL to index it. 
This plugin puts index files for kernel packages into 'kernel.org' hashget project.

If you will make `hashget-admin --status` you will see kernel.org project. `hashget-admin --list -p PROJECT` will 
show content of project:
```shell
hashget-admin --list -p kernel.org
linux-5.0.5.tar.xz (767/50579)
```

Even when new kernel package will be released (and it's not indexed anywhere), hashget will detect it and 
automatically index (at least while new linux kernels will match same 'template' as it matches now for kernels 
1.0 to 5.0.6).

> Users and developers of large packages can write their own hashget plugins using [Linux kernel hashget plugin](https://gitlab.com/yaroslaff/hashget-kernel_org/)
as example. 

### What you should index 
You should index ONLY static and permanent files, which will be available on same URL with same content.
Not all projects provides such files. Usual linux package repositories has only latest files so it's not good for this
purpose, but debian has great [snapshot.debian.org](https://snapshot.debian.org/) repository, which makes Debian great 
for hashget compression.

Do not index *latest* files, because content will change    later (it's not _static_). E.g. you may index 
https://wordpress.org/wordpress-5.1.1.zip but you should not index https://wordpress.org/latest.zip 

### Differential and incremental backups
See [Incremental backups](https://gitlab.com/yaroslaff/hashget/wikis/incremental) chapter in wiki doc.

### Using local file pool
It's possible to use local or remote (e.g. on Intranet HTTP server) file pool. This can help to unpack archives even 
when original server is not available. 

Pool populated automatically if --pool given to certain operations (`--submit`, `--index`, `--pack`, `--postunpack`/`-u`):

For example:
~~~
$ mkdir /tmp/pool
$ hashget --submit https://wordpress.org/wordpress-5.1.1.zip --pool /tmp/pool/ -p my
$ ls /tmp/pool
wordpress-5.1.1.zip
~~~
When doing `--postunpack` (`-u`) with `--pool`, hashget will read files from pool, and write it there (if file 
was not found in pool and downloaded, it will be saved to pool).


~~~
# Empty pool 
$ hashget -u . --pool /tmp/pool
...
Recovered 8534/8534 files 450.0M bytes (0 downloaded, 0 from pool, 98.7M cached) in 155.92s

# Pool populated now
$ LANG=C ls /tmp/pool
adduser_3.115_all.deb                                  liblz4-1_0.0~r131-2+b1_amd64.deb
apache2-bin_2.4.25-3+deb9u6_amd64.deb                  liblzma5_5.2.2-1.2+b1_amd64.deb
...

# Now packages are taken from pool
$ hashget -u . --pool /tmp/pool
...
Recovered 8534/8534 files 450.0M bytes (0 downloaded, 98.7M from pool, 0 cached) in 146.92s
~~~

# Documentation
For more detailed documentation see [Wiki](https://gitlab.com/yaroslaff/hashget/wikis/home).

