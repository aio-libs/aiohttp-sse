=======
CHANGES
=======

.. towncrier release notes start

3.0 (2026-10-11)
================

- Added ``send_timeout`` parameter to ``EventSourceResponse`` and ``sse_response()``
  so a stalled client can no longer block ``send()`` forever: a write that
  exceeds the timeout raises ``TimeoutError`` and aborts the connection. On
  Linux the timeout is also applied at the TCP level (``TCP_USER_TIMEOUT``),
  so a dead peer is detected even between sends as pings go unacknowledged.
  Defaults to 120 seconds; pass ``None`` to restore the previous unbounded
  behaviour.
- Disallow HTTP methods other than GET by default.
  Allowing other methods can be done by passing ``allow_all_methods`` to ``EventSourceResponse``.
  Note that SSE on browsers will only work with GET endpoints, this flag just serves as a
  reminder.
- Added ``ping_interval`` parameter to ``EventSourceResponse`` and ``sse_response()``
  for configuring the interval between keep-alive pings.
- Removed the ``EventSourceResponse.ping_interval`` property. The ping interval can
  now only be set via the ``ping_interval`` parameter when creating the response.
- ``send()`` now raises ``ValueError`` if the ``id`` or ``event`` fields contain
  line separators (or null characters for ``id``), instead of silently
  stripping them.
- ``send()`` now raises ``ValueError`` for a negative ``retry`` instead of
  sending a value that clients would ignore.
- ``sse_response()`` is now usable only as an async context manager; the
  ``resp = await sse_response(...)`` form has been removed. If ``async with`` must be
  avoided for some reason, use something like ``contextlib.AsyncExitStack``.
- Dropped support for Python 3.8, 3.9 and 3.10; added support for Python 3.13,
  3.14 and 3.15.

2.2.0 (2024-02-29)
==================

- Added typing support.
- Added ``EventSourceResponse.is_connected()`` method.
- Added ``EventSourceResponse.last_event_id`` attribute.
- Added support for SSE with HTTP methods other than GET.
- Added support for float ping intervals.
- Fixed (on Python 3.11+) ``EventSourceResponse.wait()`` swallowing user cancellation.
- Fixed ping task not getting cancelled after a send failure.
- Cancelled the ping task when a connection error occurs to help avoid errors.
- Dropped support for Python 3.7 while adding support upto Python 3.12.

2.1.0 (2021-11-13)
==================

Features
--------

- Added Python 3.10 support (`#314 <https://github.com/aio-libs/aiohttp-sse/issues/314>`_)


Deprecations and Removals
-------------------------

- Drop Python 3.6 support (`#319 <https://github.com/aio-libs/aiohttp-sse/issues/319>`_)


Misc
----

- `#163 <https://github.com/aio-libs/aiohttp-sse/issues/163>`_


2.0.0 (2018-02-19)
==================

- Drop aiohttp < 3 support
- ``EventSourceResponse.send`` is now a coroutine.

1.1.0 (2017-08-21)
==================

- Drop python 3.4 support
- Add new context manager API


1.0.0 (2017-04-14)
==================

- Release aiohttp-sse==1.0.0


0.1.0 (2017-03-23)
==================

- add support for asynchronous context manager interface
- tests refactoring
- modernize internal api to align with aiohttp


0.0.2 (2017-01-13)
==================

- Added MANIFEST.in


0.0.1 (2017-01-13)
==================

- Initial release
