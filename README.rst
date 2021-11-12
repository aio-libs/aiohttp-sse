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


The *EventSource** interface is used to receive server-sent events. It connects
to a server over HTTP and receives events in text/event-stream format without
closing the connection. *aiohttp-sse* provides support for server-sent
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
    from aiohttp.web import Response
    from aiohttp_sse import sse_response
    from datetime import datetime


    async def hello(request):
        loop = request.app.loop
        async with sse_response(request) as resp:
            while True:
                data = 'Server Time : {}'.format(datetime.now())
                print(data)
                await resp.send(data)
                await asyncio.sleep(1)
        return resp


    async def index(request):
        d = """
            <html>
            <body>
                <script>
                    var evtSource = new EventSource("/hello");
                    evtSource.onmessage = function(e) {
                        document.getElementById('response').innerText = e.data
                    }
                </script>
                <h1>Response from server:</h1>
                <div id="response"></div>
            </body>
        </html>
        """
        return Response(text=d, content_type='text/html')


    app = web.Application()
    app.router.add_route('GET', '/hello', hello)
    app.router.add_route('GET', '/', index)
    web.run_app(app, host='127.0.0.1', port=8080)


EventSource Protocol
--------------------

* http://www.w3.org/TR/2011/WD-eventsource-20110310/
* https://developer.mozilla.org/en-US/docs/Server-sent_events/Using_server-sent_events


Requirements
------------

* Python_ 3.5+
* aiohttp_ 3+


License
-------

The *aiohttp-sse* is offered under Apache 2.0 license.

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3.5/library/asyncio.html
.. _aiohttp: https://github.com/aio-libs/aiohttp
