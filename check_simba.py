import sqlite3
import os

db_path = r"c:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

simba = cur.execute("SELECT * FROM profiles WHERE user_id=8412527198").fetchone()
cols = [col[0] for col in cur.description]
simba_dict = dict(zip(cols, simba))

with open(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\simba_profile.txt", "w", encoding="utf-8") as f:
    for k, v in simba_dict.items():
        f.write(f"{k}: {v}\n")

customs = cur.execute("SELECT user_id, custom FROM profiles WHERE custom IS NOT NULL AND custom != ''").fetchall()
with open(r"c:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch\customs.txt", "w", encoding="utf-8") as f:
    for uid, c in customs:
        f.write(f"UID {uid}:\n{c}\n{'='*40}\n")

con.close()
print("Exported simba and customs successfully.")
