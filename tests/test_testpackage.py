import tempfile
import os
import shutil
import subprocess
import sys
import datetime

import hashget
import hashget.hashdb
import hashget.operations
import hashget.cacheget
import hashget.heuristics.debian
import hashget.filepool

import settings
import logging

"""
all tests in this module uses pre-populated hashdb _test with settings.testpackage
"""

hashdb = None

myloglevel = logging.INFO

project = '_test'
debproject = '_test_debsnap'

test_projects = [project, debproject]

tmpdir = None
pkgdir = None
unpacked = None
pkgfile = None

hashdb = None

log = None

statusfile_text = """\
Package: sed
Status: install ok installed
Section: utils
Architecture: amd64
Version: 4.4-1

Package: vim
Status: install ok installed
Section: editors
Architecture: amd64
Version: 2:8.0.0197-4+deb9u1

"""

standard_hp = None
pool = None
tmptmp = None

mytmpdir = None

def setup_module(module):
    global hashdb, hdb, log
    global tmpdir, pkgdir, unpacked, pkgfile
    global standard_hp, pool
    global tmptmp, mytmpdir

    # prepare logging
    log = logging.getLogger('hashget')
    log.setLevel(myloglevel)
    logstdout = logging.StreamHandler(stream=sys.stderr)
    logstdout.setFormatter(logging.Formatter('%(message)s', '%Y-%m-%d %H:%M:%S'))
    log.addHandler(logstdout)

    # prepare filesystem
    tmpdir = tempfile.mkdtemp(prefix='hashget-test-')
    print("tmpdir:", tmpdir)
    mytmpdir = tmpdir

    tmptmp = os.path.join(tmpdir,'tmp')
    os.mkdir(tmptmp)

    pooldir = os.path.join(tmpdir,'pool')
    os.mkdir(pooldir)
    pool = hashget.filepool.DirFilePool(pooldir)

    pkgdir = os.path.join(tmpdir,'pkg')
    unpacked = os.path.join(tmpdir,'unpacked')
    os.mkdir(pkgdir)
    os.mkdir(unpacked)

    cg = hashget.cacheget.CacheGet()
    r = cg.get(settings.package['url'])
    pkgfile = os.path.join(pkgdir, os.path.basename(r['file']))
    shutil.copyfile(r['file'], pkgfile)

    if settings.package['format'] == 'zip':
        cmd = ['/usr/bin/unzip', '-q', pkgfile, '-d', unpacked]
        cp = subprocess.run(cmd)
        assert cp.returncode == 0, "Unzip failed"

    # submit first package
    hashdb = hashget.hashdb.HashDBClient(enabled_hashdb=test_projects)
    hashdb.ensure_project(debproject, 'debsnap')
    standard_hp = hashget.submiturl.submit_url(
        hashdb=hashdb,
        url=settings.package['url'],
        file=pkgfile,
        project=project,
        anchors=None,
        signatures=None,
        filesz=None,
        pool=None)

    _prepare()


def _prepare(hp=None):
    """
    truncate all test projects and submit standard_hp to project

    :return:
    """
    global hashdb, hdb
    hp = hp or standard_hp

    hdb = hashdb[debproject]
    hdb.truncate()

    hdb = hashdb[project]
    hdb.truncate()

    hashdb.submit_save(hp, project)

    pool.truncate()


def teardown_module(module):

    hashdb = hashget.hashdb.HashDBClient()

    for p in [project, debproject]:
        try:
            hashdb.remove_project(p)
        except KeyError:
            pass

    shutil.rmtree(mytmpdir)

#
# utility functions
#

def populate(path):
    shutil.copytree(unpacked, path)

#
# tests
#
def test_index_empty(tmpdir):
    print(tmpdir)
    hashget.operations.index(hashdb=hashdb, root=tmpdir)

def test_index_nonempty(tmpdir):

    _prepare()

    workdir = os.path.join(tmpdir,'x')
    print(workdir)
    populate(workdir)
    stat = hashget.operations.index(hashdb=hashdb, root=workdir)
    assert stat.total == stat.local == stat.pulled == stat.new == 0, "Something was indexed in 'empty' package file"

def test_index_debpackage(tmpdir, vmroot):

    _prepare()

    hashget.heuristics.debian.project = debproject

    if vmroot:
        rootdir = vmroot
    else:
        statusfile = os.path.join(tmpdir, 'var/lib/dpkg/status')
        os.makedirs(os.path.dirname(statusfile))
        with open(statusfile, "w") as f:
            f.write(statusfile_text)

        rootdir = tmpdir

    stat = hashget.operations.index(hashdb=hashdb, root=rootdir)
    assert stat.new >= 2
    old_total = stat.total
    print(stat)

    #
    # restart with populated hashdb
    #
    stat = hashget.operations.index(hashdb=hashdb, root=rootdir)
    assert stat.local == old_total

def test_index_pool(tmpdir, vmroot):
    _prepare()

    if vmroot:
        rootdir = vmroot
    else:
        statusfile = os.path.join(tmpdir, 'var/lib/dpkg/status')
        os.makedirs(os.path.dirname(statusfile))
        with open(statusfile, "w") as f:
            f.write(statusfile_text)

        rootdir = tmpdir

    assert len(pool) == 0
    hashget.operations.index(hashdb=hashdb, root=rootdir, pool=pool)
    assert len(pool) > 0

def test_expiration(tmpdir):
    hp = standard_hp.clone()
    hp.expires = datetime.datetime.today() + datetime.timedelta(1) # HP expires tomorrow
    _prepare(hp=hp)
    workdir = os.path.join(tmpdir,"x")
    # os.mkdir(workdir)

    populate(workdir)

    # archive expires today, HP expires tomorrow, HP should be used
    r = hashget.operations.prepare(hashdb=hashdb, root=tmpdir, anchors=None,
                                   expires=datetime.datetime.today())
    assert r.sumsize >= 0, "HP was not used"

    # archive expires 2 days ahead, HP expires and should not be used
    r = hashget.operations.prepare(hashdb=hashdb, root=tmpdir, anchors=None,
                                   expires=datetime.datetime.today() + datetime.timedelta(2))
    assert r.sumsize == 0, "Expired HP used for expiration archive"

    # archive expires 2 days ahead. HP expires and should not be used
    r = hashget.operations.prepare(hashdb=hashdb, root=tmpdir, anchors=None)
    assert r.sumsize == 0, "Expired HP used for never expired archive"


