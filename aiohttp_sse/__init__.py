import asyncio
import io
from aiohttp.protocol import Response as ResponseImpl
from aiohttp.web import StreamResponse
from aiohttp.web import HTTPMethodNotAllowed

__version__ = '0.0.1'
__all__ = ['EventSourceResponse']


class EventSourceResponse(StreamResponse):

    DEFAULT_PING_INTERVAL = 15

    def __init__(self, *, status=200, reason=None, headers=None):
        super().__init__(status=status, reason=reason)

        if headers is not None:
            self.headers.extend(headers)

        self.headers['Content-Type'] = 'text/event-stream'
        self.headers['Cache-Control'] = 'no-cache'
        self.headers['Connection'] = 'keep-alive'

        self._loop = None
        self._finish_fut = None
        self._ping_interval = self.DEFAULT_PING_INTERVAL
        self._ping_task = None

    def enable_compression(self, force=False):
        raise NotImplementedError

    def send(self, data, id=None, event=None, retry=None):
        buffer = io.BytesIO()
        if id is not None:
            buffer.write('id: {0}\r\n'.format(id).encode('utf-8'))

        if event is not None:
            buffer.write('event: {0}\r\n'.format(event).encode('utf-8'))

        for chunk in data.split('\r\n'):
            buffer.write('data: {0}\r\n'.format(chunk).encode('utf-8'))

        if retry is not None:
            buffer.write('retry: {0}\r\n'.format(retry).encode('utf-8'))
        buffer.write(b'\r\n')
        self.write(buffer.getvalue())

    def start(self, request):
        if request.method != 'GET':
            raise HTTPMethodNotAllowed(request.method, ['GET'])

        self._loop = request.app.loop
        self._finish_fut = asyncio.Future(loop=self._loop)
        self._finish_fut.add_done_callback(self._cancel_ping)

        resp_impl = self._start_pre_check(request)
        if resp_impl is not None:
            return resp_impl

        self._req = request

        self._keep_alive = True
        resp_impl = self._resp_impl = ResponseImpl(
            request._writer,
            self._status,
            request.version,
            not self._keep_alive,
            self._reason)

        self._copy_cookies()

        headers = self.headers.items()
        for key, val in headers:
            resp_impl.add_header(key, val)

        resp_impl.send_headers()
        self._ping_task = asyncio.Task(self._ping(), loop=self._loop)
        return resp_impl

    @property
    def ping_interval(self):
        return self._ping_interval

    @ping_interval.setter
    def ping_interval(self, value):

        if not isinstance(value, int):
            raise TypeError("ping interval must be int")
        if value < 0:
            raise ValueError("ping interval must be greater then 0")

        self._ping_interval = value

    def _cancel_ping(self, fut):
        self._ping_task.cancel()

    def wait(self):
        if not self._finish_fut:
            raise RuntimeError('Response is not started')
        return self._finish_fut

    def stop_streaming(self):
        if not self._finish_fut:
            raise RuntimeError('Response is not started')
        self._finish_fut.set_result(None)

    @asyncio.coroutine
    def _ping(self):
        while True:
            yield from asyncio.sleep(self._ping_interval, loop=self._loop)
            self.write(b':ping\r\n\r\n')
