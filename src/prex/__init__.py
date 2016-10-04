#!/usr/bin/env python3

from .server import *
from .client import *
from . import message_pb2 
import asyncio

__all__ = server.__all__
__all__ += client.__all__

class PrexChannel():
    def __init__(self, host='localhost', port=None):
        self._loop = asyncio.get_event_loop()
        self.socket = None
        self._port = port
        self._host = host
        try:
            if self._port == None:
                self._port = os.environ['PREX_IPC_PORT']
            fut = asyncio.run_coroutine_threadsafe(self.connect(), self._loop)
            fut.result()
        except KeyError as e:
            raise RuntimeError('PREX_IPC_PORT not defined and no port specified.')

    @asyncio.coroutine
    def connect(self):
        if not self._port:
            raise RuntimeError(
                'No port was specified for the PREX communications channel. Perhaps the'
                'environment variable is not set?'
            )
        self.socket = yield from websockets.connect('ws://{}:{}'.format(self._host, self._port))

    def input(self, prompt):
        # Inform the PREX server that the remote process is now waiting for
        # user input.
        fut = asyncio.run_coroutine_threadsafe(self.__input(prompt), self._loop)
        fut.result()

    @asyncio.coroutine
    def __input(self, prompt):
        io = prex_pb.Io()
        io.type = prex_pb.Io.STDIN
        io.data = prompt.encode()
        msg = prex_pb.PrexMessage()
        msg.type = prex_pb.PrexMessage.IO
        msg.payload = io.SerializeToString()
        yield from self.socket.send(msg.SerializeToString())

    def image(self, data, format='SVG'):
        # Send image data back to the web app
        fut = asyncio.run_coroutine_threadsafe(self.__image(data, format), self._loop)
        fut.result()

    def __image(self, data, format='SVG'):
        image = prex_pb.Image()
        image.payload = data
        msg = prex_pb.PrexMessage()
        msg.type = prex_pb.PrexMessage.IMAGE
        msg.payload = image.SerializeToString()
        msg.format = format
        yield from self.socket.send(msg.SerializeToString())
