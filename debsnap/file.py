import os
import pwd, grp
import hashlib

from utils import kmgt

BUF_SIZE = 1024*1024

class Hashes():
    def __init__(self, path):
        self.sha256 = self.calculate_hash(path, hashlib.sha256)
        self.md5 = self.calculate_hash(path, hashlib.md5)    

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
    
    
    def __init__(self, filename):
        self.filename = filename            

        stat = os.stat(self.filename)

        self.size = stat.st_size        
        self.user = pwd.getpwuid(stat.st_uid).pw_name
        self.userid = stat.st_uid
        self.group = grp.getgrgid(stat.st_gid)[0]
        self.groupid = stat.st_gid

        self.atime = int(stat.st_atime)
        self.ctime = int(stat.st_ctime)
        self.mtime = int(stat.st_mtime)

        self.mode = stat.st_mode & 0777

        self.hashes = Hashes(self.filename)        

    def __repr__(self):
        return "{} {} {} {}:{} {}:{}".format(self.filename, self.hashes.md5, kmgt(self.size), self.user, self.group, self.userid, self.groupid)
        

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



