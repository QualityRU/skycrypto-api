import os

from telegram import Bot, ParseMode
from telegram.ext import Defaults

bot = Bot(os.getenv('FROZEN_CONTROLLER_BOT_TOKEN'), defaults=Defaults(parse_mode=ParseMode.HTML))
