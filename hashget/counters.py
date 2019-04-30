class Counters():
    def __init__(self, counters=None):
        counters = counters or list()
        self._counters = list()
        for cnt in counters:
            self._counters.append(cnt)
            setattr(self, cnt, 0)

    def inc(self, name, increment=1):
      v = getattr(self, name, 0)
      setattr(self, name, v+increment)
      return v

    def dict(self):
        d = dict()
        for cnt in self._counters:
            d[cnt] = getattr(self, cnt)

    def __repr__(self):
        s = ""
        for cnt in self._counters:
            if s:
                s += " "
            s += "{}={}".format(cnt, getattr(self, cnt))
        return s