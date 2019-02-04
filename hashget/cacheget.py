import os
from urllib.parse import urlparse
import tempfile
import requests
import time

from .utils import kmgt

class CacheGet():
    
    def __init__(self, cachedir = None, tmpdir = None, tmpprefix = None):

        if cachedir:
            self.cachedir = cachedir
        else:
            # default path
            if os.getuid() == 0:
                # root                
                self.cachedir = '/var/cache/CacheGet'  
            else:
                # usual user
                self.cachedir = os.path.expanduser("~/.CacheGet") 
        
        self.tmpdir = tmpdir or '/tmp/'
        self.tmpprefix = tmpprefix or 'CacheGet-'
    
    
    def get(self, url, headers=None, log=None):

        def logdebug(msg):
            # print msg
            pass

        logerror = logdebug

        headers = headers or dict()
        out = dict()
        out['url'] = url
       
        etag = None
       
        chunk_size = 1024*1024
        basename = url.split('/')[-1]
        
        # local_filename = os.path.join(prefix, basename)
        parsed = urlparse(url)
        tmpfh, tmppath = tempfile.mkstemp(prefix=self.tmpprefix, dir=self.tmpdir) 
        
        local_filename = os.path.join(self.cachedir, 'files', parsed.scheme, parsed.netloc, parsed.path[1:])
        local_dir = os.path.dirname(local_filename)  
        
        etag_filename = os.path.join(self.cachedir, 'etags', parsed.scheme, parsed.netloc, parsed.path[1:]+'.etag')
        etag_dir =  os.path.dirname(etag_filename)
        
        if os.path.isfile(etag_filename) and os.path.isfile(local_filename):
            # read etag
            with open(etag_filename, 'r') as etagf:
              etag = etagf.read()
        
        if not os.path.isdir(local_dir):
            os.makedirs(local_dir)
        
        # maybe reuse cached?
        if os.path.isfile(local_filename) and not etag:
            # have cached and will not (cannot) verify
            out['file'] = local_filename
            out['size'] = os.stat(local_filename).st_size
            return out


        if etag:
            headers['If-None-Match'] = etag


        total_size = 0
        reported_size = 0
        report_each = 1024*1024*10

        logdebug('downloading {} to {}'.format(url, local_filename))
        # NOTE the stream=True parameter


        r = None
        while r is None:
            try:
                r = requests.get(url, stream=True, headers=headers)
            except requests.exceptions.RequestException as e:
                if log:
                    log.debug('download error {}: {}. Retry.'.format(url, str(e)))
                time.sleep(10)

        out['code'] = r.status_code
        if 'ETag' in r.headers:
            out['ETag'] = r.headers['ETag']
            if not os.path.isdir(etag_dir):
                os.makedirs(etag_dir)
            with open(etag_filename,'w') as etagf:
                etagf.write(r.headers['ETag'])
                        
        if r.status_code == 304:
            # not modified
            out['file'] = local_filename
            out['size'] = os.stat(local_filename).st_size
            return out
        
        if r.status_code != 200:
            if log:
                log.error("DOWNLOAD ERROR {} {}".format(r.status_code, url))
            return None
                        
        
        for chunk in r.iter_content(chunk_size=chunk_size): 
            if chunk: # filter out keep-alive new chunks
                os.write(tmpfh, chunk)
                total_size += len(chunk)
                if(total_size >= reported_size + report_each):
                    if log:
                        log_debug('... saved {}...'.format(kmgt(total_size, frac=0)))
                    reported_size = total_size
        os.close(tmpfh)
        
        os.rename(tmppath, local_filename)
                    

        logdebug('download {} status code: {}'.format(kmgt(total_size), r.status_code))
        
        out['file'] = local_filename
        out['size'] = os.stat(local_filename).st_size
        return out
            
        
