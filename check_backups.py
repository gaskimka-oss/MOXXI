import gzip
import sqlite3
import os
import shutil

archives = [
    r"c:\Users\eiema\Downloads\AyuGram Desktop\iris_backup.db.gz",
    r"c:\Users\eiema\Downloads\AyuGram Desktop\moxxi_backup.db.gz"
]

tmp_dir = r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch"

for arch in archives:
    if not os.path.exists(arch):
        continue
    base = os.path.basename(arch).replace(".gz", "")
    target = os.path.join(tmp_dir, base)
    print("Extracting", arch, "to", target)
    with gzip.open(arch, 'rb') as f_in:
        with open(target, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    # Inspect tables and profiles
    con = sqlite3.connect(target)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(base, "tables:", tables)
    if "profiles" in tables:
        count = cur.execute("SELECT count(*) FROM profiles").fetchone()[0]
        print(base, "profiles count:", count)
        simba = cur.execute("SELECT * FROM profiles WHERE user_id=8412527198").fetchone()
        if simba:
            cols = [c[0] for c in cur.description]
            print(base, "Simba profile:", dict(zip(cols, simba)))
    con.close()
