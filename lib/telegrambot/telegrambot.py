"""
Python object to start a Telegram bot

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import html
import json
import time
import traceback
from telegram import Update, ParseMode  # type: ignore
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext  # type: ignore


class TelegramBot():
    def __init__(self, token: str, chat_id: int):
        # set up the bot
        self.updater = Updater(token)
        dispatcher = self.updater.dispatcher
        dispatcher.add_error_handler(self.error_handler)

        # limit access to a single telegram chat ID
        self.chat_id = chat_id
        self.userfilter = Filters.user(user_id=self.chat_id)

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", self.start))

        # on non command i.e message - run shell
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.logonly))

        self.updater.start_polling()
        print('updater thread going', flush=True)
        # updater.idle()

        self.send_msg(f'Bot startup completed at {time.time()}', None)

    def add_handler(self, command: str, callback: object) -> None:
        self.updater.dispatcher.add_handler(CommandHandler(command, callback, self.userfilter))

    def error_handler(self, update: object, context: CallbackContext) -> None:
        """
        Catch exceptions and send tracebacks to the identified chat_id
        """
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)

        # Build the message with some markup and additional information about what happened.
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f'An exception was raised while handling an update\n'
            f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}'
            '</pre>\n\n'
            f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
            f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
            f'<pre>{html.escape(tb_string)}</pre>'
        )
        self.send_msg(text=message, parse_mode=ParseMode.HTML)

    def logonly(self, update: object, _: CallbackContext):
        """
        Log some info locally for otherwise unhandled messages
        """
        client_message = update.message or update.edited_message
        print('Received msg',
              update.effective_chat.id,
              update.effective_user.id,
              update.effective_user.username,
              update.effective_user.first_name,
              update.effective_user.last_name,
              client_message.text)

    def send_msg(self, text: str, parse_mode=None, chat_id=None):
        """
        Send a message to a chat, autobreaking at maximum length
        """
        chat_id = chat_id or self.chat_id
        for msg in [text[i:i+4096] for i in range(0, len(text), 4096)]:
            print('Sending', len(msg), type(msg), msg, flush=True)
            self.updater.bot.send_message(chat_id=chat_id, text=msg, parse_mode=parse_mode)

    def start(self, update: Update, context: CallbackContext) -> None:
        """
        Send a message when the command /start is issued.
        """
        self.logonly(update, context)
        for msg in [
            fr'Hi {update.effective_user.mention_markdown_v2()}!',
            f'Your chat id is `{update.effective_chat.id}`.  \n' +
            'If this id matches the allow list, you will be able to use further commands.  \n' +
            'Try /help for additional information.  \n'
        ]:
            update.effective_message.reply_markdown(msg)
