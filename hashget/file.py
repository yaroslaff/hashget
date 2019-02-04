import os
import pwd, grp
import hashlib
import shutil

from .utils import kmgt

BUF_SIZE = 1024*1024

class Hashes():
    def __init__(self, path=None):
        if path:
            self.sha256 = self.calculate_hash(path, hashlib.sha256)
            self.md5 = self.calculate_hash(path, hashlib.md5)    
        else:
            self.sha256 = None
            self.md5 = None

    def calculate_hash(self, path, hashmethod):
            
        h = hashmethod()
        
        with open(path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                h.update(data)
        
        return h.hexdigest()            


class File():
    
    def __init__(self, filename=None, root=None):
        self.hashes = Hashes()
        
        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            setattr(self, name, None)
        
        if filename:
            self.read(filename, root)
    
    def read(self, filename=None, root=None):
        self.filename = filename            

        stat = os.stat(self.filename)

        self.size = stat.st_size        
        self.user = pwd.getpwuid(stat.st_uid).pw_name
        self.uid = stat.st_uid
        self.group = grp.getgrgid(stat.st_gid)[0]
        self.gid = stat.st_gid

        self.atime = int(stat.st_atime)
        self.ctime = int(stat.st_ctime)
        self.mtime = int(stat.st_mtime)

        self.mode = stat.st_mode & 0o777

        self.hashes = Hashes(self.filename)        
        self.root = root

    def __repr__(self):
        return "{} {} {} {}:{}".format(self.filename, self.hashes.md5, kmgt(self.size), self.uid, self.gid)
        

    @classmethod
    def from_dict(cls, d, root):
        f = cls()
        
        f.root = root
        f.filename = os.path.join(root, d['file'])
        f.hashes.sha256 = d['sha256']
        
        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            setattr(f, name, d[name])
        return f

    def to_dict(self):
        f = dict()
        f['file'] = os.path.relpath(self.filename, self.root)
        f['sha256'] = self.hashes.sha256

        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            f[name] = getattr(self, name)
        
        return f
    
    def recover(self, path):        
        shutil.copyfile(path, self.filename)
        os.chmod(self.filename, self.mode)
        os.chown(self.filename, self.uid, self.gid)
        os.utime(self.filename, (self.atime, self.mtime))
        
class FileList(list):
    
    def getbymd5(self, digest):
        for f in self:
            if f.hashes.md5 == digest:
                return f
        raise KeyError

    def getbypath(self, path):
        for f in self:
            if f.filename == path:
                return f
        raise KeyError



