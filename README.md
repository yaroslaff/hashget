# hashget

Deduplication tool for archiving (backup) debian virtual machines


### commands

`bin/hashget --prepack ~/delme/rootfs`

`bin/hashget --debcrawl ~/delme/rootfs/`

`tar -czf /tmp/rootfs.tar.gz -X ~/debsnap-exclude --exclude='var/lib/apt/lists' -C ~/delme/rootfs/ .`

`--exclude` - files to exclude (relative to start of directory)


## .hashlist format
.hashlist
  file:usr/bin/vim.basic perm:permissions uid:NN gid:NN sha256:HHHH 
  packagesha256:HHHH url:url* 



