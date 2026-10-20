import sqlite3
import os
import glob

dbs = [
    r"c:\Users\eiema\OneDrive\Desktop\bot\users.db",
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\moxxi_bot.db",
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\users.db",
    r"c:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db",
    r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\iris_backup.db",
    r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\moxxi_backup.db"
]

out = []
for db_path in dbs:
    if not os.path.exists(db_path):
        continue
    out.append(f"\n=================== DB: {db_path} ===================")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    out.append(f"Tables: {tables}")
    for t in tables:
        try:
            cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
            # check if 8412527198 or 'Simba' or 'simba' exists
            if "user_id" in cols:
                sim = cur.execute(f"SELECT * FROM {t} WHERE user_id=8412527198").fetchall()
                if sim:
                    out.append(f"Found Simba in {t}: {sim}")
            if any(col in cols for col in ["about", "custom", "descr", "description", "bio"]):
                out.append(f"Table {t} has descr cols: {cols}")
                non_empty = cur.execute(f"SELECT count(*) FROM {t} WHERE " + " OR ".join([f"({c} IS NOT NULL AND {c} != '')" for c in cols if c in ["about", "custom", "descr", "description", "bio"]])).fetchone()[0]
                out.append(f"Non-empty rows in {t}: {non_empty}")
        except Exception as e:
            out.append(f"Error checking {t}: {e}")
    con.close()

with open(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\all_dbs_summary.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("Summary written.")
