#!/usr/bin/env python3
"""
Telegram-MQTT Bridge and Notifier

   Copyright 2018-2021  Lucas de Carvalho Bueno Santos (beothorn)
   Copyright 2022       Pete Ezzo

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

"""

import os
import time

from mqtt import MQTT  # type: ignore
from telegrambot import TelegramBot, Update, CallbackContext  # type: ignore


class Bridge():
    def __init__(self) -> None:
        self.cmds = [
            ('chatid', 'Returns your chat id.\n    /chatid', self.chat_id),
            ('down', 'Downloads a file from the server.\n    /down <file name|file path>', self.down),
            ('get', 'Requests object from the network.\n    /get <query>', self.get),
            ('help', 'Display helpful information on how to setup bot.\n    /help', self.help),
            ('humidities', 'Display current humidities.\n    /humidities', self.humidities),
            ('img', 'Returns an image.\n    /img <path>', self.img),
            ('pub', 'Publish an arbitrary message to topic.\n    /pub <topic> <msg>', self.pub),
            ('rollcall', 'Requests all MQTT-integrated systems check-in\n    /rollcall', self.rollcall),
            ('search', 'Search for object names in Postgres\n    /search <query>', self.search),
            ('status', 'Request status from network bot\n    /status', self.search),
            ('temperatures', 'Display current temperatures.\n    /temperatures', self.temperatures),
            ('whoami', 'Returns your user id.\n    /whoami', self.who_am_i),
        ]
        self.main()

    def relay_notification(self, mosq, obj, msg):
        """
        Send a message to the chat when a Notification arrives in broker (MQTT Callback)
        """
        topic = msg.topic.split('/', maxsplit=1)[1]
        payload = msg.payload.decode()
        self.bot.send_msg(f'Notification [{topic}] {payload}')

    def chat_id(self, update: Update, context: CallbackContext) -> None:
        """Display the user's chat id (Telegram Callback)"""
        context.bot.send_message(chat_id=update.message.chat_id, text=update.message.chat_id)

    def down(self, update: Update, context: CallbackContext) -> None:
        """Imported and Unverified. (Telegram Callback)"""
        current_dir = '.'
        path = ' '.join(context.args)
        if path.startswith('/'):
            context.bot.send_document(chat_id=update.message.chat_id, document=open(path, 'rb'))
        else:
            context.bot.send_document(chat_id=update.message.chat_id, document=open(f'{current_dir}/{path}', 'rb'))

    def get(self, update: Update, context: CallbackContext) -> None:
        """Get an object from the IRC network. (Telegram Callback)"""
        self.mqtt.pub('Commands/Postgres', f'get {context.args[0]}')

    def help(self, update: Update, context: CallbackContext) -> None:
        """Display available commands when /help is issued in Telegram. (Telegram Callback)"""
        self.bot.send_msg('Commands are:\n' + '\n'.join([cmd[1] for cmd in self.cmds]) + '\n')

    def img(self, update: Update, context: CallbackContext) -> None:
        """Imported and Unverified. (Telegram Callback)"""
        path = ' '.join(context.args)
        with open(path, 'rb') as file:
            context.bot.send_photo(chat_id=update.message.chat_id, photo=file)

    def pub(self, update: Update, context: CallbackContext) -> None:
        """Perform the MQTT publish flow when /pub is issued in Telegram. (Telegram Callback)"""
        self.mqtt.pub(context.args[0], ' '.join(context.args[1:]))

    def temperatures(self, update: Update, context: CallbackContext) -> None:
        """Perform the temperature display flow when /temperatures is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/Influx', 'get-temperatures')

    def humidities(self, update: Update, context: CallbackContext) -> None:
        """Perform the temperature display flow when /humidities is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/Influx', 'get-humidities')

    def rollcall(self, update: Update, context: CallbackContext) -> None:
        """Perform a checkin of bot fleet  when /rollcall is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/ALL', 'check-in')

    def search(self, update: Update, context: CallbackContext) -> None:
        """Perform an object search in postgres /search is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/Postgres', f'search {context.args[0]}')

    def status(self, update: Update, context: CallbackContext) -> None:
        """Perform the temperature display flow when /temperatures is issued. (Telegram Callback)"""
        self.mqtt.pub('Commands/IRC', '{"type": "status"}')

    def who_am_i(self, update: Update, context: CallbackContext):
        """Imported and Unverified. (Telegram Callback)"""
        context.bot.send_message(chat_id=update.message.chat_id, text=update.message.from_user.id)

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
        for cmd in self.cmds:
            self.bot.add_handler(cmd[0], cmd[2])

        while True:
            time.sleep(1)


if __name__ == '__main__':
    Bridge()
