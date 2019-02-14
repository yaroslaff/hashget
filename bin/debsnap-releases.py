#!/usr/bin/python3

# import hashget
import datetime
import argparse
import time
import requests
import os
import shutil
import json
import hashlib


def sha256sum(filename):
    h  = hashlib.sha256()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()

parser = argparse.ArgumentParser(description='HashGet fetcher and deduplicator')

g = parser.add_argument_group('Commands')
g.add_argument('--crawl', default=None, metavar='CODENAME', help='get file by hash')

g = parser.add_argument_group('Options')
g.add_argument('--dir', '-d', default='releases', metavar='releases', help='releases directory')
g.add_argument('--sleep', '-s', type=int, default=10, metavar='releases', help='sleep after each fetch')
g.add_argument('--start', default=None, metavar='YYYYMMDD', help='start from this')

args = parser.parse_args()


headers = {
    'User-Agent': 'hashget 1.0'
}

if args.crawl:
    codename = args.crawl

    # verify dir

    assert(os.path.isdir(args.dir))
    assert(os.path.isdir(os.path.join(args.dir,codename)))
    assert(os.path.isdir(os.path.join(args.dir,codename,'files')))
    assert(os.path.isdir(os.path.join(args.dir,codename,'headers')))
    assert(os.path.isdir(os.path.join(args.dir,codename,'hash')))


    date = datetime.datetime.now()
    day = datetime.timedelta(days=1)

    lasth = dict()

    while True:
        datestr = date.strftime("%Y%m%d")

        url = 'https://snapshot.debian.org/archive/debian/{date}/dists/{codename}/Release'.format(codename = codename, date = datestr)
        release_path = os.path.join(args.dir, codename, 'files','Releases-{}'.format(datestr))
        headers_path = os.path.join(args.dir, codename, 'headers','Releases-{}.json'.format(datestr))

        if 'ETag' in lasth:
            headers['If-None-Match'] = lasth['ETag']

        r = requests.get(url, headers=headers, stream=True)
        print("{} {} etag: {}".format(r.status_code, url, r.headers['ETag']))

        assert(r.status_code in [200, 304])

        if(r.status_code == 304):
            assert(r.headers['ETag'] == lasth['ETag'])
            assert(r.headers['Last-Modified'] == lasth['Last-Modified'])

        if(r.status_code == 200):
            print("saved to {}".format(release_path))
            with open(release_path, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
            relsum = sha256sum(release_path)
            hsum_path = os.path.join(args.dir, codename, 'hash',relsum)
            if not os.path.exists(hsum_path):
                src = os.path.relpath(release_path, os.path.dirname(hsum_path))
                print("make link {} > {}".format(hsum_path, src))
                os.symlink(src, hsum_path)


        lasth = dict(r.headers)

        with open(headers_path, 'w') as f:
            json.dump(lasth, f, indent=4)

        ldate = datetime.datetime.strptime(lasth['Last-Modified'], "%a, %d %b %Y %X %Z")
        ldatestr = ldate.strftime("%Y%m%d")
        #print("Last modified: {} {}".format(ldate, ldatestr))

        if ldate >= date:
            print("date: {}, ldate: {}, go back one day")
            date -= day
        else:
            date = ldate


        # date -= day
        time.sleep(args.sleep)

