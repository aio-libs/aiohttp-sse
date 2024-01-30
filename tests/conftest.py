from asyncio import AbstractEventLoop
from typing import AsyncGenerator, cast

import aiohttp
import pytest
from pytest_asyncio.plugin import SubRequest


@pytest.fixture(
    scope="session",
    params=[True, False],
    ids=["debug:true", "debug:false"],
)
def debug(request: SubRequest) -> bool:
    return cast(bool, request.param)


@pytest.fixture(autouse=True)
def loop(event_loop: AbstractEventLoop, debug: bool) -> AbstractEventLoop:
    event_loop.set_debug(debug)
    return event_loop


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as session:
        yield session
