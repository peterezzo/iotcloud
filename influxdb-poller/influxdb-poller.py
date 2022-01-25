#!/usr/bin/env python3
"""
Read MQTT temperature metrics and send data to influxdb

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import os
import time

from influxdb import InfluxDB  # type: ignore
from mqtt import MQTT  # type: ignore


class Bot():
    def __init__(self) -> None:
        self.main()

    def pull_temperatures(self):
        print('Temperatures cmd received', flush=True)
        query = '''from(bucket: "Environment")
  |> range(start: -3h)
  |> last()
  |> filter(fn: (r) =>
    r._measurement == "environmental" and
    r._field == "temperature"
  )
  |> toFloat()
  |> map(fn: (r) => ({r with _value: r._value * 1.8 + 32.0}))'''
        self._pull_metric(query, ' °F')

    def pull_humidity(self):
        print('Temperatures cmd received', flush=True)
        query = '''from(bucket: "Environment")
  |> range(start: -3h)
  |> last()
  |> filter(fn: (r) =>
    r._measurement == "environmental" and
    r._field == "humidity"
  )'''
        self._pull_metric(query, '%')

    def _pull_metric(self, query, tail=''):
        db_response = self.db.query(query)
        results = [f'{r.values.get("sensor")}: {r.get_value():.1f}' for t in db_response for r in t]
        print(results, flush=True)
        self.mqtt.pub('Notifications/cmd-reply', '\n' + f'{tail}\n'.join(results) + f'{tail}', qos=1)

    def cmd_dispatcher(self, mosq, obj, msg):
        cmd = msg.payload.decode()
        if cmd == 'get-temperatures':
            self.pull_temperatures()
        elif cmd == 'get-humidities':
            self.pull_humidity()
        else:
            print('Unknown cmd received', cmd, flush=True)

    def main(self) -> None:
        mqtt_broker = os.getenv('MQTT_BROKER')

        self.db = InfluxDB('Environment')

        self.mqtt = MQTT(mqtt_broker)
        self.mqtt.listen()
        print('MQTT startup complete')

        print('adding callbacks', flush=True)
        self.mqtt.sub(self.cmd_dispatcher, 'Commands/Sensors', 0)

        while True:
            time.sleep(1)


if __name__ == '__main__':
    Bot()
