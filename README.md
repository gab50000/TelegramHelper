# Telegram Helper

This package provides some helper functions to ease development of Telegram bots with the python-telegram-bot package.


## Installation

To install, you need flit and Python 3.6.

```
pip install flit
```

Then

```
git clone https://github.com/gab50000/TelegramHelper
cd TelegramHelper
flit install
```


## Usage

Telegram Helper reduces the amount of code required to write a functional Telegram bot to a few lines.


1) Talk to the bot father to receive a new token for your bot

2) Write a small config file (let's call it "bot.cfg") like this:

```config
[Telegram]
token = 123456789abcdefg
admin_id = 1234567
database_filename = bot.shelve
```

3) Now write the Python script

```python
from telegram_helper import TelegramBot, command, check_id


class MyBot(TelegramBot):
    @command
    def start(self, bot, update):
        message = update.message
        message.reply_text("Hello there")

    @check_id
    @command
    def not_for_everyone(self, bot, update):
        message = update.message
        message.reply_text("Secret message")


my_bot = MyBot.from_configfile("bot.cfg")
my_bot.run()
```

When you start the conversation with your bot (or explicitly write "/start"), it should greet you with a "Hello there".

Note that the bot will answer to anybody. There are no restrictions at all. This can become a problem if your bot runs on a small server of yours and you don't want to expose it to the whole world.

In this case, you can use the decorator ```check_id```.
This decorator function will contact the administrator if an unknown Telegram user tries to use the decorated method of your bot.
You can then either ignore the request or authorize the user via the command

```
/authorize <id>
```
where you have to replace \<id\> with the id of the requesting user.

Each authorized user will be stored in a database, so even after a restart, your bot will not have forgotten your authorizations.