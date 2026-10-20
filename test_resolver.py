import re
import sqlite3

# Test query for resolve
con = sqlite3.connect('data/iris.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

def test_find(query_str):
    q = query_str.strip().lstrip('@')
    # search users by username, nick, first_name
    row = cur.execute("""
        SELECT u.user_id, u.first_name, u.username, u.nick 
        FROM users u 
        WHERE lower(u.username) = lower(?) 
           OR lower(u.nick) = lower(?)
           OR lower(u.first_name) = lower(?)
        LIMIT 1
    """, (q, q, q)).fetchone()
    if row:
        return row['user_id'], row['first_name']
    
    # search profiles by hobby, real_name, nick2
    p_row = cur.execute("""
        SELECT p.user_id, u.first_name, p.real_name, p.hobby 
        FROM profiles p
        LEFT JOIN users u ON u.user_id = p.user_id
        WHERE lower(p.hobby) = lower(?) 
           OR lower(p.real_name) = lower(?)
           OR lower(p.nick2) = lower(?)
        LIMIT 1
    """, (q, q, q)).fetchone()
    if p_row:
        return p_row['user_id'], (p_row['first_name'] or p_row['real_name'] or str(p_row['user_id']))

    # prefix match if >= 3 chars
    if len(q) >= 3:
        row = cur.execute("""
            SELECT u.user_id, u.first_name 
            FROM users u 
            WHERE lower(u.username) LIKE lower(?) || '%' 
               OR lower(u.nick) LIKE lower(?) || '%'
               OR lower(u.first_name) LIKE lower(?) || '%'
            LIMIT 1
        """, (q, q, q)).fetchone()
        if row:
            return row['user_id'], row['first_name']

        p_row = cur.execute("""
            SELECT p.user_id, u.first_name, p.real_name 
            FROM profiles p
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE lower(p.hobby) LIKE lower(?) || '%' 
               OR lower(p.real_name) LIKE lower(?) || '%'
            LIMIT 1
        """, (q, q)).fetchone()
        if p_row:
            return p_row['user_id'], (p_row['first_name'] or p_row['real_name'] or str(p_row['user_id']))

    return None, None

tests = ['Simba', 'Ксюша', 'KVAS', 'Kaktys6390', 'welwesvpn', '8412527198', 'D19_2244', 'Саня']
for t in tests:
    res = test_find(t)
    print(f"Query: {t} -> Result: {res}")

con.close()
