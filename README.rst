aiohttp-sse
===========
.. image:: https://travis-ci.org/aio-libs/aiohttp-sse.svg?branch=master
    :target: https://travis-ci.org/aio-libs/aiohttp-sse

.. image:: https://codecov.io/gh/aio-libs/aiohttp-sse/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/aio-libs/aiohttp-sse

.. image:: https://pyup.io/repos/github/aio-libs/aiohttp-sse/shield.svg
     :target: https://pyup.io/repos/github/aio-libs/aiohttp-sse/
     :alt: Updates

.. image:: https://badges.gitter.im/Join%20Chat.svg
     :target: https://gitter.im/aio-libs/Lobby
     :alt: Chat on Gitter


The **EventSource** interface is used to receive server-sent events. It connects
to a server over HTTP and receives events in text/event-stream format without
closing the connection. *aiohttp-sse* provides support for server-sent
events for aiohttp_.


Installation
------------
Installation process as simple as::

    $ pip install aiohttp-sse


Example
-------
.. code:: python

    import asyncio
    import json
    from datetime import datetime

    from aiohttp import web

    from aiohttp_sse import sse_response


    async def hello(request: web.Request) -> web.StreamResponse:
        async with sse_response(request) as resp:
            while resp.is_connected():
                time_dict = {"time": f"Server Time : {datetime.now()}"}
                data = json.dumps(time_dict, indent=2)
                print(data)
                await resp.send(data)
                await asyncio.sleep(1)
        return resp


    async def index(_request: web.Request) -> web.StreamResponse:
        html = """
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
        return web.Response(text=html, content_type="text/html")


    app = web.Application()
    app.router.add_route("GET", "/hello", hello)
    app.router.add_route("GET", "/", index)
    web.run_app(app, host="127.0.0.1", port=8080)


EventSource Protocol
--------------------

* http://www.w3.org/TR/2011/WD-eventsource-20110310/
* https://developer.mozilla.org/en-US/docs/Server-sent_events/Using_server-sent_events


Requirements
------------

* aiohttp_ 3+


License
-------

The *aiohttp-sse* is offered under Apache 2.0 license.

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3/library/asyncio.html
.. _aiohttp: https://github.com/aio-libs/aiohttp
