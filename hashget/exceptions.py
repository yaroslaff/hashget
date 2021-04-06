class HashGetBaseException(Exception):
    pass

class HashPackageExists(HashGetBaseException):
    pass

class DownloadFailure(HashGetBaseException):
    pass

class BrokenPackage(HashGetBaseException):
    pass