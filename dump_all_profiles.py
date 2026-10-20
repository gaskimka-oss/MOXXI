import sqlite3

con = sqlite3.connect(r"c:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db")
cur = con.cursor()
rows = cur.execute("SELECT p.*, u.first_name, u.username, u.nick FROM profiles p LEFT JOIN users u ON u.user_id=p.user_id").fetchall()
cols = [c[0] for c in cur.description]

with open(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\all_profiles.txt", "w", encoding="utf-8") as f:
    f.write(f"Total profiles: {len(rows)}\n\n")
    for r in rows:
        d = dict(zip(cols, r))
        f.write(str(d) + "\n")

con.close()
print("Exported all profiles.")
