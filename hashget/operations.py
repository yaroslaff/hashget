import os
import sys
import time
import logging
import tempfile
import subprocess

import hashget
import hashget.restorefile
import hashget.globlist
from hashget.singlelist import SingleList
from hashget.heuristic_base import HeuristicSet, SubmitRequest
from hashget.utils import kmgt
from hashget.counters import Counters
from hashget.exceptions import BrokenPackage, DownloadFailure

log = logging.getLogger('hashget')


def index(hashdb, root, anchors = None, filesz=None, heuristics=None, pool=None, pull=False, project=None):

    if heuristics is None:
        heuristics = list(['all'])

    filesz = filesz or 10*1024
    SubmitRequest.filesz = filesz



    anchors = anchors or hashget.anchor.AnchorList()

    heur = HeuristicSet(hashdb=hashdb, heuristics=heuristics)

    c = Counters(['total', 'local', 'pulled','new','skipped', 'failed'])

    started = time.time()

    for dir, subdirs, files in os.walk(root):
        for basename in files:
            filename = os.path.join(dir, basename)

            if os.path.islink(filename) or not os.path.isfile(filename):
                continue

            f = hashget.file.File(filename)
            anchors.check_append(f)

            srlist = heur.process(filename)

            for sr in srlist:

                c.inc('total')

                if sr.sig_present():
                    log.debug("local {}".format(sr.first_sig()[1]))
                    c.inc('local')
                    continue

                if sr.pull_sig():
                    log.info("pulled {}".format(sr.first_sig()[1]))
                    c.inc('pulled')
                    continue

                if sr.url:
                    log.info("submitting {}".format(sr.url))                    
                    try:
                        sr.submit(pool=pool, project=project)
                    except (DownloadFailure, BrokenPackage) as e:
                        c.inc('failed')
                        log.error("ERROR processing URL {}".format(sr.url))
                    else:
                        c.inc('new')
                else:
                    log.info("skipped {}".format(sr.first_sig()[1]))
                    c.inc('skipped')

    if pull:
        log.debug('Try pulling {} anchors'.format(len(anchors)))
        for a in anchors.anchorlist:
            pullanchor = hashdb.pull_anchor(a.get_hashspec())
            log.debug('pull anchor for {} {}: {}'.format(a.filename,
                                                         kmgt(a.size), pullanchor))

    log.info('Indexing done in {:.2f}s. {} local + {} pulled + {} new + {} skipped + {} failed = {} total packages'.format(
        time.time() - started,
        c.local, c.pulled, c.new, c.skipped, c.failed, c.total))
    print(c)
    return c


def prepare_readfiles(root, anchors, filesz=None, skip=None):
    total = 0
    files = list()
    skip = skip or list()
    filesz = filesz or 1024
    anchors = anchors or hashget.anchor.AnchorList()

    for directory, subdirs, dirfiles in os.walk(root):

        # if skipdir(directory, skipdirs):
        #    continue

        for basename in dirfiles:
            total += 1
            path = os.path.join(directory, basename)

            if path in skip:
                log.debug("SKIP {}".format(path))
                continue

            if os.path.islink(path) or not os.path.isfile(path):
                continue

            f = hashget.file.File(path, root=root)
            if f.size > filesz:
                files.append(f)
            anchors.check_append(f)

    return files


#
# Prepare
#

def prepare(root, hashdb, excludefile=None, anchors=None, filesz=None, skip=None, restorefile=None, expires=None):
    """
        ANCHORS ??? do we need it here? maybe delete?
    """

    restorefile = restorefile or os.path.join(root, '.hashget-restore.json')
    excludefile = excludefile or '/dev/null'

    files = prepare_readfiles(root, anchors, filesz, skip)

    rfile = hashget.restorefile.RestoreFile()
    if expires:
        rfile.set_field('expires', expires.strftime('%Y-%m-%d'))

    sl = SingleList()
    hpd = dict()

    with open(excludefile, 'wb') as excf:
        for f in files:
            """
                save url and package hashes, then write to restore-file
                write file info to restore-file
            """
            hplist = hashdb.hash2hp(f.hashspec, remote=False, expires=expires)
            if not hplist:
                continue

            sl.add([hp.hashspec for hp in hplist])

            for hp in hplist:
                hpd[hp.hashspec] = hp


            relpath = os.path.relpath(f.filename, root)
            line = os.fsencode(u"./{}\n".format(os.path.relpath(f.filename, root)))
            #excf.write(line)
            excf.write(os.fsencode("./{}\n".format(os.path.relpath(f.filename, root))))
            rfile.add_file(f)

        for hashspec in sl.optimized():
            hp = hpd[hashspec]
            rfile.add_package(hp.url, hashspec=hashspec, size = hp.attrs.get('size', None))

        rfile.save(restorefile)

    return rfile

#
# PostUnpack
#
def postunpack(root, usermode=False, recursive=False, pool=None):
    """
        Restore files after untarring
    """

    if os.getuid() and not usermode:
        log.warning('Running as UID {} (non-root) witout --user, forcing --user flag'.format(os.getuid()))
        usermode = True

    rfile = hashget.restorefile.RestoreFile(os.path.join(root, '.hashget-restore.json'))
    if rfile.expired():
        log.warning('WARNING: Restoring from expired ({}) archive.'.format(rfile.get_field('expires')))

    rfile.preiteration()

    stat_files = 0
    stat_downloaded = 0
    stat_recovered = 0
    stat_cached = 0
    stat_cached_pool = 0
    started = time.time()

    local_package_file = None

    log.debug('downloading/unpacking packages...')

    npackages = 0

    if sys.getfilesystemencoding() != 'utf-8':
        log.warning('WARNING: non unicode locale used, may fail to restore files with unicode in names')

    for pdata in rfile.packages_iter():

        npackages += 1
        if pool is not None:
            local_package_file = pool.get(pdata['hash'], name=pdata['url'], default=None)

        #
        # delete tmp from pool file? basename for file?
        #

        if local_package_file:
            log.debug('[{}/{}] restore from file {}'.format(npackages, rfile.npackages, local_package_file))
            from_pool = True
            p = hashget.package.Package(path=local_package_file)
            stat_cached_pool += os.stat(local_package_file).st_size
        else:
            from_pool = False
            log.debug('[{}/{}] restore from URL {}'.format(npackages, rfile.npackages, pdata['url']))
            p = hashget.package.Package(url=pdata['url'])

        p.recursive = recursive
        p.download()
        if pool is not None and from_pool == False:
            pool.append(p.path)
        p.unpack()
        p.read_files()

        for pf in p.all_files():

            hashspec = pf.get_hashspec()

            if rfile.should_process(hashspec):
                for rf in rfile.fbyhash(hashspec):
                    log.debug('recovered {}: {}'.format(p.basename, rf.relpath()))
                    try:
                        rf.recover(pf.filename, usermode=usermode)
                    except UnicodeEncodeError:
                        log.error('Error! Attempt to restore files with unicode names while using non-Unicode locale: '
                                  '(getfilesystemencoding()=="{}"). set any unicode locale (ru_RU.UTF-8 , en_US.UTF-8 etc.). '
                                  'e.g. LC_ALL=en_US.UTF-8 {}'.format(
                            sys.getfilesystemencoding(), ' '.join(sys.argv)))
                        return

                    rfile.set_processed(hashspec)
                    stat_recovered += rf.size
                    stat_files += 1

        stat_cached += p.stat_cached
        stat_downloaded += p.stat_downloaded
        p.cleanup()

    if pool is not None:
        pool.cleanup()

    print('Recovered {}/{} files {} bytes ({} downloaded, {} from pool, {} cached) in {:.2f}s'.format(
        stat_files, rfile.nfiles,
        hashget.utils.kmgt(stat_recovered),
        hashget.utils.kmgt(stat_downloaded),
        hashget.utils.kmgt(stat_cached_pool),
        hashget.utils.kmgt(stat_cached),
        time.time() - started
    ))

    stat_files -= 1

    rfile.check_processed()

    return stat_recovered

def pack(hashdb, root, file=None, zip=False, exclude=None, skip=None, anchors=None, filesz=None, heuristics=None,
         pool=None, pull=False, project=None, expires=None):

    # defaults
    exclude = exclude or list()
    skip = skip or list()
    filesz = filesz or 1024
    heuristics = heuristics or ['all']
    anchors = anchors or hashget.anchor.AnchorList()

    nsteps = 3
    step = 1

    if not file:
        log.error('Need -f argument for --pack')
        exit(1)

    # fix args exclude
    excludelist = list()
    for epath in exclude:
        if epath.endswith('/'):
            excludelist.append(epath + '*')
            log.warning('fixed --exclude {} to {}'.format(epath, epath + '*'))
        else:
            excludelist.append(epath)

    gl = hashget.globlist.GlobList(root=root)
    for skip in skip + exclude:
        gl.add_relpath(skip)

    #
    # STEP 1
    #

    log.info("STEP {}/{} Indexing...".format(step, nsteps))
    index(hashdb=hashdb, root=root, anchors=anchors, filesz=filesz, heuristics=heuristics, pool=pool, pull=pull, project=project)
    step += 1

    log.info('STEP {}/{} prepare exclude list for packing...'.format(step, nsteps))

    tmpdir = tempfile.mkdtemp(prefix='hashget-pack-')
    excludefile = os.path.join(tmpdir, '.hashget-exclude')
    restorefile = os.path.join(tmpdir, '.hashget-restore.json')

    r = prepare(root,
            hashdb=hashdb,
            anchors=anchors,
            filesz=filesz,
            skip=gl,
            excludefile=excludefile,
            restorefile=restorefile,
            expires=expires
            )

    print("Saved:", r)

    step += 1

    log.info('STEP {}/{} tarring...'.format(step, nsteps))

    cmd = ['tar', '-c']

    if zip:
        cmd.append('-z')

    if file:
        cmd.extend(['-f', file])

    cmd.extend(['-X', excludefile])
    for exc_path in excludelist:
        cmd.extend(['--exclude', exc_path])

    cmd.extend(['-C', root, '.'])
    cmd.extend(['-C', tmpdir, '.hashget-restore.json'])

    log.debug('Run: {}'.format(cmd))

    subprocess.run(cmd)

    # clean up
    os.unlink(excludefile)
    os.unlink(restorefile)
    os.rmdir(tmpdir)

    if file:
        statinfo = os.stat(file)
        log.info('{} ({}) packed into {} ({})'.format(root, hashget.utils.kmgt(hashget.utils.du(root)), file,
                                                      hashget.utils.kmgt(statinfo.st_size)))

def info(rfilepath, root=None, subcommand='info', pool=None):

    rfile = hashget.restorefile.RestoreFile(os.path.join(root, '.hashget-restore.json'))

    np_total = 0
    np_down = 0
    np_pool =0

    pool_bytes = 0

    if subcommand == 'info':

        if rfile.expired():
            log.warning('WARNING: Restoring from expired ({}) archive.'.format(rfile.get_field('expires')))

        for pdata in rfile.packages_iter():
            np_total += 1
            poolfile = pool.get(pdata['hash'], name=pdata['url'], default=None)
            if poolfile:
                np_pool += 1
                pool_bytes += os.stat(poolfile).st_size
            else:
                np_down += 1

        print("Total: {} packages ({})\n"
              "In pool: {} packages ({})\n"
              "Download: {} packages\n".format(
            np_total, kmgt(rfile.package_size),
            np_pool, kmgt(pool_bytes),
            np_down))

    elif subcommand == 'list':
        for pdata in rfile.packages_iter():
            np_total += 1
            if not pool.get(pdata['hash'], name=pdata['url'], default=None):
                print(pdata['url'])

