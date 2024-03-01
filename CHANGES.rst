=======
CHANGES
=======

.. towncrier release notes start

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
