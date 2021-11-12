import asyncio
import json
import weakref
from contextlib import suppress
from datetime import datetime
from functools import partial

from aiohttp import web

from aiohttp_sse import EventSourceResponse, sse_response


class SSEResponse(EventSourceResponse):
    @property
    def last_event_id(self):
        return self._req.headers.get("Last-Event-Id")

    async def send_json(
        self,
        data,
        id=None,
        event=None,
        retry=None,
        json_dumps=partial(json.dumps, indent=2),
    ):
        await self.send(json_dumps(data), id=id, event=event, retry=retry)


async def worker(app):
    while True:
        now = datetime.now()
        delay = asyncio.create_task(asyncio.sleep(1))  # Fire

        fs = []
        for stream in app["streams"]:
            data = {
                "time": f"Server Time : {now}",
                "last_event_id": stream.last_event_id,
            }
            fs.append(stream.send_json(data, id=now.timestamp()))

        # Run in parallel
        await asyncio.gather(*fs)

        # Sleep 1s - n
        await delay


async def on_startup(app):
    app["streams"] = weakref.WeakSet()
    app["worker"] = app.loop.create_task(worker(app))


async def clean_up(app):
    app["worker"].cancel()
    with suppress(asyncio.CancelledError):
        await app["worker"]


async def on_shutdown(app):
    waiters = []
    for stream in app["streams"]:
        stream.stop_streaming()
        waiters.append(stream.wait())

    await asyncio.gather(*waiters)
    app["streams"].clear()


async def hello(request):
    stream = await sse_response(request, response_cls=SSEResponse)
    request.app["streams"].add(stream)
    try:
        await stream.wait()
    finally:
        request.app["streams"].discard(stream)
    return stream


async def index(request):
    d = """
        <html>
        <head>
            <script type="text/javascript"
                src="http://code.jquery.com/jquery.min.js"></script>
            <script type="text/javascript">
            var evtSource = new EventSource("/hello");
            evtSource.onmessage = function(e) {
              $('#response').html(e.data);
            }
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
    app.router.add_route("GET", "/index", index)
    web.run_app(app, host="127.0.0.1", port=8080)
