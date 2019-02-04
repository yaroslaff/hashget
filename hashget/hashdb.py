import os
import json
import filetype
from tempfile import mkdtemp


class HashPackage(object):
    """
        represents one hashpackage, e.g. one .deb file or .tar.gz, downloaded from one URL
    """
    
    fields = ['url', 'files', 'anchors', 'sha256', 'md5', 'signature']
    
    def __init__(self, url=None, anchors=None, files=None, sha256=None, md5=None, attrs=None, signature=None):
        self.url = url
        self.anchors = anchors
        self.files = files                
        self.md5 = md5
        self.sha256 = sha256
        self.attrs = attrs or dict()
        self.signature = signature

    def __eq__(self, obj):
        return (self.url == obj.url
                and self.anchors == obj.anchors
                and self.files == obj.files
                and self.attrs == obj.attrs
                and self.signature == obj.signature)
    
    @staticmethod
    def load(stream):
        hp = HashPackage()
        try:
            data = json.load(stream)
        except ValueError:
            return None
        
        for name in data.keys():
            setattr(hp, name, data[name])
        
        return hp
        
    def __repr__(self):
        basename = self.url.split('/')[-1]
        return "{} ({}/{})".format(basename, len(self.anchors), len(self.files))
    
    def json(self):
        data = dict()

        for field in self.fields:
            data[field] = getattr(self, field)
            
        return json.dumps(data, indent=4)
    
    
class HashDB(object):
    """
        Abstract class representing HashDB, local or remote
    """

    def __init__(self):
        raise NotImplementedError

    def submit(self, url, files, anchors, attrs=None):       
        raise NotImplementedError
    
    def hash2url(self, hsum):
        raise NotImplementedError

    pass


class DirHashDB(HashDB):
    """
        Local HashDB stored in directory
    """

    def __init__(self, path=None):        
        if path:
            self.path = path        
        else:
            # default path
            if os.getuid() == 0:
                # root                
                self.path = '/var/cache/hashget/hashdb'
            else:
                # usual user
                self.path = os.path.expanduser("~/.hashget/hashdb") 
        
        # package Hash to URL
        self.h2url = dict()
        
        # File Hash to Package Hash
        self.fh2ph = dict()

        # Signature to Package Hash
        self.sig2hash = dict()

        self.load()

    def load(self):
        """
            DirHashDB.load()
        """
        
        if not os.path.isdir(self.path):
            # no hashdb
            return
        
        for f in os.listdir( self.path ):
            with open(os.path.join(self.path, f)) as f:

                hp = HashPackage().load(f)

                self.h2url[hp.sha256] = hp.url

                for hpf in hp.files:
                    self.fh2ph[hpf] = hp.sha256
                    
                if hp.signature:
                    self.sig2hash[hp.signature] = hp.sha256                                            

    def hash2url(self, hashspec):
        if hashspec in self.h2url:
            return self.h2url[hashspec]
        
        if hashspec in self.fh2ph:
            phash = self.fh2ph[hashspec]
            return self.h2url[phash]
    
        raise KeyError('Hashspec {} not found neither in package hashes nor in file hashes')

    def fhash2phash(self, hsum):
        """
            Hash of file to hash of package
        """
        return self.fh2ph[hsum]
                        
    def phash2url(self, hsum):
        """
            Hash of package to URL of package
        """
        return self.h2url[hsum]
    
    def sig_present(self, sig):
        return sig in self.sig2hash
        
    
    # HashDB.submit
    def submit(self, hp):
        """
            Submit HashPackage to hashdb
        """
        basename = hp.url.split('/')[-1]
        path = os.path.join(self.path, basename)
        dirname = os.path.dirname(path)

        save = True
        
        if os.path.isfile(path):
            # already exists. same?
            with open(path) as f:
                hp2 = HashPackage().load(f)
                
                if hp == hp2:
                    save = False
        
        if save:
            # make dirs
            if not os.path.isdir(dirname):
                os.makedirs(os.path.dirname(path))
                        
            with open(path, 'w') as f:
                f.write(hp.json())

