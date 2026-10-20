import sqlite3
from config import DB_PATH

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
print('SETTINGS:')
for r in cur.execute("SELECT chat_id, key, value FROM settings WHERE key LIKE '%boss%' OR key LIKE '%topic%'").fetchall():
    print(r)
print('CHAT_BOSS:')
for r in cur.execute("SELECT * FROM chat_boss").fetchall():
    print(r)
con.close()
