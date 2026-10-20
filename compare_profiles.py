import gzip, sqlite3, os, tempfile

gz_path = r"c:\Users\eiema\Downloads\AyuGram Desktop\iris_backup.db (17).gz"
with gzip.open(gz_path, "rb") as f_in:
    db_bytes = f_in.read()
tmp_path = os.path.join(tempfile.gettempdir(), "iris_inspect.db")
with open(tmp_path, "wb") as f_out:
    f_out.write(db_bytes)

bak = sqlite3.connect(tmp_path)
cur_bak = bak.cursor()

curr = sqlite3.connect("data/iris.db")
cur_curr = curr.cursor()

out_path = r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\comp.txt"
with open(out_path, "w", encoding="utf-8") as out:
    out.write("=== BACKUP PROFILES ===\n")
    rows = cur_bak.execute("SELECT user_id, real_name, hobby, about, custom, family, nick2, age, country, tz, gender, filled FROM profiles").fetchall()
    for r in rows:
        out.write(f"UID={r[0]}: real_name={repr(r[1])}, hobby={repr(r[2])}, about={repr(r[3])}, custom={repr(r[4])}, family={repr(r[5])}, nick2={repr(r[6])}, age={repr(r[7])}, country={repr(r[8])}, tz={repr(r[9])}, gender={repr(r[10])}, filled={r[11]}\n")

    out.write("\n=== CURRENT PROFILES ===\n")
    rows2 = cur_curr.execute("SELECT user_id, real_name, hobby, about, custom, family, nick2, age, country, tz, gender, filled FROM profiles").fetchall()
    for r in rows2:
        out.write(f"UID={r[0]}: real_name={repr(r[1])}, hobby={repr(r[2])}, about={repr(r[3])}, custom={repr(r[4])}, family={repr(r[5])}, nick2={repr(r[6])}, age={repr(r[7])}, country={repr(r[8])}, tz={repr(r[9])}, gender={repr(r[10])}, filled={r[11]}\n")

    out.write("\n=== USERS NICK IN BACKUP ===\n")
    u_bak = cur_bak.execute("SELECT user_id, nick, first_name, username FROM users WHERE nick IS NOT NULL AND nick != ''").fetchall()
    for r in u_bak:
        out.write(f"UID={r[0]}: nick={repr(r[1])}, first_name={repr(r[2])}, username={repr(r[3])}\n")

    out.write("\n=== USERS NICK IN CURRENT ===\n")
    u_curr = cur_curr.execute("SELECT user_id, nick, first_name, username FROM users WHERE nick IS NOT NULL AND nick != ''").fetchall()
    for r in u_curr:
        out.write(f"UID={r[0]}: nick={repr(r[1])}, first_name={repr(r[2])}, username={repr(r[3])}\n")

bak.close()
curr.close()
print("Done writing comp.txt")
