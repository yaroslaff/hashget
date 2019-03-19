#!/usr/bin/env python3

from setuptools import setup
import os
import sys

# check if we run under python 3+
if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 4):
    raise ValueError('Need python 3.4 or higher')


# all this magic just to import one symbol __version__ without loading whole module itself
import types
import importlib.machinery
loader = importlib.machinery.SourceFileLoader('ver', 'hashget/version.py')
vermod = types.ModuleType(loader.name)
loader.exec_module(vermod)

sys.path.insert(0, '.')


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='hashget',
    version=vermod.__version__,
    packages=['hashget'],
    scripts=['bin/hashget', 'bin/hashget-admin'],

    install_requires=['patool','filetype','filelock','setuptools', 'requests'],

    url='https://gitlab.com/yaroslaff/hashget',
    license='MIT',
    author='Yaroslav Polyakov',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    author_email='yaroslaff@gmail.com',
    description='hashget deduplication and compression tool',

    python_requires='>=3',
    classifiers=[
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Pick your license as you wish (should match "license" above)
         'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
)
