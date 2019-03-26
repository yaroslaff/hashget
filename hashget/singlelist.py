class SingleList():
    def __init__(self):
        self.__list = list()
        self.__weights = dict()

    def add(self, items):
        self.__list.append(items)

        for item in items:
            if not item in self.__weights:
                self.__weights[item] = 1
            else:
                self.__weights[item] += 1


    def heaviest(self, items):
        i = items[0]
        w = self.__weights[i]

        for item in items[1:]:
            if self.__weights[item] > w:
                i = item
                w = self.__weights[i]
        return(i)


    def optimized(self):
        r = list()
        for idx, items in enumerate(sorted(self.__list, key=lambda x: len(x))):
            # print("items: {} r: {}".format(items, r))

            if any(item in r for item in items):
                # at least one element already in r
                continue

            i = self.heaviest(items)
            r.append(i)
        return(r)

if __name__ == '__main__':
    sl = SingleList()
    sl.add(['a']) # a: w1
    sl.add(['b','c']) # b: w2, c:w1
    sl.add(['b','d']) # b: w2, z:w1
    sl.add(['d']) # b: w2, z:w1

    print(sl.optimized())
