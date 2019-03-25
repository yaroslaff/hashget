import os
import re
import json
import shutil
import requests
import urllib
import datetime
import logging

from .utils import kmgt, dircontent
from .file import File
# from tempfile import mkdtemp
from .hashpackage import HashPackage
from . import debian
from . import __user_agent__

log = logging.getLogger('hashget')


class HashDB(object):
    """
        Abstract class representing HashDB, local or remote
    """

    def __init__(self):
        raise NotImplementedError

    def submit(self, url, files, anchors, attrs=None):
        raise NotImplementedError

    def hash2hp(self, hsum):
        raise NotImplementedError

    pass


class DirHashDB(HashDB):
    """
        Local HashDB stored in directory
    """

    hpclass = HashPackage

    def __init__(self, path=None, load=True):

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

        # package or file Hash to hp
        self.__h2hp = dict()
        
        # File Hash to Package Hash
        # self.fh2hp = dict()

        # Signature to Package Hash
        self.__sig2hash = dict()

        self.loaded = False

        self.read_config()

        if load:
            self.load()

    @property
    def storage(self):
        return self.__config.get('storage','basename')

    @storage.setter
    def storage(self, value):
        if value in ['basename', 'hash2', 'hash3']:
            self.__config['storage'] = value
        else:
            raise ValueError('Wrong storage type "{}"'.format(value))

    @property
    def pkgtype(self):
        return self.__config.get('pkgtype','generic')

    @pkgtype.setter
    def pkgtype(self, value):
        if value in ['generic', 'debsnap']:
            self.__config['pkgtype'] = value
        else:
            raise ValueError('Wrong pkgtype "{}"'.format(value))

    def read_config(self):
        self.__config = {'storage': 'basename', 'pkgtype': 'generic'}

        try:
            with open(os.path.join(self.path,'.options.json')) as f:
                conf = json.load(f)
            for k,v in conf.items():
                self.__config[k] = v
        except FileNotFoundError:
            pass

        # set default values
        for hpc in self.hpclass.__subclasses__():
            if hpc.pkgtype == self.__config['pkgtype']:
                self.hpclass = hpc

    def write_config(self):
        with open(os.path.join(self.path,'.options.json'),'w') as f:
            json.dump(self.__config, f, indent=4)

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

        hp.path = path

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
                if path != os.path.join(self.path, '.options.json'):
                    os.unlink(path)
            for dirbasename in dirs:
                path = os.path.join(root, dirbasename)
                os.rmdir(path)


        self.write_config()

        for hp in self.packages:
            self.writehp(hp)


    def hp2filename(self, hp, storage=None):
        """
        assign filename to HashPackage according to storage type
        :param hp: HashPackage
        :return: filename
        """

        storage = storage or self.__config['storage']

        hsum = hp.get_phash().split(':')[1]

        if storage == 'basename':
            subpath = '/'.join(['p', hp.url.split('/')[-1]])
        elif storage == 'hash2':
            subpath = '/'.join(['p', hsum[0:2], hsum[2:4], hsum[4:]])
        elif storage == 'hash3':
            subpath = '/'.join(['p', hsum[0:2], hsum[2:4], hsum[4:6], hsum[6:]])

        return(os.path.join(self.path, subpath))

    def package_files(self):
        """
        yields each full path to each package file in DirHashDB
        """
        for root, dirs, files in os.walk(os.path.join(self.path,'p')):
            for basename in files:
                path = os.path.join(root, basename)
                if path != os.path.join(self.path, '.options'):
                    yield path

        return list()

    def packages_iter(self):
        for subpath in self.package_files():
            hp = self.hpclass.load(path = os.path.join(self.path, subpath))
            yield hp

    def load(self):
        """
            DirHashDB.load()
        """

        if not os.path.isdir(self.path):
            # no hashdb
            return

        #for f in os.listdir( self.path ):
        for subpath in self.package_files():
            hp = self.hpclass.load(path = os.path.join(self.path, subpath))
            self.submit(hp)

        self.loaded = True

    def basename2hp(self, basename):
        for hp in self.packages_iter():
            if hp.basename() == basename:
                return hp
        raise KeyError

    def sig2hp(self, sigtype, sig):
        for hp in self.packages:
            for hpsigtype, hpsig in hp.signatures.items():
                if (sigtype is None or sigtype == hpsigtype) and hpsig == sig:
                    return hp
        raise KeyError

    def hash2hp(self, hashspec):
        """
        return hashpackage by hashspec of package or any indexed file in it
        :param hashspec:
        :return:
        """

        if hashspec in self.__h2hp:
            return self.__h2hp[hashspec]

        raise KeyError('Hashspec {} not found neither in package hashes nor in file hashes'.format(hashspec))

    def sig_present(self, sigtype, sig):
        return ((sigtype in self.__sig2hash) and (sig in self.__sig2hash[sigtype]))
        

    def __repr__(self):
        return 'DirHashDB(path:{} stor:{} pkgtype:{} packages:{})'.format(self.path, self.storage, self.__config['pkgtype'], len(self.packages))

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

        # add sum of package itself, for hash
        for hsum in hp.hashes:
            self.__h2hp[hsum] = hp

        for hpf in hp.files:
            self.__h2hp[hpf] = hp

        if hp.signatures:
            for sigtype, sig in hp.signatures.items():
                if not sigtype in self.__sig2hash:
                    self.__sig2hash[sigtype] = dict()
                self.__sig2hash[sigtype][sig] = phash


class HashServer():
    """
        Interface to remote HashServer

    """
    def __init__(self, url = None):
        self.url = url
        self.config=dict()
        if not self.url.endswith('/'):
            self.url = self.url+'/'

        self.headers = dict()
        self.headers['User-Agent'] = __user_agent__


        # default config
        self.config['name'] = 'noname'
        self.config['submit'] = urllib.parse.urljoin(self.url,'submit')
        self.config['hashdb'] = urllib.parse.urljoin(self.url,'hashdb')
        self.config['motd'] = urllib.parse.urljoin(self.url,'motd.txt')
        self.config['accept_url'] = list()

        r = requests.get(urllib.parse.urljoin(self.url,'config.json'), headers=self.headers)
        if r.status_code == 200:
            self.config = {**self.config, **json.loads(r.text)}

        r = requests.get(urllib.parse.urljoin(self.url, self.config['motd']), headers=self.headers)
        log.info(r.text.rstrip())


    def fhash2url(self, hashspec):
        spec, hsum = hashspec.split(':',1)
        if spec != 'sha256':
            raise KeyError
        # prepare url
        urlpath = '/'.join(['a', hsum[:2],hsum[2:4],hsum[4:6], hsum[6:]])
        return urllib.parse.urljoin(self.url, urlpath)

    def fhash_exists(self, hashspec):
        r = requests.head(self.fhash2url(hashspec))
        return(r.status_code == 200)

    def hash2hp(self, hashspec):
        """
        User to pull hashpackage by anchor

        :param hashspec:
        :return:
        """


        r = requests.get(self.fhash2url(hashspec), headers=self.headers)

        if r.status_code != 200:
            raise KeyError

        hp = HashPackage.load(data = r.json())
        return(hp)

    def want_accept(self, url):
        for reurl in self.config['accept_url']:
            if re.search(reurl, url):
                return True
        return False

    def sig_present(self, sigtype, signature):
        if sigtype == 'deb':
            path = ['sig','deb'] + debian.debsig2path(signature)
            url = urllib.parse.urljoin(self.config['hashdb'], '/'.join(path))

            r = requests.head(url)
            if r.status_code == 200:
                return True

        return False


    def sig2hp(self, sigtype, signature):

        log.debug("{}: sig2hp {}:{}".format(self, sigtype, signature))

        if sigtype == 'deb':
            path = ['sig','deb'] + debian.debsig2path(signature)
            url = urllib.parse.urljoin(self.config['hashdb'], '/'.join(path))

            r = requests.get(url)
            if r.status_code == 200:
                hp = HashPackage.load(data = r.json())
                return(hp)
            elif r.status_code == 404:
                log.debug('No sigurl {}'.format(url))
        raise KeyError

    def basename2hp(self, basename):
        log.debug('hashserver pull by basename {}'.format(basename))
        if not basename.endswith('.deb'):
            raise KeyError('Remote HashServer works only with .deb packages')

        debsig = basename[:-4]
        return self.sig2hp('deb', debsig)

    def submit(self, url, file):
        """
        HashServer.submit()  to remote hashserver

        :param url:
        :param file:
        :return:
        """
        basename = os.path.basename(file)

        submitfile = File(file)

        data = dict()
        data['url'] = url
        data['size'] = submitfile.size

        files = dict()
        with open(file,'rb') as f:
            files['package'] = f

            if not self.want_accept(url):
                return

            hashspec = submitfile.hashes.get_hashspec()

            if self.fhash_exists(hashspec):
                log.debug('hashserver already has {}'.format(hashspec))
                return

            print("uploading {} ({}) to {}".format(basename, kmgt(submitfile.size),  self.config['submit']))
            r = requests.post(self.config['submit'], data=data, files=files)
            print("Submit {} {}".format(r.status_code, r.text))


    def __repr__(self):
        return 'HashServer({})'.format(self.url)


class HashDBClient(HashDB):
    def __init__(self, path=None, load=True):

        self.hashserver = list()
        self.stats = dict(q=0, miss=0, hits=0)


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


        if not os.path.isdir(self.path):
            log.info('Created {} local hashdb'.format(self.path))
            os.makedirs(self.path, exist_ok=True)

        self.hashdb = dict()

        for name in os.listdir(self.path):
            project_path = os.path.join(self.path, name)
            if os.path.isdir(project_path):
                self.hashdb[name] = DirHashDB(path = project_path, load=load)

    def __repr__(self):
        return("HashClient(l{} n{} q{} h{} m{})".format(
            len(self.hashdb), len(self.hashserver),
            self.stats['q'], self.stats['hits'], self.stats['miss']
        ))

    def add_hashserver(self, url):
        hs = HashServer(url = url)
        log.debug('add hashserver {}'.format(hs))
        self.hashserver.append(hs)
        if not '_cached' in self.hashdb:
            self.create_project('_cached')

    def submit_save(self, hp, project, file=None):
        hdb = self.hashdb[project]

        hdb.submit(hp)
        hdb.writehp(hp)

        if file:
            for hs in self.hashserver:
                hs.submit(url = hp.url, file = file)

    def create_project(self, name):
        project_path = os.path.join(self.path, name)
        if not os.path.isdir(project_path):
            os.mkdir(project_path)
            self.hashdb[name] = DirHashDB(path=project_path)
            return self.hashdb[name]

    def ensure_project(self, name, pkgtype=None):
        if name in self.hashdb:
            # exists, not doing it
            return self.hashdb[name]

        log.debug('create project {} (pkgtype: {})'.format(name, pkgtype))
        hdb = self.create_project(name)
        if pkgtype is not None:
            hdb.pkgtype = pkgtype
            hdb.write_config()

            # read config again, to update pkgtype
            hdb.read_config()
        return hdb

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

    def get(self, name, default=None):
        """

        :param name: name of project
        :param default: default value if project not found
        :return: Project or def value (or Exception)
        """
        return self.hashdb.get(name, default)

    """
        query methods
    """
    def pull_sig(self, sigtype, signature):
        """
        pull package by signature
        :param sigtype:
        :param signature:
        :return:
        """

        for hs in self.hashserver:
            self.stats['q'] += 1
            try:
                hp = hs.sig2hp(sigtype, signature)
                # save
                self.stats['hits'] += 1
            except KeyError:
                self.stats['miss'] += 1
                return False
            else:
                self.submit_save(hp,'_cached')
                return True

        return False


    def phash2url(self, phash):
        for hdb in self.hashdb.values():
            try:
                return hdb.phash2url(phash)
            except KeyError:
                pass
        raise KeyError

    def sig_present(self, sigtype, signature, remote=True):
        if any(x[1].sig_present(sigtype, signature) for x in self.hashdb.items()):
            # found in localdb
            return True
        if remote:
            if sigtype in ['deb']:
                for hs in self.hashserver:
                    if hs.sig_present(sigtype, signature):
                        return True
        return False


    def sig2hp(self, sigtype, sig, remote=True):
        """
        get package by signature
        :param sig:
        :param sigtype:
        :return:
        """
        for hdb in self.hashdb.values():
            try:
                return hdb.sig2hp(sigtype, sig)
            except KeyError:
                pass

        if remote:
            for hs in self.hashserver:
                hp = hs.sig2hp(sigtype, sig)
                return hp

        raise KeyError("Not found sig {} in any of hashdb: {}".format(sig, self.hashdb.keys()))

    def basename2hp(self, basename, project=None, remote=True):
        for name, hdb in self.hashdb.items():
            if name == project or project is None:
                try:
                    return hdb.basename2hp(basename)
                except KeyError:
                    pass
        if remote:
            for hs in self.hashserver:
                hp = hs.basename2hp(basename)
                return hp

        raise KeyError("Not found basename {} in any of hashdb: {}".format(basename, list(self.hashdb.keys())))

    def hash2hp(self, hspec, remote=True):

        for hdb in self.hashdb.values():
            try:
                return hdb.hash2hp(hspec)
            except KeyError:
                pass

        if remote:
            for hs in self.hashserver:
                hp = hs.hash2hp(hspec)
                return hp

        raise KeyError("Not found in any of {} hashdb".format(len(self.hashdb)))

    def pull_anchor(self, hashspec):
        """
        pull package by anchor (checks if it exists locally before pulling)

        :param hashspec: hash of anchor (sha256:aabbcc...)
        :return: None if already exists, True if pulled, False if missing on hashservers
        """

        try:
            self.hash2hp(hashspec, remote=False)
            return None
        except KeyError:
            pass

        for hs in self.hashserver:
            self.stats['q'] += 1
            try:
                hp = hs.hash2hp(hashspec)
                # save
                log.debug('pulled {} by anchor'.format(hp))
                self.stats['hits'] += 1
            except KeyError:
                self.stats['miss'] += 1
                return False
            else:
                self.submit_save(hp,'_cached')
                return True


    def clean(self):
        log.warning('Clean {}'.format(self.path))
        for basename in os.listdir(self.path):
            path = os.path.join(self.path, basename)
            log.debug('Delete {}'.format(path))
            shutil.rmtree(path)