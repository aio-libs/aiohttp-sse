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
            resp = EventSourceResponse(headers={'X-SSE': 'aiohttp_sse'})
            resp.start(request)
            resp.send('foo')
            resp.send('foo', event='bar')
            resp.send('foo', event='bar', id='xyz')
            resp.send('foo', event='bar', id='xyz', retry=1)
            return resp

        @asyncio.coroutine
        def go():
            app = web.Application(loop=self.loop)
            app.router.add_route('GET', '/', func)
            app.router.add_route('POST', '/', func)

            port = self.find_unused_port()
            srv = yield from self.loop.create_server(
                app.make_handler(), '127.0.0.1', port)
            url = "http://127.0.0.1:{}/".format(port)

            resp = yield from aiohttp.request('GET', url, loop=self.loop)
            self.assertEqual(200, resp.status)

            # make sure that EventSourceResponse supports passing
            # custom headers
            self.assertEqual(resp.headers.get('X-SSE'), 'aiohttp_sse')

            # check streamed data
            streamed_data = yield from resp.text()
            expected = 'data: foo\r\n\r\n' \
                       'event: bar\r\ndata: foo\r\n\r\n' \
                       'id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n' \
                       'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
            self.assertEqual(streamed_data, expected)

            # check that EventSourceResponse object works only
            # with GET method
            resp = yield from aiohttp.request('POST', url, loop=self.loop)
            self.assertEqual(405, resp.status)

            srv.close()
            self.addCleanup(srv.close)

        self.loop.run_until_complete(go())

    def test_wait_stop_streaming(self):

        @asyncio.coroutine
        def func(request):
            app = request.app
            resp = EventSourceResponse()
            resp.start(request)
            resp.send('foo', event='bar', id='xyz', retry=1)
            app['socket'].append(resp)
            yield from resp.wait()
            return resp

        @asyncio.coroutine
        def go():
            app = web.Application(loop=self.loop)
            app['socket'] = []
            app.router.add_route('GET', '/', func)

            port = self.find_unused_port()
            srv = yield from self.loop.create_server(
                app.make_handler(), '127.0.0.1', port)
            url = "http://127.0.0.1:{}/".format(port)

            resp_task = asyncio.async(
                aiohttp.request('GET', url, loop=self.loop),
                loop=self.loop)

            yield from asyncio.sleep(0.1, loop=self.loop)
            esourse = app['socket'][0]
            esourse.stop_streaming()
            resp = yield from resp_task

            self.assertEqual(200, resp.status)
            streamed_data = yield from resp.text()

            expected = 'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
            self.assertEqual(streamed_data, expected)

            srv.close()
            self.addCleanup(srv.close)

        self.loop.run_until_complete(go())

    def test_wait_stop_streaming_errors(self):
        response = EventSourceResponse()
        with self.assertRaises(RuntimeError):
            response.wait()

        with self.assertRaises(RuntimeError):
            response.stop_streaming()

    def test_compression_not_implemented(self):
        response = EventSourceResponse()
        with self.assertRaises(NotImplementedError):
            response.enable_compression()

    def test_ping_property(self):
        response = EventSourceResponse()
        default = response.DEFAULT_PING_INTERVAL
        self.assertEqual(response.ping_interval, default)
        response.ping_interval = 25
        self.assertEqual(response.ping_interval, 25)

        with self.assertRaises(TypeError):
            response.ping_interval = 'ten'

        with self.assertRaises(ValueError):
            response.ping_interval = -42

    def test_ping(self):

        @asyncio.coroutine
        def func(request):
            app = request.app
            resp = EventSourceResponse()
            resp.ping_interval = 1
            resp.start(request)
            resp.send('foo')
            app['socket'].append(resp)
            yield from resp.wait()
            return resp

        @asyncio.coroutine
        def go():
            app = web.Application(loop=self.loop)
            app['socket'] = []
            app.router.add_route('GET', '/', func)

            port = self.find_unused_port()
            srv = yield from self.loop.create_server(
                app.make_handler(), '127.0.0.1', port)
            url = "http://127.0.0.1:{}/".format(port)

            resp_task = asyncio.async(
                aiohttp.request('GET', url, loop=self.loop),
                loop=self.loop)

            yield from asyncio.sleep(1.15, loop=self.loop)
            esourse = app['socket'][0]
            esourse.stop_streaming()
            resp = yield from resp_task

            self.assertEqual(200, resp.status)
            streamed_data = yield from resp.text()

            expected = 'data: foo\r\n\r\n' + ':ping\r\n\r\n'
            self.assertEqual(streamed_data, expected)

            srv.close()
            self.addCleanup(srv.close)

        self.loop.run_until_complete(go())
