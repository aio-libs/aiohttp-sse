import asyncio
import socket
import unittest
import aiohttp
from aiohttp import web
from aiohttp_sse import EventSourceResponse


class TestSimple(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    def find_unused_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def test_func(self):

        @asyncio.coroutine
        def func(request):
            resp = EventSourceResponse()
            resp.start(request)
            resp.send('foo', event='bar', id='xyz', retry=1)
            return resp

        @asyncio.coroutine
        def go():
            app = web.Application(loop=self.loop)
            app.router.add_route('GET', '/', func)

            port = self.find_unused_port()
            srv = yield from self.loop.create_server(
                app.make_handler(), '127.0.0.1', port)
            url = "http://127.0.0.1:{}/".format(port)
            resp = yield from aiohttp.request('GET', url, loop=self.loop)
            self.assertEqual(200, resp.status)
            streamed_data = yield from resp.text()

            expected = 'id: xyz\nevent: bar\ndata: foo\nretry: 1\n\n'
            self.assertEqual(streamed_data, expected)

            srv.close()
            self.addCleanup(srv.close)

        self.loop.run_until_complete(go())
