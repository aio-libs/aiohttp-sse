from asyncio import AbstractEventLoop
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
def loop(event_loop: AbstractEventLoop, debug: bool) -> AbstractEventLoop:
    event_loop.set_debug(debug)
    return event_loop
