import telebot
from telebot import types
import sqlite3
import requests
import uuid

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8471607341:AAEBYmluKdzRCA0mKrJ2ZLhkTQNpCQhZF40"
CRYPTO_PAY_TOKEN = "510865:AA69PCZiydwaRTwj2zx4DcrJDGVYDn2Ngta"
ADMIN_IDS = [283991746 , 874926153]  # айди админов
DEFAULT_PRICE_USDT = 0.05

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
HEADERS = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

# ===== БАЗА =====
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS links(link TEXT);
CREATE TABLE IF NOT EXISTS used(user_id INTEGER);
CREATE TABLE IF NOT EXISTS requests(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 method TEXT,
 status TEXT
);
CREATE TABLE IF NOT EXISTS promocodes(code TEXT);
""")
db.commit()

# ===== ВСПОМОГАТЕЛЬНОЕ =====
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

# ===== START =====
@bot.message_handler(commands=["start"])
def start(m):
    add_user(m.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Купить приват", callback_data="buy"),
        types.InlineKeyboardButton("🛠 Тех поддержка", callback_data="support"),
        types.InlineKeyboardButton("❓ Что такое приват", callback_data="about")
    )
    bot.send_message(m.chat.id, "<b>Добро пожаловать</b>", reply_markup=kb)

# ===== ИНФО =====
@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):
    bot.send_message(c.message.chat.id, "<b>Техподдержка — @duracheyo</b>")

@bot.callback_query_handler(func=lambda c: c.data == "about")
def about(c):
    bot.send_message(
        c.message.chat.id,
        "<b>приватка - лучшие фиксы, кфг от участников привата, логи, огромное разнообразие всякой всячины.\n"
        "Покупая приват ты получаешь эксклюзив и превосходство над противниками!</b>"
    )

# ===== ПОКУПКА =====
@bot.callback_query_handler(func=lambda c: c.data == "buy")
def buy(c):
    if has_access(c.from_user.id):
        bot.answer_callback_query(c.id, "Вы уже получили доступ", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💎 Криптовалюта", callback_data="pay_crypto"),
        types.InlineKeyboardButton("💳 Рубли", callback_data="pay_rub"),
        types.InlineKeyboardButton("⭐ Звёзды", callback_data="pay_star")
    )
    bot.send_message(c.message.chat.id, "<b>Выберите способ оплаты</b>", reply_markup=kb)

# ===== КРИПТА =====
@bot.callback_query_handler(func=lambda c: c.data == "pay_crypto")
def pay_crypto(c):
    payload = str(uuid.uuid4())
    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers=HEADERS,
        json={"asset": "USDT", "amount": DEFAULT_PRICE_USDT, "payload": payload}
    ).json()

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Оплатить", url=r["result"]["pay_url"]),
        types.InlineKeyboardButton("Проверить оплату", callback_data=f"check_{r['result']['invoice_id']}")
    )
    bot.send_message(c.message.chat.id, "<b>Оплатите и нажмите Проверить оплату</b>", reply_markup=kb)

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
    bot.send_message(c.message.chat.id, f"<b>Оплата успешна!\n{link}</b>")

# ===== РУБЛИ =====
@bot.callback_query_handler(func=lambda c: c.data == "pay_rub")
def pay_rub(c):
    cur.execute("INSERT INTO requests(user_id, method, status) VALUES(?,?,?)",
                (c.from_user.id, "Рубли", "wait"))
    db.commit()

    bot.send_message(
        c.message.chat.id,
        """
<b>Оплату можно произвести через 💳 СБП</b>

🏦 <b>Озон Банк</b>

— <b>Карта:</b>
<code>2204320967857881</code>
<b>(Дмитрий В.)</b>

— <b>Телефон:</b>
<code>+79836973590</code>
<b>(Дмитрий В.)</b>

⚠️ <b>ТОЛЬКО Озон Банк!</b>
Другие банки не засчитываются.

📸 После оплаты отправьте <b>скриншот</b>

С уважением — <b>@Duracheyo</b>
"""
    )

# ===== ЗВЁЗДЫ =====
@bot.callback_query_handler(func=lambda c: c.data == "pay_star")
def pay_star(c):
    cur.execute("INSERT INTO requests(user_id, method, status) VALUES(?,?,?)",
                (c.from_user.id, "Звёзды", "wait"))
    db.commit()

    bot.send_message(
        c.message.chat.id,
        """
<b>Оплата звёздами ⭐</b>

🎁 Отправьте <b>РОВНО 100 звёзд</b> подарком пользователю:
<b>@emy</b>

📸 После отправки пришлите <b>скриншот</b>
"""
    )

# ===== СКРИН =====
@bot.message_handler(content_types=["photo"])
def photo(m):
    row = cur.execute(
        "SELECT id FROM requests WHERE user_id=? AND status='wait'",
        (m.from_user.id,)
    ).fetchone()
    if not row:
        return

    req_id = row[0]
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{req_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{req_id}")
    )

    for admin in ADMIN_IDS:
        bot.send_photo(
            admin,
            m.photo[-1].file_id,
            caption=f"<b>Заявка #{req_id}</b>",
            reply_markup=kb
        )

    bot.send_message(m.chat.id, "<b>Заявка отправлена админу</b>")

# ===== АДМИН РЕШЕНИЕ =====
@bot.callback_query_handler(func=lambda c: c.data.startswith(("ok_", "no_")))
def admin_decision(c):
    if c.from_user.id not in ADMIN_IDS:
        return

    req_id = c.data.split("_")[1]
    row = cur.execute("SELECT user_id FROM requests WHERE id=?", (req_id,)).fetchone()
    if not row:
        return

    uid = row[0]
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

# ===== АДМИН МЕНЮ =====
@bot.message_handler(commands=["admin"])
def admin(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📢 Рассылка", "➕ Добавить ссылку", "➕ Промокод", "➖ Удалить промокод")
    bot.send_message(m.chat.id, "<b>Админ меню</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить ссылку")
def add_link(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(m.chat.id, "<b>Отправьте ссылку</b>")
    bot.register_next_step_handler(m, lambda x:
        cur.execute("INSERT INTO links VALUES(?)", (x.text,)) or db.commit() or
        bot.send_message(m.chat.id, "<b>Ссылка добавлена</b>")
    )

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка")
def broadcast(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(m.chat.id, "<b>Введите текст рассылки</b>")
    bot.register_next_step_handler(m, send_broadcast)

def send_broadcast(m):
    users = cur.execute("SELECT id FROM users").fetchall()
    for (uid,) in users:
        try:
            bot.send_message(uid, f"<b>{m.text}</b>")
        except:
            pass
    bot.send_message(m.chat.id, "<b>Рассылка завершена</b>")

bot.infinity_polling(skip_pending=True)

