import os
import sys
import hashlib
import shutil

from .utils import kmgt

BUF_SIZE = 1024*1024

class Hashes():
    def __init__(self, path=None, sums = None):

        self._sums = sums or [ 'sha256', 'md5']
        self.hashsums = dict()

        if path:
            for sumtype in self._sums:
                hsum = self.calculate_hash(path, getattr(hashlib, sumtype))
                self.hashsums[sumtype] = hsum

    def calculate_hash(self, path, hashmethod):
            
        h = hashmethod()
        
        with open(path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                h.update(data)
        
        return h.hexdigest()            

    @property
    def hashspec(self):
        return self.get_hashspec()

    def get_hashspec(self):
        return 'sha256:' + self.hashsums['sha256']

    def get_list(self):
        sums = list()

        return [ htype + ':' + self.hashsums[htype] for htype in self.hashsums ]

    def match_hashspec(self, hashspec):
    
        spec, hsum = hashspec.split(':',1)
    
        return self.hashsums[spec] == hsum

    def __repr__(self):
        return 'sha256:{} md5:{}'.format(self.sha256, self.md5)
        
    

class File():
    
    def __init__(self, filename=None, root=None, sums = None):

        self._sums = sums or ['sha256', 'md5']

        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            setattr(self, name, None)

        self.hashes = Hashes()

        if filename:
            self.read(filename, root)
    
    def basename(self):
        return os.path.basename(self.filename)
    
    def relpath(self):
        return os.path.relpath(self.filename, self.root)
    
    def read(self, filename=None, root=None):
        """
            read all info about file
        """
        self.filename = filename            

        stat = os.stat(self.filename)

        self.size = stat.st_size        
        # self.user = pwd.getpwuid(stat.st_uid).pw_name
        self.user = None
        self.uid = stat.st_uid
        # self.group = grp.getgrgid(stat.st_gid)[0]
        self.group = None
        self.gid = stat.st_gid

        self.atime = int(stat.st_atime)
        self.ctime = int(stat.st_ctime)
        self.mtime = int(stat.st_mtime)

        self.mode = stat.st_mode & 0o777

        self.hashes = Hashes(self.filename, sums=self._sums)
        self.root = root

    def __repr__(self):
        return "{} {} {} {}:{}".format(self.filename, self.hashes.hashsums['md5'], kmgt(self.size), self.uid, self.gid)



    def get_hashspec(self):
        return self.hashes.get_hashspec()

    @property
    def hashspec(self):
        return self.hashes.get_hashspec()


    @classmethod
    def from_dict(cls, d, root):
        f = cls()

        f.root = root
        f.filename = os.path.join(root, d['file'])
        f.hashes.hashsums['sha256'] = d['sha256']
        
        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            setattr(f, name, d[name])
        return f

    def to_dict(self):
        f = dict()
        f['file'] = os.fsdecode(os.path.relpath(self.filename, self.root))
        f['sha256'] = self.hashes.hashsums['sha256']

        for name in ['size', 'mode', 'uid', 'gid', 'atime', 'ctime', 'mtime']:
            f[name] = getattr(self, name)
        
        return f
    
    def recover(self, path, usermode=False):
        filename = os.fsencode(self.filename)
        #sys.stdout.buffer.write(os.fsdecode(self.filename))
        # print("...", filename)
        shutil.copyfile(path, filename)
        os.chmod(filename, self.mode)
        os.utime(filename, (self.atime, self.mtime))
        if not usermode:
            os.chown(filename, self.uid, self.gid)


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



