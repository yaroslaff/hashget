import os
import json

from hashget.heuristic_base import BaseHeuristic, SubmitRequest

class HintHeuristic(BaseHeuristic):
    codename = 'hint'

    def __init__(self, hashdb=None):
        super().__init__(hashdb=hashdb)
        self.basenames = ['hashget-hint.json', '.hashget-hint.json']
        self.def_project = '_hints'

    def check(self, path):
        basename = os.path.basename(path)
        dirname = os.path.dirname(path)

        if basename not in self.basenames:
            return list()

        with open(path) as f:
            hint = json.load(f)

        project = hint.get('project', self.def_project)

        if 'url' in hint:
            sr = SubmitRequest(hashdb=self.hashdb, url=hint['url'], project=project)
            return [sr]

        return list()


heuristics = [ HintHeuristic ]
