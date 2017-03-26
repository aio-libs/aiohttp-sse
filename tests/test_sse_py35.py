import sys

import pytest

from aiohttp import web
from aiohttp_sse import sse_response


pytestmark = pytest.mark.skipif(sys.version_info < (3, 5),
                                reason='test module only supported by'
                                ' python3.5 and above.')


@pytest.mark.asyncio(forbid_global_loop=True)
async def test_context_manager(loop, unused_tcp_port, session):

    async def func(request):
        sse = await sse_response(request, headers={'X-SSE': 'aiohttp_sse'})
        async with sse:
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
