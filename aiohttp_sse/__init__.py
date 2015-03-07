import asyncio
from aiohttp import hdrs
from aiohttp.protocol import Response as ResponseImpl
from aiohttp.web import StreamResponse
from aiohttp.web import HTTPMethodNotAllowed

__version__ = '0.0.1'
__all__ = ['EventSourceResponse']


class EventSourceResponse(StreamResponse):

    PING_TIME = 15

    def __init__(self, *, status=200, reason=None, headers=None):
        super().__init__(status=status, reason=reason)

        if headers is not None:
            self.headers.extend(headers)

        self.headers['Content-Type'] = 'text/event-stream'
        self.headers['Cache-Control'] = 'no-cache'
        self.headers['Connection'] = 'keep-alive'

        self._loop = None
        self._finish_fut = None
        self._ping_task = None

    def send(self, data, id=None, event=None, retry=None):

        if id is not None:
            self.write('id: {0}\n'.format(id).encode('utf-8'))

        if event is not None:
            self.write('event: {0}\n'.format(event).encode('utf-8'))

        for chunk in data.split('\n'):
            self.write('data: {0}\n'.format(chunk).encode('utf-8'))

        if retry is not None:
            self.write('retry: {0}\n'.format(retry).encode('utf-8'))

        self.write(b'\n')

    def start(self, request):
        if request.method != 'GET':
            raise HTTPMethodNotAllowed()

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

        if self._compression:
            if (self._compression_force or
                    'deflate' in request.headers.get(
                        hdrs.ACCEPT_ENCODING, '')):
                resp_impl.add_compression_filter()

        if self._chunked:
            resp_impl.enable_chunked_encoding()
            if self._chunk_size:
                resp_impl.add_chunking_filter(self._chunk_size)

        headers = self.headers.items()
        for key, val in headers:
            resp_impl.add_header(key, val)

        resp_impl.send_headers()
        self._ping_task = asyncio.Task(self._ping(), loop=self._loop)
        return resp_impl

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
            yield from asyncio.sleep(self.PING_TIME, loop=self._loop)
            if self._finish_fut.done():
                break
            self.write(b':ping\n\n')
