import telebot
from config import BOT_TOKEN
from handlers import register_handlers
from admin import register_admin 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

register_handlers(bot)
register_admin(bot)      

bot.infinity_polling(skip_pending=True)
