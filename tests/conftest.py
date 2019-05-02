import pytest

option = None

def pytest_addoption(parser):
    parser.addoption("--vmroot", action="store", default=None)
    parser.addoption("--pool", action="store", default=None)


@pytest.fixture
def vmroot(request):
    return request.config.getoption("--vmroot")

@pytest.fixture
def pool(request):
    pooldir = request.config.getoption("--pool")
    if pooldir is None or pooldir.endswith('/'):
        return pooldir
    else:
        return pooldir+'/'


def pytest_configure(config):
    """Make cmdline arguments available to dbtest"""
    global option
    option =  config.option