import aiohttp
import pytest


@pytest.fixture(
    scope="session", params=[True, False], ids=["debug:true", "debug:false"]
)
def debug(request):
    return request.param


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as session:
        yield session
