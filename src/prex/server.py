#!/usr/bin/env python3

__all__ = ['Server']

import asyncio
import functools
import logging
import os
import shutil
import sys
import tempfile
import websockets
from . import message_pb2

if sys.version_info < (3,4,4):
    asyncio.ensure_future = asyncio.async

class Server():
    @classmethod
    @asyncio.coroutine
    def create(cls, host='localhost', port=43000):
        self = cls()
        self.server = yield from websockets.serve(self.ws_handler, host, port)
        return self

    @asyncio.coroutine
    def ws_handler(self, protocol, uri):
        logging.info('Received connection: ' + uri)
        connection = _Connection(protocol, uri)
        yield from connection.consumer()
        
class _Connection():

    PROGRAM_TIMEOUT = 60*60 # Seconds to allow child programs to continue running

    def __init__(self, protocol, uri):
        self.protocol = protocol
        self.uri = uri

    @asyncio.coroutine
    def consumer(self):    
        while True:
            logging.info('Waiting for message...')
            try:
                message = yield from self.protocol.recv()
                yield from self.consumer_handler(message)
            except websockets.exceptions.ConnectionClosed:
                yield from self.handle_terminate(None)
                return
    
    @asyncio.coroutine
    def consumer_handler(self, payload):
        # Parse the message
        msg = message_pb2.PrexMessage()
        logging.info('Got a message: ' + str(msg.type) + str(payload))
        try:
            msg.ParseFromString(payload)
        except Exception:
            logging.warn('Could not parse incoming message...')
            yield from self.protocol.send('ERR: Invalid format')
            return

        handlers = {
            message_pb2.PrexMessage.LOAD_PROGRAM : self.handle_load_program,
            message_pb2.PrexMessage.IO : self.handle_io,
            message_pb2.PrexMessage.IMAGE : self.handle_image,
            message_pb2.PrexMessage.TERMINATE : self.handle_terminate,
        }

        yield from handlers[msg.type](msg.payload)
    
    @asyncio.coroutine   
    def handle_load_program(self, payload):
        obj = message_pb2.LoadProgram()
        obj.ParseFromString(payload)
        logging.info('Load program. Filename: ' + obj.filename) 
        logging.info('Code: ' + obj.code)
        logging.info('argv: ' + str(obj.argv))
        # Save the code to a temporary dir
        tmpdir = tempfile.mkdtemp()
        self.tmpdir = tmpdir
        filepath = os.path.join(tmpdir, obj.filename)
        logging.info('Opening temp file at:' + filepath)
        with open(filepath, 'w') as f:
            f.write(obj.code)
            f.flush()
            loop = asyncio.get_event_loop()
            exit_future = asyncio.Future()
            self.exit_future = exit_future
            logging.info('Starting subprocess...')
            args = ['/usr/bin/python3', filepath]
            for arg in obj.argv:
                args += [arg]
            create = loop.subprocess_exec(
                functools.partial(_ExecProtocol, exit_future, self.protocol),
                *args)
            self.exec_transport, self.exec_protocol = yield from create
            asyncio.ensure_future(self.check_program_end())

    @asyncio.coroutine
    def check_program_end(self):
        try:
            yield from asyncio.shield(
                asyncio.wait_for(self.exit_future, self.PROGRAM_TIMEOUT))
        except asyncio.TimeoutError:
            pass
        yield from self.protocol.close()
        shutil.rmtree(self.tmpdir)
        logging.info('Closed protocol, subprocess.')

    @asyncio.coroutine
    def handle_io(self, payload):
        obj = message_pb2.Io()
        obj.ParseFromString(payload)
        logging.info('Received IO from client: ' + str(obj.data))
        self.exec_transport.get_pipe_transport(0).write(obj.data)

    @asyncio.coroutine
    def handle_image(self, payload):
        pass

    @asyncio.coroutine
    def handle_terminate(self, payload):
        logging.info('Terminating process...')
        self.exec_transport.kill()

class _ExecProtocol(asyncio.SubprocessProtocol):
    def __init__(self, exit_future, ws_protocol):
        self.exit_future = exit_future
        self.ws_protocol = ws_protocol

    def pipe_data_received(self, fd, data):
        logging.info('Received pipe data from subprocess: ' + str(data))
        msg = message_pb2.Io()
        msg.type = fd
        msg.data = data
        packet = message_pb2.PrexMessage()
        packet.type = message_pb2.PrexMessage.IO
        packet.payload = msg.SerializeToString()
        asyncio.ensure_future(self.ws_protocol.send(packet.SerializeToString()))

    def process_exited(self):
        logging.info('Process exited.')
        self.exit_future.set_result(True)

@asyncio.coroutine
def run(host='localhost', port=43000):
    server = yield from Server.create(host, port)
    print('Server started: ', host, ':', port)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.run_forever()
    loop.close()
    
