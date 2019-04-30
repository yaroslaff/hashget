import pytest

import hashget
import hashget.hashdb
import hashget.filepool
import hashget.operations
import settings
import os
import shutil
import subprocess

project='_test'

hashdb = None
standard_hp = None

def setup_module(module):
    global hashdb, hdb
    global standard_hp
    hashdb = hashget.hashdb.HashDBClient(enabled_hashdb=[project])
    try:
        hashdb.remove_project(project)
    except KeyError:
        pass

    hdb = hashdb.create_project(project)

    standard_hp = hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=None,
        project=project,
        anchors=None,
        signatures=None,
        filesz=None,
        pool=None)

def teardown_module(module):
    global hashdb

    try:
        hashdb.remove_project(project)
    except KeyError:
        pass

def test_submit_package_url():
    """
    Submit remote package by URL, check hashspec, few files and anchors

    :return:
    """

    # Data to compare
    package_sums = [
        'sha256:bce7f40aa8561a2c614790a31f300122909d8fcac97549f6a9460f3407458e96',
        'md5:ad6d229c6e485d084c77348d008f0612' ]


    few_anchors = [
        'sha256:41457503e8b355253802625dc0a3336692643b6b7e7f6f53e8993ac2e59bd2e0',
        'sha256:80b2930a9d6a710b2f57e89e09eab2fb472e3fb516601c93128cb82c6573b962',
        'sha256:a87edc16f0f70a29a6eae0e33ec137cab261dd0e5af605f51e2dbc53f1002d99'
    ]

    few_files = [
        'sha256:24cb93285776c895bf5e12b68bd2b500c997d27a2b46332e32ff73409cf7c845',
        'sha256:7704525ae61a1d72ab05a5178172b7abdf5649c3d33f259f1d1161c1335f5b91',
        'sha256:a160edffb3a714d09c5e6dce9ed6b514161859755ccd103ca0feb9cfc80172a8'
    ]

    n_anchors = 68
    n_files = 1366  # 1366 unique, 1373 with duplicates
    filesz=1024

    hdb.truncate()

    #
    # Check it's not exists (we re-created db)
    #
    try:
        hp = hashdb.sig2hp('url', settings.package['url'])
    except KeyError:
        pass
    else:
        assert hp is None, "Package exists in empty HashDB"

    #
    # Submit remote package
    #

    hp = hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=None,
        project=project,
        anchors=None,
        signatures=None,
        filesz=filesz,
        pool=None)

    #
    # Just query it, should throw no exception now
    #
    hashdb.sig2hp('url', settings.package['url'])

    #
    # Get it (as dict)
    #

    hp = hdb.hp1()
    d = hp.dict()

    #
    # check anchors, files
    #

    for hashspec in package_sums:
        assert(hashspec in d['hashes'])

    assert d['signatures']['url'] == settings.package['url'], "URL not same"

    for hashspec in few_anchors:
        assert hashspec in d['anchors'], "anchor {} not found in HP".format(hashspec)

    for hashspec in few_files:
        assert hashspec in d['files'], "file {} not found in HP".format(hashspec)


    assert len(d['files']) == n_files, "Incorrect number of files"
    assert len(d['anchors']) == n_anchors, "Incorrect number of anchors"

    #
    # delete this package
    #
    hp = hashdb.hp1(project=project)
    assert hp is not None, "HP not found in project hashdb"

    hp.delete()
    assert len(list(hashdb.hplist(project=project))) == 0, "HashDB is not empty after deletion"

    hdb.self_check()
    # hdb.dump()


def test_double_submit():
    hdb = hashdb.hashdb[project]

    hdb.self_check()
    # hdb.dump()

    hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=None,
        project=project,
        anchors=None,
        signatures=None,
        filesz=None,
        pool=None)

    hdb.self_check()
    # hdb.dump()

    hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=None,
        project=project,
        anchors=None,
        signatures=None,
        filesz=None,
        pool=None)

    hdb.self_check()
    # hdb.dump()

def test_pool(tmpdir):
    pool = hashget.filepool.DirFilePool(path=tmpdir)
    hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=None,
        project=project,
        anchors=None,
        signatures=None,
        filesz=None,
        pool=pool)

    assert(pool.new == 1)
    assert(pool.loaded == 1)
    assert(pool.requested == 0)
    oldstats = dict(hashget.cacheget.CacheGet.stats)
    # hashget.cacheget.CacheGet.stats['missed_files'] += 1

    pool.get('sha256:' + settings.package['sha256'])
    assert(pool.new == 1)
    assert(pool.loaded == 1)
    assert(pool.requested == 1)
    assert(oldstats == hashget.cacheget.CacheGet.stats)


def test_package():
    p = hashget.package.Package( url = settings.package['url'] )
    p.download()
    p.unpack()
    p.cleanup()
    pass

def test_compress_decompress(tmpdir):

    hdb.truncate()
    hashdb.submit_save(standard_hp, project)

    cg = hashget.cacheget.CacheGet()
    r =  cg.get(settings.package['url'])
    hgfile = os.path.join(tmpdir,'test_compress.tar.gz')
    dstfile = os.path.join(tmpdir, os.path.basename(r['file']))
    unpackdir = os.path.join(tmpdir, 'unpacked')
    pooldir = os.path.join(tmpdir, 'pool')

    os.mkdir(unpackdir)
    os.mkdir(pooldir)
    pool = hashget.filepool.DirFilePool(path=pooldir)

    shutil.copyfile(r['file'], dstfile)
    # pool.append(r['file'])

    subprocess.run(['unzip', '-q', dstfile,'-d', tmpdir])

    #
    # test packing with high filesz
    #
    hashget.operations.pack(
        hashdb=hashdb,
        root=os.path.join(tmpdir, settings.package['subdir']),
        file=hgfile,
        zip=True,
        exclude=None,
        skip=None,
        anchors=None,
        filesz=10*1024, # filesz 10k
        heuristics=None,
        pool=None,
        pull=False)

    hgf = hashget.file.File(hgfile)
    assert(hgf.size > settings.package['hgtar_10k_minsize']  and hgf.size < settings.package['hgtar_10k_maxsize'])

    #
    # packing with default filesz
    #

    hashget.operations.pack(
        hashdb=hashdb,
        root=os.path.join(tmpdir, settings.package['subdir']),
        file=hgfile,
        zip=True,
        exclude=None,
        skip=None,
        anchors=None,
        filesz=None, # filesz default
        heuristics=None,
        pool=None,
        pull=False)

    hgf = hashget.file.File(hgfile)
    assert(hgf.size < settings.package['hgtar_maxsize'])


    #
    # decompress
    #
    subprocess.run(['tar','-x','-C',unpackdir,'-f', hgfile])

    # postunpack

    cgstats1 = dict(hashget.cacheget.CacheGet.stats)

    # unpack with empty pool to populate it
    recovered = hashget.operations.postunpack(root=unpackdir, usermode=True, recursive=False, pool=pool)
    assert(recovered == settings.package['hgtar_recovered'])


    cgstats2 = dict(hashget.cacheget.CacheGet.stats)

    # assert: CacheGet stats are different, new requests happened during postunpacking
    assert(cgstats1 != cgstats2)

    ds = hashget.utils.dir_size(unpackdir)
    assert(ds > settings.package['unpacked_minsize'])


    # postunpack 2nd time, now with filled pool
    old_pool_requested = pool.requested
    recovered =  hashget.operations.postunpack(root=unpackdir, usermode=True, recursive=False, pool=pool)
    assert(recovered == settings.package['hgtar_recovered'])

    cgstats3 = dict(hashget.cacheget.CacheGet.stats)

    # assert: CacheGet stats are same, no new cacheget requests
    assert(cgstats3 == cgstats2)
    assert(pool.requested > old_pool_requested)


#

# deb indexing, other plugins
# pulling
#