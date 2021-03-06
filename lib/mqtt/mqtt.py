"""
Python object to work with MQTT Broker (tested with Mosquitto)
"""

import pathlib
import time
from functools import wraps
from typing import Any, Callable, Iterable
from paho.mqtt.client import Client, MQTTMessage  # type: ignore


HEALTHCHECK = pathlib.Path('/dev/shm/mqtt_healthcheck')


def healthcheck(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        HEALTHCHECK.touch()
        fn(*args, **kwargs)
    return wrapper


class MQTT():
    def __init__(self,
                 host: str,
                 port: int = 1883,
                 user: str = None,
                 password: str = None,
                 keepalive: int = 60,
                 client_id: str = None,
                 use_ssl: bool = False
                 ) -> None:

        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.client_id = client_id
        self.client = Client(client_id)

        if use_ssl:
            self.client.tls_set()
            self.client.tls_insecure_set(True)

        if user or password:
            self.client.username_pw_set(user, password)

        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    @healthcheck
    def on_message(self, client: Client, userdata: Any, msg: MQTTMessage) -> None:
        print(f'Msg: {msg.topic} {str(msg.qos)} {str(msg.payload)}')
        if msg.topic == 'Commands/ALL' and msg.payload == b'check-in':
            self.pub('Notifications/check-in-reply', self.client_id, qos=1)

    @healthcheck
    def on_connect(self, client: Client, userdata: Any, flags: dict, rc: int) -> None:
        print(f'Connected to {client._host}:{client._port} code {rc}')
        self.sub(None, 'Commands/ALL', qos=1)
        self.pub('Notifications/startup', f'{self.client_id} connect at {time.time()}', qos=1)

    def on_disconnect(self, client: Client, userdata: Any, rc: int) -> None:
        print(f'Disconnected from {client._host}:{client._port} code {rc}')

    @healthcheck
    def pub(self, topic: str, message: str, qos: int = 2, retain: bool = False,  verbose: bool = False) -> None:
        self.client.publish(topic, message, qos, retain)
        if verbose:
            print('PUBLISH', topic, message, flush=True)

    @healthcheck
    def sub(self, callback: Callable, topic: str, qos: int = 2) -> None:
        if callback:
            self.client.message_callback_add(topic, healthcheck(callback))
        self.client.subscribe(topic, qos)

    @healthcheck
    def multipub(self, msgs: Iterable, verbose: bool = False) -> None:
        for msg in msgs:
            self.pub(*msg, verbose=verbose)

    def listen(self, blocking: bool = False) -> None:
        """
        This is the main loop for a client waiting for messages
        """
        self.client.connect(self.host, self.port, self.keepalive)
        if blocking:
            print('Starting blocking MQTT loop', flush=True)
            self.client.loop_forever()
        else:
            print('Starting nonblocking MQTT thread', flush=True)
            self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
