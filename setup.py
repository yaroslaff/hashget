from setuptools import setup
import os

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='hashget',
    version='0.100',
    packages=['hashget'],
    scripts=['bin/hashget', 'bin/hashget-admin'],

    install_requires=['patool','filetype','filelock'],

    url='https://gitlab.com/yaroslaff/hashget',
    license='MIT',
    author='Yaroslav Polyakov',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    author_email='yaroslaff@gmail.com',
    description='hashget deduplication and compression tool'
)
