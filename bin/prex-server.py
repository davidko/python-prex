#!/usr/bin/env python3

import asyncio
import prex
import argparse
import logging

logging.basicConfig(level=logging.DEBUG)
#asyncio.get_event_loop().set_debug(True)

parser = argparse.ArgumentParser()
parser.add_argument("--host", help="specify the hostname the server should bind to")
parser.add_argument("--port", help="spcefiy the port the server should bind to", type=int)

args = parser.parse_args()

if args.host:
    hostname = args.host
else:
    hostname = 'localhost'

if args.port:
    port = args.port
else:
    port = 43000

loop = asyncio.get_event_loop()
loop.run_until_complete(prex.server.run(hostname, port))
loop.run_forever()
loop.close()
