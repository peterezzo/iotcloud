#!/usr/bin/env python3
"""
Postgres-MQTT Bridge and Notifier
"""

import collections
import json
import os
import random
import time

from mqtt import MQTT  # type: ignore
from inventorydb import InventoryDB  # type: ignore


class Bridge():
    def __init__(self) -> None:
        dbname = os.getenv('POSTGRES_DB')
        dbpass = os.getenv('POSTGRES_PASSWORD')
        self.db = InventoryDB('postgres', dbname, 'postgres', dbpass)
        self.mqtt = MQTT(os.getenv('MQTT_BROKER'), client_id='postgres-mqtt-bridge')
        self.preamble = os.getenv('PREAMBLE')

    def relay_objects(self, mosq, obj, msg):
        """
        Add object to inventory when it arrives in broker (MQTT Callback)
        """
        payload = json.loads(msg.payload)
        self.db.add_record(**payload)

    def queries(self, mosq, obj, msg):
        if b'search' in msg.payload[:6]:
            self.search(msg.payload.split(maxsplit=1)[1].decode())
        elif b'sources' in msg.payload[:7]:
            self.sources(msg.payload.split(maxsplit=1)[1].decode())
        elif b'get' in msg.payload[:3]:
            self.get(msg.payload.split(maxsplit=1)[1].decode())
        elif msg.payload == b'dbreport':
            pass

    def search(self, data):
        results = self.db.search_names(data)
        self.mqtt.pub('Notifications/cmd-reply', '\n'.join([f'{result[0]} : {result[1]}' for result in results]))

    def sources(self, data):
        results = self.db.search_all(data)
        self.mqtt.pub('Notifications/cmd-reply', '\n'.join([f'{result[1]} {result[3]}' for result in results]))

    def get(self, data):
        cmds = []
        objmap = collections.defaultdict(lambda: set())
        for name, source in [(r[3], r[1]) for r in self.db.search_all(data)]:
            objmap[name].add(source)
        for name, sources in {k: list(objmap[k]) for k in sorted(objmap, key=lambda k: len(objmap[k]))}.items():
            target = sources[random.randint(0, len(sources) - 1)]
            payload = json.dumps({'type': 'privmsg', 'target': target, 'msg': f'{self.preamble} {name}'})
            cmds.append(('Commands/IRC', payload, 2, False))
        self.mqtt.multipub(cmds)

    def start(self) -> None:
        self.mqtt.listen()
        print('MQTT startup complete')

        print('adding callbacks', flush=True)
        self.mqtt.sub(self.relay_objects, 'IRC/watchlist')
        self.mqtt.sub(self.queries, 'Commands/Postgres')

        while True:
            time.sleep(0.1)


if __name__ == '__main__':
    bridge = Bridge()
    bridge.start()
