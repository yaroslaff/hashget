import pytest

def pytest_addoption(parser):
    parser.addoption("--vmroot", action="store", default=None)


@pytest.fixture
def vmroot(request):
    return request.config.getoption("--vmroot")
