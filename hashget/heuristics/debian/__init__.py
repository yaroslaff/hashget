import logging

from hashget.heuristic_base import BaseHeuristic, SubmitRequest
from hashget.debian import DebStatus

log = logging.getLogger('hashget')

def deb_index(hashdb, path, anchors, filesz=10000, sleep=1):
    cnt_total = 0
    cnt_pulled = 0
    cnt_local = 0
    cnt_new = 0

    started = time.time()

    # ensure debsnap project exists
    hashdb.create_project('debsnap')

    debstatus = DebStatus(path)
    np = debstatus.n_installed
    print("Total: {} packages".format(np))

    for p in debstatus.packages_iter():

        cnt_total += 1

        if hashdb.sig_present('deb', p.signature, remote=False):
            log.debug('[{}/{}] local {}'.format(cnt_total, np, p.signature))
            cnt_local += 1
            continue

        if hashdb.pull_sig('deb', p.signature):
            log.info('[{}/{}] pulled {} from hashserver'.format(cnt_total, np, p.signature))
            cnt_pulled += 1
            continue

        url = p.url
        if url is None:
            log.warning('[{}/{}] FAILED to index {}'.format(cnt_total, np, p.signature))
            continue

        log.info("[{}/{}] index {}".format(cnt_total, np, p.url))

        anchors.clean_list()

        signatures = {
            'deb': p.signature
        }

        submit_url(
            url=p.url,
            hashdb=hashdb,
            project='debsnap',
            anchors=anchors,
            filesz=filesz,
            signatures=signatures)

        cnt_new += 1
        log.debug("sleep {}s".format(sleep))
        time.sleep(sleep)

    print("Indexing done in {:.2f}s. {} local + {} pulled + {} new = {} total.".format(
        time.time() - started, cnt_local, cnt_pulled, cnt_new, cnt_total))


class DebianStatusHeuristic(BaseHeuristic):
    codename = 'debian'

    def __init__(self, hashdb=None):
        super().__init__(hashdb=hashdb)
        self.project = 'debsnap'
        self.statusfile = '/var/lib/dpkg/status'
        self.sflen = len(self.statusfile)

    def check(self, path):
        if not path.endswith(self.statusfile):
            return list()

        srlist = list()

        root = path[:-self.sflen]

        log.debug('processing packages from Debian root fs {}'.format(root))

        debstatus = DebStatus(path)
        np = debstatus.n_installed
        log.debug("Total: {} dpkg packages".format(np))

        for p in debstatus.packages_iter():
            sr = SubmitRequest(
                hashdb=self.hashdb,
                urlmethod=p.get_url,
                signatures=dict(deb = p.signature),
                project=self.project)
            srlist.append(sr)
        return srlist


heuristics = [ DebianStatusHeuristic ]
