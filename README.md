# hashget

*You do not need to bear the cost to store files which you can download*

Hashget is network deduplication tool developed mainly for archiving (backup) debian virtual machines (mostly), but 
could be used for other backups too. For example, it's very useful for backup LXC containers 
before uploading to Amazon Glacier. 

Upon compressing, hashget replaces *indexed static files* (which could be downloaded by static URL) 
to it's hashes and URLs. This can compress 600Mb debian root filesystem with mysql, apache and other software to just 4Mb !

Upon decompressing, hashget downloads these files, verifies hashsum and places it on target system with same 
permissions, ownership, atime and mtime.

Hashget archive (in contrast to incremental and differential archive) is 'self-sufficient in same world' 
(where Debian or Linux kernel projects are still alive). 

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

### Compressing

Compressing [test machine](https://gitlab.com/yaroslaff/hashget/wikis/Test-machine): 

```shell
hashget -zf /tmp/mydebvm.tar.gz --pack /var/lib/lxc/mydebvm/rootfs/ \
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

Now lets compare results with usual tarring
```shell
du -sh --apparent-size /var/lib/lxc/mydebvm/rootfs/
693M	/var/lib/lxc/mydebvm/rootfs/

tar -czf /tmp/mydebvm-orig.tar.gz  --exclude=var/cache/apt \
    --exclude=var/lib/apt/lists -C /var/lib/lxc/mydebvm/rootfs/ .

ls -lh mydebvm*
-rw-r--r-- 1 root root 165M Mar 29 00:27 mydebvm-orig.tar.gz
-rw-r--r-- 1 root root 4.1M Mar 29 00:24 mydebvm.tar.gz
```
Optimized backup is 40 times smaller!

### Decompressing

Untarring:
```shell
mkdir rootfs
tar -xzf mydebvm.tar.gz -C rootfs
du -sh --apparent-size rootfs/
130M	rootfs/
```

After untarring, we have just 130 Mb. Now, get all the missing files with hashget:
```shell
hashget -u rootfs/
Recovered 8534/8534 files 450.0M bytes (49.9M downloaded, 49.1M cached) in 242.68s
```
(you can run with -v for verbosity)

Now we have fully working debian system. Some files are still missing (e.g. APT list files in /var/lib/apt/lists, 
which we **explicitly** --exclude'd. Hashget didn't misses anything on it's own) but can be created with 'apt update' command.

## Advanced

### Manually indexing files to local HashDB
Lets make test directory with wordpress for packing.

```shell
mkdir /tmp/test
cd /tmp/test/
wget -q https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip
unzip wordpress-5.1.1-ru_RU.zip 
Archive:  wordpress-5.1.1-ru_RU.zip
   creating: wordpress/
  inflating: wordpress/wp-login.php  
  inflating: wordpress/wp-cron.php   
....
du -sh --apparent-size .
54M	.
```

and now we will pack it:
```shell
hashget -zf /tmp/test.tar.gz --pack /tmp/test/
STEP 1/3 Indexing...
STEP 2/3 prepare exclude list for packing...
saved: 4 files, 3 pkgs, size: 104.6K. Download: 3.8M
STEP 3/3 tarring...
/tmp/test/ (52.3M) packed into /tmp/test.tar.gz (22.1M)
```

Thats same result as usual tar would do. Only ~100K saved (you can see it in .hashget-restore.json file, there are
usual license files). Still ok, but not as impressive as before. Lets fix miracle and make it impressive again!

We will index this WordPress version, and it will be compressed very effectively.
```shell
hashget --project my --submit https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip
hashget -zf /tmp/test.tar.gz --pack /tmp/test/
STEP 1/3 Indexing...
STEP 2/3 prepare exclude list for packing...
saved: 1396 files, 1 pkgs, size: 52.2M. Download: 11.7M
STEP 3/3 tarring...
/tmp/test/ (52.3M) packed into /tmp/test.tar.gz (157.9K)
```
50M packed into 150K. Very good! What other archiver can make such great compression? (300+ times smaller!)

We can look our project details:
```shell
hashget-admin --status -p my
my DirHashDB(path:/var/cache/hashget/hashdb/my stor:basename pkgtype:generic packages:0)
  size: 119.4K
  packages: 1
  first crawled: 2019-04-01 01:45:45
  last_crawled: 2019-04-01 01:45:45
  files: 1395
  anchors: 72
  packages size: 11.7M
  files size: 40.7M
  indexed size: 40.5M (99.61%)
  noanchor packages: 0
  noanchor size: 0
  no anchor link: 0
  bad anchor link: 0
```
It takes just 100K on disk, has 1 package indexed (11.7M), over 1395 total files. You can clean HashDB, but usually 
it's not needed, because HashDB is very small. You can get list of indexes in project with `hashget-admin --list -p my`

And one important thing - hashget archiving keeps all your changes! If you will make any changes in data, e.g.:
```shell
echo zzz >> wordpress/index.php
```
and --pack it, it will be just little bigger (158K for me instead of 157.9) but will keep your changed file as-is.
Modified file has other hashsum, so it will be .tar.gz'ipped and not recovered from wordpress archive as other 
wordpress files.

> Manual indexing is easy way to optimize packing of individual large packages.

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
hashget -zf /tmp/test.tar.gz --pack /tmp/test
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
which can auto-detect some non-indexed files which could be indexed.

Now, lets add some files to our test machine, we will download linux kernel source code, it's very large:
```shell
mydebvm# wget -q https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
mydebvm# tar -xf linux-5.0.4.tar.xz 
mydebvm# du -sh --apparent-size .
893M	.
```

If we will pack this machine same way as before we will see this:
```shell
hashget -zf /tmp/mydebian.tar.gz --pack /var/lib/lxc/mydebvm/rootfs/ \
    --exclude var/cache/apt var/lib/apt/lists
STEP 1/3 Indexing debian packages...
Total: 222 packages
Indexing done in 0.03s. 222 local + 0 pulled + 0 new = 222 total.
submitting https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.5.tar.xz
STEP 2/3 prepare exclude list for packing...
saved: 59095 files, 217 pkgs, size: 1.3G. Download: 199.1M
STEP 3/3 tarring...
/var/lib/lxc/mydebvm/rootfs/ (1.5G) packed into /tmp/mydebian.tar.gz (8.7M)
```

One very interesting line here is:
```
submitting https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.5.tar.xz
```

Hashget detected linux kernel sources package, downloaded and indexed it. And we got fantastic result again: 1.5G 
packed into just 8.7M! Package was not indexed before.

This happened because hashget has heuristical plugin which detects linux kernel sources and guesses URL to index it. 
This plugin puts index files for kernel packages into 'kernel.org' hashget project.

*Hashget packs this into 8 Mb in 28 seconds (on my Core i5 computer) vs 426Mb in 48 seconds with plain tar -czf. 
(And 3 minutes with hashget/tar/gz vs 4 minutes with tar on slower notebook). Hashget packs faster and often 
much more effective.*

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

### Incremental / Differential backups with hashget

Prepare data for test
```shell
$ mkdir /tmp/test
$ dd if=/dev/urandom of=/tmp/test/1M bs=1M count=1
1+0 records in
1+0 records out
1048576 bytes (1.0 MB, 1.0 MiB) copied, 0.0198294 s, 52.9 MB/s
```

Make first full backup (since all data is custom, disable hasherver to make it faster)
```shell

$ hashget -zf /tmp/full.tar.gz --pack /tmp/test --hashserver
STEP 1/3 Indexing...
Indexing done in 0.00s. 0 local + 0 pulled + 0 new = 0 total packages
STEP 2/3 prepare exclude list for packing...
saved: 0 files, 0 pkgs, size: 0. Download: 0
STEP 3/3 tarring...
/tmp/test (1.0M) packed into /tmp/full.tar.gz (1.0M)
```
1M packed into 1M.

Put into into http available resource and index
```shell
$ sudo cp /tmp/full.tar.gz /var/www/html/hg/
$ hashget --submit http://localhost/hg/full.tar.gz --project my_incremental --hashserver
```

Make any changes to data and pack again
```shell
$ date > /tmp/test/date

$ hashget -zf /tmp/full.tar.gz --pack /tmp/test --hashserver
STEP 1/3 Indexing...
Indexing done in 0.00s. 0 local + 0 pulled + 0 new = 0 total packages
STEP 2/3 prepare exclude list for packing...
saved: 1 files, 1 pkgs, size: 1.0M. Download: 1.0M
STEP 3/3 tarring...
/tmp/test (1.0M) packed into /tmp/full.tar.gz (482.0)
```
Incremental (delta) backup is very short. But will require full backup available on same URL for unpacking

To make new full backup delete old from index:
```shell
$ hashget-admin --purge full.tar.gz
```

Or delete my_incremental project completely
```shell
$ hashget-admin --rmproject -p my_incremental --really
```

Now make new full backup:
```shell
$ hashget -zf /tmp/full2.tar.gz --pack /tmp/test --hashserver
STEP 1/3 Indexing...
Indexing done in 0.00s. 0 local + 0 pulled + 0 new = 0 total packages
STEP 2/3 prepare exclude list for packing...
saved: 0 files, 0 pkgs, size: 0. Download: 0
STEP 3/3 tarring...
/tmp/test (1.0M) packed into /tmp/full2.tar.gz (1.0M)
```

Backups will be differential if you will index only full backups, or incremental if you will index also delta backups.

Obviously, full backup name/url could be different, e.g. full-01012019.tar.gz 

When made new full backup, to avoid creating new delta backups based on old full backup, [delete old package](https://gitlab.com/yaroslaff/hashget/wikis/hashget-admin#delete-hashpackages) from HashDB.

# Documentation
For more detailed documentation see [Wiki](https://gitlab.com/yaroslaff/hashget/wikis/home).

