#!/usr/bin/env python3

import os
import subprocess
import urllib.request

pb_files = [
    'proto/message.proto',
]
for f in pb_files:
    subprocess.check_call([
        #os.path.join(self.getdir(), 'generator-bin', 'protoc'),
        'protoc',
        '--proto_path=proto',
        '--python_out='+os.path.join('src', 'prex'),
        f ])

