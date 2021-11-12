import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from aiohttp_sse import EventSourceResponse, sse_response


async def make_runner(app, host, port):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "with_sse_response",
    (False, True),
    ids=("without_sse_response", "with_sse_response"),
)
async def test_func(loop, unused_tcp_port, with_sse_response, session):
    async def func(request):
        if with_sse_response:
            resp = await sse_response(request, headers={"X-SSE": "aiohttp_sse"})
        else:
            resp = EventSourceResponse(headers={"X-SSE": "aiohttp_sse"})
            await resp.prepare(request)
        await resp.send("foo")
        await resp.send("foo", event="bar")
        await resp.send("foo", event="bar", id="xyz")
        await resp.send("foo", event="bar", id="xyz", retry=1)
        resp.stop_streaming()
        await resp.wait()
        return resp

    app = web.Application()
    app.router.add_route("GET", "/", func)
    app.router.add_route("POST", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)

    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp = await session.request("GET", url)
    assert 200 == resp.status

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers.get("X-SSE") == "aiohttp_sse"

    # make sure default headers set
    assert resp.headers.get("Content-Type") == "text/event-stream"
    assert resp.headers.get("Cache-Control") == "no-cache"
    assert resp.headers.get("Connection") == "keep-alive"
    assert resp.headers.get("X-Accel-Buffering") == "no"

    # check streamed data
    streamed_data = await resp.text()
    expected = (
        "data: foo\r\n\r\n"
        "event: bar\r\ndata: foo\r\n\r\n"
        "id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n"
        "id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n"
    )
    assert streamed_data == expected

    # check that EventSourceResponse object works only
    # with GET method
    resp = await session.request("POST", url)
    assert 405 == resp.status
    resp.close()
    await runner.cleanup()


@pytest.mark.asyncio
async def test_wait_stop_streaming(loop, unused_tcp_port, session):
    async def func(request):
        app = request.app
        resp = EventSourceResponse()
        await resp.prepare(request)
        await resp.send("foo", event="bar", id="xyz", retry=1)
        app["socket"].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app["socket"] = []
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp_task = asyncio.create_task(session.request("GET", url))

    await asyncio.sleep(0.1)
    esourse = app["socket"][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n"
    assert streamed_data == expected

    await runner.cleanup()


@pytest.mark.asyncio
async def test_retry(loop, unused_tcp_port, session):
    async def func(request):
        resp = EventSourceResponse()
        await resp.prepare(request)
        with pytest.raises(TypeError):
            await resp.send("foo", retry="one")
        await resp.send("foo", retry=1)
        resp.stop_streaming()
        await resp.wait()
        return resp

    app = web.Application()
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp = await session.request("GET", url)
    assert 200 == resp.status

    # check streamed data
    streamed_data = await resp.text()
    expected = "data: foo\r\nretry: 1\r\n\r\n"
    assert streamed_data == expected

    await runner.cleanup()


@pytest.mark.asyncio
async def test_wait_stop_streaming_errors():
    response = EventSourceResponse()
    with pytest.raises(RuntimeError) as ctx:
        await response.wait()
    assert str(ctx.value) == "Response is not started"

    with pytest.raises(RuntimeError) as ctx:
        response.stop_streaming()
    assert str(ctx.value) == "Response is not started"


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
        response.ping_interval = "ten"

    assert str(ctx.value) == "ping interval must be int"

    with pytest.raises(ValueError):
        response.ping_interval = -42


@pytest.mark.asyncio
async def test_ping(loop, unused_tcp_port, session):
    async def func(request):
        app = request.app
        resp = EventSourceResponse()
        resp.ping_interval = 1
        await resp.prepare(request)
        await resp.send("foo")
        app["socket"].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app["socket"] = []
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp_task = asyncio.create_task(session.request("GET", url))

    await asyncio.sleep(1.15)
    esourse = app["socket"][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "data: foo\r\n\r\n" + ": ping\r\n\r\n"
    assert streamed_data == expected
    await runner.cleanup()


@pytest.mark.asyncio
async def test_context_manager(loop, unused_tcp_port, session):
    async def func(request):
        h = {"X-SSE": "aiohttp_sse"}
        async with sse_response(request, headers=h) as sse:
            await sse.send("foo")
            await sse.send("foo", event="bar")
            await sse.send("foo", event="bar", id="xyz")
            await sse.send("foo", event="bar", id="xyz", retry=1)
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", func)
    app.router.add_route("POST", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp = await session.request("GET", url)
    assert resp.status == 200

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers["X-SSE"] == "aiohttp_sse"

    # check streamed data
    streamed_data = await resp.text()
    expected = (
        "data: foo\r\n\r\n"
        "event: bar\r\ndata: foo\r\n\r\n"
        "id: xyz\r\nevent: bar\r\ndata: foo\r\n\r\n"
        "id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n"
    )
    assert streamed_data == expected
    await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "with_subclass", [False, True], ids=("without_subclass", "with_subclass")
)
async def test_custom_response_cls(with_subclass):
    class CustomResponse(EventSourceResponse if with_subclass else object):
        pass

    request = make_mocked_request("GET", "/")
    if with_subclass:
        with pytest.warns(RuntimeWarning):
            sse_response(request, response_cls=CustomResponse)
    else:
        with pytest.raises(TypeError):
            sse_response(request, response_cls=CustomResponse)


@pytest.mark.asyncio
@pytest.mark.parametrize("sep", ["\n", "\r", "\r\n"], ids=("LF", "CR", "CR+LF"))
async def test_custom_sep(loop, unused_tcp_port, session, sep):
    async def func(request):
        h = {"X-SSE": "aiohttp_sse"}
        async with sse_response(request, headers=h, sep=sep) as sse:
            await sse.send("foo")
            await sse.send("foo", event="bar")
            await sse.send("foo", event="bar", id="xyz")
            await sse.send("foo", event="bar", id="xyz", retry=1)
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp = await session.request("GET", url)
    assert resp.status == 200

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers["X-SSE"] == "aiohttp_sse"

    # check streamed data
    streamed_data = await resp.text()
    expected = (
        "data: foo{0}{0}"
        "event: bar{0}data: foo{0}{0}"
        "id: xyz{0}event: bar{0}data: foo{0}{0}"
        "id: xyz{0}event: bar{0}data: foo{0}retry: 1{0}{0}"
    )

    assert streamed_data == expected.format(sep)
    await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stream_sep,line_sep",
    [
        (
            "\n",
            "\n",
        ),
        (
            "\n",
            "\r",
        ),
        (
            "\n",
            "\r\n",
        ),
        (
            "\r",
            "\n",
        ),
        (
            "\r",
            "\r",
        ),
        (
            "\r",
            "\r\n",
        ),
        (
            "\r\n",
            "\n",
        ),
        (
            "\r\n",
            "\r",
        ),
        (
            "\r\n",
            "\r\n",
        ),
    ],
    ids=(
        "steam-LF:line-LF",
        "steam-LF:line-CR",
        "steam-LF:line-CR+LF",
        "steam-CR:line-LF",
        "steam-CR:line-CR",
        "steam-CR:line-CR+LF",
        "steam-CR+LF:line-LF",
        "steam-CR+LF:line-CR",
        "steam-CR+LF:line-CR+LF",
    ),
)
async def test_multiline_data(loop, unused_tcp_port, session, stream_sep, line_sep):
    async def func(request):
        h = {"X-SSE": "aiohttp_sse"}
        lines = line_sep.join(["foo", "bar", "xyz"])
        async with sse_response(request, headers=h, sep=stream_sep) as sse:
            await sse.send(lines)
            await sse.send(lines, event="bar")
            await sse.send(lines, event="bar", id="xyz")
            await sse.send(lines, event="bar", id="xyz", retry=1)
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp = await session.request("GET", url)
    assert resp.status == 200

    # make sure that EventSourceResponse supports passing
    # custom headers
    assert resp.headers["X-SSE"] == "aiohttp_sse"

    # check streamed data
    streamed_data = await resp.text()
    expected = (
        "data: foo{0}data: bar{0}data: xyz{0}{0}"
        "event: bar{0}data: foo{0}data: bar{0}data: xyz{0}{0}"
        "id: xyz{0}event: bar{0}data: foo{0}data: bar{0}data: xyz{0}{0}"
        "id: xyz{0}event: bar{0}data: foo{0}data: bar{0}data: xyz{0}"
        "retry: 1{0}{0}"
    )
    assert streamed_data == expected.format(stream_sep)
    await runner.cleanup()
