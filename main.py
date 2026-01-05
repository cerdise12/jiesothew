import telebot
from config import BOT_TOKEN
from handlers import register_handlers

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

register_handlers(bot)

bot.infinity_polling(skip_pending=True)
