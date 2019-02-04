import os
import json
import filetype
from tempfile import mkdtemp


class HashPackage(object):
    """
        represents one hashpackage, e.g. one .deb file or .tar.gz, downloaded from one URL
    """
    
    fields = ['url', 'files', 'hashes', 'anchors', 'signatures']
    
    def __init__(self, url=None, anchors=None, files=None, hashes=None, attrs=None, signatures=None):
        self.url = url
        self.anchors = anchors
        self.files = files                
        self.hashes = hashes
        self.attrs = attrs or dict()
        self.signatures = signatures

    def __eq__(self, obj):
        return (self.url == obj.url
                and self.anchors == obj.anchors
                and self.files == obj.files
                and self.attrs == obj.attrs
                and self.signatures == obj.signatures)
    
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
    
    def get_phash(self):
        for hspec in self.hashes:
            if hspec.startswith('sha256:'):
                return hspec 
    
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
                phash = hp.get_phash()

                for hsum in hp.hashes:                                                            
                    self.h2url[hsum] = hp.url

                for hpf in hp.files:
                    self.fh2ph[hpf] = phash
                    
                if hp.signatures:
                    for sigtype, sig in hp.signatures.items():
                        if not sigtype in self.sig2hash:
                            self.sig2hash[sigtype]=dict()
                        self.sig2hash[sigtype][sig] = phash                                            

    def hash2url(self, hashspec):
    
        if hashspec in self.h2url:
            return self.h2url[hashspec]
        
        if hashspec in self.fh2ph:
            phash = self.fh2ph[hashspec]
            return self.h2url[phash]

        #print(json.dumps(self.fh2ph, indent=4))
    
        raise KeyError('Hashspec {} not found neither in package hashes nor in file hashes'.format(hashspec))

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
    
    def sig_present(self, sigtype, sig):
        return ((sigtype in self.sig2hash) and (sig in self.sig2hash[sigtype]))
        
    
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

