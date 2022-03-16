"""
Python Inventory Object Management and Retrieval through MQTT Broker (tested with Mosquitto)

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import collections
import json
import os
import random
import sys
from paho.mqtt.publish import multiple  # type: ignore
from inventorydb import InventoryDB  # type: ignore


class InvenCLI():
    def __init__(self) -> None:
        dbname = os.getenv('POSTGRES_DB')
        dbpass = os.getenv('POSTGRES_PASSWORD')
        self.db = InventoryDB('postgres', dbname, 'postgres', dbpass)
        self.mqtt_broker = os.getenv('MQTT_BROKER')
        self.preamble = os.getenv('PREAMBLE')

    def names(self, data: str) -> None:
        results = self.db.search_all(data)
        for result in results:
            print(f'{result[1]} {result[3]} : {result[2]}')

    def unames(self, data: str) -> None:
        results = self.db.search_names(data)
        for result in results:
            print(f'{result[0]} : {result[1]}')

    def sources(self, data: str) -> None:
        results = self.db.search_all_by_src(data)
        for result in results:
            print(f'{result[3]} : {result[2]}')

    def get(self, data: str, dryrun: bool) -> None:
        cmds = []
        objmap = collections.defaultdict(lambda: set())
        for name, source in [(r[3], r[1]) for r in self.db.search_all(data)]:
            objmap[name].add(source)
        for name, sources in {k: list(objmap[k]) for k in sorted(objmap, key=lambda k: len(objmap[k]))}.items():
            target = sources[random.randint(0, len(sources) - 1)]
            payload = json.dumps({'type': 'privmsg', 'target': target, 'msg': f'{self.preamble} {name}'})
            cmds.append(('Commands/IRC', payload, 2, False))

        print('\n'.join([c[1] for c in cmds]))
        if not dryrun:
            multiple(cmds, hostname=self.mqtt_broker)


if __name__ == '__main__':
    inventory = InvenCLI()
    if len(sys.argv) < 3:
        print('Unrecognized command, try: names, unames, find, sources, get')
    elif sys.argv[1][:2] == 'na':
        inventory.names(sys.argv[2])
    elif sys.argv[1][:2] == 'un' or sys.argv[1][:2] == 'fi':
        inventory.unames(sys.argv[2])
    elif sys.argv[1][:2] == 'so':
        inventory.sources(sys.argv[2])
    elif sys.argv[1][:2] == 'ge':
        inventory.get(sys.argv[2], '-n' in sys.argv)
