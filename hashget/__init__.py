
from .anchor import AnchorList
from .version import __version__
from . import cacheget

__user_agent__ = 'HashGet/{version}'.format(version=__version__)


__all__ = ["utils", "cacheget", "package", "restorefile", "hashdb", "hashpackage", "file", "submiturl"]

cacheget.user_agent = __user_agent__
