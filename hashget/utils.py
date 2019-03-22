import os
import shutil
import hashlib
from tempfile import mkdtemp
import patoolib
import time

unpack_suffixes = [ '.deb', '.gz', '.xz' ]

def sha1sum(filename):
    h  = hashlib.sha1()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def sha256sum(filename):
    h  = hashlib.sha256()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()

def rmrf(dirname):
    for path in dircontent(dirname):
        if not os.path.islink(path):
            os.chmod(path, 0o777)
    shutil.rmtree(dirname)

def dir_size(root_path = '.'):
    return sum([os.path.getsize(fp) for fp in (os.path.join(dirpath, f) for dirpath, dirnames, filenames in os.walk(root_path) for f in filenames) if not os.path.islink(fp)])

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


def rmlinks(dirname):
    for path in dircontent(dirname):
        if os.path.islink(path):
            os.unlink(path)   
    
    
def kmgt(sz, frac=1):
    t={
        'K': pow(1024,1),
        'M': pow(1024,2),
        'G': pow(1024,3),
        'T': pow(1024,4),
        '': 1}        

    if sz == 0:
        return '0'

    for k in sorted(t,key=t.__getitem__,reverse=True):
        fmul = pow(10,frac)

        if sz>=t[k]:
            #n = int((float(sz)*fmul / t[k]))
            n = sz/float(t[k])
            #n = n/float(fmul)

            tpl = "{:."+str(frac)+"f}{}"

            return tpl.format(n,k)


def recursive_unpack(path, udir='/tmp', recursive=True):
    """
        Recursively unpack archive and all archives in content
        Deletes symlinks
    """

    if all( not path.endswith(suffix) for suffix in unpack_suffixes ):
        # print("skip {}".format(path))
        return None

    try:
        patoolib.test_archive(path, verbosity=-1)
    except patoolib.util.PatoolError:
        return None
    
    nudir = mkdtemp(prefix='hashget-uniunpack-', dir=udir)
    patoolib.extract_archive(path, outdir=nudir, verbosity=-1)

    for f in dircontent(nudir):
        if os.path.islink(f):
            os.unlink(f)

    if recursive:
        for f in dircontent(nudir):
            if os.path.isfile(f) and not os.path.islink(f):
                recursive_unpack(f, nudir)
                
    return nudir
    
class Times():

    def __init__(self):
        self.times = list()
        self.add('init')

    def add(self,name):
        self.times.append((name, time.time()))

    def dump(self):
        lasttime = None
        for ttuple in self.times:
            if lasttime is None:
                lasttime = ttuple[1]
                continue

            print("{}: {:.2f}s".format(ttuple[0], ttuple[1]-lasttime))
            lasttime = ttuple[1]
