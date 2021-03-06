import configparser
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
    def new_func(self, bot, update, *args, **kwargs):
        requesting_id = update.message.chat_id
        if requesting_id in self.authorized:
            logger.debug("Found ID in database")
            func(self, bot, update, *args, **kwargs)
        else:
            chat = update.message.chat
            warning = f"User {chat.first_name} {chat.last_name} with id " \
                      f"{requesting_id} not in id list"
            logger.warning(warning)
            if requesting_id not in self.pending:
                bot.send_message(chat_id=self.admin_id, text=warning)
                self.pending[requesting_id] = {"first_name": chat.first_name,
                                               "last_name": chat.last_name}
    return new_func


def only_admin(func):
    @wraps(func)
    def new_func(self, bot, update, *args, **kwargs):
        requesting_id = update.message.chat_id
        if requesting_id == self.admin_id:
            func(self, bot, update, *args, **kwargs)
        else:
            logger.warn("Non-admin %s tried to use command %s", requesting_id, func.__name__)
    return new_func


def command(*command_args, **command_kwargs):
    logger.debug("Arguments to CommandHandler: %s %s", command_args, command_kwargs)
    called_wo_args = len(command_args) == 1 and len(command_kwargs) == 0 and callable(command_args[0])
    if called_wo_args:
        fun = command_args[0]
        command_args = ()
        logger.debug("%s was decorated without args and kwargs", fun)
    def _command(func):
        logger.debug("Adding command options to %s", func)
        logger.debug("args = %s", command_args)
        logger.debug("kwargs = %s", command_kwargs)
        func._command_options = (command_args, command_kwargs)
        return func
    if called_wo_args:
        return _command(fun)
    return _command
command.__signature__ = partial_commandhandler()


class TelegramBot:
    """The TelegramBot class is a simple object oriented wrapper
    around the python-telegram-bot API.

    By subclassing this class, an authentication method will be
    available which automatically reports messages from
    unauthenticated users to the admin.
    Furthermore, a database (as a shelve) is set up in order to
    store the bot state on long terms.
    """
    def __init__(self, token, admin_id, database_filename=None):
        self.handlers = []
        self.updater = Updater(token=token)
        self.token = token
        self.admin_id = admin_id
        if not database_filename:
            database_filename = f"{type(self).__name__}.shelve"
        self.database_filename = database_filename
        logger.debug("Opening %s", self.database_filename)
        self.database = shelve.open(database_filename, writeback=True)
        self.authorized = self.database.setdefault("authorized", {self.admin_id: {}})
        self.pending = self.database.setdefault("pending", set())

        for x in dir(self):
            if not x.startswith("__"):
                attr = getattr(self, x)
                if hasattr(attr, "_command_options"):
                    logger.debug("Adding %s to handlers", attr)
                    logger.debug("Command options: %s", attr._command_options)
                    self.handlers.append(CommandHandler(command=attr.__name__,
                                                        callback=attr,
                                                        *attr._command_options[0],
                                                        **attr._command_options[1]))

        dispatcher = self.updater.dispatcher
        for h in self.handlers:
            dispatcher.add_handler(h)

    def __del__(self):
        logger.debug("Closing %s", self.database_filename)
        self.database.close()

    @classmethod
    def from_configfile(cls, configfile):
        """
        Load values from config file.

        [Telegram]
        token: Telegram token needed as authentication
        admin_id: Telegram id of the admin
        database_filename: file name of the shelve in which the bot state is
        saved

        [<Bot name>]
        If an additional section with the name of the bot is present in the
        config file, attributes with the corresponding values will be created
        during the bot initialization.
        """
        defaults = {"Telegram": ["token", "admin_id", "database_filename"]}
        cp = configparser.ConfigParser()
        config = cp.read(configfile)
        if not config:
            logger.info("No configfile with name %s was found. Creating one...", configfile)
            for section in defaults:
                cp.add_section(section)
                for key in defaults[section]:
                    cp.set(section, key, "")
            with open(configfile, "w") as f:
                cp.write(f)

        token = cp.get("Telegram", "token")
        admin_id = cp.getint("Telegram", "admin_id")
        database_filename = cp.get("Telegram", "database_filename")

        obj = cls(token=token, admin_id=admin_id, database_filename=database_filename)

        bot_name = cls.__name__
        if cp.has_section(bot_name):
            for k, v in cp[bot_name].items():
                setattr(obj, k, v)
        return obj

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    @command(pass_args=True)
    @only_admin
    def authorize(self, bot, update, args):
        user_id = update.message.from_user.id
        if not args:
            logger.debug("No ids specified")
            return
        try:
            new_ids = [int(arg) for arg in args]
        except ValueError:
            bot.send_message(chat_id=self.admin_id, text="Ungültige id")
        logger.debug("New ids: %s", new_ids)
        for id_ in new_ids:
            name_dict = self.pending.pop(id_) if id_ in self.pending else {}
            self.authorized[id_] = name_dict
            bot.send_message(chat_id=self.admin_id, text=f"Füge id {id_} hinzu.")
            bot.send_message(chat_id=id_, text="Willkommen!")
