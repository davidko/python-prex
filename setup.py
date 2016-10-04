#!/usr/bin/env python3

import codecs
import os
import re
from setuptools import setup
import sys

if sys.version_info < (3, 4, 2):
    raise Exception('Python 3.4.2 or higher is required to use prex.')

version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('src/prex/server.py').read(),
    re.M
    ).group(1)

here = os.path.abspath(os.path.dirname(__file__))
README = codecs.open(os.path.join(here, 'README.txt'), encoding='utf8').read()
setup (name = 'prex',
       author = 'David Ko',
       author_email = 'david@barobo.com',
       version = version, 
       description = "Execute Python scripts on a remote sandbox",
       long_description = README,
       package_dir = {'':'src'},
       packages = ['prex', ],
       scripts = ['bin/prex-server.py', 'bin/prex-image.py' ],
       url = 'http://github.com/BaroboRobotics/prex',
       install_requires=[
           'protobuf>=3.0.0',
           'websockets>=3.0.0',
           'pylinkbot3>=3.1.7',
           'psutil'],
       classifiers=[
           'Development Status :: 3 - Alpha',
           'Operating System :: OS Independent',
           'Programming Language :: Python :: 3.5',
       ],
)
