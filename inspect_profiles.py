import sqlite3, os, tempfile

tmp_path = os.path.join(tempfile.gettempdir(), "iris_inspect.db")
con = sqlite3.connect(tmp_path)
cur = con.cursor()

print("Profiles columns:")
for row in cur.execute("PRAGMA table_info(profiles)").fetchall():
    print(row)

print("\nProfiles with non-empty fields:")
rows = cur.execute("SELECT user_id, real_name, hobby, about, custom, family, nick2 FROM profiles LIMIT 10").fetchall()
for r in rows:
    print(r)

print("\nNon-empty 'about' count:", cur.execute("SELECT COUNT(*) FROM profiles WHERE about IS NOT NULL AND about != ''").fetchone()[0])
print("Non-empty 'custom' count:", cur.execute("SELECT COUNT(*) FROM profiles WHERE custom IS NOT NULL AND custom != ''").fetchone()[0])
print("Non-empty 'hobby' count:", cur.execute("SELECT COUNT(*) FROM profiles WHERE hobby IS NOT NULL AND hobby != ''").fetchone()[0])

con.close()
