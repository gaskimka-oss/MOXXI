import sqlite3

for db_name in [r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\iris_backup.db", r"c:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db"]:
    con = sqlite3.connect(db_name)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        try:
            cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
            for c in cols:
                try:
                    res = cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} LIKE '%farforo66%' OR {c} LIKE '%ZefirkaRUS%'").fetchall()
                    if res:
                        print(f"Found in {db_name} table {t} column {c}: {res}")
                except Exception:
                    pass
        except Exception:
            pass
    con.close()
