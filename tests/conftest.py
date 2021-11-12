import aiohttp
import pytest


@pytest.fixture(
    scope="session", params=[True, False], ids=["debug:true", "debug:false"]
)
def debug(request):
    return request.param


@pytest.fixture
def loop(event_loop, debug):
    event_loop.set_debug(debug)
    return event_loop


@pytest.fixture
def session(loop):
    async def create_session(loop):
        return aiohttp.ClientSession()

    session = loop.run_until_complete(create_session(loop))
    yield session
    loop.run_until_complete(session.close())
