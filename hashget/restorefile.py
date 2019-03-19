import json
import os
from .file import File
from . import utils


class RestoreFile(object):
    
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

    def fbyhash(self, hashspec):
    
        spec, hsum = hashspec.split(':')
    
        for fdata in self.data['files']:
            if fdata[spec] == hsum:
                f = File.from_dict(fdata, self.root)
                yield f

    def packages(self):
        for pdata in self.data['packages']:
            yield pdata['url']

    def add_file(self, f):
        self.data['files'].append(f.to_dict())

    def add_package(self, url, hashspec):
        p = dict()
        p['url'] = url
        p['hash'] = hashspec
        self.data['packages'].append(p)
    
    def save(self, path):
        with open(path,'w') as f:
            json.dump(self.data, f, indent=4, sort_keys=True) 
        
    def load(self, path):
        with open(path) as f:
            self.data = json.load(f)


    def should_process(self, hashspec):
        spec, hsum = hashspec.split(':')

        for fdata in self.data['files']:
            if fdata[spec] == hsum:
                return not fdata['processed']
        return False

    def set_processed(self, hashspec):
        """
        sets processed flag

        :param hashspec:
        :return: old value of processed flag. or None if no such file
        """
        spec, hsum = hashspec.split(':')

        old_state = None

        for fdata in self.data['files']:
            if fdata[spec] == hsum:
                old_state = fdata['processed']
                fdata['processed'] = True
        return old_state

    def preiteration(self):
        for fdata in self.data['files']:
            fdata['processed'] = False     
  
    def sumsize(self):
        sumsize = 0
        for fd in self.data['files']:
            sumsize += fd['size']
        return sumsize
            
    def __repr__(self):
        return '{} files, {} pkgs, size: {}'.format(
                len(self.data['files']),
                len(self.data['packages']),
                utils.kmgt(self.sumsize()))

    def get_nfiles(self):
        return len(self.data['files'])

    def check_processed(self):
        np = 0
        nnp =0

        for fdata in self.data['files']:
            if fdata['processed']:
                np += 1
            else:
                print("NOT PROCESSED {} {}".format(fdata['sha256'], fdata['file']))
                nnp += 1
        if nnp > 0:
            print("processed: {}/{} files, missing {} files. Try --recursive option".format(np, len(self.data['files']), nnp))
