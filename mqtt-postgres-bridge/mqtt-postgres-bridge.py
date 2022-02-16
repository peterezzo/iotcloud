#!/usr/bin/env python3
"""
Postgres-MQTT Bridge and Notifier
"""

import datetime
import json
import os
import time

from mqtt import MQTT  # type: ignore
from inventorydb import InventoryDB  # type: ignore


def serializer(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()


class Bridge():
    def __init__(self) -> None:
        self.main()

    def relay_objects(self, mosq, obj, msg):
        """
        Add object to inventory when it arrives in broker (MQTT Callback)
        """
        payload = json.loads(msg.payload)
        self.db.add_record(**payload)

    def queries(self, mosq, obj, msg):
        if b'search' in msg.payload:
            results = self.db.search(msg.payload.split(maxsplit=1)[1].decode())
            print(results, flush=True)
            self.mqtt.pub('CommandResponses/DB', json.dumps(results, default=serializer))
        elif msg.payload == b'dbreport':
            pass

    def main(self) -> None:
        dbname = os.getenv('POSTGRES_DB')
        dbpass = os.getenv('POSTGRES_PASSWORD')
        mqtt_broker = os.getenv('MQTT_BROKER')

        self.db = InventoryDB('postgres', dbname, 'postgres', dbpass)

        self.mqtt = MQTT(mqtt_broker, client_id='postgres-mqtt-bridge')
        self.mqtt.listen()
        print('MQTT startup complete')

        print('adding callbacks', flush=True)
        self.mqtt.sub(self.relay_objects, 'IRC/watchlist')
        self.mqtt.sub(self.queries, 'Commands/DB')

        self.mqtt.pub('Logs', f'Postgres Bridge Startup at {time.time()}', qos=1)
        while True:
            time.sleep(1)


if __name__ == '__main__':
    Bridge()
