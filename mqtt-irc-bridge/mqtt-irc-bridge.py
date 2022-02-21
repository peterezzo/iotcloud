"""
Python IRC Client controlled by MQTT Broker (tested with Mosquitto)

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import collections
import json
import os
import pathlib
import re
import ssl
import struct
import time
from typing import Any, Callable
import irc.client  # type: ignore
import paho.mqtt.client  # type: ignore
from jaraco.stream import buffer  # type: ignore


Transfer = collections.namedtuple('Transfer', ['dcc', 'file'])
ServerConnection = irc.client.ServerConnection
Event = irc.client.Event
MQTTMessage = paho.mqtt.client.MQTTMessage
Client = paho.mqtt.client.Client


class IRC(irc.client.SimpleIRCClient):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.connargs = args
        self.connkwargs = kwargs

        self.debug_file = open('/data/unparsed.log', 'at')
        self.dccfiles = {}
        self.dccpeers = {}

        self.watchlist = os.getenv('IRC_WATCHLIST').split(';')

    def connect(self) -> None:
        print('Connecting to IRC', flush=True)
        if os.getenv('IRC_SSL'):
            self.connkwargs['connect_factory'] = irc.connection.Factory(wrapper=ssl.wrap_socket)
        self.connection.connect(*self.connargs, **self.connkwargs)

    def join_channels(self) -> None:
        channels = os.getenv('IRC_CHANNELS').split(';')
        for channel in channels:
            print('JOINING', channel, flush=True)
            self.connection.join(channel)

    def on_privmsg(self, connection: ServerConnection, event: Event) -> None:
        print('PRIVMSG', event)

    def on_pubmsg(self, connection: ServerConnection, event: Event) -> None:
        if event.target in self.watchlist:
            extract = re.match(r'.{4,16} +\d+x \[([^\]]+)\] (.*)', event.arguments[0])
            if extract:
                src = event.source.split('!')[0]
                meta = extract.group(1)
                name = extract.group(2)
                mqtt.pub('IRC/watchlist', json.dumps({'src': src, 'meta': meta, 'name': name}))
            else:
                self.debug('PUBMSG', event)

    def on_privnotice(self, connection: ServerConnection, event: Event) -> None:
        if 'NickServ!NickServ@services' in event.source:
            if 'IDENTIFY' in event.arguments[0]:
                print('Identifying with NickServ')
                connection.privmsg('NickServ', 'IDENTIFY ' + os.getenv('NICKSERV_PASS'))
            elif 'Password accepted' in event.arguments[0]:
                print('Identified')
                self.join_channels()
        elif 'MD5' in event.arguments[0]:
            mqtt.pub('Notifications/irc', json.dumps({'notice': event.arguments[0]}))
        else:
            print('PRIVNOTICE', event)

    def on_pubnotice(self, connection: ServerConnection, event: Event) -> None:
        print('PUBNOTICE', event)

    def on_ctcp(self, connection: ServerConnection, event: Event) -> None:
        print('CTCP', event)
        if event.arguments[0] == 'DCC':
            command = event.arguments[1].split(maxsplit=1)[0]
            peer_nick = event.source.split('!')[0]
            if command == 'SEND':
                self.handle_dcc_send(peer_nick, event.arguments[1])
            elif command == 'ACCEPT':
                self.handle_dcc_accept(peer_nick, event.arguments[1])

    def on_dccmsg(self, connection: ServerConnection, event: Event) -> None:
        if self.dccfiles.get(event.source):
            data = event.arguments[0]
            received_bytes = self.dccfiles[event.source].file.write(data)
            self.dccfiles[event.source].dcc.send_bytes(received_bytes)
        else:
            print('DCC-MSG', event)

    def on_dcc_disconnect(self, connection: ServerConnection, event: Event) -> None:
        print('DCC-DISCONNECT', event)
        if self.dccfiles.get(event.source):
            _, file = self.dccfiles.pop(event.source)
            print(f'Received file {file.filename} ({file.received_bytes}B out of {file.size}B).')
            mqtt.pub('Notifications/irc', f'Transferred {file.received_bytes/file.size*100:0.2f}% of {file.filename}')
            file.close()

    def on_ping(self, connection: ServerConnection, event: Event) -> None:
        print('PING', event)

    def on_disconnect(self, connection: ServerConnection, event: Event) -> None:
        self.debug_file.close()
        for file in self.dccfiles:
            file.close()

    def debug(self, *msg) -> None:
        print(*msg, file=self.debug_file, flush=True)

    def handle_dcc_send(self, peer_nick: str, msg: str) -> None:
        try:
            # DCC SEND filename ip port size
            _, filename, peer_address, peer_port, size = msg.split()
        except ValueError:
            print('CTCP DCC SEND unexpected format in request')
            return

        mqtt.pub('Notifications/irc', f'Incoming transfer of {filename}')
        file = File(filename, int(size))
        if file.received:
            print(f'{file.filename} is already fetched.')
            mqtt.pub('Notifications/irc', f'Not starting transfer of {filename}, already fetched')
        else:
            peer_address = irc.client.ip_numstr_to_quad(peer_address)
            self.dccpeers[peer_nick] = peer_address
            self.dccfiles[peer_address] = Transfer(self.dcc('raw'), file)

            if file.received_bytes > 8:
                print(f'{file.filename} could resume. Requesting.')
                # DCC RESUME filename port position
                # subtract 8 bytes à la mirc
                self.connection.ctcp('DCC', peer_nick, f'RESUME {filename} {peer_port} {file.received_bytes - 8}')
            else:
                self._safe_dcc_connect(peer_address, peer_port)

    def handle_dcc_accept(self, peer_nick: str, msg: str) -> None:
        # DCC ACCEPT filename port position
        try:
            _, filename, peer_port, seek = msg.split()
        except ValueError:
            print('CTCP DCC ACCEPT unexpected format in request')
            return

        mqtt.pub('Notifications/irc', f'Resuming transfer of {filename}')
        peer_address = self.dccpeers[peer_nick]
        self.dccfiles[peer_address].file.resume(int(seek))
        self._safe_dcc_connect(peer_address, peer_port)

    def _safe_dcc_connect(self, peer_address, peer_port) -> None:
        filename = self.dccfiles[peer_address].file.filename
        print(f'fetching {filename}')
        try:
            self.dccfiles[peer_address].dcc.connect(peer_address, int(peer_port))
        except irc.client.DCCConnectionError as e:
            print(f'Transfer of {filename} failed due to {e}')
            mqtt.pub('Notifications/irc', f'Transfer of {filename} failed due to {e}')


class File():
    def __init__(self, filename: str, size: int) -> None:
        self.fileh = None
        self.received = False
        self.size = size
        self.filename = pathlib.Path('/data') / pathlib.Path(filename).name

        self.received_bytes = 0
        if self.filename.exists():
            self.received_bytes = self.filename.stat().st_size
            if self.received_bytes >= self.size:
                self.received = True

    def resume(self, offset: int) -> None:
        if not self.fileh:
            self.fileh = self.filename.open('wb')
        self.fileh.seek(offset)

    def write(self, data: bytes) -> int:
        if not self.fileh:
            self.fileh = self.filename.open('wb')
        self.fileh.write(data)
        self.received_bytes = self.received_bytes + len(data)
        if self.size <= 4294967295:
            format = '!I'  # 4-bit big-endian unsigned int
        else:
            format = '!Q'  # 8-bit big-endian unsigned long long int
        return struct.pack(format, self.received_bytes)

    def close(self) -> None:
        self.fileh.close()


class MQTT():
    def __init__(self, host: str, port: int = 1883, user=None, password=None, keepalive=60, client_id=None):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.client = paho.mqtt.client.Client(client_id)

        self.client.tls_set()
        self.client.tls_insecure_set(True)

        if user or password:
            self.client.username_pw_set(user, password)

        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    def on_message(self, client: Client, userdata: Any, msg: MQTTMessage):
        print(f'Msg: {msg.topic} {str(msg.qos)} {str(msg.payload)}')
        if msg.topic == 'Commands/ALL' and msg.payload == b'check-in':
            self.pub('Notifications/check-in-reply', self.client_id, qos=1)

    def on_connect(self, client: Client, userdata: Any, flags: dict, rc):
        print(f'Connected to {client._host}:{client._port} code {rc}')
        self.sub(None, 'Commands/ALL', qos=1)
        self.pub('Notifications/startup', f'{self.client_id} connect at {time.time()}', qos=1)

    def on_disconnect(self, client: Client, userdata: Any, rc):
        print(f'Disconnected from {client._host}:{client._port} code {rc}')

    def pub(self, topic: str, message: str, retain: bool = False, qos: int = 0):
        self.client.publish(topic, message, qos)

    def sub(self, callback: Callable, topic: str, qos: int = 0):
        if callback:
            self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic, qos)

    def listen(self, blocking: bool = False):
        """
        This is the main loop for a client waiting for messages
        """
        self.client.connect(self.host, self.port, self.keepalive)
        if blocking:
            print('Starting blocking MQTT loop', flush=True)
            self.client.loop_forever()
        else:
            print('Starting nonblocking MQTT thread', flush=True)
            self.client.loop_start()


class Bot():
    def start(self):
        mqtt.listen()
        mqtt.sub(self.bridge, 'Commands/IRC')

        client.connect()
        while True:
            client.reactor.process_once()
            time.sleep(0.01)

    def stop(self):
        client.connection.disconnect('bye')
        print('Cleanly exited')

    def bridge(self, mosq, obj, msg):
        """MQTT Callback"""
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            payload = {'type': 'broken'}
        print('MQTT', payload)
        if payload.get('type') == 'privmsg':
            client.connection.privmsg(payload['target'], payload['msg'])
        else:
            mqtt.pub('Notifications/errors', 'Unknown IRC Command')


if __name__ == "__main__":
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    ge = os.getenv
    mqtt = MQTT(ge('MQTT_BROKER'), int(ge('MQTT_PORT')), ge('MQTT_USER'), ge('MQTT_PASS'), client_id='mqtt-irc-bridge')
    client = IRC(ge('IRC_SERVER'), int(ge('IRC_PORT')), ge('NICKNAME'))
    bot = Bot()
    try:
        bot.start()
    except irc.client.ServerConnectionError as x:
        print(x)
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(e, flush=True)
        bot.stop()
        mqtt.pub('Notifications/irc', f'Error: {e}')
        raise
