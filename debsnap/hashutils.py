from tempfile import mkdtemp
import filetype
import subprocess
import os
import hashlib
import shutil

def load_release(filename):
    """
        load Release file as data structure
    """
    data = dict()
    datalist = list()
    lastkey = None    
    
    array = False
    
    with open(filename) as f:
        for line in f:
            if line == '\n':
                # list element
                array = True
                datalist.append(data)
                data = dict()                    
            elif line[0] == ' ':
                # starts with space
                if data[lastkey] == '':
                    data[lastkey] = list()
                else:
                    if isinstance(data[lastkey], list):
                        data[lastkey].append(line.strip())
                    else:
                        # string continues on new line
                        data[lastkey] += line.strip()
            else:
                # usual key: value
                k, v = line.rstrip().split(':',1)
                data[k] = v.strip()
                lastkey = k

    # end of file
    if array:
        return datalist
    
    return data


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


def dircontent(root):
    """
        Yields all elements of directory (recursively). Starting from top. Good for chmod.
        Do not follow symlinks
    """
    for i in os.listdir(root):
        path = os.path.join(root, i)
        if os.path.islink(path):
            yield path
        elif os.path.isdir(path):
            yield path            
            for subpath in dircontent(path):
                yield subpath                
        else:
            yield path

def rmrf(dirname):
    for path in dircontent(dirname):
        if not os.path.islink(path):
            os.chmod(path, 0777)
    shutil.rmtree(dirname)

def rmlinks(dirname):
    for path in dircontent(dirname):
        if os.path.islink(path):
            os.unlink(path)   


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
        tdir = mkdtemp(prefix='gethash-', dir=tmpdir)
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

