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
    author='akeil',
    url='http://github.com/akeil/mapmaker',
    description='Create map images from slippy map tiles.',
    long_description=long_description,
    py_modules=['mapmaker'],
    install_requires=required,
    entry_points = {
        'console_scripts': [
            'mapmaker = mapmaker:main',
        ]
    },
    license='???',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.2',
    ],
)
