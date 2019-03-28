import re
import os
import json

from .base import BaseHeuristic, SubmitRequest


class HintHeuristic(BaseHeuristic):
    codename = 'hint'

    def __init__(self):
        super().__init__()
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
            sr = SubmitRequest(url=hint['url'], project=project)
            return [sr]

        return list()
