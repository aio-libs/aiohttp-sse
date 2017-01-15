import pytest


@pytest.fixture(scope="session", params=[True, False],
                ids=['debug:true', 'debug:false'])
def debug(request):
    return request.param
