import os
import glob

class GlobList():

    def __init__(self, root=None):
        self.root = root or '/'
        self.path = list()
        self.root_files = list()
        self.root_dirs = list()

    def add_relpath(self, globpath):
        self.path.append(globpath)

        for p in glob.glob(os.path.join(self.root, globpath)):
            if os.path.isdir(p):
                self.root_dirs.append(p)
            else:
                self.root_files.append(p)


    #
    # matching
    #


    def match(self, path):

        if path in self.root_files:
            return True

        for dir in self.root_dirs:
            if not os.path.relpath(path, dir).startswith(os.pardir):
                return True

        return False

    def __contains__(self, item):
        return self.match(item)

    def match_relpath(self, path):
        return self.match(os.path.join(self.root, path))



if __name__ == '__main__':
    gl = GlobList('/')
    gl.add_relpath('/tmp')
    gl.add_relpath('/tmp/z')

    print(gl.match('/tmp'))
    print(gl.match('/tmp/z'))
    print(gl.match('/tmp/test/dir1/file1'))
