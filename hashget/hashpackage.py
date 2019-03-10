import os
import json
import logging

from . import utils

log = logging.getLogger('hashget')

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

    fields = ['url', 'files', 'anchors', 'signatures', 'hashes', 'attrs']

    def __init__(self, url=None, anchors=None, files=None, hashes=None, attrs=None, signatures=None):
        self.url = url
        self.path = None
        self.anchors = anchors
        self.files = files
        self.hashes = hashes  # list of hashspec for package file itself
        self.attrs = attrs or dict()
        self.signatures = signatures

    def __eq__(self, obj):
        return (self.url == obj.url
                and self.anchors == obj.anchors
                and self.files == obj.files
                and self.attrs == obj.attrs
                and self.signatures == obj.signatures)

    def set_attr(self, name, value):
        self.attrs[name] = value

    @classmethod
    def load(cls, path=None, stream=None, data=None):
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

        for name in data.keys():
            setattr(hp, name, data[name])
        return hp

    def basename(self):
        return self.url.split('/')[-1]

    def __repr__(self):
        return "{} ({}/{})".format(self.basename(), len(self.anchors), len(self.files))

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

        os.unlink(self.path)
