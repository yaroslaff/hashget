import importlib
import pkgutil
import logging
import hashget.heuristics

log = logging.getLogger('hashget')

class SubmitRequest():
    def __init__(self, url, project):
        self.url = url
        self.project = project

class BaseHeuristic():

    def __init__(self):
        pass

    def check(self, path):
        raise NotImplementedError

class HeuristicSet():

    def __init__(self, heuristics):

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
                    self._heuristics.append(cls())


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
