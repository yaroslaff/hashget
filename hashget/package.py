import logging
import filetype
from tempfile import mkdtemp
import os
import subprocess


from . import cacheget
from . import file
from . import utils

class Package(object):
        
    def __init__(self, path=None, url=None, log=None):
        self.path = path
        self.url = url
        self.unpacked = None
        self.base_tmpdir = '/tmp'
        self.tmpdir = None
        self.loghandler = log
        self.log = log or logging.getLogger('dummy')
        self.hashes = None
        self.basename = None
        self.files = list()

        self.stat_downloaded = 0
        self.stat_cached = 0

        if self.path:
            accept_file()
    
    def accept_file(self):
        self.hashes = file.Hashes(self.path)
        self.basename = os.path.basename(self.path)
    
    def hash2path(self, hashspec):
        self.unpack()        
        self.hash_content()
        self.log.debug('look for ' + hashspec)
        for f in self.files:
            if f.hashes.match_hashspec(hashspec):
                return f.filename
    
    def hash_content(self):
        
        if self.files:
            # files are already hashed
            return

        if not self.unpacked:
            self.unpack()
            
        for path in utils.dircontent(self.unpacked):
            if os.path.isfile(path) and not os.path.islink(path):
                self.files.append(file.File(path, root=self.unpacked))
            
            
    
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

        # self.download()

        k = filetype.guess(str(self.path))

        if k is None:
            raise("ERROR Cannot get filetype for {}".format(filename))

        if k.mime == 'application/x-deb':
            self.unpacked = mkdtemp(prefix='hashget-deb-{}-'.format(os.path.basename(self.path)), dir=self.base_tmpdir)
            #print "tdir:", tdir
            # Archive(filename).extractall(tdir)
            Package.unpack_deb(self.path, self.unpacked)
            self.rmlinks()
            return self.unpacked
        
    
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
     
        cg = cacheget.CacheGet(log = self.loghandler)
        r = cg.get(self.url)
        self.stat_cached += r['cached']
        self.stat_downloaded += r['downloaded']
        self.path = r['file']
        self.accept_file()
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
            self.log.debug("clean dir " + self.unpacked)
            utils.rmrf(self.unpacked)
