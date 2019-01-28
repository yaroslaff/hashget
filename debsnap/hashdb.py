import os
import json
import filetype
from tempfile import mkdtemp

class Package(object):
    
    
    def __init__(self, path=None, url=None):
        self.path = path
        self.url = url
        self.unpacked = None
        self.base_tmpdir = '/tmp'
        self.tmpdir = None

    def unpack(self):

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

        def rmlinks(dirpath):
            for path in dircontent(dirpath):
                if os.path.islink(path):
                    os.unlink(path)   



        if self.unpacked: return self.unpacked 
        self.download()

        k = filetype.guess(str(filename))

        if k is None:
            raise("ERROR Cannot get filetype for {}".format(filename))

        if k.mime == 'application/x-deb':
            self.tmpdir = mkdtemp(prefix='debsnap-{}-'.format(os.path.basename(self.path)), dir=self.base_tmpdir)
            #print "tdir:", tdir
            # Archive(filename).extractall(tdir)
            Package.unpack_deb(self.path, self.tmpdir)
            self.rmlinks()
    
    @staticmethod            
    def unpack_deb(filename, dirname):
        code = subprocess.call( ['dpkg', '-x', filename, dirname ])
        if code != 0:
            log.error('ERROR unpack_deb({}, {})'.format(filename, dirname))

    
    def rmlinks(self):
        """ remove symlinks from tmp dir """
    
    def download(self):
        if self.path:
            """ already downloaded """
            return self.path
     
    def scan_hashes(self, filename, minsz=0, maxn=3, log=None):
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


class HashPackage(object):
    """
        represents one hashpackage, e.g. one .deb file or .tar.gz, downloaded from one URL
    """
    
    fields = ['url', 'files', 'anchors', 'sha256', 'md5']
    
    def __init__(self, url=None, anchors=None, files=None, sha256=None, md5=None, attrs=None):
        self.url = url
        self.anchors = anchors
        self.files = files                
        self.md5 = md5
        self.sha256 = sha256
        self.attrs = attrs or dict()
    

    def __eq__(self, obj):
        return (self.url == obj.url
                and self.anchors == obj.anchors
                and self.files == obj.files
                and self.attrs == obj.attrs)
    
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
                self.path = '/var/cache/debsnap/hashdb'
            else:
                # usual user
                self.path = os.path.expanduser("~/.debsnap/hashdb") 
        self.h2url = dict()
        self.fh2ph = dict()

        self.load()

    def load(self):
        """
            DirHashDB.load()
        """
        for f in os.listdir( self.path ):
            with open(os.path.join(self.path, f)) as f:

                hp = HashPackage().load(f)

                for hpf in hp.files:
                    self.fh2ph[hpf] = hp.sha256
                    
                self.h2url[hp.sha256] = hp.url
        


    def fhash2phash(self, hsum):
        """
            Hash of file to hash of package
        """
        return self.fh2ph[hsum]
                        
    def phash2url(self, hsum):
        return self.h2url[hsum]

    def submit(self, hp):
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

