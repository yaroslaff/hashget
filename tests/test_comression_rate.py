import sys
import subprocess
import requests
import os
import json
import shutil
import logging

import hashget
import hashget.hashdb
import hashget.operations
import hashget.heuristics
import hashget.filepool
from hashget.utils import kmgt, du

import pytest

from conftest import option

project = '_test'

hashdb = None
pool = None

urls = dict(
    wordpress='https://wordpress.org/wordpress-5.1.1.zip',
    kernel='https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.0.10.tar.xz'
)

hp_kernel = None
results = list()

def setup_module(module):
    global hashdb, hdb
    global pool
    global hp_kernel

    if option.pool:
        pool = hashget.filepool.DirFilePool(option.pool)

    _logging(logging.INFO)

    hashdb = hashget.hashdb.HashDBClient()
    try:
        hp_kernel = hashdb.sig2hp('url', urls['kernel'])
        print("hp_kernel:", hp_kernel)
    except KeyError:
        print("TO SPEED UP: hashget --submit {} --project kernel.org".format(urls['kernel']))

    hashdb = hashget.hashdb.HashDBClient(enabled_hashdb=[project])
    try:
        hashdb.remove_project(project)
    except KeyError:
        pass

    hdb = hashdb.ensure_project(project)
    hdb.truncate()


    # configure to import ALL heuristics
    for path in sys.path:
        hhpath = os.path.join(path,'hashget', 'heuristics')
        if os.path.isdir(hhpath):
            hashget.heuristic_base.heuristics_path.append(hhpath)

def teardown_module(module):
    global hashdb

    _table()

    try:
        hashdb.remove_project(project)
    except KeyError:
        pass


def _table():

    columns = [ "File", "Unpacked", "Packed", "Ratio" ]
    fmt_data  = "{:<30} {:<15} {:<15} {:<15.3f}"
    fmt_title = "{:<30} {:<15} {:<15} {:<15}"
    print()
    print(fmt_title.format(*columns))
    print(fmt_title.format( *(["---"] * len(columns)) ))
    for data in results:
        print(fmt_data.format(
            os.path.basename(data['url']),
            kmgt(data['unpacked']),
            kmgt(data['packed']),
            data['packed'] * 100.0 / data['unpacked']
            ))


def _logging(level=None):
    global log
    level = level or logging.INFO

    # prepare logging
    log = logging.getLogger('hashget')
    log.setLevel(level)
    logstdout = logging.StreamHandler(stream=sys.stderr)
    logstdout.setFormatter(logging.Formatter('%(message)s', '%Y-%m-%d %H:%M:%S'))
    log.addHandler(logstdout)


def _download(url, dirpath):
    chunk_size = 10*1024*1024
    downloaded = 0
    path = os.path.join(dirpath, os.path.basename(url))

    if pool:
        # check in pool
        poolpath = pool.get_by_basename(os.path.basename(url))
        if poolpath:
            # found in pool!
            shutil.copyfile(poolpath, path)
            print("Take from pool", poolpath)
            return path


    r = requests.get(url, stream=True)
    assert(r.status_code == 200)

    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                downloaded += chunk_size
                print("... downloaded {}".format(kmgt(downloaded)))

    print("Downloaded {} to {}".format(kmgt(os.stat(path).st_size), path))

    if pool:
        print("Put to pool")
        pool.append(path)

    return path

def test_wordpress(tmpdir):
    unpacked = os.path.join(tmpdir, 'unpacked')
    hgfile = os.path.join(tmpdir,'test_compress.tar.gz')

    os.mkdir(unpacked)
    dstfile = _download(urls['wordpress'], tmpdir)
    cp = subprocess.run(['unzip', '-q', dstfile,'-d', unpacked])
    assert cp.returncode == 0
    dusz = du(unpacked)

    # write hint
    hint = dict(url = urls['wordpress'], project=project)
    hintfile = os.path.join(unpacked, '.hashget-hint.json')
    with open(hintfile, 'w') as outfile:
        json.dump(hint, outfile)

    hashget.operations.pack(
        hashdb=hashdb,
        root=unpacked,
        file=hgfile,
        zip=True,
        exclude=None,
        skip=None,
        anchors=None,
        heuristics=None,
        pool=pool,
        pull=False)

    hgsz = os.stat(hgfile).st_size
    ratio = hgsz * 100.0 / dusz
    assert(ratio < 1)
    print("Compressed {} to {} {:.2f}%".format(kmgt(dusz), kmgt(hgsz), ratio))


    results.append(dict(
        url=urls['wordpress'],
        unpacked=dusz,
        packed=hgsz
    ))

def test_kernel(tmpdir):
    unpacked = os.path.join(tmpdir, 'unpacked')
    hgfile = os.path.join(tmpdir,'test_compress.tar.gz')


    if hp_kernel:
        print("use hp_kernel")
        hashdb.submit_save(hp_kernel, project=project)

    os.mkdir(unpacked)

    dstfile = _download(urls['kernel'], tmpdir)

    print("unpack")
    cp = subprocess.run(['tar', '-xf', dstfile, '-C', unpacked])
    assert cp.returncode == 0
    dusz = du(unpacked)

    print("pack")
    hashget.operations.pack(
        hashdb=hashdb,
        root=unpacked,
        file=hgfile,
        zip=True,
        exclude=None,
        skip=None,
        anchors=None,
        heuristics=None,
        pool=pool,
        pull=False,
        project=project)

    hgsz = os.stat(hgfile).st_size
    ratio = hgsz * 100.0 / dusz
    print("Compressed {} to {} {:.2f}%".format(kmgt(dusz), kmgt(hgsz), ratio))
    assert(ratio < 1)


    results.append(dict(
        url=urls['kernel'],
        unpacked=dusz,
        packed=hgsz
    ))

