import os
import json
import logging
import datetime

from . import utils
import requests

log = logging.getLogger('hashget')
from . import __user_agent__

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

    pkgtype = 'generic'

    fields = ['url', 'files', 'anchors', 'signatures', 'hashes', 'attrs', 'expires']

    def __init__(self, url=None, anchors=None, files=None, hashes=None, attrs=None, signatures=None, expires = None):
        self.url = url
        self.path = None
        self.anchors = anchors
        self.files = files
        self.hashes = hashes  # list of hashspec for package file itself
        self.attrs = attrs or dict()
        self.signatures = signatures
        self.hashdb = None

        self.expires = utils.str2dt(expires)

        self.fix()

    def expired(self, dt=None):
        if self.expires is None:
            # not expired, never expires
            return False

        dt = dt or datetime.datetime.now()
        return self.expires < dt

    def __eq__(self, obj):
        return (self.url == obj.url
                and self.anchors == obj.anchors
                and self.files == obj.files
                and self.attrs == obj.attrs
                and self.signatures == obj.signatures)

    def set_attr(self, name, value):
        self.attrs[name] = value

    def fix(self):
        """
        fix hp, transform it to nice unified format

        anchors and files has no duplicates
        :return:
        """
        if self.files:
            self.files = list(set(self.files))

        if self.anchors:
            self.anchors = list(set(self.anchors))

        if isinstance(self.expires, str):
            self.expires = utils.str2dt(self.expires)

    @classmethod
    def load(cls, path=None, stream=None, data=None):
        """
            load from path/stream or data
            can throw json.decoder.JSONDecodeError if not JSON (e.g. empty file)
        :param path:
        :param stream:
        :param data:
        :return:
        """
        hp = cls()

        if path:
            hp.path = path
            with open(path) as stream:
                data = json.load(stream)
        elif stream:
            data = json.load(stream)
        elif data:
            pass
        else:
            raise (ValueError)

        if 'expires' in data:
            data['expires'] = utils.str2dt(data['expires'])

        for name in data.keys():
            setattr(hp, name, data[name])

        hp.fix()

        return hp

    def save(self, path=None):
        if path:
            self.path=path
        path = self.path
        assert(path)
        with open(path, "w") as f:
            f.write(self.json())

    @property
    def basename(self):
        return self.url.split('/')[-1]

    def clone(self):
        return self.__class__.load(data=self.dict())

    def __repr__(self):
        # return "{} {} {}".format(self.basename(), id(self), self.hashspec)
        return "{} ({}/{})".format(self.basename, len(self.anchors), len(self.files))


    def get_phash(self):
        """
        OBSOLETE method, use get_hashspec for unified
        :return:
        """
        return self.hashspec

    @property
    def hashspec(self):
        for hspec in self.hashes:
            if hspec.startswith('sha256:'):
                return hspec

    def dict(self):
        data = dict()
        for field in self.fields:
            data[field] = getattr(self, field)
        return data

    def json(self):
        # data['hashes'] = self.hashes.get_list()
        self.fix()
        d = self.dict()
        if 'expires' in d and d['expires'] is not None:
            d['expires'] = d['expires'].strftime('%Y-%m-%d')

        return json.dumps(d, indent=4)

    def get_special_anchors(self):
        return list()

    def get_anchors(self):
        for a, subpath in self.get_special_anchors():
            yield (a, subpath)

        for a in self.hashes + self.anchors:
            spec, hsum = a.split(':', 1)
            if spec != 'sha256':
                continue
            yield ( a, '/'.join(['a', hsum[0:2], hsum[2:4], hsum[4:6], hsum[6:]]))

    def make_anchors(self, webroot):
        log.debug("{} make anchors to {} in {}".format(self, self.path, webroot))

        for hspec, subpath in self.get_anchors():
            # log.debug("sub {}".format(subpath))
            linkpath = os.path.join(webroot, subpath)
            os.makedirs(os.path.dirname(linkpath), exist_ok=True)
            if not os.path.islink(linkpath):
                log.debug('make symlink {} to {}'.format(linkpath, self.path))
                os.symlink(self.path, linkpath)

    def purge(self, webroot=None, full=False):
        log.debug("purge {} root: {}".format(self, webroot))
        if webroot:
            if full:
                for path in utils.dircontent(webroot):
                    if os.path.islink(path) and os.readlink(path) == self.path:
                        print(path)
            else:
                for subpath in self.get_anchors():
                    path = os.path.join(webroot, subpath)
                    log.debug("delete symlink {} to {}".format(path, self))
                    if os.path.islink(path):
                        os.unlink(path)
        self.delete()

    def delete(self):
        if self.hashdb:
            self.hashdb.delete_by_hashspec(self.hashspec)
        os.unlink(self.path)

    def verify(self):
        log.debug('verify {} {}'.format(self, self.url))
        headers = dict()
        headers['User-Agent'] = __user_agent__
        r = requests.head(self.url, headers=headers)
        if r.status_code != 200:
            log.debug('Bad status code: {} {}'.format(r.status_code, self))
            return False

        if 'Content-Length' in r.headers and 'size' in self.attrs:
            clen = int(r.headers.get('Content-Length'))
            if self.attrs['size'] != clen:
                log.debug('Bad Content-Length {} != size {}'.format(clen, self.attrs['size']))
                return False
            else:
                log.debug('size {} match Content-Length'.format(self.attrs['size']))

        return True

    def match_hpspec(self, hpspec):

        prefix, value = hpspec.split(':', 1)

        #print(prefix, value)

        if prefix == 'all':
            return True

        if prefix == 'name':
            return self.basename == value

        if prefix in ['expires', 'expired']:

            if value:
                exp_date = utils.str2dt(value)
                return self.expired(exp_date)
            return self.expired()

        if prefix == 'url':
            return self.url == value

        if prefix == 'sig':
            try:
                sigtype, signature = value.split(':', 1)
                return self.signatures[sigtype] == signature
            except (ValueError, KeyError):
                return False

        return False
