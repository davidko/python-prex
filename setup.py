#!/usr/bin/env python3

import codecs
import os
from setuptools import setup
import sys

if sys.version_info < (3, 4, 2):
    raise Exception('Python 3.4.2 or higher is required to use prex.')

here = os.path.abspath(os.path.dirname(__file__))
README = codecs.open(os.path.join(here, 'README.txt'), encoding='utf8').read()
setup (name = 'prex',
       author = 'David Ko',
       author_email = 'david@barobo.com',
       version = '0.0.1',
       description = "Execute Python scripts on a remote sandbox",
       long_description = README,
       package_dir = {'':'src'},
       packages = ['prex', ],
       scripts = ['bin/prex-server.py', ],
       url = 'http://github.com/BaroboRobotics/prex',
       install_requires=[
           'protobuf==3.0.0b3',
           'websockets>=3',],
       classifiers=[
           'Development Status :: 3 - Alpha',
           'Operating System :: OS Independent',
           'Programming Language :: Python :: 3.5',
       ],
)
