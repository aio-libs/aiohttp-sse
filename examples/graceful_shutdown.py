import asyncio
import json
import logging
import weakref
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from functools import partial
from typing import Any, Optional

from aiohttp import web

from aiohttp_sse import EventSourceResponse, sse_response

streams_key = web.AppKey("streams_key", weakref.WeakSet["SSEResponse"])
worker_key = web.AppKey("worker_key", asyncio.Task[None])


class SSEResponse(EventSourceResponse):
    async def send_json(
        self,
        data: dict[str, Any],
        id: Optional[str] = None,
        event: Optional[str] = None,
        retry: Optional[int] = None,
        json_dumps: Callable[[Any], str] = partial(json.dumps, indent=2),
    ) -> None:
        await self.send(json_dumps(data), id=id, event=event, retry=retry)


async def send_event(
    stream: SSEResponse,
    data: dict[str, Any],
    event_id: str,
) -> None:
    try:
        await stream.send_json(data, id=event_id)
    except Exception:
        logging.exception("Exception when sending event: %s", event_id)


async def worker(app: web.Application) -> None:
    while True:
        now = datetime.now()
        delay = asyncio.create_task(asyncio.sleep(1))  # Fire

        fs = []
        for stream in app[streams_key]:
            data = {
                "time": f"Server Time : {now}",
                "last_event_id": stream.last_event_id,
            }
            coro = send_event(stream, data, str(now.timestamp()))
            fs.append(coro)

        # Run in parallel
        await asyncio.gather(*fs)

        # Sleep 1s - n
        await delay


async def on_startup(app: web.Application) -> None:
    app[streams_key] = weakref.WeakSet[SSEResponse]()
    app[worker_key] = asyncio.create_task(worker(app))


async def clean_up(app: web.Application) -> None:
    app[worker_key].cancel()
    with suppress(asyncio.CancelledError):
        await app[worker_key]


async def on_shutdown(app: web.Application) -> None:
    waiters = []
    for stream in app[streams_key]:
        stream.stop_streaming()
        waiters.append(stream.wait())

    await asyncio.gather(*waiters, return_exceptions=True)
    app[streams_key].clear()


async def hello(request: web.Request) -> web.StreamResponse:
    stream: SSEResponse = await sse_response(request, response_cls=SSEResponse)
    request.app[streams_key].add(stream)
    try:
        await stream.wait()
    finally:
        request.app[streams_key].discard(stream)
    return stream


async def index(_request: web.Request) -> web.StreamResponse:
    d = """
    <html>
        <head>
            <script>
                var eventSource = new EventSource("/hello");
                eventSource.addEventListener("message", event => {
                    document.getElementById("response").innerText = event.data;
                });
            </script>
        </head>
        <body>
            <h1>Response from server:</h1>
            <pre id="response"></pre>
        </body>
    </html>
    """
    return web.Response(text=d, content_type="text/html")


if __name__ == "__main__":
    app = web.Application()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.on_cleanup.append(clean_up)

    app.router.add_route("GET", "/hello", hello)
    app.router.add_route("GET", "/", index)
    web.run_app(app, host="127.0.0.1", port=8080)
