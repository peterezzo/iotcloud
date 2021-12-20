#!/usr/bin/env python3
"""
Read syslog temperature file and send data to influxdb

Author: Pete Ezzo <peter.ezzo@gmail.com>

"""

import datetime
import json
import re
import subprocess
import sys

import influxdb_client


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


class SensorLog(Log):
    def __init__(self, logfile):
        self.logfile = logfile
        self.dht22_pattern = re.compile(rb'(\w+\s+\d+ \d+:\d+:\d+) [^{]+({.*})')

    def metrics_streamer(self):
        lines = self.logtail(self.logfile)
        for line in lines:
            extract = self.dht22_pattern.match(line)
            if extract:
                rawtime = extract.group(1).decode()
                time = datetime.datetime.strptime(rawtime, r'%b %d %H:%M:%S').replace(year=datetime.date.today().year)
                metrics = json.loads(extract.group(2))
                metrics['time'] = str(time)
                yield metrics
            else:
                print('WARNING: Unparsed: ', line, file=sys.stderr)


class InfluxDB():
    def __init__(self, bucket, hostname='influxdb'):
        self.token = None
        self.org = None
        self.bucket = bucket
        self.load_config()

        url = f'http://{hostname}:8086'
        self.client = influxdb_client.InfluxDBClient(url=url, token=self.token, org=self.org)

        self.write_api = self.client.write_api(write_options=influxdb_client.client.write_api.SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def load_config(self):
        with open('/etc/influxdb2/influx-configs') as f:
            for line in f:
                if 'token =' in line and not self.token:
                    self.token = line.split()[-1].strip('"')
                    print('Token is: ', self.token, file=sys.stderr)
                if 'org =' in line and not self.org:
                    self.org = line.split()[-1].strip('"')
                    print('Org is: ', self.org, file=sys.stderr)

    def write(self, record):
        self.write_api.write(bucket=self.bucket, record=record)

    def write_tempdata(self, coop, temperature, humidity):
        p = influxdb_client.Point("environmental").tag("coop", coop).field("temperature", temperature).field('humidity', humidity)
        self.write(p)

    def write_points(self, points):
        self.client.write_points(json.dumps(points))


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
