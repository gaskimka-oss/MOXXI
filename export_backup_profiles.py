import sqlite3

con_back = sqlite3.connect(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\iris_backup.db")
cur_back = con_back.cursor()

rows_back = cur_back.execute("SELECT * FROM profiles").fetchall()
cols_back = [c[0] for c in cur_back.description]

print("iris_backup.db profiles count:", len(rows_back))
with open(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\backup_profiles_full.txt", "w", encoding="utf-8") as f:
    for r in rows_back:
        d = dict(zip(cols_back, r))
        f.write(str(d) + "\n")

con_back.close()
print("Backup profiles written.")
