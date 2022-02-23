"""
Python IRC Client controlled by MQTT Broker (tested with Mosquitto)

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import hashlib
import json
import os
import pathlib
import re
import struct
from typing import Any, Tuple
from ircbot import IRCBot, ServerConnection, Event, DCCConnectionError  # type: ignore
from mqtt import MQTT, Client, MQTTMessage  # type: ignore


class File():
    def __init__(self, filename: str) -> None:
        self.fileh = None
        self.md5 = hashlib.md5()
        self.filename = pathlib.Path('/data') / pathlib.Path(filename).name

        self.received_bytes = 0
        if self.filename.exists():
            self.received_bytes = self.filename.stat().st_size

    def resume(self, offset: int) -> None:
        if not self.fileh:
            self.fileh = self.filename.open('wb')
        self.fileh.seek(offset)

    def write(self, data: bytes) -> int:
        if not self.fileh:
            self.fileh = self.filename.open('wb')
        self.fileh.write(data)
        self.md5.update(data)
        self.received_bytes = self.received_bytes + len(data)
        return self.received_bytes

    def close(self) -> None:
        self.fileh.close()
        self.fileh = None


class Transfers():
    # transfer schema {'name', 'size', 'src', 'md5', 'ip', 'port', 'file', 'connection'}
    def __init__(self) -> None:
        self.transfers = []

    def upsert_transfer(self, name: str, **kwargs) -> dict:
        transfer = self.find_transfer_by_name(name)
        if not transfer:
            transfer = {'name': name, 'file': File(name)}
            self.transfers.append(transfer)
        return self.update_transfer(transfer, **kwargs)

    def update_transfer(self, transfer: dict, **kwargs) -> dict:
        for key, value in kwargs.items():
            if key in ['port', 'size', 'startat']:
                value = int(value)
            transfer[key] = value
        return transfer

    def start(self, transfer: dict) -> bool:
        try:
            transfer['connection'].connect(transfer['ip'], transfer['port'])
        except DCCConnectionError as e:
            print('ERROR', str(e))
            return False
        transfer['file'].resume(transfer.get('startat', 0))
        return True

    def write_and_reply(self, transfer: dict, content: bytes) -> None:
        if transfer:
            transfer['file'].write(content)
            if transfer.get('size', 0) <= 4294967295:
                format = '!I'  # 4-bit big-endian unsigned int
            else:
                format = '!Q'  # 8-bit big-endian unsigned long long int
            transfer['connection'].send_bytes(struct.pack(format, transfer['file'].received_bytes))

    def close(self, transfer: dict) -> Tuple[str, float]:
        transfer['file'].close()
        transfer['end_md5'] = transfer['file'].md5.hexdigest()
        if transfer['size'] > 0:
            transfer['pct_complete'] = transfer['file'].received_bytes / transfer['size'] * 100
        else:
            transfer['pct_complete'] = float('nan')
        return transfer

    def find_transfer_by_name(self, name: str) -> dict:
        return self._find_transfer_by_x('name', name)

    def find_transfer_by_src(self, src: str) -> dict:
        return self._find_transfer_by_x('src', src)

    def find_transfer_by_ip(self, ip: str) -> dict:
        return self._find_transfer_by_x('ip', ip)

    def _find_transfer_by_x(self, field: str, value: str) -> dict:
        for transfer in self.transfers:
            if transfer.get(field) == value:
                return transfer
        return {}


class Bot():
    def __init__(self) -> None:

        self.mqtt = MQTT(os.getenv('IRC_MQTT_BROKER'),
                         int(os.getenv('IRC_MQTT_PORT')),
                         os.getenv('IRC_MQTT_USER'),
                         os.getenv('IRC_MQTT_PASS'),
                         use_ssl=True,
                         client_id='mqtt-irc-bridge'
                         )
        self.irc = IRCBot(os.getenv('IRC_SERVER'),
                          int(os.getenv('IRC_PORT')),
                          os.getenv('IRC_NICKNAME'),
                          os.getenv('IRC_NICKSERV_PASS'),
                          os.getenv('IRC_CHANNELS').split(';')
                          )
        self.transfers = Transfers()
        self.watchlist = os.getenv('IRC_WATCHLIST').split(';')

        self.callbacks = [
            ('ctcp', 'Process CTCP Messages', self.handle_ctcp),
            ('dccmsg', 'Dispatch DCC messages to appropriate object', self.handle_dcc_msg),
            ('dcc_disconnect', 'Close DCC chat states', self.handle_dcc_disconnect),
            ('ping', 'Ping Debug', self.debug_print),
            ('privmsg', 'Private Message Debug', self.debug_print),
            ('privnotice', 'Record interesting values from private notices', self.handle_watchlist),
            ('pubmsg', 'Record interesting public messages from watchlisted channels', self.handle_watchlist),
            ('pubnotice', 'Public Notice Debug', self.debug_print)
        ]
        for eventtype, _, callback in self.callbacks:
            self.irc.sub(callback, eventtype)

    def start(self) -> None:
        self.mqtt.listen()
        self.mqtt.sub(self.mqtt_bridge, 'Commands/IRC')

        self.irc.start()

    def stop(self) -> None:
        self.irc.stop()

    def mqtt_bridge(self, client: Client, userdata: Any, msg: MQTTMessage) -> None:
        """MQTT Callback"""
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            payload = {'type': 'broken'}
        print('MQTT', payload)
        if payload.get('type') == 'privmsg':
            self.irc.privmsg(payload['target'], payload['msg'])
        else:
            self.mqtt.pub('Notifications/errors', 'Unknown IRC Command')

    def handle_watchlist(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        if event.target in self.watchlist:
            extract = re.match(r'.{4,16} +\d+x \[([^\]]+)\] (.*)', event.arguments[0])
            if extract:
                src = event.source.nick
                meta = extract.group(1)
                name = extract.group(2)
                self.mqtt.pub('IRC/watchlist', json.dumps({'src': src, 'meta': meta, 'name': name}))
        elif event.target == connection.nickname:
            extract = re.match(r'.{21,30}\"([^\"]+)\".{3,15}\w{3}:([^\]]+)', event.arguments[0])
            if extract:
                name = extract.group(1)
                md5 = extract.group(2)
                self.transfers.upsert_transfer(name=name, md5=md5)

    def handle_ctcp(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        if event.arguments[0] == 'DCC':
            self.handle_dcc(connection, event)
        else:
            print('CTCP', event)

    def handle_dcc(self, connection: ServerConnection, event: Event) -> None:
        """Not actually an IRC Callback"""
        src = event.source.nick
        cmd, name, v1, v2, size = (event.arguments[1].split() + [0])[:5]
        if cmd == 'SEND':   # DCC SEND filename ip port size
            ip = ".".join(map(str, struct.unpack('BBBB', struct.pack('>L', int(v1)))))
            metadata = {'name': name, 'src': src, 'ip': ip, 'port': v2, 'size': size, 'connection': self.irc.dcc()}
        elif cmd == 'ACCEPT':  # DCC ACCEPT filename port position
            metadata = {'name': name, 'src': src, 'port': v1, 'startat': v2}
        else:
            return

        transfer = self.transfers.upsert_transfer(**metadata)

        if transfer['file'].received_bytes == transfer['size']:
            msg = (f'{name} already transferred, not sending')
        elif cmd == 'SEND' and transfer['file'].received_bytes > 16384:
            msg = (f'Requesting resume of {name}')
            # DCC RESUME filename port position
            # subtract 16384 bytes à la mirc as this seems to be one block
            self.irc.ctcp('DCC', src, f"RESUME {name} {transfer['port']} {transfer['file'].received_bytes - 16384}")
        else:
            if self.transfers.start(transfer):
                msg = f"Started transfer of {name} from {src} at {metadata.get('startat', 0)}B"
        self.mqtt.pub('Notifications/irc', msg, verbose=True)

    def handle_dcc_msg(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        self.transfers.write_and_reply(self.transfers.find_transfer_by_ip(event.source), event.arguments[0])

    def handle_dcc_disconnect(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        transfer = self.transfers.close(self.transfers.find_transfer_by_ip(event.source))
        print('TRANSFER', transfer, flush=True)

        valid = 'verified' if transfer.get('md5', '') == transfer.get('end_md5') else 'unverified'
        msg = f"Received {valid} transfer of {transfer['pct_complete']:0.2f}% of file {transfer['name']}"
        self.mqtt.pub('Notifications/irc', msg, verbose=True)

    def debug_print(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        print(event, flush=True)


if __name__ == "__main__":
    bot = Bot()
    try:
        bot.start()
    except (KeyboardInterrupt, Exception) as e:
        print(e, flush=True)
        raise
    finally:
        bot.stop()
