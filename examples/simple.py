import asyncio
from aiohttp.web import Application, Response
from aiohttp_sse import EventSourceResponse


@asyncio.coroutine
def hello(request):
    resp = EventSourceResponse()
    resp.start(request)
    for i in range(0, 100):
        print('foo')
        yield from asyncio.sleep(1, loop=loop)
        resp.send('foo {}'.format(i))


@asyncio.coroutine
def index(request):
    d = b"""
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
            <div id="response"></div>
        </body>
    </html>
    """
    resp = Response(body=d)

    return resp


@asyncio.coroutine
def init(loop):
    app = Application(loop=loop)
    app.router.add_route('GET', '/hello', hello)
    app.router.add_route('GET', '/index', index)

    handler = app.make_handler()
    srv = yield from loop.create_server(handler, '127.0.0.1', 8080)
    print("Server started at http://127.0.0.1:8080")
    return srv, handler


loop = asyncio.get_event_loop()
srv, handler = loop.run_until_complete(init(loop))
try:
    loop.run_forever()
except KeyboardInterrupt:
    loop.run_until_complete(handler.finish_connections())
