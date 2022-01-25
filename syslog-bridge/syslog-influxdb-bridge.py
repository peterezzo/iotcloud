#!/usr/bin/env python3
"""
Read syslog temperature file and send data to influxdb

Author: Pete Ezzo <peter.ezzo@gmail.com>

"""

import datetime
import json
import pathlib
import re
import subprocess

from influxdb import InfluxDB  # type: ignore


class Log():
    @staticmethod
    def logtail(filename):
        cmd = ['tail', '-n', '1', '-q', '-F', filename]
        p = subprocess.Popen(' '.join(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        while True:
            # this is trivially simple but readline is a blocking call
            # an async/threaded app will lock here
            # something like os.set_blocking(p.stdout.fileno(), False)
            # would be needed for an async model
            yield p.stdout.readline()

    @staticmethod
    def fulllogs(folder, pattern):
        for filepath in pathlib.Path(folder).glob(pattern):
            print('Reading: ', filepath)
            with filepath.open() as f:
                for line in f:
                    yield line


class SensorLog(Log):
    def __init__(self, logfile):
        self.logfile = logfile
        self.json_payload_pattern = re.compile(rb'(\w+\s+\d+ \d+:\d+:\d+) [^{]+({.*})')

    def metrics_streamer(self):
        lines = self.logtail(self.logfile)
        for line in lines:
            extract = self.json_payload_pattern.match(line)
            if extract:
                rawtime = extract.group(1).decode()
                time = datetime.datetime.strptime(rawtime, r'%b %d %H:%M:%S').replace(year=datetime.date.today().year)
                metrics = json.loads(extract.group(2))
                if not metrics.get('time'):
                    metrics['time'] = str(time)
                if metrics.get('model') == 'Acurite-606TX':
                    metrics['location'] = 'outside2'
                    metrics['temperature'] = metrics['temperature_C']
                    metrics['humidity'] = None
                if metrics.get('location'):
                    yield metrics
                else:
                    print('WARNING: Unknown json payload: ', metrics)
            else:
                # print('WARNING: Unparsed: ', line, file=sys.stderr)
                print('WARNING: Unparsed: ', line)


def read_syslog():
    sensors = SensorLog('/var/log/iot/192.168.0.*.log')
    db = InfluxDB('Environment')

    for metric in sensors.metrics_streamer():
        try:
            location = metric['location']
            data_payload = {
                'measurement': 'environmental',
                'tags': {
                    'sensor': location
                },
                'time': metric['time'],
                'fields': {
                    'temperature': metric['temperature'],
                    'humidity': metric['humidity']
                }
            }
            print(data_payload)
            db.write(data_payload)
        except Exception as e:
            print(f'ERROR: {str(e)}')


if __name__ == '__main__':
    read_syslog()
