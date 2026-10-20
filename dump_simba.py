import sqlite3

for db_name in ["iris_backup.db"]:
    path = rf"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\{db_name}"
    con = sqlite3.connect(path)
    cur = con.cursor()
    simba = cur.execute("SELECT * FROM profiles WHERE user_id=8412527198").fetchone()
    cols = [c[0] for c in cur.description]
    with open(rf"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\simba_backup.txt", "w", encoding="utf-8") as f:
        for k, v in zip(cols, simba):
            f.write(f"{k}: {v}\n")
    con.close()
