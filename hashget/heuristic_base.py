import importlib
import pkgutil
import logging
import hashget.heuristics

log = logging.getLogger('hashget')

class SubmitRequest():
    def __init__(self, hashdb=None, url=None, urlmethod=None, signatures=None, project=None):
        self.hashdb = hashdb
        self._url = url
        self._urlmethod = urlmethod
        self.signatures = signatures or dict()
        self.project = project or '_submitted'


    def first_sig(self):
        """
        return any sig tuple (but not url if possible)
        :return:
        """

        sigkeys = list(self.signatures.keys())
        try:
            sigkeys.remove('url')
        except ValueError:
            pass

        if sigkeys:
            return (sigkeys[0], self.signatures[sigkeys[0]])
        else:
            return ('url', self.url)

    def sig_present(self, remote=False):
        if self.signatures:
            # if signatures, check signatures, not url
            for sigtype, signature in self.signatures.items():
                if self.hashdb.sig_present(sigtype, signature, remote=remote):
                    return True
        else:
            # process 'url' signature if missing in signatures
            if not 'url' in self.signatures:
                return self.hashdb.sig_present('url', self.url)

        return False

    def submit(self):
        hashget.submiturl.submit_url(
            hashdb=self.hashdb,
            url=self.url,
            project=self.project,
            signatures = self.signatures,
            )

    def pull_sig(self):
        sigtype, signature = self.first_sig()
        return self.hashdb.pull_sig(sigtype, signature)

    def __repr__(self):
        return "SR {} {}".format(self._url, self.signatures)

    @property
    def url(self):
        if self._url:
            return self._url

        if self._urlmethod:
            return self._urlmethod()

class BaseHeuristic():

    def __init__(self, hashdb=None):
        self.hashdb = hashdb
        pass

    def check(self, path):
        raise NotImplementedError

class HeuristicSet():

    def __init__(self, hashdb, heuristics):

        self._heuristics = list()

        self.plugins = {
            name: importlib.import_module(name)
            for finder, name, ispkg
            in iter_namespace(hashget.heuristics)
        }

        for name, mod in self.plugins.items():
            for cls in mod.heuristics:
                if 'all' in heuristics or cls.codename in heuristics:
                    log.debug("import heuristic {} from {}".format(cls.codename, name))
                    self._heuristics.append(cls(hashdb=hashdb))

    def process(self, path):
        r = list()
        for cls in self._heuristics:
            r.extend(cls.check(path))
        return r


def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")
