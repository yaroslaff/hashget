import json
import requests
import time
import os
import logging

from .utils import sha1sum

from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from .cacheget import CacheGet

from .submiturl import submit_url
from .hashpackage import HashPackage

rsess = None

log = logging.getLogger('hashget')

class DebPackage(object):
    """
    For installed packages in var/lib/dpkg/status
    """
    
    rsess = None

    def __init__(self, info=None):
        self.info = None        
        self.__url = None
        if info:
            self.set_package_info(info)

    def is_installed(self):        
        return self.status == 'install ok installed'
            
    
    def set_package_info(self, info):
        self.status = info['Status']
        self.package = info['Package']
        self.section = info['Section']
        self.version = info['Version']
        self.arch = info['Architecture']

    @property
    def signature(self):
        return "{}_{}_{}".format(self.package, self.version, self.arch)
    
    def __repr__(self):
        return self.signature


    @property
    def url(self):
        if self.__url:
            return self.__url

        self.__url = self.get_snapshot_url()
        return self.url

    def get_snapshot_url(self):
        prefix = 'http://snapshot.debian.org/mr/'
        aurl_prefix = 'http://snapshot.debian.org/archive'    


        cg = CacheGet()

        if self.rsess is None:
            DebPackage.rsess = requests.Session()

        retries = Retry(total=50,
            connect=20,
            backoff_factor=5,
            status_forcelist=[ 500, 502, 503, 504 ])
        self.rsess.mount('http://', HTTPAdapter(max_retries=retries))            

        hashsum = None
        
        # print "Crawl package", p['Package']
        
        url = prefix + 'binary/' + self.package + '/' + self.version + '/binfiles'

        r = self.rsess.get(url)

        data = json.loads(r.text)
        
        # print json.dumps(data, indent=4)
        for r in data['result']:
            if r['architecture'] == self.arch:
                hashsum = r['hash']
        
        url = prefix + 'file/' + hashsum + '/info'
        r = self.rsess.get(url)
        data = json.loads(r.text)
        result = data['result'][0]
        
        # print json.dumps(data, indent=4)
        

        arcname = result['archive_name']
        first_seen = result['first_seen']     
        path = result['path'][1:]
        size = result['size']
        name = result['name']
        
        url = '/'.join([ aurl_prefix, arcname, first_seen, path, name ]) 
        return url


class DebHashPackage(HashPackage):

    pkgtype = 'debsnap'

    def get_special_anchors(self):
        def debsig2path(sig):
            sigbase = sig.split('_')[0]
            path = list()

            if sigbase.startswith('lib'):
                path.append('lib' + sigbase[3])
            else:
                path.append(sigbase[0])

            path.append(sigbase)
            path.append(sig)
            return path

        for sigtype, sig in self.signatures.items():
            if sigtype == 'deb':
                yield '/'.join(['sig', 'deb'] + debsig2path(sig))




def load_release(filename):
    """
        load Release file as data structure
    """
    data = dict()
    datalist = list()
    lastkey = None    
    
    array = False
    
    with open(filename, encoding='utf-8') as f:
        for line in f:
            if line == '\n':
                # list element
                array = True
                datalist.append(data)
                data = dict()                    
            elif line[0] == ' ':
                # starts with space
                if data[lastkey] == '':
                    data[lastkey] = list()
                else:
                    if isinstance(data[lastkey], list):
                        data[lastkey].append(line.strip())
                    else:
                        # string continues on new line
                        data[lastkey] += line.strip()
            else:
                # usual key: value
                k, v = line.rstrip().split(':',1)
                data[k] = v.strip()
                lastkey = k

    # end of file
    if array:
        return datalist
    
    return data


#
# Crawling
#


def debcrawl_packages(root):
    cnt_total = 0
    cnt_installed = 0
    cnt_not_installed = 0
    cnt_already = 0
    cnt_new = 0

    def file2pkgname(filename):
        # delete suffix (.list) or :arch.list
        if ':' in filename:
            return filename.split(':')[0]
        else:
            return '.'.join(filename.split('.')[:-1])

    status = load_release(os.path.join(root, 'var/lib/dpkg/status'))

    for pdict in status:
        p = DebPackage(info=pdict)
        if not p.is_installed():
           continue
        yield(p)

def deb2snapurl(path):
    """
    check .deb file, verify and return snapurl for it
    :param path:
    :return:
    """
    hsum = sha1sum(path)
    url = 'http://snapshot.debian.org/mr/file/{}/info'.format(hsum)
    r = requests.get(url)
    if r.status_code != 200:
        return None

    data = r.json()

    for r in data['result']:
        if r['archive_name'] == 'debian':
            url = 'http://snapshot.debian.org/archive/{archive_name}/{first_seen}{path}/{name}'.format(**r)
            return url

    r=data['results'][0]
    url = '/'.join(['http://snapshot.debian.org/archive', r['archive_name'], r['first_seen'], r['path'], r['name']])
    return url


def debsubmit(hashdb, path, anchors, attrs=None):
    url = deb2snapurl(path)
    attrs = attrs or dict()

    log.info("debsubmit from URL: {}".format(url))
    assert(url.endswith('.deb'))

    basename = url.split('/')[-1]
    debsig = '.'.join(basename.split('.')[:-1])

    if hashdb.sig_present('url', url):
        raise ValueError("HashDB has URL sig {}".format(url))

    if hashdb.sig_present('deb', debsig):
        raise ValueError("HashDB has deb sig {}".format(debsig))

    signatures = {
        'deb': debsig
    }

    log.debug("submitting...")
    hp = submit_url(
        url = url,
        file = path,
        project = 'debsnap',
        anchors = anchors,
        # filesz=args.filesz,
        signatures = signatures,
        hashdb = hashdb,
        attrs = attrs,
        hpclass = DebHashPackage)
    log.debug("submitted... {}".format(hp))

    return hp
