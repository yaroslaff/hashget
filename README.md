# hashget

Deduplication tool for archiving (backup) debian virtual machines

For example, very useful for backup LXC containers before uploading to Amazon Glacier.


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

Create debian machine (optional). Later with this example we will use 'mydebvm' container in default LXC location.
~~~
# lxc-create -n mydebvm -t download -- --dist=debian --release=stretch --arch=amd64
~~~

Update local and network hashdb with packages from this VM. (optional, but very recommended to get maximal efficiency)
~~~
# hashget --debcrawl /var/lib/lxc/mydebvm/rootfs/ 
~~~

Now, main work, prepare 
~~~
# hashget -p /var/lib/lxc/mydebvm/rootfs/
Development hashget hashdb repository
https://gitlab.com/yaroslaff/hashget
saved: 5905 files, 133 pkgs, size: 165.3M
~~~
Creates .hashget-restore file in rootfs and (by default) creates `gethash-exclude` file (for later tar command) in homedir of current user.

Now, compress:
~~~
# tar -czf /tmp/mydebvm.tar.gz -X ~/hashget-exclude --exclude='var/lib/apt/lists' -C /var/lib/lxc/mydebvm/rootfs .
~~~

Now lets compare results with usual tarring
~~~

# du -sh /var/lib/lxc/mydebvm/rootfs/
321M	/var/lib/lxc/mydebvm/rootfs/

# tar -czf /tmp/mydebvm-orig.tar.gz --exclude='var/lib/apt/lists' -C /var/lib/lxc/mydebvm/rootfs .

# ls -lh /tmp/mydebvm.tar.gz /tmp/mydebvm-orig.tar.gz 
-rw-r--r-- 1 root root 99M Mar  4 22:01 /tmp/mydebvm-orig.tar.gz
-rw-r--r-- 1 root root 29M Mar  4 21:59 /tmp/mydebvm.tar.gz
~~~

Optimized backup is 70Mb shorter, just 29 instead of 99, 70% saved!

After this step, you have very small (just 29Mb for 300Mb+ generic debian 9 LXC machine rootfs)

Untarring:
~~~
# tar -xzf mydebvm.tar.gz -C rootfs
~~~

Just unpack to any directory as usual tar.gz file

~~~
# du -sh rootfs/
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

## Documentation
For more detailed documentation see [Wiki](https://gitlab.com/yaroslaff/hashget/wikis/home).



