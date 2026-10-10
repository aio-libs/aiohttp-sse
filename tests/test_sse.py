import asyncio
import pathlib
import socket as sock_mod

import aiohttp
import pytest
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import make_mocked_request

from aiohttp_sse import EventSourceResponse, sse_response

socket = web.AppKey("socket", list[EventSourceResponse])


@pytest.mark.parametrize(
    "with_sse_response",
    (False, True),
    ids=("without_sse_response", "with_sse_response"),
)
async def test_func(with_sse_response: bool, aiohttp_client: AiohttpClient) -> None:
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

    client = await aiohttp_client(app)
    resp = await client.get("/")
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


async def test_wait_stop_streaming(aiohttp_client: AiohttpClient) -> None:
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

    client = await aiohttp_client(app)
    resp_task = asyncio.create_task(client.get("/"))

    await asyncio.sleep(0.1)
    esourse = app[socket][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "id: xyz\r\nevent: bar\r\ndata: foo\r\nretry: 1\r\n\r\n"
    assert streamed_data == expected


async def test_retry(aiohttp_client: AiohttpClient) -> None:
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

    client = await aiohttp_client(app)
    resp = await client.get("/")
    assert 200 == resp.status

    # check streamed data
    streamed_data = await resp.text()
    expected = "data: foo\r\nretry: 1\r\n\r\n"
    assert streamed_data == expected


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
    @pytest.mark.parametrize("value", (25, 25.0, 0), ids=("int", "float", "zero int"))
    def test_success(self, value: float) -> None:
        response = EventSourceResponse()
        response.ping_interval = value
        assert response.ping_interval == value

    @pytest.mark.parametrize("value", [None, "foo"], ids=("None", "str"))
    def test_wrong_type(self, value: float) -> None:
        response = EventSourceResponse()
        with pytest.raises(TypeError) as ctx:
            response.ping_interval = value

        assert ctx.match("ping interval must be int or float")

    def test_negative_int(self) -> None:
        response = EventSourceResponse()
        with pytest.raises(ValueError) as ctx:
            response.ping_interval = -42

        assert ctx.match("ping interval must be greater then 0")

    def test_default_value(self) -> None:
        response = EventSourceResponse()
        assert response.ping_interval == response.DEFAULT_PING_INTERVAL


async def test_ping(aiohttp_client: AiohttpClient) -> None:
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

    client = await aiohttp_client(app)
    resp_task = asyncio.create_task(client.get("/"))

    await asyncio.sleep(1.15)
    esourse = app[socket][0]
    esourse.stop_streaming()
    await esourse.wait()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "data: foo\r\n\r\n" + ": ping\r\n\r\n"
    assert streamed_data == expected


async def test_ping_reset(
    aiohttp_client: AiohttpClient,
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

    client = await aiohttp_client(app)
    resp_task = asyncio.create_task(client.get("/"))

    await asyncio.sleep(1.15)
    esource = app[socket][0]

    def reset_error_write(data: str) -> None:
        raise ConnectionResetError("Cannot write to closing transport")

    assert esource._ping_task
    assert not esource._ping_task.done()
    monkeypatch.setattr(esource, "write", reset_error_write)
    await esource.wait()

    assert esource._ping_task.done()
    resp = await resp_task

    assert 200 == resp.status
    streamed_data = await resp.text()

    expected = "data: foo\r\n\r\n" + ": ping\r\n\r\n"
    assert streamed_data == expected


async def test_ping_auto_close(aiohttp_client: AiohttpClient) -> None:
    """Test ping task automatically closed on send failure."""

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request) as sse:
            sse.ping_interval = 999

            request.protocol.force_close()
            with pytest.raises(ConnectionResetError):
                await sse.send("never-should-be-delivered")

            assert sse._ping_task is not None
            assert sse._ping_task.cancelled()

        return sse  # pragma: no cover

    app = web.Application()
    app.router.add_route("GET", "/", handler)

    client = await aiohttp_client(app)

    async with client.get("/") as response:
        assert 200 == response.status


async def test_context_manager(aiohttp_client: AiohttpClient) -> None:
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

    client = await aiohttp_client(app)
    resp = await client.get("/")
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
async def test_custom_sep(aiohttp_client: AiohttpClient, sep: str) -> None:
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

    client = await aiohttp_client(app)
    resp = await client.get("/")
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
    aiohttp_client: AiohttpClient,
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

    client = await aiohttp_client(app)
    resp = await client.get("/")
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


class TestSSEState:
    async def test_context_states(self, aiohttp_client: AiohttpClient) -> None:
        async def func(request: web.Request) -> web.StreamResponse:
            async with sse_response(request) as resp:
                assert resp.is_connected()

            assert not resp.is_connected()
            return resp

        app = web.Application()
        app.router.add_route("GET", "/", func)

        client = await aiohttp_client(app)
        resp = await client.get("/")
        assert resp.status == 200

    async def test_not_prepared(self) -> None:
        response = EventSourceResponse()
        assert not response.is_connected()


async def test_connection_is_not_alive(aiohttp_client: AiohttpClient) -> None:
    async def func(request: web.Request) -> web.StreamResponse:
        # within context manager first preparation is already done
        async with sse_response(request) as sse:
            request.protocol.force_close()

            # this call should be cancelled, cause connection is closed
            with pytest.raises(asyncio.CancelledError):
                await sse.prepare(request)

            return sse  # pragma: no cover

    app = web.Application()
    app.router.add_route("GET", "/", func)

    client = await aiohttp_client(app)
    async with client.get("/") as resp:
        assert resp.status == 200


class TestLastEventId:
    async def test_success(self, aiohttp_client: AiohttpClient) -> None:
        async def func(request: web.Request) -> web.StreamResponse:
            async with sse_response(request) as sse:
                assert sse.last_event_id is not None
                await sse.send(sse.last_event_id)
            return sse

        app = web.Application()
        app.router.add_route("GET", "/", func)

        client = await aiohttp_client(app)
        async with client.get("/") as resp:
            assert resp.status == 200

        last_event_id = "42"
        headers = {EventSourceResponse.DEFAULT_LAST_EVENT_HEADER: last_event_id}
        async with client.get("/", headers=headers) as resp:
            assert resp.status == 200

            # check streamed data
            streamed_data = await resp.text()
            assert streamed_data == f"data: {last_event_id}\r\n\r\n"

    async def test_get_before_prepare(self) -> None:
        sse = EventSourceResponse()
        with pytest.raises(RuntimeError):
            _ = sse.last_event_id


@pytest.mark.parametrize(
    "http_method",
    ("GET", "POST", "PUT", "DELETE", "PATCH"),
)
async def test_http_methods(aiohttp_client: AiohttpClient, http_method: str) -> None:
    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request) as sse:
            await sse.send("foo")
        return sse

    app = web.Application()
    app.router.add_route(http_method, "/", handler)

    client = await aiohttp_client(app)
    async with client.request(http_method, "/") as resp:
        assert resp.status == 200
        # check streamed data
        streamed_data = await resp.text()

    assert streamed_data == "data: foo\r\n\r\n"


async def test_cancelled_not_swallowed(aiohttp_client: AiohttpClient) -> None:
    """Test asyncio.CancelledError is not swallowed by .wait().

    Relates to:
    https://github.com/aio-libs/aiohttp-sse/issues/458
    """

    async def endless_task(sse: EventSourceResponse) -> None:
        while True:
            await sse.wait()

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request) as sse:
            task = asyncio.create_task(endless_task(sse))
            await asyncio.sleep(0)
            task.cancel()
            await task

        return sse  # pragma: no cover

    app = web.Application()
    app.router.add_route("GET", "/", handler)

    client = await aiohttp_client(app)

    async with client.get("/") as response:
        assert 200 == response.status


@pytest.mark.parametrize("timeout", (None, 0.1))
async def test_with_timeout(
    aiohttp_client: AiohttpClient,
    timeout: float | None,
) -> None:
    """Test that a timeout occurs when client is not reading responses."""
    timeout_raised = False
    should_raise_timeout = timeout is not None

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request, send_timeout=timeout) as sse:
            while True:
                # .send() only yields if socket is full, so yield here to run client.
                await asyncio.sleep(0)
                try:
                    await sse.send("x" * 10000000)  # Enough data to fill socket
                except TimeoutError:
                    nonlocal timeout_raised
                    timeout_raised = True
                    break

        assert False

    app = web.Application()
    app.router.add_route("GET", "/", handler)

    client = await aiohttp_client(app)
    async with client.get("/") as resp:
        assert resp.status == 200
        await asyncio.sleep(0.5)
        assert timeout_raised is should_raise_timeout


async def test_ping_timeout(aiohttp_client: AiohttpClient) -> None:
    """Test that a ping write timeout aborts a stalled connection."""

    async def handler(request: web.Request) -> EventSourceResponse:
        # Huge separator makes the ping message itself fill the socket.
        sep = "\r\n" + " " * 10_000_000
        async with sse_response(request, sep=sep, send_timeout=0.1) as sse:
            sse.ping_interval = 0.01
            # Returns once the timed-out ping stops the stream. The test
            # server then cancels the handler (handler_cancellation=True),
            # so nothing after this await is reachable under test.
            await sse.wait()
        assert False

    app = web.Application()
    app.router.add_route("GET", "/", handler)

    client = await aiohttp_client(app)
    async with client.get("/") as resp:
        assert resp.status == 200
        await asyncio.sleep(0.5)  # Let the server stall on a ping and time out.
        # The server must have aborted the connection; otherwise reading
        # would stream pings forever (bounded here by the timeout below).
        with pytest.raises(aiohttp.ClientPayloadError):
            async with asyncio.timeout(5):
                await resp.content.read(-1)


async def test_abort_when_transport_already_gone() -> None:
    """A timeout can race a disconnect; cleanup must cope without a transport.

    Uses a plain AppRunner because TestServer enables handler_cancellation,
    which would cancel the handler at the moment of disconnect.
    """
    aborted = asyncio.Event()

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request, send_timeout=10) as sse:
            # Wait for connection_lost to clear the transport.
            while request.protocol.transport is not None:
                await asyncio.sleep(0.01)
            # Same state as a timeout firing in the window where the
            # peer already disconnected: no transport left to abort.
            sse._abort_transport()
            # Restore is equally safe once the socket is closed.
            sse._restore_tcp_user_timeout()
            aborted.set()
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        await reader.readuntil(b"\r\n\r\n")  # Response headers received.
        writer.close()
        await writer.wait_closed()
        async with asyncio.timeout(5):
            await aborted.wait()
    finally:
        await runner.cleanup()


@pytest.mark.skipif(
    not hasattr(sock_mod, "TCP_USER_TIMEOUT"),
    reason="TCP_USER_TIMEOUT is Linux-only",
)
async def test_tcp_user_timeout_set(aiohttp_client: AiohttpClient) -> None:
    """send_timeout is mirrored into TCP_USER_TIMEOUT for kernel detection.

    The asyncio-level timeout only fires once enough data queues to block
    on flow control; TCP_USER_TIMEOUT detects a hung peer as soon as any
    write (e.g. a ping) goes unacknowledged for the same duration.
    """
    value = None

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request, send_timeout=2.5) as sse:
            assert request.transport is not None
            sock = request.transport.get_extra_info("socket")
            nonlocal value
            value = sock.getsockopt(sock_mod.IPPROTO_TCP, sock_mod.TCP_USER_TIMEOUT)
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", handler)

    client = await aiohttp_client(app)
    async with client.get("/") as resp:
        assert resp.status == 200
    assert value == 2500


@pytest.mark.skipif(
    not hasattr(sock_mod, "TCP_USER_TIMEOUT"),
    reason="TCP_USER_TIMEOUT is Linux-only",
)
async def test_tcp_user_timeout_aborts_hung_client() -> None:
    """The kernel aborts a hung connection long before buffers fill.

    The client's receive window is shrunk so it exhausts after a few KB,
    while the server writes less than aiohttp's 64KiB flow-control limit:
    send() returns immediately and no asyncio timer is ever pending, so
    only TCP_USER_TIMEOUT (zero-window handling, Linux 5.1+) can detect
    the hung peer.  Without the sockopt this test times out.

    Uses a plain AppRunner so the handler survives the disconnect
    (TestServer enables handler_cancellation).
    """
    loop = asyncio.get_running_loop()
    woke = asyncio.Event()

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request, send_timeout=1) as sse:
            sse.ping_interval = 0.1
            # Over the client's tiny receive window, under the 64KiB
            # high-water mark, so send() does not block on flow control.
            await sse.send("x" * 48_000)
            # Woken by the ping task ending when the kernel aborts.
            await sse.wait()
            woke.set()
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", handler)
    runner = web.AppRunner(app, shutdown_timeout=1)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    try:
        # Must be set before connect to cap the advertised window.
        # By reducing the client buffer, we can ensure the stall appears due to
        # the client not accepting any more data once the buffer is full.
        sock.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_RCVBUF, 4096)
        sock.setblocking(False)
        await loop.sock_connect(sock, ("127.0.0.1", port))
        await loop.sock_sendall(sock, b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await loop.sock_recv(sock, 1024)  # Headers; then never read again.
        # send_timeout=1 plus one retransmission backoff; generous margin.
        async with asyncio.timeout(5):
            await woke.wait()
    finally:
        sock.close()
        await runner.cleanup()


@pytest.mark.skipif(
    not hasattr(sock_mod, "AF_UNIX"),
    reason="Unix sockets unavailable",
)
async def test_unix_socket(tmp_path: pathlib.Path) -> None:
    """SSE over a Unix socket works: TCP_USER_TIMEOUT must not be applied."""

    async def handler(request: web.Request) -> EventSourceResponse:
        async with sse_response(request) as sse:  # Default send_timeout.
            await sse.send("hi")
        return sse

    app = web.Application()
    app.router.add_route("GET", "/", handler)
    runner = web.AppRunner(app, shutdown_timeout=1)
    await runner.setup()
    path = str(tmp_path / "sse.sock")
    await web.UnixSite(runner, path).start()

    try:
        connector = aiohttp.UnixConnector(path=path)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("http://localhost/") as resp:
                assert resp.status == 200
                assert await resp.text() == "data: hi\r\n\r\n"
    finally:
        await runner.cleanup()


@pytest.mark.skipif(
    not hasattr(sock_mod, "TCP_USER_TIMEOUT"),
    reason="TCP_USER_TIMEOUT is Linux-only",
)
async def test_tcp_user_timeout_restored_on_keepalive_reuse(
    aiohttp_client: AiohttpClient,
) -> None:
    seen = []

    def record(request: web.Request) -> None:
        assert request.transport is not None
        sock = request.transport.get_extra_info("socket")
        seen.append(
            (
                sock.getpeername(),
                sock.getsockopt(sock_mod.IPPROTO_TCP, sock_mod.TCP_USER_TIMEOUT),
            )
        )

    async def sse_handler(request: web.Request) -> EventSourceResponse:
        assert request.transport is not None
        # Simulate a value inherited from the listening socket.
        request.transport.get_extra_info("socket").setsockopt(
            sock_mod.IPPROTO_TCP, sock_mod.TCP_USER_TIMEOUT, 7000
        )
        async with sse_response(request, send_timeout=1) as sse:
            record(request)
            await sse.send("x")
        return sse

    async def plain_handler(request: web.Request) -> web.Response:
        record(request)
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_route("GET", "/first", sse_handler)
    app.router.add_route("GET", "/second", plain_handler)

    client = await aiohttp_client(app)
    async with client.get("/first") as resp:
        await resp.text()
    async with client.get("/second") as resp:
        await resp.text()

    (peer1, timeout1), (peer2, timeout2) = seen
    assert peer1 == peer2  # Same connection, or the test proves nothing.
    assert timeout1 == 1000  # Active during the SSE stream.
    assert timeout2 == 7000  # Original value restored for the next request.
