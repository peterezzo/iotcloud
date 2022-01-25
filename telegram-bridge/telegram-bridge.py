#!/usr/bin/env python3
"""
Telegram-MQTT Bridge and Notifier
"""

import os
import time

from mqtt import MQTT  # type: ignore
from telegrambot import TelegramBot, Update, CallbackContext, ParseMode  # type: ignore


class Bridge():
    def __init__(self) -> None:
        self.main()

    def relay_notification(self, mosq, obj, msg):
        """
        Send a message to the chat when a Notification arrives in broker (MQTT Callback)
        """
        topic = msg.topic.split('/', maxsplit=1)[1]
        payload = msg.payload.decode()
        self.bot.send_msg(f'Notification [{topic}] {payload}')

    def help(self, update: Update, context: CallbackContext) -> None:
        """Display available commands when /help is issued in Telegram. (Telegram Callback)"""
        self.bot.send_msg('Commands are:  \n' +
                          '/pub  \n' +
                          '/temperatures  \n' +
                          '/humidities  \n' +
                          '/rollcall  \n',
                          parse_mode=ParseMode.MARKDOWN_V2)

    def pub(self, update: Update, context: CallbackContext) -> None:
        """Perform the MQTT publish flow when /pub is issued in Telegram. (Telegram Callback)"""
        self.mqtt.pub('Test', 'publish command')

    def temperatures(self, update: Update, context: CallbackContext) -> None:
        """Perform the temperature display flow when /temperatures is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/Sensors', 'get-temperatures', qos=1)

    def humidities(self, update: Update, context: CallbackContext) -> None:
        """Perform the temperature display flow when /humidities is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/Sensors', 'get-humidities', qos=1)

    def rollcall(self, update: Update, context: CallbackContext) -> None:
        """Perform a checkin of bot fleet  when /rollcall is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/ALL', 'check-in')

    def main(self) -> None:
        token = os.getenv('TELEGRAM_TOKEN')
        chat_id = int(os.getenv('TELEGRAM_CHAT_ID'))
        mqtt_broker = os.getenv('MQTT_BROKER')

        self.bot = TelegramBot(token, chat_id)
        if self.bot.updater.running:
            print('Bot startup complete')

        self.mqtt = MQTT(mqtt_broker, client_id='telegram-mqtt-bridge')
        self.mqtt.listen()
        print('MQTT startup complete')

        print('adding callbacks', flush=True)
        self.mqtt.sub(self.relay_notification, 'Notifications/#')
        self.bot.add_handler('help', self.help)
        self.bot.add_handler('pub', self.pub)
        self.bot.add_handler('temperatures', self.temperatures)
        self.bot.add_handler('humidities', self.humidities)
        self.bot.add_handler('rollcall', self.rollcall)

        self.mqtt.pub('Logs', f'Telegram Bridge Startup at {time.time()}', qos=1)
        while True:
            time.sleep(1)


if __name__ == '__main__':
    Bridge()
