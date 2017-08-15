import asyncio

import pytest
from aiohttp import web
from aiohttp_sse import EventSourceResponse, sse_response


@pytest.mark.asyncio
@pytest.mark.parametrize('with_sse_response', (False, True),
                         ids=('without_sse_response',
                              'with_sse_response'))
async def test_func(loop, unused_tcp_port, with_sse_response, session):

    async def func(request):
        if with_sse_response:
            resp = await sse_response(request,
                                      headers={'X-SSE': 'aiohttp_sse'})
        else:
            resp = EventSourceResponse(headers={'X-SSE': 'aiohttp_sse'})
            await resp.prepare(request)
        resp.send('foo')
        resp.send('foo', event='bar')
        resp.send('foo', event='bar', id='xyz')
        resp.send('foo', event='bar', id='xyz', retry=1)
        resp.stop_streaming()
        await resp.wait()
        return resp

    app = web.Application()
    app.router.add_route('GET', '/', func)
    app.router.add_route('POST', '/', func)

    handler = app.make_handler(loop=loop)
    srv = await loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp = await session.request('GET', url)
    assert 200 == resp.status

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers.get('X-SSE') == 'aiohttp_sse'

    # check streamed data
    streamed_data = await resp.text()
    expected = 'data: foo\r\n\r\n' \
               'event: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    # check that EventSourceResponse object works only
    # with GET method
    resp = await session.request('POST', url)
    assert 405 == resp.status
    resp.close()
    srv.close()
    await srv.wait_closed()
    await handler.shutdown(0)


@pytest.mark.asyncio
async def test_wait_stop_streaming(loop, unused_tcp_port, session):

    async def func(request):
        app = request.app
        resp = EventSourceResponse()
        await resp.prepare(request)
        resp.send('foo', event='bar', id='xyz', retry=1)
        app['socket'].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    handler = app.make_handler(loop=loop)
    srv = await loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp_task = asyncio.ensure_future(session.request('GET', url), loop=loop)

    await asyncio.sleep(0.1, loop=loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = 'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()
    await srv.wait_closed()
    await handler.shutdown(0)


@pytest.mark.asyncio
async def test_retry(loop, unused_tcp_port, session):

    async def func(request):
        resp = EventSourceResponse()
        await resp.prepare(request)
        with pytest.raises(TypeError):
            resp.send('foo', retry='one')
        resp.send('foo', retry=1)
        resp.stop_streaming()
        await resp.wait()
        return resp

    app = web.Application()
    app.router.add_route('GET', '/', func)

    handler = app.make_handler(loop=loop)
    srv = await loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp = await session.request('GET', url)
    assert 200 == resp.status

    # check streamed data
    streamed_data = await resp.text()
    expected = 'data: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected

    srv.close()
    await srv.wait_closed()
    await handler.shutdown(0)


@pytest.mark.asyncio
async def test_wait_stop_streaming_errors():
    response = EventSourceResponse()
    with pytest.raises(RuntimeError) as ctx:
        await response.wait()
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


@pytest.mark.asyncio
async def test_ping(loop, unused_tcp_port, session):

    async def func(request):
        app = request.app
        resp = EventSourceResponse()
        resp.ping_interval = 1
        await resp.prepare(request)
        resp.send('foo')
        app['socket'].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app['socket'] = []
    app.router.add_route('GET', '/', func)

    handler = app.make_handler(loop=loop)
    srv = await loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp_task = asyncio.ensure_future(session.request('GET', url), loop=loop)

    await asyncio.sleep(1.15, loop=loop)
    esourse = app['socket'][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = 'data: foo\r\n\r\n' + ': ping\r\n\r\n'
    assert streamed_data == expected
    srv.close()
    await srv.wait_closed()
    await handler.shutdown(0)


@pytest.mark.asyncio
async def test_context_manager(loop, unused_tcp_port, session):

    async def func(request):
        h = {'X-SSE': 'aiohttp_sse'}
        async with sse_response(request, headers=h) as sse:
            sse.send('foo')
            sse.send('foo', event='bar')
            sse.send('foo', event='bar', id='xyz')
            sse.send('foo', event='bar', id='xyz', retry=1)
        return sse

    app = web.Application()
    app.router.add_route('GET', '/', func)
    app.router.add_route('POST', '/', func)

    handler = app.make_handler(loop=loop)
    srv = await loop.create_server(
        handler, '127.0.0.1', unused_tcp_port)
    url = "http://127.0.0.1:{}/".format(unused_tcp_port)

    resp = await session.request('GET', url)
    assert resp.status == 200

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers['X-SSE'] == 'aiohttp_sse'

    # check streamed data
    streamed_data = await resp.text()
    expected = 'data: foo\r\n\r\n' \
               'event: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n' \
               'id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n'
    assert streamed_data == expected
    srv.close()
    await srv.wait_closed()
    await handler.shutdown(0)
