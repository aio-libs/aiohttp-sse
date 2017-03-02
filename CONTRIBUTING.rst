Contributing
============

Running Tests
-------------

.. _GitHub: https://github.com/aio-libs/aiohttp-sse

Thanks for your interest in contributing to ``aiohttp-sse``, there are multiple
ways and places you can contribute.

Fist of all just clone repository::

    $ git clone git@github.com:aio-libs/aiohttp-sse.git

Create virtualenv with python 3.5 or 3.6. For example
using *virtualenvwrapper* commands could look like::

   $ cd aiohttp-sse
   $ mkvirtualenv --python=`which python3.5` aiohttp-sse


After that please install libraries required for development::

    $ pip install -r requirements-dev.txt
    $ pip install -e .

Congratulations, you are ready to run the test suite::

    $ make cov

To run individual test use following command::

    $ py.test -sv tests/test_sse.py -k test_name


Reporting an Issue
------------------
If you have found issue with `aiohttp-sse` please do
not hesitate to file an issue on the GitHub_ project. When filing your
issue please make sure you can express the issue with a reproducible test
case.

When reporting an issue we also need as much information about your environment
that you can include. We never know what information will be pertinent when
trying narrow down the issue. Please include at least the following
information:

* Versions of `aiohttp-sse`, `aiohttp` and `python`.
* Platform you're running on (OS X, Linux).
