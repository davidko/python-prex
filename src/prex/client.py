#!/usr/bin/env python3

import asyncio
import websockets
import message_pb2
import sys
import logging

logging.basicConfig(level=logging.DEBUG)
code = """
print("Hello!")
var = input("Enter some input: ")
print("You entered: ", var)
"""

class PrexTerm():
    def __init__(self):
        pass

    async def hello(self):
        async with websockets.connect('ws://localhost:43000') as websocket:
            self.ws_protocol = websocket

            message = message_pb2.PrexMessage()
            message.type = message_pb2.PrexMessage.LOAD_PROGRAM

            message_program = message_pb2.LoadProgram()
            message_program.filename = 'hello.py'
            message_program.code = code
            message.payload = message_program.SerializeToString()
            await websocket.send(message.SerializeToString())
            await self.consumer()

    async def consumer(self):
        while True:
            try:
                payload = await self.ws_protocol.recv()
                logging.info('Received message.')
                msg = message_pb2.PrexMessage()
                msg.ParseFromString(payload)
                if msg.type == message_pb2.PrexMessage.IO:
                    io = message_pb2.Io()
                    io.ParseFromString(msg.payload)
                    print(io.data)
            except websockets.exceptions.ConnectionClosed:
                return

    async def send_io(self, data):
        message_data = message_pb2.Io()
        message_data.type = 0
        message_data.data = data.encode('UTF-8')

        message = message_pb2.PrexMessage()
        message.type = message_pb2.PrexMessage.IO
        message.payload = message_data.SerializeToString()
        await self.ws_protocol.send(message.SerializeToString())

    def got_user_input(self):
        asyncio.ensure_future(self.send_io(sys.stdin.readline()))
        

prex = PrexTerm()
loop = asyncio.get_event_loop()
loop.add_reader(sys.stdin, prex.got_user_input)
loop.run_until_complete(prex.hello())
loop.close()

