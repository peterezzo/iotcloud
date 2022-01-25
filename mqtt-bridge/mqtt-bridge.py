#!/usr/bin/env python3
"""
Read MQTT temperature metrics and send data to influxdb

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import datetime
import json
import os
import time

from influxdb import InfluxDB  # type: ignore
from mqtt import MQTT  # type: ignore


class Bridge():
    def __init__(self) -> None:
        self.main()

    def relay_metric(self, mosq, obj, msg):
        """
        Send a message to InfluxDB when reading arrives in broker (MQTT Callback)
        """
        location = msg.topic.split('/', maxsplit=1)[1]
        metrics = json.loads(msg.payload)

        data_payload = {
            'measurement': 'environmental',
            'tags': {
                'sensor': location
            },
            'time': str(datetime.datetime.utcnow().replace(microsecond=0)),
            'fields': {
                'temperature': metrics['temperature'],
                'humidity': metrics['humidity']
            }
        }
        print(data_payload, flush=True)
        self.db.write(data_payload)

    def main(self) -> None:
        mqtt_broker = os.getenv('MQTT_BROKER')

        self.db = InfluxDB('Environment')

        self.mqtt = MQTT(mqtt_broker, client_id='mqtt-influxdb-bridge')
        self.mqtt.listen()
        print('MQTT startup complete')

        print('adding callbacks', flush=True)
        self.mqtt.sub(self.relay_metric, 'Sensors/#')

        while True:
            time.sleep(1)


if __name__ == '__main__':
    Bridge()
