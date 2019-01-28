# debsnap

Deduplication tool for archiving (backup) debian virtual machines


### commands

`bin/debsnap --prepack ~/delme/rootfs`

`bin/debsnap --crawl ~/delme/rootfs/`

`tar -czf /tmp/rootfs.tar.gz -X ~/debsnap-exclude --exclude='var/lib/apt/lists' -C ~/delme/rootfs/ .`

## .snapfiles format
.snapfiles
  file:usr/bin/vim.basic perm:permissions uid:NN gid:NN sha256:HHHH 
  packagesha256:HHHH url:url* 

exclude - files to exclude (relative to start of directory)

