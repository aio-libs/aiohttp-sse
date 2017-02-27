import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp_sse import EventSourceResponse, sse_response


@pytest.mark.asyncio(forbid_global_loop=True)
@pytest.mark.parametrize('with_deprecated_start', (False, True))
@pytest.mark.parametrize('with_sse_response', (False, True),
                         ids=('without_sse_response',
                              'with_sse_response'))
def test_func(event_loop, unused_tcp_port, with_deprecated_start,
              with_sse_response):

    @asyncio.coroutine
    def func(request):
        if with_sse_response:
            resp = yield from sse_response(request,
                                           headers={'X-SSE': 'aiohttp_sse'})
        else:
            resp = EventSourceResponse(headers={'X-SSE': 'aiohttp_sse'})
            if with_deprecated_start:
                resp.start(request)
            else:
                yield from resp.prepare(request)
        resp.send('foo')
        resp.send('foo', event='bar')
        resp.send('foo', event='bar', id='xyz')
        resp.send('foo', event='bar', id='xyz', retry=1)
        resp.stop_streaming()
        yield from resp.wait()
        return resp

    app = web.Application(loop=event_loop)
    app.router.add_route('GET', '/', func)
    app.router.add_route('POST', '/', func)

    handler = app.make_handler()
    srv = yield from event_loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp = yield from aiohttp.request('GET', url, loop=event_loop)
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
    resp = yield from aiohttp.request('POST', url, loop=event_loop)
    assert 405 == resp.status
    srv.close()
    yield from srv.wait_closed()
    yield from handler.shutdown(0)


@pytest.mark.asyncio(forbid_global_loop=True)
def test_wait_stop_streaming(event_loop, unused_tcp_port):
    loop = event_loop

    @asyncio.coroutine
    def func(request):
        app = request.app
        resp = EventSourceResponse()
        yield from resp.prepare(request)
        resp.send('foo', event='bar', id='xyz', retry=1)
        app['socket'].append(resp)
        yield from resp.wait()
        return resp

    app = web.Application(loop=event_loop)
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    handler = app.make_handler()
    srv = yield from loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp_task = asyncio.async(
        aiohttp.request('GET', url, loop=event_loop),
        loop=event_loop)

    yield from asyncio.sleep(0.1, loop=event_loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    yield from esourse.wait()
    resp = yield from resp_task

    assert 200 == resp.status
    streamed_data = yield from resp.text()

    expected = 'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()
    yield from srv.wait_closed()
    yield from handler.shutdown(0)


@pytest.mark.asyncio(forbid_global_loop=True)
def test_retry(event_loop, unused_tcp_port):

    @asyncio.coroutine
    def func(request):
        resp = EventSourceResponse()
        yield from resp.prepare(request)
        with pytest.raises(TypeError):
            resp.send('foo', retry='one')
        resp.send('foo', retry=1)
        resp.stop_streaming()
        yield from resp.wait()
        return resp

    app = web.Application(loop=event_loop)
    app.router.add_route('GET', '/', func)

    handler = app.make_handler()
    srv = yield from event_loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp = yield from aiohttp.request('GET', url, loop=event_loop)
    assert 200 == resp.status

    # check streamed data
    streamed_data = yield from resp.text()
    expected = 'data: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()
    yield from srv.wait_closed()
    yield from handler.shutdown(0)


@pytest.mark.asyncio(forbid_global_loop=True)
def test_wait_stop_streaming_errors():
    response = EventSourceResponse()
    with pytest.raises(RuntimeError) as ctx:
        yield from response.wait()
    assert str(ctx.value) == 'Response is not started'

    with pytest.raises(RuntimeError) as ctx:
        response.stop_streaming()
    assert str(ctx.value) == 'Response is not started'


def test_compression_not_implemented():
    response = EventSourceResponse()
    with pytest.raises(NotImplementedError):
        response.enable_compression()


def test_ping_property(event_loop):
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


@pytest.mark.asyncio(forbid_global_loop=True)
def test_ping(event_loop, unused_tcp_port):

    @asyncio.coroutine
    def func(request):
        app = request.app
        resp = EventSourceResponse()
        resp.ping_interval = 1
        yield from resp.prepare(request)
        resp.send('foo')
        app['socket'].append(resp)
        yield from resp.wait()
        return resp

    app = web.Application(loop=event_loop)
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    handler = app.make_handler()
    srv = yield from event_loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp_task = asyncio.async(
        aiohttp.request('GET', url, loop=event_loop),
        loop=event_loop)

    yield from asyncio.sleep(1.15, loop=event_loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    yield from esourse.wait()
    resp = yield from resp_task

    assert 200 == resp.status
    streamed_data = yield from resp.text()

    expected = 'data: foo\r\n\r\n' + ': ping\r\n\r\n'
    assert streamed_data == expected
    srv.close()
    yield from srv.wait_closed()
    yield from handler.shutdown(0)
