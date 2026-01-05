import sqlite3

db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS banned(user_id INTEGER, reason TEXT);
CREATE TABLE IF NOT EXISTS links(link TEXT);
CREATE TABLE IF NOT EXISTS used(user_id INTEGER);

CREATE TABLE IF NOT EXISTS promocodes(
    code TEXT UNIQUE,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS referrals(
    user_id INTEGER PRIMARY KEY,
    ref_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS referred(
    user_id INTEGER PRIMARY KEY
);
""")
db.commit()

# ===== helpers =====
def is_banned(uid):
    return cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,)).fetchone()

def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users VALUES(?)", (uid,))
    cur.execute("INSERT OR IGNORE INTO referrals(user_id) VALUES(?)", (uid,))
    db.commit()

def give_access(uid):
    cur.execute("INSERT OR IGNORE INTO used VALUES(?)", (uid,))
    db.commit()

def has_access(uid):
    return cur.execute("SELECT 1 FROM used WHERE user_id=?", (uid,)).fetchone()

def get_link():
    row = cur.execute("SELECT link FROM links LIMIT 1").fetchone()
    if not row:
        return None
    cur.execute("DELETE FROM links WHERE link=?", (row[0],))
    db.commit()
    return row[0]
