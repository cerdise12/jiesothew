import telebot
from telebot import types
import sqlite3
import requests
import uuid
import random

# ========= НАСТРОЙКИ =========
BOT_TOKEN = "8471607341:AAEBYmluKdzRCA0mKrJ2ZLhkTQNpCQhZF40"
CRYPTO_PAY_TOKEN = "510865:AA69PCZiydwaRTwj2zx4DcrJDGVYDn2Ngta"
ADMIN_IDS = [283991746 , 874926153]
DEFAULT_PRICE_USDT = 3

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
HEADERS = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

# ========= БАЗА =========
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS banned(user_id INTEGER, reason TEXT);
CREATE TABLE IF NOT EXISTS links(link TEXT);
CREATE TABLE IF NOT EXISTS used(user_id INTEGER);
CREATE TABLE IF NOT EXISTS promocodes(code TEXT UNIQUE, used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, status TEXT);
""")
db.commit()

captcha_sessions = {}

# ========= ВСПОМОГАТЕЛЬНОЕ =========
def is_banned(uid):
    return cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,)).fetchone()

def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users VALUES(?)", (uid,))
    db.commit()

def has_access(uid):
    return cur.execute("SELECT 1 FROM used WHERE user_id=?", (uid,)).fetchone()

def give_access(uid):
    cur.execute("INSERT OR IGNORE INTO used VALUES(?)", (uid,))
    db.commit()

def get_link():
    row = cur.execute("SELECT link FROM links LIMIT 1").fetchone()
    if not row:
        return None
    cur.execute("DELETE FROM links WHERE link=?", (row[0],))
    db.commit()
    return row[0]

# ========= КАПЧА =========
@bot.message_handler(commands=["start"])
def start(m):
    if is_banned(m.from_user.id):
        return

    emojis = ["🍎", "🍌", "🍇", "🍉"]
    correct = random.choice(emojis)
    captcha_sessions[m.from_user.id] = correct

    kb = types.InlineKeyboardMarkup()
    for e in emojis:
        kb.add(types.InlineKeyboardButton(e, callback_data=f"captcha_{e}"))

    bot.send_message(m.chat.id, "<b>Подтверди, что ты не бот\nНажми на:</b> " + correct, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("captcha_"))
def captcha(c):
    choice = c.data.split("_")[1]
    correct = captcha_sessions.get(c.from_user.id)

    if choice != correct:
        bot.answer_callback_query(c.id, "Капча неверна", show_alert=True)
        return

    del captcha_sessions[c.from_user.id]
    add_user(c.from_user.id)

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Купить приват", callback_data="buy"),
        types.InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo"),
        types.InlineKeyboardButton("🛠 Техподдержка", callback_data="support"),
        types.InlineKeyboardButton("❓ Что такое приват", callback_data="about")
    )

    with open("photo.png", "rb") as p:
        bot.send_photo(c.message.chat.id, p, caption="<b>Главное меню</b>", reply_markup=kb)

# ========= ИНФО =========
@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):
    bot.send_message(c.message.chat.id, "<b>Техподдержка — @duracheyo</b>")

@bot.callback_query_handler(func=lambda c: c.data == "about")
def about(c):
    bot.send_message(c.message.chat.id,
        "<b>Приват — это эксклюзивные фиксы, конфиги, логи и контент.\n"
        "Покупка даёт превосходство над другими.</b>")

# ========= ПОКУПКА =========
@bot.callback_query_handler(func=lambda c: c.data == "buy")
def buy(c):
    if has_access(c.from_user.id):
        bot.answer_callback_query(c.id, "Доступ уже выдан", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Крипта", callback_data="pay_crypto"),
        types.InlineKeyboardButton("💳 Рубли", callback_data="pay_rub"),
        types.InlineKeyboardButton("⭐ Звёзды", callback_data="pay_star")
    )
    bot.send_message(c.message.chat.id, "<b>Выбери способ оплаты</b>", reply_markup=kb)

# ========= КРИПТА =========
@bot.callback_query_handler(func=lambda c: c.data == "pay_crypto")
def crypto(c):
    payload = str(uuid.uuid4())
    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers=HEADERS,
        json={"asset": "USDT", "amount": DEFAULT_PRICE_USDT, "payload": payload}
    ).json()

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Оплатить", url=r["result"]["pay_url"]),
        types.InlineKeyboardButton("Проверить", callback_data=f"check_{r['result']['invoice_id']}")
    )
    bot.send_message(c.message.chat.id, "<b>Оплати и нажми Проверить</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check_crypto(c):
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

    give_access(c.from_user.id)
    bot.send_message(c.message.chat.id, f"<b>Оплата прошла!\n{link}</b>")

# ========= РУБЛИ / ЗВЁЗДЫ =========
@bot.callback_query_handler(func=lambda c: c.data in ["pay_rub", "pay_star"])
def manual(c):
    method = "Рубли" if c.data == "pay_rub" else "Звёзды"
    cur.execute("INSERT INTO requests(user_id, method, status) VALUES(?,?,?)",
                (c.from_user.id, method, "wait"))
    db.commit()

    text = (
        "<b>200₽ по СБП — Озон Банк</b>\n"
        "<code>2204320967857881</code>\n"
        "<code>+79836973590</code>\n"
        "Получатель: Дмитрий В.\n\n"
        "⚠️ Только Озон Банк\n\n"
        "📸 Отправь скрин"
        if method == "Рубли"
        else "<b>Отправь 150 ⭐ подарком @emy\nПосле — пришли скрин</b>"
    )

    bot.send_message(c.message.chat.id, text)

# ========= СКРИН =========
@bot.message_handler(content_types=["photo"])
def photo(m):
    row = cur.execute("SELECT id FROM requests WHERE user_id=? AND status='wait'",
                      (m.from_user.id,)).fetchone()
    if not row:
        return

    req_id = row[0]
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"ok_{req_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{req_id}")
    )

    for admin in ADMIN_IDS:
        bot.send_photo(admin, m.photo[-1].file_id,
                       caption=f"<b>Заявка #{req_id}</b>", reply_markup=kb)

    bot.send_message(m.chat.id, "<b>Заявка отправлена админу</b>")

# ========= АДМИН РЕШЕНИЕ =========
@bot.callback_query_handler(func=lambda c: c.data.startswith(("ok_", "no_")))
def decision(c):
    if c.from_user.id not in ADMIN_IDS:
        return

    req_id = c.data.split("_")[1]
    uid = cur.execute("SELECT user_id FROM requests WHERE id=?",
                      (req_id,)).fetchone()[0]

    if c.data.startswith("ok_"):
        link = get_link()
        if link:
            give_access(uid)
            bot.send_message(uid, f"<b>Оплата подтверждена!\n{link}</b>")
        cur.execute("UPDATE requests SET status='ok' WHERE id=?", (req_id,))
    else:
        bot.send_message(uid, "<b>Оплата отклонена</b>")
        cur.execute("UPDATE requests SET status='no' WHERE id=?", (req_id,))
    db.commit()

# ========= ПРОМОКОД =========
@bot.callback_query_handler(func=lambda c: c.data == "promo")
def promo(c):
    bot.send_message(c.message.chat.id, "<b>Введите промокод</b>")
    bot.register_next_step_handler(c.message, check_promo)

def check_promo(m):
    row = cur.execute("SELECT used FROM promocodes WHERE code=?", (m.text,)).fetchone()
    if not row or row[0]:
        bot.send_message(m.chat.id, "<b>Промокод фигня соси баранку</b>")
        return

    link = get_link()
    if not link:
        bot.send_message(m.chat.id, "<b>Ссылки закончились</b>")
        return

    cur.execute("UPDATE promocodes SET used=1 WHERE code=?", (m.text,))
    give_access(m.from_user.id)
    db.commit()
    bot.send_message(m.chat.id, f"<b>Промокод принят!\n{link}</b>")

# ========= АДМИН МЕНЮ =========
@bot.message_handler(commands=["admin"])
def admin(m):
    if m.from_user.id not in ADMIN_IDS:
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Статистика", "➕ Ссылка", "➕ Промо", "🚫 Бан", "📢 Рассылка")
    bot.send_message(m.chat.id, "<b>Админ меню</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats(m):
    users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    sold = cur.execute("SELECT COUNT(*) FROM used").fetchone()[0]
    req = cur.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    bot.send_message(m.chat.id, f"<b>Юзеры: {users}\nПродано: {sold}\nЗаявки: {req}</b>")

@bot.message_handler(func=lambda m: m.text == "➕ Промо")
def addpromo(m):
    bot.send_message(m.chat.id, "<b>Слово для промокода</b>")
    bot.register_next_step_handler(m, lambda x:
        cur.execute("INSERT INTO promocodes VALUES(?,0)", (f"PRIVAT-PREVO-{x.text}",)) or
        db.commit() or bot.send_message(m.chat.id, "<b>Промокод создан</b>")
    )

@bot.message_handler(func=lambda m: m.text == "🚫 Бан")
def ban(m):
    bot.send_message(m.chat.id, "<b>ID пользователя</b>")
    bot.register_next_step_handler(m, ban2)

def ban2(m):
    uid = int(m.text)
    cur.execute("INSERT INTO banned VALUES(?,?)", (uid, "Ban"))
    db.commit()
    bot.send_message(m.chat.id, "<b>Пользователь забанен</b>")

bot.infinity_polling(skip_pending=True)

