from telebot import types
from config import ADMIN_IDS
from db import cur, db, get_link, give_access

def register_admin(bot):

    # ===== ADMIN MENU =====
    @bot.message_handler(commands=["admin"])
    def admin_menu(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(
            "📊 Статистика",
            "➕ Ссылка",
            "➕ Промо",
            "🚫 Бан",
            "📢 Рассылка"
        )
        bot.send_message(m.chat.id, "<b>Админ меню</b>", reply_markup=kb)

    # ===== STATS =====
    @bot.message_handler(func=lambda m: m.text == "📊 Статистика")
    def stats(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sold = cur.execute("SELECT COUNT(*) FROM used").fetchone()[0]
        refs = cur.execute("SELECT SUM(ref_count) FROM referrals").fetchone()[0] or 0

        bot.send_message(
            m.chat.id,
            f"<b>👤 Юзеры: {users}\n"
            f"💎 Доступов: {sold}\n"
            f"👥 Всего рефов: {refs}</b>"
        )

    # ===== ADD LINK =====
    @bot.message_handler(func=lambda m: m.text == "➕ Ссылка")
    def add_link(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        bot.send_message(m.chat.id, "<b>Отправь ссылку</b>")
        bot.register_next_step_handler(m, save_link)

    def save_link(m):
        cur.execute("INSERT INTO links VALUES(?)", (m.text,))
        db.commit()
        bot.send_message(m.chat.id, "<b>✅ Ссылка добавлена</b>")

    # ===== ADD PROMO =====
    @bot.message_handler(func=lambda m: m.text == "➕ Промо")
    def add_promo(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        bot.send_message(m.chat.id, "<b>Слово для промокода</b>")
        bot.register_next_step_handler(m, save_promo)

    def save_promo(m):
        code = f"PRIVAT-{m.text}"
        cur.execute("INSERT OR IGNORE INTO promocodes VALUES(?,0)", (code,))
        db.commit()
        bot.send_message(m.chat.id, f"<b>✅ Промокод создан:\n<code>{code}</code></b>")

    # ===== BAN =====
    @bot.message_handler(func=lambda m: m.text == "🚫 Бан")
    def ban(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        bot.send_message(m.chat.id, "<b>ID пользователя</b>")
        bot.register_next_step_handler(m, ban_save)

    def ban_save(m):
        try:
            uid = int(m.text)
        except:
            bot.send_message(m.chat.id, "❌ Неверный ID")
            return

        cur.execute("INSERT INTO banned VALUES(?,?)", (uid, "admin ban"))
        db.commit()
        bot.send_message(m.chat.id, "<b>🚫 Пользователь забанен</b>")

    # ===== BROADCAST =====
    @bot.message_handler(func=lambda m: m.text == "📢 Рассылка")
    def broadcast(m):
        if m.from_user.id not in ADMIN_IDS:
            return

        bot.send_message(m.chat.id, "<b>Текст рассылки</b>")
        bot.register_next_step_handler(m, send_broadcast)

    def send_broadcast(m):
        users = cur.execute("SELECT id FROM users").fetchall()
        ok = 0

        for (uid,) in users:
            try:
                bot.send_message(uid, m.text)
                ok += 1
            except:
                pass

        bot.send_message(m.chat.id, f"<b>📢 Отправлено: {ok}</b>")
