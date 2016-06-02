#!/usr/bin/env python3

import asyncio
import websockets
import message_pb2
import sys
import logging

if sys.version_info < (3,4,4):
    asyncio.ensure_future = asyncio.async

#logging.basicConfig(level=logging.DEBUG)
code = """
print("Hello!")
var = input("Enter some input: ")
print("You entered: ", var)
"""

class PrexTerm():
    def __init__(self):
        pass

    @asyncio.coroutine
    def run(self):
        try:
            websocket = yield from websockets.connect('ws://localhost:43000')
            self.ws_protocol = websocket

            message = message_pb2.PrexMessage()
            message.type = message_pb2.PrexMessage.LOAD_PROGRAM

            message_program = message_pb2.LoadProgram()
            message_program.filename = 'hello.py'
            message_program.code = code
            message.payload = message_program.SerializeToString()
            yield from websocket.send(message.SerializeToString())
            yield from self.consumer()
            websocket.close()
        except Exception as exc:
            raise

    @asyncio.coroutine
    def consumer(self):
        while True:
            try:
                payload = yield from self.ws_protocol.recv()
                logging.info('Received message.')
                msg = message_pb2.PrexMessage()
                msg.ParseFromString(payload)
                if msg.type == message_pb2.PrexMessage.IO:
                    io = message_pb2.Io()
                    io.ParseFromString(msg.payload)
                    print(io.data.decode())
            except websockets.exceptions.ConnectionClosed:
                return
    @asyncio.coroutine
    def send_io(self, data):
        message_data = message_pb2.Io()
        message_data.type = 0
        message_data.data = data.encode('UTF-8')

        message = message_pb2.PrexMessage()
        message.type = message_pb2.PrexMessage.IO
        message.payload = message_data.SerializeToString()
        yield from self.ws_protocol.send(message.SerializeToString())

    def got_user_input(self):
        asyncio.ensure_future(self.send_io(sys.stdin.readline()))
        

prex = PrexTerm()
loop = asyncio.get_event_loop()
loop.add_reader(sys.stdin, prex.got_user_input)
loop.run_until_complete(prex.run())
loop.close()

