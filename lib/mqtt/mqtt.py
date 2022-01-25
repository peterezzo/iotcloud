"""
Python object to work with MQTT Broker (tested with Mosquitto)

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import sys
import time
import paho.mqtt.client  # type: ignore


class MQTT():
    def __init__(self, host, port=1883, user=None, password=None, keepalive=60, client_id=None, connect=True):
        self.client = paho.mqtt.client.Client(client_id)

        self._subscribed = set()
        self._keepalive = keepalive

        if user or password:
            self.client.username_pw_set(user, password)

        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        # self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe

        if connect:
            self.client.connect(host, port, keepalive)

    def on_message(self, mosq, obj, msg):
        print(f'Msg: {msg.topic} {str(msg.qos)} {str(msg.payload)}')
        if msg.topic == 'Commands/ALL' and msg.payload == b'check-in':
            self.pub('Notifications/check-in-reply', sys.argv[0], qos=1)

    def on_connect(self, mqttc, obj, flags, rc):
        print(f'Connected to {mqttc._host}:{mqttc._port} code {rc}', flush=True)
        self.sub(None, 'Commands/ALL', qos=1)
        self.pub('Logs', f'InfluxDB Bridge Startup at {time.time()}', qos=1)
        # for sub in self._subscribed:
        #     print('Resubscribing to', sub)
        #     self.sub(*sub)

    def on_disconnect(self, mqttc, obj, rc):
        print(f'Disconnected from {mqttc._host}:{mqttc._port} code {rc}', flush=True)

    def on_publish(self, mqttc, obj, mid):
        print(f'mid: {str(mid)}')

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        print(f'Subscribed {str(mid)} {str(granted_qos)}')

    def listen(self, blocking=False):
        """
        This is the main loop for a client waiting for messages
        """
        if blocking:
            print('Starting blocking MQTT loop', flush=True)
            self.client.loop_forever()
        else:
            print('Starting nonblocking MQTT loop', flush=True)
            self.client.loop_start()

    def pub(self, topic, message, retain=False, qos=0):
        self.client.publish(topic, message, qos)

    def sub(self, callback, topic, qos=0):
        if callback:
            self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic, qos)
