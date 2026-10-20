import gzip
import sqlite3
import os
import tempfile

gz_path = r"c:\Users\eiema\Downloads\AyuGram Desktop\iris_backup.db (17).gz"
print("gz exists:", os.path.exists(gz_path))
if os.path.exists(gz_path):
    with gzip.open(gz_path, "rb") as f_in:
        db_bytes = f_in.read()
    print("read gz bytes:", len(db_bytes))
    tmp_path = os.path.join(tempfile.gettempdir(), "iris_inspect.db")
    with open(tmp_path, "wb") as f_out:
        f_out.write(db_bytes)
    con = sqlite3.connect(tmp_path)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("tables:", tables)
    for t in tables:
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"table {t} ({cnt} rows): {cols}")
    con.close()
