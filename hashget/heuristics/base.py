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

        for cls in BaseHeuristic.__subclasses__():
            if 'all' in heuristics or cls.codename in heuristics:
                self._heuristics.append(cls())

    def process(self, path):
        r = list()
        for cls in self._heuristics:
            r.extend(cls.check(path))
        return r
