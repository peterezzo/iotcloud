"""
Python headless IRC Client
"""

import ssl
from typing import Callable
from irc.client import Reactor, DCCConnection, DCCConnectionError, Event, ServerConnection  # type: ignore
from irc.connection import Factory  # type: ignore
from jaraco.stream import buffer  # type: ignore

ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer


class IRCBot():
    def __init__(self,
                 host: str,
                 port: int,
                 nick: str,
                 nickpass: str = '',
                 channels: list = None,
                 use_ssl: bool = True
                 ) -> None:
        self.reactor = Reactor()
        self.connection = self.reactor.server()

        factory = Factory(wrapper=ssl.wrap_socket) if use_ssl else Factory()
        self.connstring = {'server': host, 'port': port, 'nickname': nick, 'connect_factory': factory}

        self.channels = channels
        self.nickpass = nickpass
        if self.nickpass:
            self.sub(self.nickserv_auth, 'privnotice')
        else:
            self.sub(self.join_channels, 'connect')

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
        return self.reactor.dcc('raw')

    def dcc_connect(self, peer_address: str, peer_port: int) -> DCCConnection | None:
        try:
            return self.reactor.dcc('raw').connect(peer_address, int(peer_port))
        except DCCConnectionError as e:
            print(f'Connection failed due to {e}')
