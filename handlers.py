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

    # ========= START + CAPTCHA =========
    @bot.message_handler(commands=["start"])
    def start(m):
        if is_banned(m.from_user.id):
            return

        args = m.text.split()
        if len(args) > 1:
            try:
                ref_sessions[m.from_user.id] = int(args[1])
            except:
                pass

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

        # === REF COUNT ===
        ref = ref_sessions.get(uid)
        if ref and ref != uid:
            if not cur.execute(
                "SELECT 1 FROM referred WHERE user_id=?",
                (uid,)
            ).fetchone():
                cur.execute("INSERT INTO referred VALUES(?)", (uid,))
                cur.execute(
                    "UPDATE referrals SET ref_count = ref_count + 1 WHERE user_id=?",
                    (ref,)
                )
                db.commit()

        bot.send_message(uid, "<b>Главное меню</b>", reply_markup=main_menu())

    # ========= MAIN MENU =========
    @bot.callback_query_handler(func=lambda c: c.data == "buy")
    def buy(c):
        if has_access(c.from_user.id):
            bot.answer_callback_query(c.id, "Доступ уже есть", show_alert=True)
            return
        bot.send_message(c.message.chat.id, "<b>Выбери способ оплаты</b>", reply_markup=buy_menu())

    @bot.callback_query_handler(func=lambda c: c.data == "support")
    def support(c):
        bot.send_message(c.message.chat.id, f"<b>Техподдержка: {SUPPORT_USERNAME}</b>")

    @bot.callback_query_handler(func=lambda c: c.data == "about")
    def about(c):
        bot.send_message(
            c.message.chat.id,
            "<b>Приват — эксклюзивные фиксы, конфиги, логи и контент.</b>"
        )

    # ========= PROMO =========
    @bot.callback_query_handler(func=lambda c: c.data == "promo")
    def promo(c):
        bot.send_message(c.message.chat.id, "<b>Введите промокод</b>")
        bot.register_next_step_handler(c.message, check_promo)

    def check_promo(m):
        row = cur.execute(
            "SELECT used FROM promocodes WHERE code=?",
            (m.text,)
        ).fetchone()

        if not row or row[0]:
            bot.send_message(m.chat.id, "<b>❌ Промокод недействителен</b>")
            return

        link = get_link()
        if not link:
            bot.send_message(m.chat.id, "<b>❌ Ссылки закончились</b>")
            return

        cur.execute("UPDATE promocodes SET used=1 WHERE code=?", (m.text,))
        give_access(m.from_user.id)
        db.commit()

        bot.send_message(m.chat.id, f"<b>✅ Промокод принят!\n{link}</b>")

    # ========= REF SYSTEM =========
    @bot.callback_query_handler(func=lambda c: c.data == "refs")
    def refs(c):
        uid = c.from_user.id
        refs = cur.execute(
            "SELECT ref_count FROM referrals WHERE user_id=?",
            (uid,)
        ).fetchone()[0]

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔄 Обменять 15 → 1 прокрут", callback_data="ref_exchange"))

        bot.send_message(
            uid,
            f"<b>👥 Рефералы: {refs}/{REF_NEED}\n\n"
            f"🔗 Твоя ссылка:\nhttps://t.me/{bot.get_me().username}?start={uid}</b>",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data == "ref_exchange")
    def ref_exchange(c):
        uid = c.from_user.id
        refs = cur.execute(
            "SELECT ref_count FROM referrals WHERE user_id=?",
            (uid,)
        ).fetchone()[0]

        if refs < REF_NEED:
            bot.answer_callback_query(c.id, "❌ Недостаточно рефов", show_alert=True)
            return

        link = get_link()
        if not link:
            bot.send_message(uid, "<b>Ссылки закончились</b>")
            return

        cur.execute(
            "UPDATE referrals SET ref_count = ref_count - ? WHERE user_id=?",
            (REF_NEED, uid)
        )
        give_access(uid)
        db.commit()

        bot.send_message(uid, f"<b>🎉 Обмен выполнен!\n{link}</b>")

        for admin in ADMIN_IDS:
            bot.send_message(admin, f"<b>🔔 РЕФ ОБМЕН</b>\nID: {uid}")

    # ========= CRYPTO =========
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
            bot.answer_callback_query(c.id, "❌ Не оплачено", show_alert=True)
            return

        link = get_link()
        if not link:
            bot.send_message(c.message.chat.id, "<b>Ссылки закончились</b>")
            return

        give_access(c.from_user.id)
        bot.send_message(c.message.chat.id, f"<b>✅ Оплата прошла!\n{link}</b>")

    # ========= RUB / STARS =========
    @bot.callback_query_handler(func=lambda c: c.data in ["pay_rub", "pay_star"])
    def manual_pay(c):
        method = "Рубли" if c.data == "pay_rub" else "Звёзды"

        cur.execute(
            "INSERT INTO requests(user_id, method, status) VALUES(?,?,?)",
            (c.from_user.id, method, "wait")
        )
        db.commit()

        if method == "Рубли":
            text = (
                "<b>200₽ по СБП — Озон Банк</b>\n"
                "<code>2204320967857881</code>\n"
                "<code>+79836973590</code>\n"
                "Получатель: Дмитрий В.\n\n"
                "📸 После оплаты отправь скрин"
            )
        else:
            text = "<b>Отправь 150 ⭐ подарком @emy\nПосле пришли скрин</b>"

        bot.send_message(c.message.chat.id, text)

    # ========= PHOTO =========
    @bot.message_handler(content_types=["photo"])
    def get_photo(m):
        row = cur.execute(
            "SELECT id FROM requests WHERE user_id=? AND status='wait'",
            (m.from_user.id,)
        ).fetchone()

        if not row:
            return

        req_id = row[0]

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅ Принять", callback_data=f"ok_{req_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{req_id}")
        )

        for admin in ADMIN_IDS:
            bot.send_photo(
                admin,
                m.photo[-1].file_id,
                caption=f"<b>Заявка #{req_id}</b>",
                reply_markup=kb
            )

        bot.send_message(m.chat.id, "<b>✅ Заявка отправлена админу</b>")

    # ========= ADMIN DECISION =========
    @bot.callback_query_handler(func=lambda c: c.data.startswith(("ok_", "no_")))
    def admin_decision(c):
        if c.from_user.id not in ADMIN_IDS:
            return

        req_id = int(c.data.split("_")[1])
        uid = cur.execute(
            "SELECT user_id FROM requests WHERE id=?",
            (req_id,)
        ).fetchone()[0]

        if c.data.startswith("ok_"):
            link = get_link()
            if link:
                give_access(uid)
                bot.send_message(uid, f"<b>✅ Оплата подтверждена!\n{link}</b>")
            cur.execute("UPDATE requests SET status='ok' WHERE id=?", (req_id,))
        else:
            bot.send_message(uid, "<b>❌ Оплата отклонена</b>")
            cur.execute("UPDATE requests SET status='no' WHERE id=?", (req_id,))

        db.commit()
