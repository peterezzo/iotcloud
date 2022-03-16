#!/usr/bin/env python3
"""
Pull National Weather Service observations and send data to influxdb

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import os
import time
import requests

from influxdb import InfluxDB  # type: ignore


class WeatherPoller():
    def __init__(self):
        self.headers = {
            'accept': 'application/geo+json',
            'user-agent': 'iotcloud data comparator'
        }

    def pull_latest(self, station):
        print('pulling metric for', station, flush=True)
        url = f'https://api.weather.gov/stations/{station}/observations/latest'
        response = requests.get(url, headers=self.headers).json()
        yield self._process_metric(response)

    def pull_all(self, station):
        print('pulling all metrics for', station, flush=True)
        url = f'https://api.weather.gov/stations/{station}/observations'
        responses = requests.get(url, headers=self.headers).json()

        for response in responses['features']:
            yield self._process_metric(response)

    def metrics_streamer(self, station):
        yield self.pull_latest(station)
        print('sleeping', flush=True)
        time.sleep(60 * 15)

    def _process_metric(self, response):
        timestamp = response['properties']['timestamp']
        print('metric pulled for timestamp', timestamp, flush=True)

        metrics = {}
        for metric in response['properties']:
            if metric == 'elevation':
                continue
            try:
                value = response['properties'][metric].get('value')
            except AttributeError:
                continue
            if value is not None:
                if metric == 'relativeHumidity':
                    metric = 'humidity'
                if metric in ['temperature', 'dewpoint', 'windSpeed', 'humidity']:
                    value = float(value)

                metrics[metric] = value

        return timestamp, metrics


def poll_and_update():
    db = InfluxDB('Environment')
    locations = os.getenv('OBSERVATION_STATIONS').split(';')
    poller = WeatherPoller()

    while True:
        for location in locations:
            # for timestamp, metrics in poller.pull_all(location):
            for timestamp, metrics in poller.pull_latest(location):
                try:
                    data_payload = {
                        'measurement': 'environmental',
                        'tags': {
                            'sensor': location
                        },
                        'time': timestamp,
                        'fields': metrics
                    }
                    print(data_payload, flush=True)
                    db.write(data_payload)
                except Exception as e:
                    print(f'ERROR: {str(e)}', flush=True)
        print('sleeping', flush=True)
        time.sleep(60 * 15)


if __name__ == '__main__':
    poll_and_update()
