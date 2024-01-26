import aiohttp
import pytest


@pytest.fixture(
    scope="session", params=[True, False], ids=["debug:true", "debug:false"]
)
def debug(request):
    return request.param


@pytest.fixture(autouse=True)
def loop(event_loop, debug):
    event_loop.set_debug(debug)
    return event_loop


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as session:
        yield session
