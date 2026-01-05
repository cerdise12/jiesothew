import random
import uuid
import requests
from telebot import types

from config import *
from db import *
from keyboards import *

captcha_sessions = {}
ref_sessions = {}

def register_handlers(bot):
    HEADERS = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

    # ===== START + CAPTCHA =====
    @bot.message_handler(commands=["start"])
    def start(m):
        if is_banned(m.from_user.id):
            return

        args = m.text.split()
        if len(args) > 1:
            ref_sessions[m.from_user.id] = int(args[1])

        emojis = ["🍎", "🍌", "🍇", "🍉"]
        correct = random.randint(0, 3)
        captcha_sessions[m.from_user.id] = correct

        kb = types.InlineKeyboardMarkup(row_width=2)
        for i, e in enumerate(emojis):
            kb.add(types.InlineKeyboardButton(e, callback_data=f"captcha_{i}"))

        bot.send_message(
            m.chat.id,
            f"<b>Подтверди, что ты не бот\nНажми на:</b> {emojis[correct]}",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("captcha_"))
    def captcha(c):
        uid = c.from_user.id
        choice = int(c.data.split("_")[1])

        if captcha_sessions.get(uid) != choice:
            bot.answer_callback_query(c.id, "❌ Неверно", show_alert=True)
            return

        del captcha_sessions[uid]
        add_user(uid)

        ref = ref_sessions.get(uid)
        if ref and ref != uid:
            if not cur.execute("SELECT 1 FROM referred WHERE user_id=?", (uid,)).fetchone():
                cur.execute("INSERT INTO referred VALUES(?)", (uid,))
                cur.execute("UPDATE referrals SET ref_count = ref_count + 1 WHERE user_id=?", (ref,))
                db.commit()

        bot.send_message(uid, "<b>Главное меню</b>", reply_markup=main_menu())

    # ===== BUY =====
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(c):
        bot.send_message(c.message.chat.id, "<b>Выбери способ оплаты</b>", reply_markup=buy_menu())

    # ===== CRYPTO =====
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
    def check(c):
        inv = c.data.split("_")[1]
        r = requests.get(
            "https://pay.crypt.bot/api/getInvoices",
            headers=HEADERS,
            params={"invoice_ids": inv}
        ).json()

        if r["result"]["items"][0]["status"] != "paid":
            bot.answer_callback_query(c.id, "Не оплачено", show_alert=True)
            return

        link = get_link()
        if not link:
            bot.send_message(c.message.chat.id, "Ссылки закончились")
            return

        give_access(c.from_user.id)
        bot.send_message(c.message.chat.id, f"<b>Оплата прошла!\n{link}</b>")

    # ===== REFS =====
    @bot.callback_query_handler(func=lambda c: c.data == "refs")
    def refs(c):
        uid = c.from_user.id
        refs = cur.execute("SELECT ref_count FROM referrals WHERE user_id=?", (uid,)).fetchone()[0]

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔄 Обменять 15 → 1 прокрут", callback_data="ref_exchange"))

        bot.send_message(
            uid,
            f"<b>👥 Рефы: {refs}/{REF_NEED}\n"
            f"https://t.me/{bot.get_me().username}?start={uid}</b>",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data == "ref_exchange")
    def ref_exchange(c):
        uid = c.from_user.id
        refs = cur.execute("SELECT ref_count FROM referrals WHERE user_id=?", (uid,)).fetchone()[0]

        if refs < REF_NEED:
            bot.answer_callback_query(c.id, "❌ Мало рефов", show_alert=True)
            return

        link = get_link()
        if not link:
            bot.send_message(uid, "Ссылки закончились")
            return

        cur.execute("UPDATE referrals SET ref_count = ref_count - ? WHERE user_id=?", (REF_NEED, uid))
        give_access(uid)
        db.commit()

        bot.send_message(uid, f"<b>🎉 Обмен успешен\n{link}</b>")

        for admin in ADMIN_IDS:
            bot.send_message(admin, f"🔔 Реф обмен\nID: {uid}")
