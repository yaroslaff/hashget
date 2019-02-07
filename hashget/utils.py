import os
import shutil
from tempfile import mkdtemp
import patoolib




def rmrf(dirname):
    for path in dircontent(dirname):
        if not os.path.islink(path):
            os.chmod(path, 0o777)
    shutil.rmtree(dirname)
    

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


def recursive_unpack(path, udir='/tmp'):
    """
        Recursively unpack archive and all archives in content
        Deletes symlinks
    """

    try:
        patoolib.test_archive(path, verbosity=-1)
    except patoolib.util.PatoolError:
        return None
    
    nudir = mkdtemp(prefix='hashget-uniunpack-', dir=udir)
    patoolib.extract_archive(path, outdir=nudir, verbosity=-1)

    for f in dircontent(nudir):
        if os.path.islink(f):
            os.unlink(f)
    
    for f in dircontent(nudir):
        if os.path.isfile(f) and not os.path.islink(f):
            recursive_unpack(f, nudir)
                
    return nudir
    
    
    
