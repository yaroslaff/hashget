import re


class AnchorList(object):
    """
    Class for filtering anchors
    """
    def __init__(self, minsz=102400):
        self.minsz = minsz
        self.re_list = list()
        self.re = None
        self.anchorlist = list()

    def add_fanchor(self, regex):
        """"
            add forced anchor regex
        """
        self.re_list.append(regex)
        self.__make_re()

    def is_anchor(self, f):
        if self.minsz is not None and f.size > self.minsz:
            return True

        if self.re and self.re.match(f.relpath()):
            return True

        return False

    def __make_re(self):
        regex = '|'.join(self.re_list)
        self.re = re.compile(regex)

    def check_append(self, f):
        """"
            check file and append it to anchors
        """
        if self.is_anchor(f):
            self.anchorlist.append(f)

    def clean_list(self):
        self.anchorlist = list()

    def __repr__(self):
        return 'AnchorList(minsz: {} {} re, {} anchors)'.format(self.minsz, len(self.re_list), len(self.anchorlist))
