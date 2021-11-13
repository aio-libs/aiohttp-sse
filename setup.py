import ast
import codecs
import os
import sys

from setuptools import find_packages, setup

PY_VER = sys.version_info

if not PY_VER >= (3, 5):
    raise RuntimeError("aiohttp-sse doesn't support Python earlier than 3.5")


def read(f):
    with codecs.open(
        os.path.join(os.path.dirname(__file__), f), encoding="utf-8"
    ) as ofile:
        return ofile.read()


class VersionFinder(ast.NodeVisitor):
    def __init__(self):
        self.version = None

    def visit_Assign(self, node):
        if not self.version:
            if node.targets[0].id == "__version__":
                self.version = node.value.s


def read_version():
    init_py = os.path.join(os.path.dirname(__file__), "aiohttp_sse", "__init__.py")
    finder = VersionFinder()
    finder.visit(ast.parse(read(init_py)))
    if finder.version is None:
        msg = "Cannot find version in aiohttp_sse/__init__.py"
        raise RuntimeError(msg)
    return finder.version


install_requires = ["aiohttp>=3.0"]


setup(
    name="aiohttp-sse",
    version=read_version(),
    description=("Server-sent events  support for aiohttp."),
    lond_description=read("README.rst"),
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: WWW/HTTP",
        "Framework :: AsyncIO",
    ],
    author="Nikolay Novik",
    author_email="nickolainovik@gmail.com",
    url="https://github.com/aio-libs/aiohttp_sse/",
    license="Apache 2",
    python_requires=">=3.7",
    packages=find_packages(),
    install_requires=install_requires,
    include_package_data=True,
)
