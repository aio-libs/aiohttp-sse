from collections.abc import Coroutine


class _ContextManager(Coroutine):

    __slots__ = ("_coro", "_obj")

    def __init__(self, coro):
        self._coro = coro
        self._obj = None

    def send(self, arg):
        return self._coro.send(arg)  # pragma: no cover

    def throw(self, arg):
        return self._coro.throw(arg)  # pragma: no cover

    def close(self):
        return self._coro.close()  # pragma: no cover

    @property
    def gi_frame(self):
        return self._coro.gi_frame  # pragma: no cover

    @property
    def gi_running(self):
        return self._coro.gi_running  # pragma: no cover

    @property
    def gi_code(self):
        return self._coro.gi_code  # pragma: no cover

    def __next__(self):
        return self.send(None)  # pragma: no cover

    def __await__(self):
        return self._coro.__await__()

    async def __aenter__(self):
        self._obj = await self._coro
        return await self._obj.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        await self._obj.__aexit__(exc_type, exc, tb)
