import daiquiri
import pytest
from unittest import mock

import telegram_helper


logger = daiquiri.getLogger(__name__)


def test_command_decorator():
    @telegram_helper.command
    def func1():
        pass

    @telegram_helper.command(bla=5, blub=7)
    def func2():
        pass

    assert func1._command_options == ((), {})
    assert func2._command_options == ((), {"bla": 5, "blub": 7})


def test_check_id():
    pseudo_command = mock.Mock()
    self = mock.Mock()
    self.authorized = {}
    self.pending = {}
    bot = mock.Mock()
    update = mock.Mock()
    update.message.chat_id = 1234

    decorated = telegram_helper.check_id(pseudo_command)
    decorated(self, bot, update)

    # as the id is not contained in authorized,
    # check_id should send a warning message
    bot.send_message.assert_called_once()
    assert 1234 in self.pending

    # Call the decorated command three more times
    # No more messages should be sent as the id
    # is now in pending
    for i in range(3):
        decorated(self, bot, update)

    logger.debug(self.pending)
    bot.send_message.assert_called_once()

    bot.reset_mock()
    self.authorized = {1234}
    decorated(self, bot, update)

    bot.send_message.assert_not_called()


def test_authorize():
    self = mock.Mock()
    bot = mock.Mock()
    update = mock.Mock()
    id_to_be_authorized = 5678
    update.message.chat_id = self.admin_id = 1234
    self.authorized = {}
    self.pending = {}

    telegram_helper.TelegramBot.authorize(self, bot, update, [id_to_be_authorized])
    assert id_to_be_authorized in self.authorized

    ids_to_be_authorized = [111, 222, 333]
    telegram_helper.TelegramBot.authorize(self, bot, update, ids_to_be_authorized)
    assert all([id_ in self.authorized for id_ in ids_to_be_authorized])
