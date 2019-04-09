#!/bin/bash

VMNAME=mydebvm

RECREATE=0
VMTEST=1

LXC_STOP_OPTS="-t 10"



TDIR=`mktemp -d`

if [ "$(id -u)" -ne 0 ]; then
        echo 'This script must be run by root' >&2
        exit 1
fi

if [ "VMTEST" = "1" ]
then

    if [ "$RECREATE" = "1" ]
    then

        echo "# Delete $VMNAME"
        lxc-stop -n $VMNAME $LXC_STOP_OPTS
        lxc-destroy -n $VMNAME

        echo "# Create new $VMNAME"
        lxc-create -n $VMNAME -t download -- --dist=debian --release=stretch --arch=amd64
        lxc-start -n $VMNAME
        lxc-attach -n $VMNAME -- apt update
        lxc-attach -n $VMNAME -- apt install -y wget apache2 mysql-server vim
        lxc-stop -n $VMNAMT $LXC_STOP_OPTS
    else
        echo "skip recreation"
    fi

    cat <<CHECKPOINT
#
# Checkpoint 1
#
CHECKPOINT

    /bin/echo -e "724M\t/var/lib/lxc/$VMNAME"
    sudo du -sh /var/lib/lxc/$VMNAME
    echo


    ########## COMPRESSING VM

    hashget --pack /var/lib/lxc/$VMNAME/rootfs/ -zf /tmp/$VMNAME.tar.gz \
        --exclude var/cache/apt var/lib/apt/lists

    tar -czf /tmp/$VMNAME-orig.tar.gz  --exclude=var/cache/apt \
        --exclude=var/lib/apt/lists -C /var/lib/lxc/mydebvm/rootfs/ .


    cat <<CHECKPOINT
#
# Checkpoint 2
#
# 165M / 4.1M
#
CHECKPOINT

    ls -lh /tmp/${VMNAME}*gz
    echo


    ########## DECOMPRESSING VM

    mkdir $TDIR/r
    tar -xzf /tmp/$VMNAME.tar.gz -C $TDIR/r
    du -sh $TDIR/r
    hashget -u $TDIR/r

    cat <<CHECKPOINT
#
# Checkpoint 3
#
# 607M
#
CHECKPOINT

    du -sh $TDIR/r

else
    echo ... skip VMTEST
fi


########## WORDPRESS manual

hashget-admin --purge --hp https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip

mkdir $TDIR/wp
cd $TDIR/wp
wget -q https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip
unzip -q wordpress-5.1.1-ru_RU.zip
hashget -p my --submit https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip --hashserver
hashget --pack $TDIR/wp -zf /tmp/test-wp.tar.gz --hashserver

cat <<CHECKPOINT
#
# Checkpoint 3
#
# 158K
#
CHECKPOINT

ls -lh /tmp/test-wp.tar.gz

########## WORDPRESS hint

hashget-admin --purge --hp https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip

cd $TDIR/wp
echo '{"project": "wordpress.org", "url": "https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip"}'> $TDIR/wp/hashget-hint.json

hashget --pack $TDIR/wp -zf /tmp/test-hint-wp.tar.gz --hashserver

cat <<CHECKPOINT
#
# Checkpoint 4
#
# 158K
#
CHECKPOINT

ls -lh /tmp/test-hint-wp.tar.gz


########## WORDPRESS no hint


hashget-admin --purge --hp https://ru.wordpress.org/wordpress-5.1.1-ru_RU.zip
hashget --pack $TDIR/wp -zf /tmp/test-nohint-wp.tar.gz -v --heur --hashserver --hashdb wordpress.org

cat <<CHECKPOINT
#
# Checkpoint 5
#
# 23M
#
CHECKPOINT

ls -lh /tmp/test-nohint-wp.tar.gz


########## DECOMPRESSING CLEANUP
# echo clean $TDIR
rm -r $TDIR
