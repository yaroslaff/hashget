import json
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from .cacheget import CacheGet


rsess = None

class DebPackage(object):
    
    rsess = None

    def __init__(self, info=None):
        self.info = None        
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
    
    def get_signature(self):
        return "{} {} {}".format(self.package, self.version, self.arch)        
    
    def __repr__(self):
        return self.get_signature()
    
    def snapshot_url(self):
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



def load_release(filename):
    """
        load Release file as data structure
    """
    data = dict()
    datalist = list()
    lastkey = None    
    
    array = False
    
    with open(filename) as f:
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


