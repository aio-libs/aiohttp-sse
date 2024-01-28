import asyncio
from typing import List, Union

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import make_mocked_request

from aiohttp_sse import EventSourceResponse, sse_response

socket = web.AppKey("socket", List[EventSourceResponse])


async def make_runner(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner


@pytest.mark.parametrize(
    "with_sse_response",
    (False, True),
    ids=("without_sse_response", "with_sse_response"),
)
async def test_func(
    unused_tcp_port: int,
    with_sse_response: bool,
    session: ClientSession,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
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


async def test_wait_stop_streaming(
    unused_tcp_port: int,
    session: ClientSession,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        app = request.app
        resp = EventSourceResponse()
        await resp.prepare(request)
        await resp.send("foo", event="bar", id="xyz", retry=1)
        app[socket].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app[socket] = []
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp_task = asyncio.create_task(session.request("GET", url))

    await asyncio.sleep(0.1)
    esourse = app[socket][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n"
    assert streamed_data == expected

    await runner.cleanup()


async def test_retry(
    unused_tcp_port: int,
    session: ClientSession,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        resp = EventSourceResponse()
        await resp.prepare(request)
        with pytest.raises(TypeError):
            await resp.send("foo", retry="one")  # type: ignore[arg-type]
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


async def test_wait_stop_streaming_errors() -> None:
    response = EventSourceResponse()
    with pytest.raises(RuntimeError) as ctx:
        await response.wait()
    assert str(ctx.value) == "Response is not started"

    with pytest.raises(RuntimeError) as ctx:
        response.stop_streaming()
    assert str(ctx.value) == "Response is not started"


def test_compression_not_implemented() -> None:
    response = EventSourceResponse()
    with pytest.raises(NotImplementedError):
        response.enable_compression()


class TestPingProperty:
    @pytest.mark.parametrize("value", [25, 25.0], ids=("int", "float"))
    def test_success(self, value: Union[int, float]) -> None:
        response = EventSourceResponse()
        response.ping_interval = value
        assert response.ping_interval == value

    @pytest.mark.parametrize("value", [None, "foo"], ids=("None", "str"))
    def test_wrong_type(self, value: Union[None, str]) -> None:
        response = EventSourceResponse()
        with pytest.raises(TypeError) as ctx:
            response.ping_interval = value  # type: ignore[assignment]

        assert ctx.match("ping interval must be int or float")

    def test_negative_int(self) -> None:
        response = EventSourceResponse()
        with pytest.raises(ValueError) as ctx:
            response.ping_interval = -42

        assert ctx.match("ping interval must be greater then 0")

    def test_default_value(self) -> None:
        response = EventSourceResponse()
        assert response.ping_interval == response.DEFAULT_PING_INTERVAL


async def test_ping(unused_tcp_port: int, session: ClientSession) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        app = request.app
        resp = EventSourceResponse()
        resp.ping_interval = 1
        await resp.prepare(request)
        await resp.send("foo")
        app[socket].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app[socket] = []
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp_task = asyncio.create_task(session.request("GET", url))

    await asyncio.sleep(1.15)
    esourse = app[socket][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "data: foo\r\n\r\n" + ": ping\r\n\r\n"
    assert streamed_data == expected
    await runner.cleanup()


async def test_ping_reset(
    unused_tcp_port: int,
    session: ClientSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        app = request.app
        resp = EventSourceResponse()
        resp.ping_interval = 1
        await resp.prepare(request)
        await resp.send("foo")
        app[socket].append(resp)
        await resp.wait()
        return resp

    app = web.Application()
    app[socket] = []
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)
    url = f"http://127.0.0.1:{unused_tcp_port}/"

    resp_task = asyncio.create_task(session.request("GET", url))

    await asyncio.sleep(1.15)
    esource = app[socket][0]

    def reset_error_write(data: str) -> None:
        raise ConnectionResetError("Cannot write to closing transport")

    monkeypatch.setattr(esource, "write", reset_error_write)
    await esource.wait()

    assert esource._ping_task and esource._ping_task.cancelled()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "data: foo\r\n\r\n" + ": ping\r\n\r\n"
    assert streamed_data == expected
    await runner.cleanup()


async def test_context_manager(unused_tcp_port: int, session: ClientSession) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
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


class TestCustomResponseClass:
    async def test_subclass(self) -> None:
        class CustomEventSource(EventSourceResponse):
            pass

        request = make_mocked_request("GET", "/")
        await sse_response(request, response_cls=CustomEventSource)

    async def test_not_related_class(self) -> None:
        class CustomClass:
            pass

        request = make_mocked_request("GET", "/")
        with pytest.raises(TypeError):
            await sse_response(
                request=request,
                response_cls=CustomClass,  # type: ignore[type-var]
            )


@pytest.mark.parametrize("sep", ["\n", "\r", "\r\n"], ids=("LF", "CR", "CR+LF"))
async def test_custom_sep(
    unused_tcp_port: int, session: ClientSession, sep: str
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
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
async def test_multiline_data(
    unused_tcp_port: int,
    session: ClientSession,
    stream_sep: str,
    line_sep: str,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
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


class TestSSEState:
    async def test_context_states(
        self, unused_tcp_port: int, session: ClientSession
    ) -> None:
        async def func(request: web.Request) -> web.StreamResponse:
            async with sse_response(request) as resp:
                assert resp.is_connected()

            assert not resp.is_connected()
            return resp

        app = web.Application()
        app.router.add_route("GET", "/", func)

        host = "127.0.0.1"
        runner = await make_runner(app, host, unused_tcp_port)
        await session.request("GET", f"http://{host}:{unused_tcp_port}/")
        await runner.cleanup()

    async def test_not_prepared(self) -> None:
        response = EventSourceResponse()
        assert not response.is_connected()


async def test_connection_is_not_alive(
    unused_tcp_port: int,
    session: ClientSession,
) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        # within context manager first preparation is already done
        async with sse_response(request) as resp:
            resp.ping_interval = 1

            # we should sleep to switch asyncio Task
            # and let connection to be closed
            while resp.is_connected():
                await asyncio.sleep(0.01)

            # this call should be cancelled, cause connection is closed
            with pytest.raises(asyncio.CancelledError):
                await resp.prepare(request)

            return resp  # pragma: no cover

    app = web.Application()
    app.router.add_route("GET", "/", func)

    host = "127.0.0.1"
    runner = await make_runner(app, host, unused_tcp_port)

    async with session.get(f"http://{host}:{unused_tcp_port}/") as resp:
        assert resp.status == 200

    await runner.cleanup()


class TestLastEventId:
    async def test_success(self, unused_tcp_port: int, session: ClientSession) -> None:
        async def func(request: web.Request) -> web.StreamResponse:
            async with sse_response(request) as sse:
                assert sse.last_event_id is not None
                await sse.send(sse.last_event_id)
            return sse

        app = web.Application()
        app.router.add_route("GET", "/", func)

        host = "127.0.0.1"
        runner = await make_runner(app, host, unused_tcp_port)
        url = f"http://{host}:{unused_tcp_port}/"

        last_event_id = "42"
        headers = {EventSourceResponse.DEFAULT_LAST_EVENT_HEADER: last_event_id}
        resp = await session.request("GET", url, headers=headers)
        assert resp.status == 200

        # check streamed data
        streamed_data = await resp.text()
        assert streamed_data == f"data: {last_event_id}\r\n\r\n"
        await runner.cleanup()

    async def test_get_before_prepare(self) -> None:
        sse = EventSourceResponse()
        with pytest.raises(RuntimeError):
            _ = sse.last_event_id
