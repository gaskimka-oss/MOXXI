import sqlite3

con = sqlite3.connect("data/iris.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

# Find Simba
rows = cur.execute("SELECT * FROM users WHERE lower(username) LIKE '%simba%' OR lower(first_name) LIKE '%simba%'").fetchall()
for r in rows:
    print("User:", r["user_id"], r["username"], r["first_name"])
    p = cur.execute("SELECT * FROM profiles WHERE user_id=?", (r["user_id"],)).fetchone()
    if p:
        print("Profile keys:", p.keys())
        for k in p.keys():
            if p[k]:
                val_safe = str(p[k]).encode("ascii", "backslashreplace").decode("ascii")
                print(f"  {k}: {val_safe}")
