import logging

from hashget.heuristic_base import BaseHeuristic, SubmitRequest
from hashget.debian import DebStatus

log = logging.getLogger('hashget')

project = 'debsnap'

class DebianStatusHeuristic(BaseHeuristic):
    codename = 'debian'

    def __init__(self, hashdb=None):
        super().__init__(hashdb=hashdb)

        self.project = project
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
                project=self.project,
                pkgtype='debsnap')
            srlist.append(sr)
        return srlist


heuristics = [ DebianStatusHeuristic ]
