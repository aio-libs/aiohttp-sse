import asyncio
import io
from aiohttp.protocol import Response as ResponseImpl
from aiohttp.web import StreamResponse
from aiohttp.web import HTTPMethodNotAllowed

__version__ = '0.0.2'
__all__ = ['EventSourceResponse']


class EventSourceResponse(StreamResponse):
    """This object could be used as regular aiohttp response for
    streaming data to client, usually browser with EventSource::

        @asyncio.coroutine
        def hello(request):
            # create response object
            resp = EventSourceResponse()
            # prepare and send headers
            resp.start(request)
            # stream data
            resp.send('foo')
            return resp
    """

    DEFAULT_PING_INTERVAL = 15

    def __init__(self, *, status=200, reason=None, headers=None):
        super().__init__(status=status, reason=reason)

        if headers is not None:
            self.headers.extend(headers)

        # mandatory for servers-sent events headers
        self.headers['Content-Type'] = 'text/event-stream'
        self.headers['Cache-Control'] = 'no-cache'
        self.headers['Connection'] = 'keep-alive'

        self._loop = None
        self._finish_fut = None
        self._ping_interval = self.DEFAULT_PING_INTERVAL
        self._ping_task = None

    def start(self, request):
        """Prepare for streaming and send HTTP headers.

        :param request: regular aiohttp.web.Request.
        """
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
            close=not self._keep_alive,
            reason=self._reason)

        # explicitly enabling chunked encoding, since content length
        # usually not known beforehand.
        self._chunked = True
        resp_impl.enable_chunked_encoding()

        headers = self.headers.items()
        for key, val in headers:
            resp_impl.add_header(key, val)

        resp_impl.send_headers()
        self._ping_task = asyncio.Task(self._ping(), loop=self._loop)
        return resp_impl

    def send(self, data, id=None, event=None, retry=None):
        """Send data using EventSource protocol

        :param str data: The data field for the message.
        :param str id: The event ID to set the EventSource object's last
            event ID value to.
        :param str event: The event's type. If this is specified, an event will
            be dispatched on the browser to the listener for the specified
            event name; the web site would use addEventListener() to listen
            for named events. The default event type is "message".
        :param int retry: The reconnection time to use when attempting to send
            the event. [What code handles this?] This must be an integer,
            specifying the reconnection time in milliseconds. If a non-integer
            value is specified, the field is ignored.
        """
        buffer = io.BytesIO()
        if id is not None:
            buffer.write('id: {0}\r\n'.format(id).encode('utf-8'))

        if event is not None:
            buffer.write('event: {0}\r\n'.format(event).encode('utf-8'))

        for chunk in data.split('\r\n'):
            buffer.write('data: {0}\r\n'.format(chunk).encode('utf-8'))

        if retry is not None:
            if not isinstance(retry, int):
                raise TypeError('retry argument must be int')
            buffer.write('retry: {0}\r\n'.format(retry).encode('utf-8'))

        buffer.write(b'\r\n')
        self.write(buffer.getvalue())

    def wait(self):
        """EventSourceResponse object is used for streaming data to the client,
        this method returns future, so we can wain until connection will
        be closed or other task explicitly call ``stop_streaming`` method.
        """
        if not self._finish_fut:
            raise RuntimeError('Response is not started')
        return self._finish_fut

    def stop_streaming(self):
        """Used in conjunction with ``wait`` could be called from other task
        to notify client that server no longer wants to stream anything.
        """
        if not self._finish_fut:
            raise RuntimeError('Response is not started')
        self._finish_fut.set_result(None)

    def enable_compression(self, force=False):
        raise NotImplementedError

    @property
    def ping_interval(self):
        """Time interval between two ping massages"""
        return self._ping_interval

    @ping_interval.setter
    def ping_interval(self, value):
        """Setter for ping_interval property.

        :param int value: interval in sec between two ping values.
        """

        if not isinstance(value, int):
            raise TypeError("ping interval must be int")
        if value < 0:
            raise ValueError("ping interval must be greater then 0")

        self._ping_interval = value

    def _cancel_ping(self, fut):
        # task with connection was canceled or user called ``stop_streaming``
        # method, this callback will cancel ping task so we will not have
        # pending task related errors, like trying to write into closed socket.
        self._ping_task.cancel()

    @asyncio.coroutine
    def _ping(self):
        # periodically send ping to the browser. Any message that
        # starts with ":" colon ignored by a browser and could be used
        # as ping message.
        while True:
            yield from asyncio.sleep(self._ping_interval, loop=self._loop)
            self.write(b': ping\r\n\r\n')
