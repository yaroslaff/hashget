import json
import os
from .file import File

class hashfile(object):
    
    def __init__(self, path=None):
        self.path = path
        self.data = dict()
        self.data['packages'] = list()
        self.data['files'] = list()
        
        if path is not None:
            self.root = os.path.dirname(path)
            self.load(path)
    
        pass

    def files(self):
        for fdata in self.data['files']:
            f = File.from_dict(fdata, self.root)
            yield f

    def fbyhash(self, h):
        for fdata in self.data['files']:
            if fdata['sha256'] == h:
                f = File.from_dict(fdata, self.root)
                return f
        raise LookupError('No file with hash {}'.format(h))
            
    def packages(self):
        for pdata in self.data['packages']:
            yield pdata['url']

    def add_file(self, f):
        self.data['files'].append(f.to_dict())

    def add_package(self, url, sha256):
        p = dict()
        p['url'] = url
        p['sha256'] = sha256
        self.data['packages'].append(p)
    
    def save(self, path):
        with open(path,'w') as f:
            json.dump(self.data, f, indent=4, sort_keys=True) 
        
    def load(self, path):
        with open(path) as f:
            self.data = json.load(f)
    
    def set_processed(self, h):
        for fdata in self.data['files']:
            if fdata['sha256'] == h:
                fdata['processed'] = False     
        
    
    def preiteration(self):
        for fdata in self.data['files']:
            fdata['processed'] = False     
     
    def __repr__(self):
        return 'snap: {} files, {} pkgs'.format(len(self.data['files']), len(self.data['packages']))
        
