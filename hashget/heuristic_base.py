import importlib
import pkgutil
import logging
import os
import hashget.heuristics

log = logging.getLogger('hashget')

heuristics_path = list()

class SubmitRequest():

    filesz = None

    def __init__(self, hashdb=None, url=None, urlmethod=None, signatures=None, project=None, pkgtype=None):
        self.hashdb = hashdb
        self._url = url
        self._urlmethod = urlmethod
        self.signatures = signatures or dict()
        self.project = project or '_submitted'
        self.pkgtype = pkgtype


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

    def submit(self, pool=None, project=None):
        """
        project can be used to override self.project

        :param pool:
        :param project:
        :return:
        """
        project = project or self.project

        if self.url is None:
            log.debug('Do not submit {} beause empty URL'.format(self))
            return

        hashget.submiturl.submit_url(
            hashdb=self.hashdb,
            url=self.url,
            project=project,
            signatures=self.signatures,
            pool=pool,
            pkgtype=self.pkgtype,
            filesz=self.filesz
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

        #self.plugins += {
        #    name: importlib.import_module(name)
        #    for finder, name, ispkg
        #    in pkgutil.iter_modules(heuristics_path, 'hashget.heuristics.')
        #}

        for nt in pkgutil.iter_modules(heuristics_path):
            mpath = os.path.join(nt.module_finder.path, nt.name, '__init__.py')
            mname = 'hashget.heuristics.' + nt.name

            if mname in self.plugins:
                log.debug("skip already loaded {}".format(mname))
            else:
                spec = importlib.util.spec_from_file_location(mname, mpath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                log.debug("loading special plugin: {}".format(module))
                self.plugins[mname] = module

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
