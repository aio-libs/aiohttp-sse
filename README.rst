aiohttp_sse
===========
.. image:: https://travis-ci.org/jettify/aiohttp_sse.svg?branch=master
    :target: https://travis-ci.org/jettify/aiohttp_sse

.. image:: https://coveralls.io/repos/jettify/aiohttp_sse/badge.svg
    :target: https://coveralls.io/r/jettify/aiohttp_sse

The EventSource interface is used to receive server-sent events. It connects
to a server over HTTP and receives events in text/event-stream format without
closing the connection. *aiohttp_sse* provides support for server-sent
events for aiohttp_.


Example
-------
.. code:: python

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

Requirements
------------

* Python_ 3.3+
* asyncio_ or Python_ 3.4+
* aiohttp_


License
-------

The *aiohttp_sse* is offered under Apache 2.0 license.

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3.4/library/asyncio.html
.. _aiohttp: https://github.com/KeepSafe/aiohttp
