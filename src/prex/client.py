#!/usr/bin/env python3

__all__ = ['SimpleTerm']

import asyncio
import websockets
import prex.message_pb2 as message_pb2
import sys
import logging

class SimpleTerm():
    def __init__(self):
        pass

    @asyncio.coroutine
    def run(self, uri, code="print('Hello, world!')", argv=[]):
        try:
            websocket = yield from websockets.connect(uri)
            self.ws_protocol = websocket

            message = message_pb2.PrexMessage()
            message.type = message_pb2.PrexMessage.LOAD_PROGRAM

            message_program = message_pb2.LoadProgram()
            message_program.filename = 'hello.py'
            message_program.code = code
            for arg in argv:
                new_arg = message_program.argv.append(arg)
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
                if msg.type == message_pb2.PrexMessage.IMAGE:
                    image = message_pb2.Image()
                    image.ParseFromString(msg.payload)
                    print('Received {} bytes of image data.'.format(len(image.payload)))
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
        