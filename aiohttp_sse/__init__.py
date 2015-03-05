__version__ = '0.0.1'

import aiohttp
from aiohttp.web import StreamResponse
from aiohttp.protocol import Response as ResponseImpl
from aiohttp import hdrs


class EventSourceResponse(StreamResponse):

    def __init__(self, *, status=200, reason=None, headers=None):
        super().__init__(status=status, reason=reason)

        if headers is not None:
            self.headers.extend(headers)

        self.headers.add('Content-Type', 'text/event-stream')
        self.headers.add('Cache-Control', 'no-cache')
        self.headers.add('Connection', 'keep-alive')

    def send(self, data, id=None, event=None, retry=None):

        if retry is not None:
            self.write('retry: {0}\n'.format(retry).encode('utf-8'))
        if id is not None:
            self.write('id: {0}\n'.format(id).encode('utf-8'))

        if event is not None:
            self.write('event: {0}\n'.format(event).encode('utf-8'))

        for chunk in data.split('\n'):
            self.write('data: {0}\n'.format(chunk).encode('utf-8'))
        self.write(b'\n')

    def start(self, request):
        resp_impl = self._start_pre_check(request)
        if resp_impl is not None:
            return resp_impl

        self._req = request
        keep_alive = self._keep_alive

        resp_impl = self._resp_impl = ResponseImpl(
            request._writer,
            self._status,
            request.version,
            not keep_alive,
            self._reason)

        self._copy_cookies()

        if self._compression:
            if (self._compression_force or
                    'deflate' in request.headers.get(
                        hdrs.ACCEPT_ENCODING, '')):
                resp_impl.add_compression_filter()

        headers = self.headers.items()
        for key, val in headers:
            resp_impl.add_header(key, val)

        resp_impl.send_headers()
        return resp_impl
