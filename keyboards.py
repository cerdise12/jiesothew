from telebot import types

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Купить приват", callback_data="buy"),
        types.InlineKeyboardButton("🎯 Реферальная система", callback_data="refs"),
        types.InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo"),
        types.InlineKeyboardButton("🛠 Техподдержка", callback_data="support"),
        types.InlineKeyboardButton("❓ Что такое приват", callback_data="about")
    )
    return kb

def buy_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Крипта", callback_data="pay_crypto"),
        types.InlineKeyboardButton("💳 Рубли", callback_data="pay_rub"),
        types.InlineKeyboardButton("⭐ Звёзды", callback_data="pay_star")
    )
    return kb
