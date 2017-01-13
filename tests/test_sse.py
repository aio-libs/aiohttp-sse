import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp_sse import EventSourceResponse


@pytest.mark.run_loop
def test_func(loop, unused_port):

    @asyncio.coroutine
    def func(request):
        resp = EventSourceResponse(headers={'X-SSE': 'aiohttp_sse'})
        resp.start(request)
        resp.send('foo')
        resp.send('foo', event='bar')
        resp.send('foo', event='bar', id='xyz')
        resp.send('foo', event='bar', id='xyz', retry=1)
        return resp

    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', func)
    app.router.add_route('POST', '/', func)

    port = unused_port()
    srv = yield from loop.create_server(
        app.make_handler(), '127.0.0.1', port)
    url = "http://127.0.0.1:{}/".format(port)

    resp = yield from aiohttp.request('GET', url, loop=loop)
    assert 200 == resp.status

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers.get('X-SSE') == 'aiohttp_sse'

    # check streamed data
    streamed_data = yield from resp.text()
    expected = 'data: foo\r\n\r\n' \
               'event: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    # check that EventSourceResponse object works only
    # with GET method
    resp = yield from aiohttp.request('POST', url, loop=loop)
    assert 405 == resp.status
    srv.close()


@pytest.mark.run_loop
def test_wait_stop_streaming(loop, unused_port):

    @asyncio.coroutine
    def func(request):
        app = request.app
        resp = EventSourceResponse()
        resp.start(request)
        resp.send('foo', event='bar', id='xyz', retry=1)
        app['socket'].append(resp)
        yield from resp.wait()
        return resp

    app = web.Application(loop=loop)
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    port = unused_port()
    srv = yield from loop.create_server(
        app.make_handler(), '127.0.0.1', port)
    url = "http://127.0.0.1:{}/".format(port)

    resp_task = asyncio.async(
        aiohttp.request('GET', url, loop=loop),
        loop=loop)

    yield from asyncio.sleep(0.1, loop=loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    resp = yield from resp_task

    assert 200 == resp.status
    streamed_data = yield from resp.text()

    expected = 'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()


@pytest.mark.run_loop
def test_retry(loop, unused_port):

    @asyncio.coroutine
    def func(request):
        resp = EventSourceResponse()
        resp.start(request)
        with pytest.raises(TypeError):
            resp.send('foo', retry='one')
        resp.send('foo', retry=1)
        return resp

    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', func)

    port = unused_port()
    srv = yield from loop.create_server(
        app.make_handler(), '127.0.0.1', port)
    url = "http://127.0.0.1:{}/".format(port)

    resp = yield from aiohttp.request('GET', url, loop=loop)
    assert 200 == resp.status

    # check streamed data
    streamed_data = yield from resp.text()
    expected = 'data: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()


def test_wait_stop_streaming_errors(loop):
    response = EventSourceResponse()
    with pytest.raises(RuntimeError) as ctx:
        response.wait()
    assert str(ctx.value) == 'Response is not started'

    with pytest.raises(RuntimeError) as ctx:
        response.stop_streaming()
    assert str(ctx.value) == 'Response is not started'


def test_compression_not_implemented():
    response = EventSourceResponse()
    with pytest.raises(NotImplementedError):
        response.enable_compression()


def test_ping_property(loop):
    response = EventSourceResponse()
    default = response.DEFAULT_PING_INTERVAL
    assert response.ping_interval == default
    response.ping_interval = 25
    assert response.ping_interval == 25
    with pytest.raises(TypeError) as ctx:
        response.ping_interval = 'ten'

    assert str(ctx.value) == 'ping interval must be int'

    with pytest.raises(ValueError):
        response.ping_interval = -42


@pytest.mark.run_loop
def test_ping(loop, unused_port):

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

    app = web.Application(loop=loop)
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    port = unused_port()
    srv = yield from loop.create_server(
        app.make_handler(), '127.0.0.1', port)
    url = "http://127.0.0.1:{}/".format(port)

    resp_task = asyncio.ensure_future(
        aiohttp.request('GET', url, loop=loop),
        loop=loop)

    yield from asyncio.sleep(1.15, loop=loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    resp = yield from resp_task

    assert 200 == resp.status
    streamed_data = yield from resp.text()

    expected = 'data: foo\r\n\r\n' + ': ping\r\n\r\n'
    assert streamed_data == expected
    srv.close()
