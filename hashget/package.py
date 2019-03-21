import logging
import filetype
from tempfile import mkdtemp
from collections import namedtuple
import os
import subprocess



from . import cacheget
from . import file
from . import utils

class Package(object):
    """
        Represents universal interface to any kind of package, e.g. .deb or .tar.xz

        Do not confuse it with HashPackage
    """
        
    def __init__(self, path=None, url=None, log=None):
        self.path = path
        self.package_size = 0
        self.url = url
        self.unpacked = None
        self.base_tmpdir = '/tmp'
        self.tmpdir = None
        self.loghandler = log
        self.log = log or logging.getLogger('dummy')
        self.hashes = None
        self.basename = None
        self.files = list()
        self.sum_size = 0
        self.recursive = True

        self.stat_downloaded = 0
        self.stat_cached = 0

        if self.path:
            self.accept_file()
    
    def accept_file(self):
        self.hashes = file.Hashes(self.path)
        self.basename = os.path.basename(self.path)
        self.package_size = os.path.getsize(self.path)
    
    def hash2path(self, hashspec):
        """

        :param hashspec: e.g. sha256:aabbcc...
        :return: path on disk

        used in --get <hashspec>
        """
        self.unpack()        
        self.read_files()
        self.log.debug('look for ' + hashspec)
        for f in self.files:
            if f.hashes.match_hashspec(hashspec):
                return f.filename
    
    def read_files(self):
        
        if self.files:
            # files are already hashed
            return

        # someone forgot to unpack before read_files
        assert(self.unpacked)

        for path in utils.dircontent(self.unpacked):
            if os.path.isfile(path) and not os.path.islink(path):
                f = file.File(path, root=self.unpacked)
                self.files.append(f)
                self.sum_size += f.size
            

    def unpack(self):                
        
        self.unpacked = utils.recursive_unpack(self.path, recursive=self.recursive)

        if self.unpacked:
            # remove links
            for f in utils.dircontent(self.unpacked):
                if os.path.islink(f):
                    os.unlink(f)
        return self.unpacked            
    
    def download(self):
        
        if self.path:
            """ already downloaded """
            return self.path
     
        cg = cacheget.CacheGet()
        r = cg.get(self.url)
        self.stat_cached += r['cached']
        self.stat_downloaded += r['downloaded']
        self.path = r['file']
        self.accept_file()
        return self.path

    def __repr__(self):
        text = 'package ['
        if self.url:
            text += ' url: ' + self.url
        
        if self.path:
            text += ' path:' + self.path
            
        if self.unpacked:
            text += ' unpacked:' + self.unpacked
              
        text += ' ]'
        return text
        
    def cleanup(self):
        if self.unpacked:
            utils.rmrf(self.unpacked)

    def all_files(self):
        # first: return package itself
        yield file.File(self.path, root=os.path.dirname(self.path))

        for f in self.files:
            yield f
