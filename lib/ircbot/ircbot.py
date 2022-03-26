"""
Python headless IRC Client

Copyright (c) 2021-2022 Pete Ezzo
Copyright (c) 2011-2022 Jason R. Coombs
Copyright (c) 2009 Ferry Boender
Copyright (c) 1999-2002 Joel Rosdahl
"""

import ssl
import socket
import socks
from typing import Callable, Tuple
from irc.client import Reactor, Connection, DCCConnectionError, Event, ServerConnection  # type: ignore
from jaraco.stream import buffer  # type: ignore

ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer


def identity(x):
    return x


class Factory:
    """
    From https://github.com/jaraco/irc/blob/96f506b2a6b4169f86f09afc0906c021a097433f/irc/connection.py#L10
    Patched for proxy support and code style
    """
    def __init__(self, bind_address=None, wrapper=identity, ipv6=False, proxy=None):
        self.bind_address = bind_address
        self.wrapper = wrapper
        self.proxy = proxy
        self.family = socket.AF_INET6 if ipv6 else socket.AF_INET

    def connect(self, server_address):
        if self.proxy:
            _socket = socks.socksocket(self.family, socket.SOCK_STREAM)
            _socket.set_proxy(socks.SOCKS5, *self.proxy)
            _socket.connect(server_address)
            sock = self.wrapper(_socket)
        else:
            sock = self.wrapper(socket.socket(self.family, socket.SOCK_STREAM))
            self.bind_address and sock.bind(self.bind_address)
            sock.connect(server_address)
        return sock

    __call__ = connect


class DCCConnection(Connection):
    """
    From https://github.com/jaraco/irc/blob/96f506b2a6b4169f86f09afc0906c021a097433f/irc/connection.py#L10
    Patched for proxy support and code style
    """
    socket = None
    connected = False
    passive = False
    peeraddress = None
    peerport = None

    def __init__(self, reactor: Reactor, dcctype: str, proxy: Tuple[str, int] | None = None):
        super().__init__(reactor)
        self.dcctype = dcctype
        self.proxy = proxy

    def connect(self, address: str, port: int):
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.buffer = buffer.LineBuffer()
        self.handlers = {}
        if self.proxy:
            self.socket = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setproxy(socks.SOCKS5, *self.proxy)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error as x:
            raise DCCConnectionError("Couldn't connect to socket: %s" % x)
        self.connected = True
        self.reactor._on_connect(self.socket)
        return self

    def disconnect(self, message: str = ''):
        try:
            del self.connected
        except AttributeError:
            return

        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass
        del self.socket
        self.reactor._handle_event(
            self, Event("dcc_disconnect", self.peeraddress, "", [message])
        )
        self.reactor._remove_connection(self)

    def process_data(self):
        """[Internal]"""
        try:
            new_data = self.socket.recv(2**14)
        except socket.error:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        chunks = [new_data]
        command = "dccmsg"
        prefix = self.peeraddress
        target = None
        for chunk in chunks:
            arguments = [chunk]
            event = Event(command, prefix, target, arguments)
            self.reactor._handle_event(self, event)

    def send_bytes(self, bytes):
        try:
            self.socket.send(bytes)
        except socket.error:
            self.disconnect("Connection reset by peer.")


class IRCBot():
    def __init__(self,
                 host: str,
                 port: int,
                 nick: str,
                 nickpass: str = '',
                 channels: list = None,
                 use_ssl: bool = True,
                 proxy: Tuple[str, int] | None = None
                 ) -> None:
        self.reactor = Reactor()
        self.connection = self.reactor.server()

        factory = Factory(wrapper=ssl.wrap_socket, proxy=proxy) if use_ssl else Factory(proxy=proxy)
        self.connstring = {'server': host, 'port': port, 'nickname': nick, 'connect_factory': factory}
        self.proxy = proxy

        self.channels = channels
        self.nickpass = nickpass
        if self.nickpass:
            self.sub(self.nickserv_auth, 'privnotice', -10)
        else:
            self.sub(self.join_channels, 'endofmotd', -10)

    def start(self) -> None:
        print('Connecting to IRC', flush=True)
        self.connection.connect(**self.connstring)
        print('Connected to IRC', flush=True)
        self.reactor.process_forever(timeout=0.01)

    def stop(self) -> None:
        self.connection.disconnect('bye')
        print('Cleanly exited')

    def nickserv_auth(self, connection: ServerConnection, event: Event) -> None:
        if event.source.nick == 'NickServ':
            if 'IDENTIFY' in event.arguments[0]:
                print('Identifying with NickServ')
                connection.privmsg('NickServ', f'IDENTIFY {self.nickpass}')
            elif 'Password accepted' in event.arguments[0]:
                print('Identified with NickServ', flush=True)
                self.join_channels()

    def join_channels(self, *args, **kwargs) -> None:
        for channel in self.channels:
            print('JOINING', channel, flush=True)
            self.connection.join(channel)

    def sub(self, callback: Callable, event: str, priority: int = 0) -> None:
        """Subscribe to an IRC event"""
        self.reactor.add_global_handler(event, callback, priority)

    def privmsg(self, target: str, msg: str) -> None:
        self.connection.privmsg(target, msg)

    def ctcp(self, type: str, target: str, msg: str) -> None:
        self.connection.ctcp(type, target, msg)

    def dcc(self) -> DCCConnection:
        with self.reactor.mutex:
            conn = DCCConnection(self.reactor, 'raw', self.proxy)
            self.reactor.connections.append(conn)
        return conn
