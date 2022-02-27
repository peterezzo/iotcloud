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


def log(*args, **kwargs):
    # msg = json.dumps(args, default=str)
    kwargs['flush'] = True
    print(*args, **kwargs)


class Transfer():
    def __init__(self, filename: str) -> None:
        # this first block of variables must be provided externally
        self.md5 = None
        self.connection = None
        self.ip = ''
        self.port = 0
        self.startat = 0
        self.size = 0

        # remaining variables are controlled internally
        self._fileh = None
        self._md5 = hashlib.md5()
        self.filename = pathlib.Path('/data') / pathlib.Path(filename).name
        self.received_bytes = 0
        if self.filename.exists():
            self.received_bytes = self.disksize

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if key in ['port', 'size', 'startat']:
                value = int(value)
            setattr(self, key, value)

    def start(self) -> None:
        self._fileh = self.filename.open('wb')
        self._fileh.seek(self.startat)
        self.connection.connect(self.ip, self.port)

    def write(self, data: bytes) -> int:
        self._fileh.write(data)
        self._md5.update(data)
        self.received_bytes = self.received_bytes + len(data)
        return self.received_bytes

    def close(self) -> None:
        try:
            self._fileh.close()
        except AttributeError:
            pass
        self._fileh = None
        if self.connection and self.connection.connected:
            self.connection.disconnect()

        if 'verified' not in str(self.filename.resolve()):
            destdir = pathlib.Path('verified') if self.verified else pathlib.Path('unverified')
            self.filename = self.filename.rename(self.filename.parent / destdir / self.filename.name)

    @property
    def name(self) -> str:
        return self.filename.name

    @property
    def disksize(self) -> int:
        try:
            size = self.filename.stat().st_size
        except FileNotFoundError:
            size = 0
        return size

    @property
    def fileopen(self) -> bool:
        return bool(self._fileh)

    @property
    def verified(self) -> bool:
        return self.md5 == self._md5.hexdigest()

    @property
    def pct_complete(self) -> float:
        try:
            return self.disksize / self.size * 100
        except ZeroDivisionError:
            return float('nan')

    def __repr__(self) -> str:
        return json.dumps({
            'name': self.name,
            'size': self.size,
            'disksize': self.disksize,
            'fileopen': self.fileopen,
            'md5': self.md5,
            '_md5': self._md5.hexdigest(),
            'pct_complete': self.pct_complete,
            'verified': self.verified,
            'src': self.src,
            'ip': self.ip,
            'port': self.port,
            'startat': self.startat,
            'received_bytes': self.received_bytes
        })


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
        self.watchlist = os.getenv('IRC_WATCHLIST').split(';')
        self.transfers = {}
        self.chatlist = set()
        self.md5 = {}

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
        log('MQTT', payload)
        if payload.get('type') == 'privmsg':
            self.irc.privmsg(payload['target'], payload['msg'])
            self.chatlist.add(payload['target'])
        elif payload.get('type') == 'status':
            reply = self.transfer_status()
            self.mqtt.pub('Notifications/cmd-reply', reply)
        else:
            self.mqtt.pub('Notifications/errors', 'Unknown IRC Command')

    def transfer_status(self):
        if len(self.transfers) == 0:
            return 'No active transfers'
        else:
            active = []
            for t in self.transfers.values():
                active.append(f'{t.name} {t.fileopen} {t.src} {t.ip} {t.pct_complete}%')
            return '\n' + '\n'.join(active)

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
            extract = re.match(r'.{21,35}\"([^\"]+)\".{3,15}\w{3}:([^\]]+)', event.arguments[0])
            if extract:
                name = extract.group(1)
                md5 = extract.group(2)
                self.md5[name] = md5
            elif 'MD5' in event.arguments[0]:
                log(event.arguments[0])

    def handle_ctcp(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        if event.arguments[0] != 'DCC':
            log('CTCP', event)
        else:
            src = event.source.nick
            if src not in self.chatlist:
                msg = f'Unauthorized DCC request from {src}'
                return

            cmd, name, v1, v2, size = (event.arguments[1].split() + [0])[:5]
            if cmd == 'SEND':   # DCC SEND filename ip port size
                ip = ".".join(map(str, struct.unpack('BBBB', struct.pack('>L', int(v1)))))
                metadata = {'name': name, 'src': src, 'ip': ip, 'port': v2, 'size': size, 'connection': self.irc.dcc()}
            elif cmd == 'ACCEPT':  # DCC ACCEPT filename port position
                metadata = {'name': name, 'src': src, 'port': v1, 'startat': v2}
            else:
                return

            metadata['md5'] = self.md5.get(name)
            transfer = self.upsert_transfer(**metadata)

            if transfer.pct_complete == 100.:
                msg = f'{name} already transferred, ignoring request from {src}'
            elif self.transfers.get(transfer.ip):
                msg = f'SHENANIGANS! Existing transfer of {self.transfers[transfer.ip].name}' + \
                      f' from {transfer.ip} is underway, cannot start {name} from {src}'
            # elif cmd == 'SEND' and transfer['file'].received_bytes > 16384:
            #     msg = (f'Requesting resume of {name}')
            #     # DCC RESUME filename port position
            #     # subtract 16384 bytes à la mirc as this seems to be one block
            #     self.irc.ctcp('DCC', src, f"RESUME {name} {transfer.port} {transfer.received_bytes - 16384}")
            else:
                try:
                    transfer.start()
                    self.transfers[transfer.ip] = transfer
                    msg = f'Started transfer of {name} from {src} at {transfer.ip}'
                except DCCConnectionError as e:
                    msg = f'Could not connect to {src} for {name} at {transfer.ip}: {e}'
            self.mqtt.pub('Notifications/irc', msg, verbose=True)
            log('OPENED', transfer)

    def handle_dcc_msg(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        transfer = self.transfers.get(event.source)
        if transfer:
            try:
                transfer.write(event.arguments[0])
                if transfer.size <= 4294967295:
                    format = '!I'  # 4-bit big-endian unsigned int
                else:
                    format = '!Q'  # 8-bit big-endian unsigned long long int
                transfer.connection.send_bytes(struct.pack(format, transfer.received_bytes))
            except AttributeError:
                log('WTF-DC', transfer)
                transfer.close()
            except Exception as e:
                log('WTF-UNKNOWN', e, transfer)
                transfer.close()
        else:
            log('WTF-NC', f'Received {len(event.arguments[0])} bytes from {event.source} without existing transfer')

    def handle_dcc_disconnect(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        transfer = self.transfers.pop(event.source)
        if transfer:
            transfer.close()
        log('CLOSED', transfer)

        verified = 'verified' if transfer.verified else 'UNVERIFIED'
        msg = f"Received {verified} transfer of {transfer.pct_complete:0.2f}% of file {transfer.name}"
        self.mqtt.pub('Notifications/irc', msg, verbose=True)

    def upsert_transfer(self, name: str, **kwargs) -> dict:
        transfer = self.find_transfer_by_name(name)
        if not transfer:
            transfer = Transfer(name)
        transfer.update(**kwargs)
        return transfer

    def find_transfer_by_name(self, name: str) -> dict:
        return self._find_transfer_by_x('name', name)

    def find_transfer_by_src(self, src: str) -> dict:
        return self._find_transfer_by_x('src', src)

    def find_transfer_by_ip(self, ip: str) -> dict:
        return self._find_transfer_by_x('ip', ip)

    def _find_transfer_by_x(self, field: str, value: str) -> Tuple[dict, None]:
        for transfer in self.transfers.values():
            if getattr(transfer, field) == value:
                return transfer

    def debug_print(self, connection: ServerConnection, event: Event) -> None:
        """IRC Callback"""
        log(event)


if __name__ == "__main__":
    bot = Bot()
    try:
        bot.start()
    except (KeyboardInterrupt, Exception) as e:
        log(e)
        raise
    finally:
        bot.stop()
        for transfer in bot.transfers:
            transfer.close()
