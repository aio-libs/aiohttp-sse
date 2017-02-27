aiohttp_sse
===========
.. image:: https://travis-ci.org/aio-libs/aiohttp_sse.svg?branch=master
    :target: https://travis-ci.org/aio-libs/aiohttp_sse

.. image:: https://codecov.io/gh/aio-libs/aiohttp_sse/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/aio-libs/aiohttp_sse

.. image:: https://pyup.io/repos/github/aio-libs/aiohttp_sse/shield.svg
     :target: https://pyup.io/repos/github/aio-libs/aiohttp_sse/
     :alt: Updates

The *EventSource** interface is used to receive server-sent events. It connects
to a server over HTTP and receives events in text/event-stream format without
closing the connection. *aiohttp_sse* provides support for server-sent
events for aiohttp_.


Installation
------------
Installation process as simple as::

    $ pip install aiohttp-sse


Mailing List
------------

*aio-libs* google group: https://groups.google.com/forum/#!forum/aio-libs


Example
-------
.. code:: python

    import asyncio
    from aiohttp import web
    from aiohttp_sse import EventSourceResponse


    async def hello(request):
        loop = asyncio.get_event_loop()
        resp = EventSourceResponse()
        await resp.prepare(request)
        for i in range(0, 100):
            print('foo')
            await asyncio.sleep(1, loop=loop)
            resp.send('foo {}'.format(i))

        resp.stop_streaming()
        return resp


    async def index(request):
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
        return Response(body=d)


    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/hello', hello)
    app.router.add_route('GET', '/index', index)
    web.run_app(app, host='127.0.0.1', port=8080)


EventSource Protocol
--------------------

* http://www.w3.org/TR/2011/WD-eventsource-20110310/
* https://developer.mozilla.org/en-US/docs/Server-sent_events/Using_server-sent_events


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
