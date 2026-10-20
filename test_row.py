import sqlite3

class DictRow(dict):
    def __init__(self, cursor, values):
        fields = [col[0] for col in cursor.description]
        super().__init__(zip(fields, values))
        self._values = values

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return super().__getitem__(item)

    def get(self, key, default=None):
        val = super().get(key, default)
        return default if val is None else val

con = sqlite3.connect(':memory:')
con.row_factory = DictRow
cur = con.cursor()
cur.execute('SELECT 1 as a, NULL as b, "hello" as c')
row = cur.fetchone()
print("row:", type(row), row)
print("keys:", list(row.keys()))
print("by key:", row['a'], row['c'])
print("by index:", row[0], row[1], row[2])
print("get existing:", row.get('a'))
print("get null default:", row.get('b', 123))
print("get missing default:", row.get('d', 'default_val'))
print("in test:", 'a' in row, 'd' in row)
