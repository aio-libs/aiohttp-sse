import asyncio
from aiohttp import web
from aiohttp.web import Application, Response
from aiohttp_sse import sse_response


async def hello(request):
    async with sse_response(request) as resp:
        for i in range(0, 100):
            print('foo')
            await asyncio.sleep(1)
            resp.send('foo {}'.format(i))
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
            <div id="response"></div>
        </body>
    </html>
    """
    resp = Response(text=d, content_type='text/html')
    return resp


loop = asyncio.get_event_loop()
app = Application(loop=loop)
app.router.add_route('GET', '/hello', hello)
app.router.add_route('GET', '/index', index)
web.run_app(app, host='127.0.0.1', port=8080)
