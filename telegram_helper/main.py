import configparser
from inspect import isfunction
from functools import wraps
import inspect
import logging
import shelve

from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler)


logger = logging.getLogger(__name__)


def partial_commandhandler():
    commandhandler_sign = inspect.signature(CommandHandler)
    params = [v for k, v in commandhandler_sign.parameters.items()
              if k not in ("command", "callback")]
    return inspect.Signature(params)


def check_id(func):
    @wraps(func)
    def new_func(self, bot, update, **kwargs):
        requesting_id = update.message.chat_id
        if requesting_id in self.authorized:
            logger.debug("Found ID in database")
            func(self, bot, update, **kwargs)
        else:
            chat = update.message.chat
            warning = f"User {chat.first_name} {chat.last_name} with id " \
                      f"{requesting_id} not in id list"
            logger.warning(warning)
            bot.send_message(chat_id=self.admin_id, text=warning)
    return new_func


def command(*command_args, **command_kwargs):
    logger.debug("Arguments to CommandHandler: %s %s", command_args, command_kwargs)
    called_wo_args = len(command_args) == 1 and len(command_kwargs) == 0 and callable(command_args[0])
    if called_wo_args:
        fun = command_args[0]
        command_args = []
        logger.debug(f"{fun} was decorated without args and kwargs")
    def _command(func):
        logger.debug(f"Adding command options to {func}")
        func._command_options = (command_args, command_kwargs)
        return func
    if called_wo_args:
        return _command(fun)
    return _command
command.__signature__ = partial_commandhandler()


class TelegramBot:
    def __init__(self, token, admin_id, database_filename=None):
        self.handlers = []
        self.updater = Updater(token=token)
        self.token = token
        self.admin_id = admin_id
        if not database_filename:
            database_filename = f"{type(self).__name}.shelve"
        self.database_filename = database_filename
        logger.debug(f"Opening {self.database_filename}")
        self.database = shelve.open(database_filename, writeback=True)
        self.authorized = self.database.setdefault("authorized", [])

        for x in dir(self):
            if not x.startswith("__"):
                attr = getattr(self, x)
                if hasattr(attr, "_command_options"):
                    logger.debug(f"Adding {attr} to handlers")
                    logger.debug(f"Command options: {attr._command_options}")
                    self.handlers.append(CommandHandler(command=attr.__name__,
                                                        callback=attr,
                                                        *attr._command_options[0],
                                                        **attr._command_options[1]))

        dispatcher = self.updater.dispatcher
        for h in self.handlers:
            dispatcher.add_handler(h)

    def __del__(self):
        logger.debug(f"Closing {self.database_filename}")
        self.database.close()

    @classmethod
    def from_configfile(cls, configfile):
        defaults = {"Telegram": ["token", "admin_id", "database_filename"]}
        cp = configparser.ConfigParser()
        config = cp.read(configfile)
        if not config:
            logger.info(f"No configfile with name {configfile} was found. Creating one...")
            for section in defaults:
                cp.add_section(section)
                for key in defaults[section]:
                    cp.set(section, key, "")
            with open(configfile, "w") as f:
                cp.write(f)

        token = cp.get("Telegram", "token")
        admin_id = cp.getint("Telegram", "admin_id")
        database_filename = cp.get("Telegram", "database_filename")
        return cls(token=token, admin_id=admin_id, database_filename=database_filename)

    def run(self):
            self.updater.start_polling()
            self.updater.idle()

    @command(pass_args=True)
    def authorize(self, bot, update, args):
        user_id = update.message.from_user.id
        if user_id != self.admin_id:
            logger.debug("Authorization request from non-Admin")
            return
        if not args:
            logger.debug("No ids specified")
            return
        try:
            new_ids = [int(arg) for arg in args]
        except ValueError:
            bot.send_message(chat_id=self.admin_id, text="Ungültige id")
        logger.debug("New ids: %s", new_ids)
        for id_ in new_ids:
            self.authorized.append(id_)
            bot.send_message(chat_id=self.admin_id, text=f"Füge id {id_} hinzu.")
            bot.send_message(chat_id=id_, text=f"Willkommen!")
