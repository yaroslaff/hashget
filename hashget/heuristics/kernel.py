import re
import os

from .base import BaseHeuristic, SubmitRequest


def kernel_url(v, pl, sl=None, extension=None):

    url_prefix = 'https://cdn.kernel.org/pub/linux/kernel'
    extension = extension or 'tar.xz'

    if v==1 or v==2:
        subdir = 'v{}.{}'.format(v,pl)
    elif v>=3:
        subdir = 'v{}.x'.format(v)

    if sl is not None:
        filename = 'linux-{}.{}.{}'.format(v,pl,sl) + '.' + extension
    else:
        filename = 'linux-{}.{}'.format(v,pl) + '.' + extension

    return '/'.join([url_prefix, subdir, filename])


class LinuxKernelHeuristic(BaseHeuristic):
    codename = 'kernel'

    def __init__(self):
        self.pattern = re.compile('linux-(?P<version>[\d]+)\.(?P<patchlevel>[\d]+)(\.(?P<sublevel>[\d]+))?\.'
                                  '(?P<extension>tar\.gz|tar\.xz|tar\.bz2)')

    def check(self, path):
        basename = os.path.basename(path)
        m = self.pattern.match(basename)
        if m:
            gd = m.groupdict()

            v=int(gd['version'])
            pl=int(gd['patchlevel'])
            sl=gd.get('sublevel')
            sl=int(sl) if sl else None
            extension = m.group('extension')

            url = kernel_url(v=v, pl=pl, sl=sl, extension=extension)

            sr = SubmitRequest(url=url, project='kernel.org')
            return [sr]

        return list()


class LinuxMakefileHeuristic(BaseHeuristic):
    codename = 'kernelmake'

    def __init__(self):
        # few files (our of 213 total) which are common for 1.0 - 5.0.5
        self.checkfiles = [
            './drivers/block/floppy.c',
            './drivers/scsi/scsi.c',
            './fs/ext2/file.c',
            './fs/proc/inode.c',
            './include/linux/kernel.h',
            './kernel/panic.c',
            './mm/vmalloc.c',
            './net/socket.c'
        ]
        self.max_make_size = 200*1024*1024


    def check(self, path):

        basename = os.path.basename(path)

        if basename != 'Makefile':
            return list()

        dirname = os.path.dirname(path)

        for checkfile in self.checkfiles:
            if not os.path.isfile(os.path.join(dirname, checkfile)):
                return list()

        size = os.stat(path).st_size

        if size > self.max_make_size:
            # sanity check. today Makefile if 60K, 200K max limit
            return list()

        with open(path, 'r') as f:
            content = f.read()

        v = self.get_make_var('VERSION', content, type=int)
        pl = self.get_make_var('PATCHLEVEL', content, type=int)
        sl = self.get_make_var('SUBLEVEL', content, type=int)

        url = kernel_url(v=v, pl=pl, sl=sl)
        sr = SubmitRequest(url=url, project='kernel.org')
        return [sr]

        return list()

    def get_make_var(self, varname, content, type=None):
        m = re.search('^' + varname + ' *= *(\\d+)', content, flags=re.MULTILINE)

        if m is None:
            return None

        if type is None:
            return m.group(1)
        else:
            return type(m.group(1))
