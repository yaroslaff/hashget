import os
import json
import shutil
# from tempfile import mkdtemp


class HashPackage(object):
    """
        represents one hashpackage, e.g. one .deb file or .tar.gz, downloaded from one URL
    
        url - permanent url to download package
        hashes - list of hashes of package file itself (sha256 + md5)        
        anchors - list of anchors (and forced anchors) hashes (could be used to retrieve package files over network)
        files - list of hashes of files
        signatures - dict of signatures, e.g. {'url': 'http://...', 'deb': 'package.deb 1.0 i386'}
        
        attributes:
            selfhash: True -- user should download package himself and scan it
    
    """
    
    fields = ['url', 'files', 'anchors', 'signatures','hashes']
    
    def __init__(self, url=None, anchors=None, files=None, hashes=None, attrs=None, signatures=None):
        self.url = url
        self.anchors = anchors
        self.files = files                
        self.hashes = hashes # list of hashspec for package file itself
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
        # data['hashes'] = self.hashes.get_list()
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

        self.__config = dict()

        self.packages = list()

        # package Hash to URL
        self.h2url = dict()
        
        # File Hash to Package Hash
        self.fh2ph = dict()

        # Signature to Package Hash
        self.sig2hash = dict()

        self.load()

    @property
    def storage(self):
        return self.__config.get('storage','basename')

    @storage.setter
    def storage(self, value):
        if value in ['basename', 'hash2', 'hash3']:
            self.__config['storage'] = value

    def read_config(self):
        try:
            with open(os.path.join(self.path,'.options')) as f:
                self.__config = json.load(f)
        except FileNotFoundError:
            pass

    def writehp(self, hp):
        """
        writes one HashPackage
        :param hp:
        :return:
        """
        path = self.hp2filename(hp)

        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path,"w") as f:
            f.write(hp.json())

        return path

    def write(self):
        """
        write .options and all files
        :return:
        """

        # delete all package files
        for root, dirs, files in os.walk(self.path, topdown=False):
            for basename in files:
                path = os.path.join(root, basename)
                if path != os.path.join(self.path, '.options'):
                    os.unlink(path)
            for dirbasename in dirs:
                path = os.path.join(root, dirbasename)
                os.rmdir(path)


        with open(os.path.join(self.path,'.options'),'w') as f:
            json.dump(self.__config, f, indent=4)

        for hp in self.packages:
            self.writehp(hp)


    def hp2filename(self, hp):
        """
        assign filename to HashPackage according to storage type
        :param hp: HashPackage
        :return: filename
        """

        hsum = hp.get_phash().split(':')[1]


        if self.__config['storage'] == 'basename':
            subpath = hp.url.split('/')[-1]
        elif self.__config['storage'] == 'hash2':
            subpath = '/'.join([hsum[0:2], hsum[2:4], hsum[4:]])
        elif self.__config['storage'] == 'hash3':
            subpath = '/'.join([hsum[0:2], hsum[2:4], hsum[4:6], hsum[6:]])

        return(os.path.join(self.path, subpath))

    def package_files(self):
        """
        yields each full path to each package file in DirHashDB
        """
        for root, dirs, files in os.walk(self.path):
            for basename in files:
                path = os.path.join(root, basename)
                if path != os.path.join(self.path, '.options'):
                    yield path

        return list()

    def load(self):
        """
            DirHashDB.load()
        """

        self.read_config()

        if not os.path.isdir(self.path):
            # no hashdb
            return

        #for f in os.listdir( self.path ):
        for f in self.package_files():
            with open(os.path.join(self.path, f)) as f:
                hp = HashPackage().load(f)
                self.submit(hp)

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
        

    def __repr__(self):
        return 'DirHashDB(path:{} stor:{} packages:{})'.format(self.path, self.storage, len(self.packages))

    def dump(self):
        print("packages: {}".format(len(self.packages)))
        for p in self.packages:
            print("  {}".format(p))

    # DirHashDB.submit
    def submit(self, hp):
        """
            Append HashPackage to hashdb internal structures
            (not saving to disk)
        """

        self.packages.append(hp)
        phash = hp.get_phash()

        for hsum in hp.hashes:
            self.h2url[hsum] = hp.url

        for hpf in hp.files:
            self.fh2ph[hpf] = phash

        if hp.signatures:
            for sigtype, sig in hp.signatures.items():
                if not sigtype in self.sig2hash:
                    self.sig2hash[sigtype] = dict()
                self.sig2hash[sigtype][sig] = phash


class HashDBClient(HashDB):
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
        self.hashdb = dict()

        for name in os.listdir(self.path):
            project_path = os.path.join(self.path, name)
            if os.path.isdir(project_path):
                self.hashdb[name] = DirHashDB(path = project_path)

    def hash2url(self, hspec):
        for hdb in self.hashdb:
            try:
                return hdb.hash2url(hspec)
            except KeyError:
                pass
        raise KeyError("Not found in any of {} hashdb".format(len(self.hashdb)))
            
    def submit(self, hp, project):
        hdb = self.hashdb[project]

        hdb.submit(hp)
        hdb.writehp(hp)

    def create_project(self, name):
        project_path = os.path.join(self.path, name)
        os.mkdir(project_path)

    def remove_project(self, name):
        p = self.hashdb[name]
        shutil.rmtree(p.path)


    """
        HashDBClient
        Dictionary-style interface
    """

    def items(self):
        return self.hashdb.items()

    def __getitem__(self, item):
        return self.hashdb[item]

    def get(self,name, default=None):
        """

        :param name: name of project
        :param default: default value if project not found
        :return: Project or def value (or Exception)
        """
        return self.hashdb.get(name, default)

