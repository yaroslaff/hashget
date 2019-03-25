# hashget

Network deduplication tool for archiving (backup) debian virtual machines (mostly). For example, very useful for backup LXC containers 
before uploading to Amazon Glacier. 

When compressing, hashget replaces *indexed static files* (which could be downloaded by static URL) 
to it's hashes and URLs. This can compress 600Mb debian root filesystem with mysql, apache and other software to just 4Mb !

When decompressing, hashget downloads these files, verifies hashsum and places it on target system with same 
permissions, ownership, atime and mtime.

Hashget archive (in contrast to incremental and differential archive) is 'self-sufficient in same world' 
(where Debian or Linux kernel projects are still alive). 

## Installation

Pip (recommended):
~~~
pip3 install hashget
~~~

or clone from git:
~~~
git clone https://gitlab.com/yaroslaff/hashget.git
~~~


## QuickStart

### Compressing

Compressing [test machine](https://gitlab.com/yaroslaff/hashget/wikis/Test-machine): 

~~~
# hashget -zf /tmp/mydebvm.tar.gz --pack /var/lib/lxc/mydebvm/rootfs/ --exclude var/cache/apt var/lib/apt/lists 
STEP 1/3 Crawling...
Total: 222 packages
Crawling done in 0.01s. 222 total, 0 new, 0 already in db.
STEP 2/3 prepare exclude list for packing...
saved: 8515 files, 219 pkgs, size: 445.8M
STEP 3/3 tarring...
/var/lib/lxc/mydebvm/rootfs/ (687.2M) packed into /tmp/mydebvm.tar.gz (4.0M)
~~~

Now lets compare results with usual tarring
~~~
# du -sh --apparent-size /var/lib/lxc/mydebvm/rootfs/
693M	/var/lib/lxc/mydebvm/rootfs/

# tar -czf /tmp/mydebvm-orig.tar.gz  --exclude=var/cache/apt --exclude=var/lib/apt/lists -C /var/lib/lxc/mydebvm/rootfs/ .

# ls -lh mydebvm*
-rw-r--r-- 1 root root 165M мар 25 19:58 mydebvm-orig.tar.gz
-rw-r--r-- 1 root root 4,1M мар 25 19:54 mydebvm.tar.gz
~~~
Optimized backup is 40 times smaller!

### Decompressing

Untarring:
~~~
# tar -xzf mydebvm.tar.gz -C rootfs
# du -sh --apparent-size rootfs/
130M	rootfs/
~~~

After untarring, we have just 130 Mb. Now, get all the missing files with hashget:
~~~
root@mir:/tmp# hashget -u rootfs/
Recovered 8534/8534 files 450.0M bytes (49.9M downloaded, 49.1M cached) in 242.68s
~~~
(you can run with -v for verbosity)

Now we have fully working debian system. Some files are still missing (e.g. APT list files in /var/lib/apt/lists, 
which we explicitly --exclude'd) but can be created with 'apt update' command.

## Adding (indexing) files to local HashDB
Now, lets add some files to our test machine:

~~~
mydebvm# wget -q https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
mydebvm# tar -xf linux-5.0.4.tar.xz 
mydebvm# du -sh --apparent-size .
893M	.
~~~

We added almost 900Mb of files to system, Lets see how it will be compressed:
~~~
# hashget -zf /tmp/mydebvm.tar.gz --pack /var/lib/lxc/mydebvm/rootfs/ --exclude var/cache/apt var/lib/apt/lists 
STEP 1/3 Crawling...
Total: 222 packages
Crawling done in 0.01s. 222 total, 0 new, 0 already in db.
STEP 2/3 prepare exclude list for packing...
saved: 8515 files, 219 pkgs, size: 445.8M
STEP 3/3 tarring...
/var/lib/lxc/mydebvm/rootfs/ (1.5G) packed into /tmp/mydebvm.tar.gz (265.0M)
~~~

Still very good, but 265M is not as impressive as 4M. Lets fix miracle and make it impressive again!

~~~
hashget --project my --submit https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
~~~  
We created our own project 'my' and indexed file https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz

We can look our project details:
~~~
# hashget-admin --status --project my
my DirHashDB(path:/var/cache/hashget/hashdb/my stor:basename pkgtype:generic packages:0)
  size: 4.1M
  packages: 1
  first crawled: 2019-03-25 21:54:54
  last_crawled: 2019-03-25 21:54:54
  files: 50579
  anchors: 767
  packages size: 100.4M
  files size: 774.9M
  indexed size: 768.9M (99.23%)
  noanchor packages: 0
  noanchor size: 0
  no anchor link: 0
  bad anchor link: 0
~~~
It takes just 4M on disk, has 1 package indexed (100.4M), over 50K total files. 

You can list contents of project:
~~~
# hashget-admin --list --project my
linux-5.0.4.tar.xz (767/50579)
~~~
Here you see list of all (one) indexed packages. This package has 50K files and 700+ 'anchors' (large files, over 100K).

Now, lets compress again, with same command:
~~~
STEP 1/3 Crawling...
Total: 222 packages
Crawling done in 0.00s. 222 total, 0 new, 0 already in db.
STEP 2/3 prepare exclude list for packing...
saved: 59095 files, 220 pkgs, size: 1.3G
STEP 3/3 tarring...
/var/lib/lxc/mydebvm/rootfs/ (1.5G) packed into /tmp/mydebvm.tar.gz (8.6M)
~~~

Great! We packed 1.5G into just 8.6Mb! 

Hashget packs this into 8 Mb in 28 seconds (on my Core i5 computer) vs 426Mb in 48 seconds with plain tar -czf. 
It's two times faster and 53 times more effective on indexed static files.

## What you should NOT index
You should index ONLY static and permanent files, which will be available on same URL with same content.
Not all projects provides such files. Usual linux package repositories has only latest files so it's not good for this
purpose, but debian has great [snapshot.debian.org](https://snapshot.debian.org/) repository, which makes Debian great 
for hashget compression.

Do not index *latest* files, because content will change    later (it's not _static_). E.g. you may index 
https://wordpress.org/wordpress-5.1.1.zip but you should not index https://wordpress.org/latest.zip 

## Not only Debian, not only virtual machines
For now development hashserver has index files (*HashPackages*) for Debian only. But this does not means you can use 
power of hashget only for debian VMs. In previous example you added linux kernel to local HashDB. You can pack anything
which has indexed files from HashDB:
~~~
# wget -q https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.4.tar.xz
# tar -xf linux-5.0.4.tar.xz
# hashget -zf /tmp/mykernel.tar.gz --pack .
STEP 1/3 Crawling [skipped]...
STEP 2/3 prepare exclude list for packing...
saved: 50580 files, 1 pkgs, size: 869.3M
STEP 3/3 tarring...
. (875.3M) packed into /tmp/mykernel.tar.gz (4.6M)
~~~


## Documentation
For more detailed documentation see [Wiki](https://gitlab.com/yaroslaff/hashget/wikis/home).



