import sqlite3

con = sqlite3.connect('data/iris.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

FIELDS = [
    ('имя', 'Имя', 'real_name'),
    ('возраст', 'Возраст', 'age'),
    ('страна', 'Страна', 'country'),
    ('время по мск', 'Время по МСК', 'tz'),
    ('семейное положение', 'Семейное положение', 'family'),
    ('айди', 'Айди', 'nick2'),
    ('ник', 'Ник', 'hobby'),
    ('пол', 'Пол', 'gender'),
]
MIN_FIELDS = 2

rows = cur.execute("""SELECT p.*, u.username, u.first_name, u.nick FROM profiles p 
                      LEFT JOIN users u ON u.user_id=p.user_id 
                      ORDER BY p.filled_ts DESC, p.user_id ASC""").fetchall()

done, empty = [], []
for r in rows:
    has = bool(('custom' in r.keys() and r['custom'] and not r['custom'].startswith('🧠 ИИ проверил'))
               or r['filled']
               or sum(1 for _, _, c in FIELDS if r[c]) >= MIN_FIELDS)
    (done if has else empty).append(r)

print('Done count:', len(done))
print('Empty count:', len(empty))
for idx, r in enumerate(done[:10], 1):
    nm = r['real_name'] or r['nick'] or r['first_name'] or (f"@{r['username']}" if r['username'] else str(r['user_id']))
    details = []
    if r['age']: details.append(f"{r['age']} лет")
    if r['country']: details.append(str(r['country']))
    if r['hobby']: details.append(f"ник: {r['hobby']}")
    print(f"{idx}. {nm} ({r['user_id']}) - {', '.join(details)}")
con.close()
