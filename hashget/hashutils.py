#from tempfile import mkdtemp
import tempfile
#print "mkdtemp:", mkdtemp
import filetype
import subprocess
import os
import hashlib
import shutil

def get_hash(filename, hashmethod=None):
    
    BUF_SIZE=1024*1024
    
    if hashmethod is None:
        h = hashlib.sha256()
    
    with open(filename, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            h.update(data)
    
    return h.hexdigest()


def unpack_deb(filename, dirname):
    code = subprocess.call( ['dpkg', '-x', filename, dirname ])
    if code != 0:
        log.error('ERROR unpack_deb({}, {})'.format(filename, dirname))


def walk_arc(filename, minsz=0, maxn=3, log=None):
    tmpdir = '/tmp'
    
    log.debug('walk {}'.format(filename))
    
    k = filetype.guess(str(filename))

    if k is None:
        log.error("ERROR Cannot get filetype for {}".format(filename))

    if k.mime == 'application/x-deb':
        tdir = tempfile.mkdtemp(prefix='gethash-', dir=tmpdir)
        #print "tdir:", tdir
        # Archive(filename).extractall(tdir)
        unpack_deb(filename, tdir)
        rmlinks(tdir)
        
        anchors = list()
        hashes = list()
        amin = None
        
        for f in os.walk(tdir):
            subpath = f[0][len(tdir):]
            for fn in f[2]:
                filename = os.path.join(f[0], fn)
                if os.path.isfile(filename):
                    filesz = os.stat(filename).st_size
                    #try:
                    #    unicode(filename, 'utf8')
                    #except UnicodeDecodeError:
                    #    log.error('skip file {} (bad file name). {} bytes'.format(filename, filesz))
                    #    continue
                    from tempfile import mkdtemp

                    
                        
                    digest = get_hash(filename)
                    # Hashes
                    if filesz > 1024:
                        hashes.append(digest)

                    # Anchors
                    if filesz > minsz:
                        # maybe add to anchors
                        if len(anchors) < maxn:
                            # simple. new anchors
                            # print p['basename'], "add new anchor"
                            anchors.append( (filesz, digest) )
                            if amin is None or filesz < amin:
                                amin = filesz
                        else:
                            # full anchor. maybe replace?
                            if filesz > amin:
                                # replace
                                for aa in anchors:
                                    if aa[0] == amin:
                                        # print "{} delete {}, add {}".format(p['basename'], aa['size'], cc['size'])
                                        anchors.remove(aa)
                                        anchors.append( (filesz, digest) )
                                        amin = min(anchors, key = lambda t: t[0])[0]
                                        break
                else:
                    log.debug("skip {} {}".format(ftype(filename), filename))
                
        
        rmrf(tdir)
        out_anchors = list()
        
        for aa in anchors:
            out_anchors.append(aa[1]) # add only hashsum
        
        return (out_anchors, hashes)   

