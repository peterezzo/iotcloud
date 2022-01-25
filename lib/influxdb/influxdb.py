"""
Python object to work with InfluxDB2 using credentials from configuration files on shared docker volume

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import sys
import influxdb_client  # type: ignore


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

    def query(self, query):
        return self.query_api.query(org=self.org, query=query)
