import os
import re
import json
import shutil
import requests
import urllib.parse
import logging

from .utils import kmgt
from .file import File
from .hashpackage import HashPackage
from . import debian
from . import __user_agent__

log = logging.getLogger('hashget')


class HashDB(object):
    """
        Abstract class representing HashDB, local or remote
    """

    def __init__(self):
        pass

    def submit(self, hp):
        pass

    def hash2hp(self, hsum):
        pass


class DirHashDB(HashDB):
    """
        Local HashDB stored in directory
    """

    hpclass = HashPackage

    def __init__(self, path=None, load=True):

        super().__init__()

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

        self._config = dict()

        self.packages = list()

        # package or file Hash to hp
        self._h2hp = dict()

        # only loaded packages hashes (one hashspec per package)
        self._loaded_packages = list()

        # File Hash to Package Hash
        # self.fh2hp = dict()

        # Signature to Package Hash
        self._sig2hash = dict()

        self.loaded = False

        self.read_config()

        if load:
            self.load()


    @property
    def storage(self):
        return self._config.get('storage', 'basename')

    @storage.setter
    def storage(self, value):
        if value in ['basename', 'hash2', 'hash3']:
            self._config['storage'] = value
        else:
            raise ValueError('Wrong storage type "{}"'.format(value))

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def pkgtype(self):
        return self._config.get('pkgtype', 'generic')

    @pkgtype.setter
    def pkgtype(self, value):
        if value in ['generic', 'debsnap']:
            self._config['pkgtype'] = value
        else:
            raise ValueError('Wrong pkgtype "{}"'.format(value))

    def read_config(self):
        self._config = {'storage': 'basename', 'pkgtype': 'generic'}

        try:
            with open(os.path.join(self.path, '.options.json')) as f:
                conf = json.load(f)
            for k, v in conf.items():
                self._config[k] = v
        except FileNotFoundError:
            pass

        # set default values
        for hpc in self.hpclass.__subclasses__():
            if hpc.pkgtype == self._config['pkgtype']:
                self.hpclass = hpc

    def write_config(self):
        with open(os.path.join(self.path, '.options.json'), 'w') as f:
            json.dump(self._config, f, indent=4)

    def writehp(self, hp):
        """
        writes one HashPackage
        :param hp:
        :return:
        """
        path = self.hp2filename(hp)

        os.makedirs(os.path.dirname(path), exist_ok=True)

        hp.save(path)

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
        :param storage: storage type (string)
        :return: filename
        """

        storage = storage or self._config['storage']

        hsum = hp.get_phash().split(':')[1]

        if storage == 'basename':
            subpath = '/'.join(['p', hp.url.split('/')[-1]]) + '.json'
        elif storage == 'hash2':
            subpath = '/'.join(['p', hsum[0:2], hsum[2:4], hsum[4:]])
        elif storage == 'hash3':
            subpath = '/'.join(['p', hsum[0:2], hsum[2:4], hsum[4:6], hsum[6:]])
        else:
            raise ValueError('bad storage type {}'.format(storage))

        return os.path.join(self.path, subpath)

    def package_files(self):
        """
        yields each relative path to each package file in DirHashDB
        """
        for root, dirs, files in os.walk(os.path.join(self.path, 'p')):
            for basename in files:
                path = os.path.join(root, basename)
                if path != os.path.join(self.path, '.options'):
                    yield os.path.join(self.path, path)

    def packages_iter(self):
        for path in self.package_files():
            try:
                hp = self.hpclass.load(path=path)
            except json.decoder.JSONDecodeError:
                log.warning('Skipping incorrent HashPackage file {}'.format(path))
                continue
            hp.hashdb = self
            yield hp

    def hplist(self, hpspec=None):
        for hp in self.packages_iter():
            if hpspec is None or hp.match_hpspec(hpspec):
                yield hp

    def hp1(self, hpspec=None):
        """
        Returns one first hashpackage
        or IndexError
        :param project:
        :param hpspec:
        :return:
        """
        return list(self.hplist(hpspec=hpspec))[0]

    def load(self):
        """
            DirHashDB.load()
        """

        if not os.path.isdir(self.path):
            # no hashdb
            return

        for path in self.package_files():
            try:
                hp = self.hpclass.load(path=path)
                if hp.expired():
                    log.warning('Skip loading expired HP file {}'.format(path))
                else:
                    self.submit(hp)
            except json.decoder.JSONDecodeError:
                log.error('Skip incorrect HP file {}'.format(path))

        self.loaded = True

    def basename2hp(self, basename):
        for hp in self.packages_iter():
            if hp.basename == basename:
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
        return LIST of hashpackages by hashspec of package or any indexed file in it
        :param hashspec:
        :return:
        """

        if hashspec in self._h2hp:
            return self._h2hp[hashspec]

        raise KeyError('Hashspec {} not found neither in package hashes nor in file hashes'.format(hashspec))

    def sig_present(self, sigtype, sig):
        return (sigtype in self._sig2hash) and (sig in self._sig2hash[sigtype])

    def __repr__(self):
        return 'DirHashDB(path:{} stor:{} pkgtype:{} packages:{})'.format(self.path, self.storage,
                                                                          self._config['pkgtype'], len(self.packages))

    def dump(self):
        print("packages: {}".format(len(self.packages)))
        ids_packages = [ id(x) for x in self.packages]

        for p in self.packages:
            print("  {}".format(p))
        print(ids_packages)
        print("_h2hp:", len(self._h2hp))
        ids_ref = list()
        for hsum, pkgs in self._h2hp.items():
            for pkg in pkgs:
                if not id(pkg) in ids_ref:
                    ids_ref.append(id(pkg))
        print(ids_ref)

    def __add_h2hp(self, hashspec, value):
        if hashspec not in self._h2hp:
            self._h2hp[hashspec] = list()

        if value in self._h2hp[hashspec]:
            print("ERR", value, "already in _h2hp[", hashspec, "]")

        assert(value not in self._h2hp[hashspec])
        self._h2hp[hashspec].append(value)

    # DirHashDB.submit
    def submit(self, hp):
        """
            Append HashPackage to hashdb internal structures
            (not saving to disk)
        """

        phash = hp.hashspec
        if phash in self._loaded_packages:
            # delete old package
            for old_hp in list(self._h2hp[phash]):
                if old_hp.hashspec == phash:
                    log.debug('delete old package with hashspec {}: {}'.format(old_hp.hashspec, old_hp))
                    old_hp.delete()
        assert(not phash in self._loaded_packages)

        self.packages.append(hp)

        # add sum of package itself, for hash
        for hsum in hp.hashes:
            self.__add_h2hp(hsum, hp)

        for hpf in hp.files:
            self.__add_h2hp(hpf, hp)

        if hp.signatures:
            for sigtype, sig in hp.signatures.items():
                if sigtype not in self._sig2hash:
                    self._sig2hash[sigtype] = dict()
                self._sig2hash[sigtype][sig] = phash

        self._loaded_packages.append(phash)
        hp.hashdb = self



    def delete_by_hashspec(self, hashspec):

        def filter_hplist(hplist, hashspec):
            return [ hp for hp in hplist if hp.hashspec != hashspec ]

        # self._h2hp = {k: v.remove(hp) for k, v in self._h2hp.items()}
        del_hsum = list()

        for hsum in self._h2hp:
#            for hp in self._h2hp[hsum]:
            self._h2hp[hsum] = filter_hplist(self._h2hp[hsum], hashspec)
            if not self._h2hp[hsum]:
                # empty list, delete it
                if not hsum in del_hsum:
                    del_hsum.append(hsum)
            else:
                # non empty list, some hashsum still exists (which belongs to other packages)
                pass

        for hsum in del_hsum:
            del(self._h2hp[hsum])

        for sigtype in self._sig2hash:
            self._sig2hash[sigtype] = {k: v for k, v in self._sig2hash[sigtype].items() if v != hashspec}

        self.packages = filter_hplist(self.packages, hashspec)
        self._loaded_packages.remove(hashspec)

    def __len__(self):
        return len(self.packages)

    def self_check(self):
        error = False
        for hsum, hplist in self._h2hp.items():
            p = set(list([ hp.hashspec for hp in hplist ]))
            if len(p) != len(hplist):
                print("ERR HPLIST:", hplist)
                print("   HASHSET:", p)
                error = True

        if error:
            print("SELF CHECK FAIL")
        else:
            # print("SELF CHECK OK")
            pass
        return not error

    def truncate(self):
        """
        delete all packages from this hashdb
        :return:
        """
        self.packages = list()
        self._h2hp = dict()
        self._loaded_packages = list()
        self._sig2hash = dict()
        self.loaded = True
        for path in self.package_files():
            os.unlink(path)


class HashServer:
    """
        Interface to remote HashServer

    """
    def __init__(self, url=None):
        self.url = url
        self.config = dict()
        if not self.url.endswith('/'):
            self.url = self.url+'/'

        log.debug('Initialize remote HashDB {}'.format(self.url))

        self.headers = dict()
        self.headers['User-Agent'] = __user_agent__

        # default config

        self.config['name'] = 'noname'
        self.config['submit'] = urllib.parse.urljoin(self.url, 'submit')
        self.config['hashdb'] = urllib.parse.urljoin(self.url, 'hashdb')
        self.config['motd'] = urllib.parse.urljoin(self.url, 'motd.txt')
        self.config['accept_url'] = list()

        r = requests.get(urllib.parse.urljoin(self.url, 'config.json'), headers=self.headers)

        if r.status_code == 200:
            self.config.update(json.loads(r.text))
            # this method works only with 3.5 and above
            # self.config = {**self.config, **json.loads(r.text)}

        r = requests.get(urllib.parse.urljoin(self.url, self.config['motd']), headers=self.headers)
        self.motd_text = r.text.rstrip()
        self.motd_displayed = False

    def display_motd(self):
        if self.motd_displayed:
            return
        self.motd_displayed = True
        log.info(self.motd_text)

    def fhash2url(self, hashspec):
        self.display_motd()

        spec, hsum = hashspec.split(':', 1)
        if spec != 'sha256':
            raise KeyError
        # prepare url
        urlpath = '/'.join(['a', hsum[:2], hsum[2:4], hsum[4:6], hsum[6:]])
        return urllib.parse.urljoin(self.url, urlpath)

    def fhash_exists(self, hashspec):
        r = requests.head(self.fhash2url(hashspec))
        return r.status_code == 200

    def hash2hp(self, hashspec):
        """
        User to pull hashpackage by anchor

        :param hashspec:
        :return:
        """
        self.display_motd()
        r = requests.get(self.fhash2url(hashspec), headers=self.headers)

        if r.status_code != 200:
            return list()

        hp = HashPackage.load(data=r.json())
        return [hp]

    def want_accept(self, url):
        for reurl in self.config['accept_url']:
            if re.search(reurl, url):
                return True
        return False

    def sig_present(self, sigtype, signature):
        self.display_motd()
        if sigtype == 'deb':
            path = ['sig', 'deb'] + debian.debsig2path(signature)
            url = urllib.parse.urljoin(self.config['hashdb'], '/'.join(path))

            r = requests.head(url)
            if r.status_code == 200:
                return True

        return False

    def sig2hp(self, sigtype, signature):
        self.display_motd()
        if sigtype == 'deb':
            path = ['sig', 'deb'] + debian.debsig2path(signature)
            url = urllib.parse.urljoin(self.config['hashdb'], '/'.join(path))

            r = requests.get(url)
            if r.status_code == 200:
                hp = HashPackage.load(data=r.json())
                return hp
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
        with open(file, 'rb') as f:
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
    def __init__(self, path=None, load=True, enabled_hashdb=None):

        super().__init__()

        self.hashserver = list()
        self.stats = dict(q=0, miss=0, hits=0)

        if enabled_hashdb is None:
            self.enabled_hashdb = ['all']
        else:
            self.enabled_hashdb = enabled_hashdb

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

            if 'all' in self.enabled_hashdb or name in self.enabled_hashdb:
                log.debug('Load hashdb {}'.format(name))
                project_path = os.path.join(self.path, name)
                if os.path.isdir(project_path):
                    self.hashdb[name] = DirHashDB(path=project_path, load=load)
            else:
                log.debug('Skip loading hashdb {}'.format(name))

    def __repr__(self):
        return("HashClient(l{} n{} q{} h{} m{})".format(
            len(self.hashdb), len(self.hashserver),
            self.stats['q'], self.stats['hits'], self.stats['miss']
        ))

    def add_hashserver(self, url):
        hs = HashServer(url=url)
        self.hashserver.append(hs)
        if '_cached' not in self.hashdb:
            self.create_project('_cached')

    def submit_save(self, hp, project, file=None):
        hdb = self.hashdb[project]

        hdb.submit(hp)
        hdb.writehp(hp)

        if file:
            for hs in self.hashserver:
                hs.submit(url=hp.url, file=file)

    def submit(self, hp):
        """
        use submit_save

        :param hp:
        :return:
        """
        raise NotImplementedError

    def create_project(self, name):
        project_path = os.path.join(self.path, name)
        if not os.path.isdir(project_path):
            os.mkdir(project_path)
            self.hashdb[name] = DirHashDB(path=project_path)
            return self.hashdb[name]
        else:
            log.debug("project {}  already exists".format(name))

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
                self.submit_save(hp, '_cached')
                return True

        return False

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
        :param remote: do remote requests
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

    def hash2hp(self, hspec, remote=True, expires=None):
        """

        :param hspec:
        :param remote:
        :return: list of hashpackages (maybe empty)
        """

        r = list()

        for hdb in self.hashdb.values():
            try:
                r.extend(hdb.hash2hp(hspec))
            except KeyError:
                pass

        if remote:
            for hs in self.hashserver:
                hp = hs.hash2hp(hspec)
                r.extend(hp)

        # filter from expired
        if expires:
            # finite expiration
            r = [ hp for hp in r if not hp.expired(expires) ]
        else:
            # infinite expiration
            r = [ hp for hp in r if not hp.expires ]


        return r

    def pull_anchor(self, hashspec):
        """
        pull package from server by anchor (checks if it exists locally before pulling)

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
                self.submit_save(hp, '_cached')
                return True

    def hplist(self, project=None, hpspec=None):
        for name, hdb in self.hashdb.items():
            if project is None or name == project:
                for hp in hdb.packages_iter():
                    if hpspec is None or hp.match_hpspec(hpspec):
                        yield hp

    def hp1(self, project=None, hpspec=None):
        """
        Returns one first hashpackage
        or raise IndexError
        :param project:
        :param hpspec:
        :return:
        """
        return list(self.hplist(project=project, hpspec=hpspec))[0]


    def clean(self):
        log.warning('Clean {}'.format(self.path))
        for basename in os.listdir(self.path):
            path = os.path.join(self.path, basename)
            log.debug('Delete {}'.format(path))
            shutil.rmtree(path)
