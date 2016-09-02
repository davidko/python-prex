#!/usr/bin/env python3

import asyncio
import websockets
import prex.message_pb2 as message_pb2
import prex
import sys
import logging

if sys.version_info < (3,4,4):
    asyncio.ensure_future = asyncio.async

#logging.basicConfig(level=logging.DEBUG)
code = """
import linkbot3 as linkbot
linkbot.scatter_plot([0, 1], [0, 1])
channel = linkbot.PrexChannel()
channel.input("Enter some text:")
a = input("Enter some text:")
print(a)
"""

term = prex.SimpleTerm()
loop = asyncio.get_event_loop()
loop.add_reader(sys.stdin, term.got_user_input)
loop.run_until_complete(term.run('ws://localhost:43000', code))
loop.close()

