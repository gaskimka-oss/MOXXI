import asyncio
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

CHATS_TO_BIND = {
    "global_community_chat": "https://t.me/moxxi_chat",
    "global_reviews_chat": "https://t.me/moxxi_reviews",
    "global_ideas_chat": "https://t.me/moxxi_ideas",
    "global_support_chat": "https://t.me/moxxi_support",
    "global_commands_chat": "https://t.me/moxxi_chat",
}

def update_db(db_path: str):
    if not os.path.exists(db_path):
        return
    print(f"Updating {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (chat_id, key)
            )
        """)
        for k, v in CHATS_TO_BIND.items():
            cur.execute("""
                INSERT INTO settings (chat_id, key, value) VALUES (0, ?, ?)
                ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value
            """, (k, v))
            print(f"  [OK] {k} = {v}")
        conn.commit()
        
        # Verify
        cur.execute("SELECT key, value FROM settings WHERE chat_id=0")
        rows = cur.fetchall()
        print(f"Current global settings in {db_path}:")
        for r in rows:
            print(f"    {r[0]}: {r[1]}")
        conn.close()
    except Exception as e:
        print(f"Error updating {db_path}: {e}")

if __name__ == "__main__":
    db_paths = [
        os.path.join("data", "iris.db"),
        "bot.db",
        "moxxi.db"
    ]
    for p in db_paths:
        update_db(p)
