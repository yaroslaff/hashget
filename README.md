# hashget

Deduplication tool for archiving (backup) debian virtual machines


## Installation

~~~
pip3 install hashget
~~~

## commands

### Get file by hash
~~~
$ bin/hashget --get sha256:e30642d899811439c641210124c23444af5f01f5bc8b6f5248101944486122dd
./adduser.local.conf
$ sha256sum adduser.local.conf 
e30642d899811439c641210124c23444af5f01f5bc8b6f5248101944486122dd  adduser.local.conf
~~~

### Pack (deduplicate) and unpack directories (virtual machines)

#### Crawl
`# bin/hashget --debcrawl ~/delme/rootfs/`

Crawls debian packages from rootfs of VM filesystem using snapshot.debian.org into local HashDB (/var/cache/hashget/hashdb). Crawling need to update local database. Crawling not needed if system not installed many new packaged.


#### Prepack

`# bin/hashget --prepack ~/delme/rootfs`

Creates .hashget-restore file in rootfs and (by default) creates `gethash-exclude` file (for later tar command) in homedir of current user.

#### Tarring
`# tar -czf /tmp/rootfs.tar.gz -X ~/gethash-exclude --exclude='var/lib/apt/lists' -C ~/delme/rootfs/ .`

Effective tarring command, which excludes large directories (not needed for backup) and duplicate files

`--exclude` - files to exclude (relative to start of directory)

After this step, you have very small (just 29Mb for 300Mb+ generic debian 9 LXC machine rootfs)

#### Untarring
`# tar -xzf rootfs.tar.gz -C rootfs`

Just unpack to any directory as usual tar.gz file

~~~
root@braconnier:/tmp# du -sh rootfs/
80M	rootfs/
~~~

At this stage we have just 80 Mb out of 300+ Mb total.

#### Restoring

After unpacking, you can restore files to new rootfs
~~~
# hashget -u rootfs
recovered rootfs/usr/bin/vim.basic
recovered rootfs/lib/i386-linux-gnu/libdns-export.so.162.1.3
...
recovered rootfs/usr/share/doc/systemd/changelog.Debian.gz
recovered rootfs/usr/share/doc/systemd/copyright
~~~


## .hashget-restore format
.hashget-restore
~~~
{
    "files": [
        {
            "atime": 1549290263,
            "ctime": 1545336770,
            "file": "usr/bin/vim.basic",
            "gid": 0,
            "mode": 493,
            "mtime": 1506795698,
            "sha256": "61532c99ea444f8911793bdf9fa58f8f8cbcf03750fabea26fc11a1652b01677",
            "size": 2652916,
            "uid": 1000
        },
        ...
    "packages": [
        {
            "hash": "sha256:ee4ee5dcc3b67611f57fcce6144d687a80ec16a9209bf8184afff7dc8e11d643",
            "url": "http://snapshot.debian.org/archive/debian/20171002T041924Z/pool/main/v/vim/vim_8.0.0197-4+deb9u1_i386.deb"
        },
        
~~~

