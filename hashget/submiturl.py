import datetime
# from .hashpackage import HashPackage
from .package import Package
import logging

log = logging.getLogger('hashget')

def submit_url(url, project, anchors, filesz=1024, hashdb=None, file=None, signatures=None, pkgtype=None, attrs=None):
    """
    function interface

    :param url: permanent url where package can be downloaded
    :param project: string, name of project (e.g. 'debsnap')
    :param anchors: AnchorList class (may be empty)
    :param filesz: Minimal size of file to be included to HashPackage
    :param hashdb: HashDBClient where to save it
    :param file: if given, package will not be downloaded, but taken from this file
    :param signatures: additional signatures (e.g. 'deb')
    :param attrs: addtional attributes such as size, date of hashing etc.
    :return:
    """

    hdb = hashdb.ensure_project(project, pkgtype=pkgtype)

    hpclass = hdb.hpclass

    signatures = signatures or dict()
    attrs = attrs or dict()

    if file:
        p = Package(path = file)
    else:
        p = Package(url = url)

    p.download()
    p.unpack()
    p.read_files()
    files = list()

    signatures['url'] = url

    indexed_size = 0

    for f in p.files:
        if filesz >= 0 and f.size > filesz:
            files.append(f.get_hashspec())
            indexed_size += f.size

        anchors.check_append(f)

    p.cleanup()

    hp = hpclass(
        anchors=[ f.get_hashspec() for f in anchors.anchorlist ],
        files=files,
        url=url,
        attrs=attrs,
        hashes=p.hashes.get_list(),
        signatures=signatures
    )

    hp.set_attr('size', p.package_size)
    hp.set_attr('sum_size', p.sum_size)
    hp.set_attr('indexed_size', indexed_size)
    hp.set_attr('crawled_date', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    hashdb.submit_save(hp, project=project, file=p.path)
    return hp

