import shutil
import os
import hashget.file
import logging
import tempfile
import urllib
import requests

log = logging.getLogger('hashget')

from .file import Hashes


class FilePool(object):
    def __init__(self):
        pass

    def __getitem__(self, hashspec):
        pass

    def append(self, path):
        return False

    def get(self, item, default=None, name=None):
        pass

    def __repr__(self):
        return self.__class__.__name__

    def hashspec2subpath(self, hashspec):
        hashtype, hsum = hashspec.split(':')
        subpath = '/'.join(['pool', hashtype, hsum[0:2], hsum[2:4], hsum[4:6], hsum[6:]])
        return subpath

    def cleanup(self):
        # nothing.
        pass

class NullFilePool(FilePool):
    def __init__(self):
        super().__init__()

    def __getitem__(self, item):
        raise KeyError

    def get(self, item, default=None, name=None):
        return default


class FilePoolMultiplexer(FilePool):

    def __init__(self):
        self._pools = list()

    def __getitem__(self, item):
        for pool in self._pools:
            try:
                x = pool[item]
                return x
            except KeyError:
                pass
        raise KeyError

    def get(self, item, default=None, name=None):
        for pool in self._pools:
            x = pool.get(item, default=default, name=name)
            if x != default:
                return x
        return default

    def append(self, path):
        for pool in self._pools:
            if pool.append(path):
                # append only to first pool which accepted it
                return

    def add(self, poolpath):
        if poolpath.startswith('http://') or poolpath.startswith('https://') \
                or poolpath.startswith('ftp://'):
            self._pools.append(hashget.filepool.HttpFilePool(url=poolpath))
        else:
            self._pools.append(hashget.filepool.DirFilePool(path=poolpath))

    def __repr__(self):
        s = self.__class__.__name__ + '('
        for pool in self._pools:
            s += str(pool) + ', '
        s += ')'
        return s

class DirFilePool(FilePool):
    def __init__(self, path=None):
        super().__init__()
        self._sums = ['sha256']
        self.path = path
        self._hashes = dict()
        self.files = list()

        # statistics
        self.loaded = 0 # loaded from disk
        self.new = 0 # new files
        self.requested = 0 # successful requests

        self.load()

    def load(self):
        for root, dirs, files in os.walk(self.path):
            for f in files:
                self.load1(os.path.join(root, f))

    def load1(self, path):
        if os.path.islink(path):
            target = os.readlink(path)
            path = os.path.join(os.path.dirname(path), target)

        f = hashget.file.File(path, sums=self._sums)
        for spec in f.hashes.get_list():
            self._hashes[spec] = path
        self.files.append(path)
        self.loaded += 1

    def fixname(self, path):
        if not os.path.isfile(path):
            return path

        idx = 0
        while True:
            idx += 1
            tmp_path = "{}.{}".format(path, idx)
            if not os.path.isfile(tmp_path):
                return tmp_path

    def append(self, path):
        """
        copy file to pool
        :param path:
        :return:
        """
        f = hashget.file.File(path, sums=self._sums)

        if f.hashspec in self._hashes:
            log.debug('Do not put {} to pool, hash already in pool'.format(path))
            return

        basename = os.path.basename(path)
        dst = os.path.join(self.path, basename)

        dst = self.fixname(dst)
        shutil.copyfile(path, dst)
        self.load1(dst)
        self.new += 1
        log.debug('Added to local pool {}'.format(dst))
        return True

    def __getitem__(self, hashspec):
        return self._hashes[hashspec]

    def __len__(self):
        return self.loaded

    def get(self, hashspec, default=None, name=None):
        try:
            r = self._hashes[hashspec]
            self.requested += 1
            return r
        except KeyError:
            return default

    def get_by_basename(self, basename):
        for sum, path in self._hashes.items():
            if os.path.basename(path) == basename:
                return path

    def truncate(self):
        """
        delete all files from pool
        :return:
        """
        for path in self.files:
            os.unlink(path)

        self.files = list()
        self._hashes = dict()
        self.loaded = 0

    def pool_files(self):
        for dirname, dirs, files in os.walk(self.path):
            for file in files:
                path = os.path.join(dirname, file)
                yield path

    def __repr__(self):
        return "{} ({}) {}".format(self.__class__.__name__, self.path, self.loaded)


class HttpFilePool(FilePool):
    """
    read-only HTTP pool
    """
    def __init__(self, url=None, path=None):

        if url.endswith('/'):
            self.url = url
        else:
            self.url = url+'/'
        self.path = path
        self.path_created = False

        # create tmp path
        if self.path is None:
            self.path = tempfile.mkdtemp(prefix='hashget-tmp-pool-')
            self.path_created = True

        if os.path.isdir(self.path):
            # tmp dir already exists
            pass
        else:
            os.mkdir(self.path)
            self.path_created = True

    def __repr__(self):
        return "{} ({}) {}".format(self.__class__.__name__, self.path, self.url)

    def append(self, path):
        """
        HTTP
        :param path:
        :return:
        """
        return False

    def __getitem__(self, hashspec):
        item = self.get(hashspec, name=hashspec)
        if item is None:
            raise KeyError
        return item

    def __len__(self):
        raise NotImplemented

    def get(self, hashspec, default=None, name=None):
        name = name or hashspec
        filename = os.path.join(self.path, os.path.basename(name))
        url = urllib.parse.urljoin(self.url, self.hashspec2subpath(hashspec))

        r = requests.get(url, stream=True)
        if r.status_code == 200:
            log.debug("http pool: get {} to {}".format(url, filename))
            with open(filename, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
        else:
            log.debug("http pool: no {} in {}".format(hashspec, self.url))
            return None
        return filename

    def cleanup(self):
        if self.path_created:
            shutil.rmtree(self.path)