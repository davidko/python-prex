#!/usr/bin/env python3

__all__ = ['Server']

__version__ = "0.2.0"

import asyncio
import functools
import linkbot3 as linkbot
import logging
import os
import psutil
import shutil
import subprocess
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
        self.connections = {}
        # The process queue is in change of starting processes in a serial
        # manner so that the dongles aren't suddenly overloaded.
        self.process_queue = asyncio.Queue()
        # start the queue pump
        asyncio.ensure_future(self.process_queue_pump())
        
        return self

    @asyncio.coroutine
    def ws_handler(self, protocol, uri):
        logging.info('Received connection: ' + str(protocol.remote_address))
        connection = _Connection(self, protocol, uri)
        self.connections[protocol.remote_address] = connection
        yield from connection.consumer()

    @asyncio.coroutine
    def process_queue_pump(self):
        while True:
            process_future = yield from self.process_queue.get()
            process_future.set_result(True)
            yield from asyncio.sleep(0.5)
        
class _Connection():

    PROGRAM_TIMEOUT = 60*60 # Seconds to allow child programs to continue running

    def __init__(self, server, protocol, uri):
        self._server = server
        self.protocol = protocol
        self.uri = uri
        self.exec_transport = None

    @asyncio.coroutine
    def consumer(self):    
        while True:
            logging.info('Waiting for message...')
            try:
                message = yield from self.protocol.recv()
                yield from self.consumer_handler(message)
            except websockets.exceptions.ConnectionClosed:
                yield from self.handle_terminate(None)
                yield from self.handle_disconnect()
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
            message_pb2.PrexMessage.TERMINATE_ALL : self.handle_terminate_all,
            message_pb2.PrexMessage.VERSION : self.handle_version,
        }

        yield from handlers[msg.type](msg.payload)

    @asyncio.coroutine
    def handle_version(self, payload):
        packet = message_pb2.PrexMessage()
        packet.type = message_pb2.PrexMessage.VERSION
        packet.payload = __version__.encode()
        asyncio.ensure_future(self.protocol.send(packet.SerializeToString()))
    
    @asyncio.coroutine   
    def handle_load_program(self, payload):
        # First, check to see if a program is already running. If so, terminate
        # the old process first.
        yield from self.handle_terminate(None)
        obj = message_pb2.LoadProgram()
        obj.ParseFromString(payload)
        logging.info('Load program. Filename: ' + obj.filename) 
        logging.info('Code: ' + obj.code)
        logging.info('argv: ' + str(obj.argv))
        logging.info('interpreter: ' + str(obj.interpreter))
        interp = obj.interpreter
        if len(interp) == 0:
            interp = 'python3'

        interp_handlers = {
            'python3': self.handle_run_python,
            'cxx': self.handle_run_cxx,
            'ch': self.handle_run_ch,
        }

        try:
            yield from interp_handlers[interp](obj)
        except KeyError:
            yield from self.send_io(2, bytes("Error: Unknown interpreter requested: {}".format(interp)))

    @asyncio.coroutine
    def handle_run_python(self, payload_object):
        # Save the code to a temporary dir
        tmpdir = tempfile.mkdtemp()
        self.tmpdir = tmpdir
        filepath = os.path.join(tmpdir, payload_object.filename)
        logging.info('Opening temp file at:' + filepath)

        # Start the interprocess communications channel
        self.ipc_server = yield from _ChildProcessWsServer.create(self.protocol)

        with open(filepath, 'w') as f:
            f.write(payload_object.code)
            f.flush()
        loop = asyncio.get_event_loop()
        exit_future = asyncio.Future()
        self.exit_future = exit_future
        # Add ourselves to the process queue
        queue_future = asyncio.Future()
        yield from self._server.process_queue.put(queue_future)
        yield from queue_future

        logging.info('Starting subprocess...')
        args = ['python3', '-u', filepath]

        for arg in payload_object.argv:
            args += [arg]
        create = loop.subprocess_exec(
            functools.partial(_ExecProtocol, exit_future, self.protocol),
            *args,
            env={
                 'PREX_IPC_PORT':str(self.ipc_server.port),
                 'PATH':os.environ['PATH'],
                })
        self.exec_transport, self.exec_protocol = yield from create
        asyncio.ensure_future(self.check_program_end())

    @asyncio.coroutine
    def handle_run_ch(self, payload_object):
        # Save the code to a temporary dir
        tmpdir = tempfile.mkdtemp()
        self.tmpdir = tmpdir
        filepath = os.path.join(tmpdir, payload_object.filename)
        logging.info('Opening temp file at:' + filepath)

        # Start the interprocess communications channel
        self.ipc_server = yield from _ChildProcessWsServer.create(self.protocol)

        with open(filepath, 'w') as f:
            f.write(payload_object.code)
            f.flush()
        loop = asyncio.get_event_loop()
        exit_future = asyncio.Future()
        self.exit_future = exit_future
        # Add ourselves to the process queue
        queue_future = asyncio.Future()
        yield from self._server.process_queue.put(queue_future)
        yield from queue_future

        logging.info('Starting subprocess...')
        args = ['ch', filepath]

        for arg in payload_object.argv:
            args += [arg]
        create = loop.subprocess_exec(
            functools.partial(_ExecProtocol, exit_future, self.protocol),
            *args,
            env={
                 'PREX_IPC_PORT':str(self.ipc_server.port),
                 'PATH':os.environ['PATH'],
                 'CHHOME':'/usr/local/ch7.5',
                })
        self.exec_transport, self.exec_protocol = yield from create
        asyncio.ensure_future(self.check_program_end())

    @asyncio.coroutine
    def handle_run_cxx(self, payload_object):
        # Save the code to a temporary dir
        tmpdir = tempfile.mkdtemp()
        self.tmpdir = tmpdir
        filepath = os.path.join(tmpdir, payload_object.filename)
        logging.info('Opening temp file at:' + filepath)

        # Start the interprocess communications channel
        self.ipc_server = yield from _ChildProcessWsServer.create(self.protocol)

        with open(filepath, 'w') as f:
            f.write(payload_object.code)
            f.flush()

        # Add ourselves to the process queue
        queue_future = asyncio.Future()
        yield from self._server.process_queue.put(queue_future)
        yield from queue_future

        # Compile the damn thing
        yield from self.send_io(1, b'Compiling...\n')
        process = yield from asyncio.create_subprocess_exec(
            "g++", 
            "-std=c++11", 
            "-I/include", 
            filepath, 
            "-o", os.path.join(tmpdir, "a.out"), 
            "-llinkbot",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output = yield from process.communicate()
        if process.returncode:
            yield from self.send_io(2, 
                'Error encountered while compiling. Return code: {}'.format(process.returncode).encode() )
            if output[0]:
                yield from self.send_io(2, output[0])
            if output[1]:
                yield from self.send_io(2, output[1])
            # Send a "terminate" message back
            yield from self.emit_terminate_message()
            yield from self.rm_tmp_dir()
            return

        # Now run it
        yield from self.send_io(1, b'Executing...\n')

        loop = asyncio.get_event_loop()
        exit_future = asyncio.Future()
        self.exit_future = exit_future
        logging.info('Starting subprocess...')

        args = ['stdbuf', '-i0', '-o0', '-e0', os.path.join(tmpdir, 'a.out')]
        for arg in payload_object.argv:
            args += [arg]
        create = loop.subprocess_exec(
            functools.partial(_ExecProtocol, exit_future, self.protocol),
            *args,
            env={
                 'PREX_IPC_PORT':str(self.ipc_server.port),
                 'PATH':os.environ['PATH'],
                })
        self.exec_transport, self.exec_protocol = yield from create
        asyncio.ensure_future(self.check_program_end())

    @asyncio.coroutine
    def check_program_end(self):
        try:
            yield from asyncio.shield(
                asyncio.wait_for(self.exit_future, self.PROGRAM_TIMEOUT))
        except asyncio.TimeoutError:
            pass
        yield from self.emit_terminate_message()
        yield from self.rm_tmp_dir()

    @asyncio.coroutine
    def emit_terminate_message(self):
        # Send a TERMINATE message back 
        message = message_pb2.PrexMessage()
        message.type = message_pb2.PrexMessage.TERMINATE
        try:
            yield from self.protocol.send(message.SerializeToString())
        except websockets.exceptions.ConnectionClosed:
            pass

    @asyncio.coroutine
    def rm_tmp_dir(self):
        try:
            shutil.rmtree(self.tmpdir)
        except FileNotFoundError:
            pass
        logging.info('Process termination cleanup complete.')

    @asyncio.coroutine
    def handle_io(self, payload):
        obj = message_pb2.Io()
        obj.ParseFromString(payload)
        logging.info('Received IO from client: ' + str(obj.data))
        self.exec_transport.get_pipe_transport(0).write(obj.data)

    @asyncio.coroutine
    def handle_image(self, payload):
        logging.info('Server received {} bytes of image data.'.format(len(payload)))

    @asyncio.coroutine
    def handle_terminate(self, payload):
        logging.info('Terminating process...')
        try:
            self.exec_transport.kill()
        except ProcessLookupError:
            # Process was not running. Ignore
            pass
        except AttributeError:
            # exec_transport isn't valid. Ignore
            pass
        self.exec_transport = None

    @asyncio.coroutine
    def handle_disconnect(self):
        try:
            del self._server.connections[self.uri]
        except KeyError:
            pass

    @asyncio.coroutine
    def handle_terminate_all(self, payload):
        # First, we suspend all client programs
        for k, i in self._server.connections.items():
            try:
                psProcess = psutil.Process(pid=i.exec_transport.get_pid())
                psProcess.suspend()
            except:
                pass
        # Now we tell the daemon to emit a global kill
        d = linkbot.Daemon()
        d.ping()
        # terminate all other processes
        while len(self._server.connections) > 0:
            logging.info('Num Connections: {}'.format(len(self._server.connections)))
            k, i = self._server.connections.popitem()
            logging.info('Terminating uri: {}'.format(k))
            yield from i.handle_terminate(None)

    @asyncio.coroutine
    def send_io(self, fd, data):
        msg = message_pb2.Io()
        msg.type = fd
        msg.data = data
        packet = message_pb2.PrexMessage()
        packet.type = message_pb2.PrexMessage.IO
        packet.payload = msg.SerializeToString()
        asyncio.ensure_future(self.protocol.send(packet.SerializeToString()))

# This WS server receives communications from the child process. For instance,
# the child process can send an image to the client application by sending it
# to this server.
class _ChildProcessWsServer():
    @classmethod
    @asyncio.coroutine
    def create(cls, client_app_protocol, host='localhost', port=0):
        self = cls()
        self.client_app_protocol = client_app_protocol
        self.server = yield from websockets.serve(self.ws_handler, host, port)
        #_, self.port = self.server.server.sockets[0].getsockname()
        hostport = self.server.server.sockets[0].getsockname()
        self.port = hostport[1]
        return self

    @asyncio.coroutine
    def ws_handler(self, protocol, uri):
        logging.info('Received connection: ' + uri)
        connection = _ChildProcessConnection(protocol, uri, self.client_app_protocol)
        yield from connection.consumer()

class _ChildProcessConnection():
    def __init__(self, protocol, uri, client_app_protocol):
        self.protocol = protocol
        self.uri = uri
        self.client_app_protocol = client_app_protocol

    @asyncio.coroutine
    def consumer(self):    
        while True:
            logging.info('Waiting for message...')
            try:
                message = yield from self.protocol.recv()
                # Forward the message directly back up to the client
                yield from self.client_app_protocol.send(message)
            except websockets.exceptions.ConnectionClosed:
                return

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
    
