from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import AsyncIterator
from typing import cast

import pytest


@pytest.fixture(
    scope="session",
    params=[True, False],
    ids=["debug:true", "debug:false"],
)
def debug(request: pytest.FixtureRequest) -> bool:
    return cast(bool, request.param)


@pytest.fixture(autouse=True)
async def loop(debug: bool) -> AsyncIterator[AbstractEventLoop]:
    event_loop = get_running_loop()
    event_loop.set_debug(debug)
    yield event_loop
