#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement

import os
import sys

from setuptools import setup

with open('mapmaker.py') as f:
    for line in f:
        if line.startswith('__version__'):
            VERSION = line.split('\'')[1]
            break

with open('requirements.txt') as f:
    required = f.readlines()

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='mapmaker',
    version=VERSION,
    author='Alexander Keil',
    author_email='alex@akeil.net',
    maintainer='Alexander Keil',
    url='http://github.com/akeil/mapmaker',
    project_urls={
        'Source': 'http://github.com/akeil/mapmaker',
        'Bug Reports': 'http://github.com/akeil/mapmaker/issues',
    },
    description='Create map images from slippy map tiles.',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    # single python file
    py_modules=['mapmaker'],
    install_requires=required,
    entry_points = {
        'console_scripts': [
            'mapmaker = mapmaker:main',
        ]
    },
    license='MIT',
    license_file = 'LICENSE.txt',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    keywords = 'osm, openstreetmap, tiles, map, image, cli',
    python_requires='>=3'
)
