import telebot
from telebot import types
import requests
import uuid
import sqlite3
import time

BOT_TOKEN = "8471607341:AAEBYmluKdzRCA0mKrJ2ZLhkTQNpCQhZF40"
CRYPTO_PAY_TOKEN = "510865:AA69PCZiydwaRTwj2zx4DcrJDGVYDn2Ngta"

ADMIN_IDS = [8226485380]
DEFAULT_PRICE = 0.05

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
HEADERS = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS links (link TEXT);
CREATE TABLE IF NOT EXISTS used (user_id INTEGER);
CREATE TABLE IF NOT EXISTS promocodes (code TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT, value TEXT);
CREATE TABLE IF NOT EXISTS discounts (
    price REAL,
    limit_users INTEGER,
    used_users INTEGER,
    end_time INTEGER
);
""")
conn.commit()


def get_price():
    d = cur.execute("SELECT price, limit_users, used_users, end_time FROM discounts").fetchone()
    if not d:
        return DEFAULT_PRICE
    price, limit_u, used_u, end_t = d
    if (limit_u and used_u >= limit_u) or (end_t and time.time() > end_t):
        cur.execute("DELETE FROM discounts")
        conn.commit()
        return DEFAULT_PRICE
    return price


def get_link():
    r = cur.execute("SELECT link FROM links LIMIT 1").fetchone()
    if not r:
        return None
    cur.execute("DELETE FROM links WHERE link=?", (r[0],))
    conn.commit()
    return r[0]


def mark_used(uid):
    cur.execute("INSERT INTO used VALUES (?)", (uid,))
    conn.commit()


def has_used(uid):
    return cur.execute("SELECT 1 FROM used WHERE user_id=?", (uid,)).fetchone()


@bot.message_handler(commands=["start"])
def start(m):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (m.from_user.id,))
    conn.commit()

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Купить приват", callback_data="buy"),
        types.InlineKeyboardButton("Ввести промокод", callback_data="promo"),
        types.InlineKeyboardButton("Тех поддержка", callback_data="support"),
        types.InlineKeyboardButton("Что такое приват", callback_data="about")
    )
    bot.send_message(m.chat.id, "<b>Добро пожаловать</b>", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "support")
def sup(c):
    bot.send_message(c.message.chat.id, "<b>Техподдержка - @duracheyo</b>")


@bot.callback_query_handler(func=lambda c: c.data == "about")
def ab(c):
    bot.send_message(c.message.chat.id,
        "<b>приватка - лучшие фиксы, кфг, логи и эксклюзивный контент</b>")


@bot.callback_query_handler(func=lambda c: c.data == "promo")
def promo(c):
    bot.send_message(c.message.chat.id, "<b>Введите промокод</b>")
    bot.register_next_step_handler(c.message, check_promo)


def check_promo(m):
    code = m.text.strip()
    if has_used(m.from_user.id):
        bot.send_message(m.chat.id, "<b>Вы уже получили доступ</b>")
        return
    r = cur.execute("SELECT code FROM promocodes WHERE code=?", (code,)).fetchone()
    if not r:
        bot.send_message(m.chat.id, "<b>Промокод недействителен</b>")
        return
    link = get_link()
    if not link:
        bot.send_message(m.chat.id, "<b>Ссылки закончились</b>")
        return
    cur.execute("DELETE FROM promocodes WHERE code=?", (code,))
    mark_used(m.from_user.id)
    bot.send_message(m.chat.id, f"<b>Ваш доступ:\n{link}</b>")


@bot.callback_query_handler(func=lambda c: c.data == "buy")
def buy(c):
    if has_used(c.from_user.id):
        bot.answer_callback_query(c.id, "Вы уже получили доступ", show_alert=True)
        return

    price = get_price()
    payload = str(uuid.uuid4())

    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers=HEADERS,
        json={"asset": "USDT", "amount": price, "payload": payload}
    ).json()

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Оплатить", url=r["result"]["pay_url"]),
        types.InlineKeyboardButton("Проверить оплату", callback_data=f"check_{r['result']['invoice_id']}")
    )

    bot.send_message(c.message.chat.id, f"<b>Цена: {price} USDT</b>", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check(c):
    inv = c.data.split("_")[1]
    r = requests.get(
        "https://pay.crypt.bot/api/getInvoices",
        headers=HEADERS,
        params={"invoice_ids": inv}
    ).json()

    if r["result"]["items"][0]["status"] != "paid":
        bot.answer_callback_query(c.id, "Оплата не найдена", show_alert=True)
        return

    link = get_link()
    if not link:
        bot.send_message(c.message.chat.id, "<b>Ссылки закончились</b>")
        return

    cur.execute("UPDATE discounts SET used_users=used_users+1")
    conn.commit()

    mark_used(c.from_user.id)
    bot.send_message(c.message.chat.id, f"<b>Оплата успешна\n{link}</b>")


@bot.message_handler(commands=["admin"])
def admin(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Создать промокод", "Удалить промокод", "Загрузить ссылки", "Рассылка", "Акция")
    bot.send_message(m.chat.id, "<b>Админ меню</b>", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "Создать промокод")
def cp(m):
    bot.send_message(m.chat.id, "<b>Введите слово для промокода</b>")
    bot.register_next_step_handler(m, lambda x:
        cur.execute("INSERT INTO promocodes VALUES (?)",
        (f"PRIVAT-PREVO-{x.text}",)) or conn.commit() or
        bot.send_message(m.chat.id, "<b>Промокод создан</b>")
    )


@bot.message_handler(func=lambda m: m.text == "Удалить промокод")
def dp(m):
    bot.send_message(m.chat.id, "<b>Введите промокод</b>")
    bot.register_next_step_handler(m, lambda x:
        cur.execute("DELETE FROM promocodes WHERE code=?", (x.text,)) or conn.commit() or
        bot.send_message(m.chat.id, "<b>Удалён</b>")
    )


@bot.message_handler(func=lambda m: m.text == "Акция")
def act(m):
    bot.send_message(m.chat.id, "<b>Введите цену, лимит пользователей и время в минутах\nпример: 0.02 10 60</b>")
    bot.register_next_step_handler(m, set_discount)


def set_discount(m):
    p, lim, mins = m.text.split()
    cur.execute("DELETE FROM discounts")
    cur.execute("INSERT INTO discounts VALUES (?,?,0,?)",
        (float(p), int(lim), int(time.time()+int(mins)*60)))
    conn.commit()
    bot.send_message(m.chat.id, "<b>Акция активирована</b>")


bot.infinity_polling(skip_pending=True)
