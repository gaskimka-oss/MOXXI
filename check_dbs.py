import sqlite3
import os

db_paths = [
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db",
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\moxxi_bot.db",
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\users.db",
]

for p in db_paths:
    if not os.path.exists(p):
        continue
    print("=== Checking DB:", p, "===")
    con = sqlite3.connect(p)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    if "profiles" in tables:
        count = cur.execute("SELECT count(*) FROM profiles").fetchone()[0]
        print("profiles count:", count)
        # Check Simba user_id 8412527198
        simba = cur.execute("SELECT * FROM profiles WHERE user_id=8412527198").fetchone()
        if simba:
            cols = [col[0] for col in cur.description]
            print("Simba profile:", dict(zip(cols, simba)))
        # Check any profiles with 'ИИ' or 'custom'
        customs = cur.execute("SELECT user_id, custom FROM profiles WHERE custom IS NOT NULL AND custom != ''").fetchall()
        print("Profiles with custom:", len(customs))
        for uid, c in customs:
            print(f"UID {uid}: {c[:60]}")
    if "users" in tables:
        ucount = cur.execute("SELECT count(*) FROM users").fetchone()[0]
        print("users count:", ucount)
    con.close()
