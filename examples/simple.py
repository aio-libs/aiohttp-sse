import asyncio
import json
from datetime import datetime

from aiohttp import web

from aiohttp_sse import sse_response


async def hello(request):
    async with sse_response(request) as resp:
        while True:
            time_dict = {"time": f"Server Time : {datetime.now()}"}
            data = json.dumps(time_dict, indent=2)
            print(data)
            await resp.send(data)
            await asyncio.sleep(1)
    return resp


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
    app.router.add_route("GET", "/hello", hello)
    app.router.add_route("GET", "/index", index)
    web.run_app(app, host="127.0.0.1", port=8080)
