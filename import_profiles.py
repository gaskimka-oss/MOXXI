"""Скрипт безопасного импорта анкет, описаний и никнеймов из бэкапа."""
import gzip
import os
import sqlite3
import time
from pathlib import Path

BACKUP_GZ = Path(r"C:\Users\eiema\Downloads\AyuGram Desktop\iris_backup.db (17).gz")
SCRATCH_DIR = Path(r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\scratch")
SCRATCH_DB = SCRATCH_DIR / "backup_unpacked.db"
ACTIVE_DB = Path(r"C:\Users\eiema\OneDrive\Desktop\бот2.0\data\iris.db")


def main():
    print(f"1. Распаковка архива {BACKUP_GZ}...")
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(BACKUP_GZ, "rb") as gz_in:
        with open(SCRATCH_DB, "wb") as f_out:
            f_out.write(gz_in.read())
    print(f"Распаковано: {SCRATCH_DB.stat().st_size} байт.")

    print(f"2. Подключение к бэкапу и целевой базе: {ACTIVE_DB}...")
    b_conn = sqlite3.connect(SCRATCH_DB)
    b_conn.row_factory = sqlite3.Row
    b_cur = b_conn.cursor()

    a_conn = sqlite3.connect(ACTIVE_DB)
    a_conn.row_factory = sqlite3.Row
    a_cur = a_conn.cursor()

    # --- Импорт никнеймов и пользователей ---
    b_cur.execute("SELECT user_id, username, first_name, verified, created_at FROM users")
    b_users = b_cur.fetchall()
    print(f"Найдено пользователей в бэкапе: {len(b_users)}")

    users_inserted = 0
    users_updated = 0

    for u in b_users:
        uid = u["user_id"]
        uname = u["username"]
        fname = u["first_name"]
        created = u["created_at"] or int(time.time())

        # Проверяем наличие в активной базе
        a_cur.execute("SELECT user_id, username, first_name, balance FROM users WHERE user_id=?", (uid,))
        existing = a_cur.fetchone()

        if existing is None:
            # Создаем нового пользователя с дефолтным балансом (не трогая экономику)
            a_cur.execute(
                "INSERT INTO users (user_id, username, first_name, balance, created_at, verified) VALUES (?, ?, ?, 1000, ?, 1)",
                (uid, uname, fname, created)
            )
            users_inserted += 1
        else:
            # Обновляем ник и имя, если они заполнены, БАЛАНС НЕ ТРОГАЕМ
            new_uname = uname if uname else existing["username"]
            new_fname = fname if fname else existing["first_name"]
            a_cur.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (new_uname, new_fname, uid)
            )
            users_updated += 1

    # --- Импорт анкет и описаний (profiles) ---
    b_cur.execute("SELECT * FROM profiles")
    b_profiles = b_cur.fetchall()
    print(f"Найдено анкет/профилей в бэкапе: {len(b_profiles)}")

    profiles_imported = 0

    for p in b_profiles:
        uid = p["user_id"]
        gender = p["gender"]
        custom = p["custom"]
        custom_by = p["custom_by"]
        custom_ts = p["custom_ts"]
        real_name = p["real_name"]
        country = p["country"]
        tz = p["tz"]
        family = p["family"]
        nick2 = p["nick2"]
        filled = p["filled"]
        filled_ts = p["filled_ts"]

        a_cur.execute("""
            INSERT INTO profiles (user_id, gender, custom, custom_by, custom_ts, real_name, country, tz, family, nick2, filled, filled_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender = COALESCE(excluded.gender, profiles.gender),
                custom = COALESCE(excluded.custom, profiles.custom),
                custom_by = COALESCE(excluded.custom_by, profiles.custom_by),
                custom_ts = COALESCE(excluded.custom_ts, profiles.custom_ts),
                real_name = COALESCE(excluded.real_name, profiles.real_name),
                country = COALESCE(excluded.country, profiles.country),
                tz = COALESCE(excluded.tz, profiles.tz),
                family = COALESCE(excluded.family, profiles.family),
                nick2 = COALESCE(excluded.nick2, profiles.nick2),
                filled = MAX(excluded.filled, profiles.filled),
                filled_ts = COALESCE(excluded.filled_ts, profiles.filled_ts)
        """, (uid, gender, custom, custom_by, custom_ts, real_name, country, tz, family, nick2, filled, filled_ts))
        profiles_imported += 1

    a_conn.commit()
    b_conn.close()
    a_conn.close()

    print("\n✅ ИМПОРТ УСПЕШНО ЗАВЕРШЕН!")
    print(f"• Пользователей добавлено: {users_inserted}")
    print(f"• Пользователей обновлено никами: {users_updated}")
    print(f"• Анкет и описаний перенесено: {profiles_imported}")
    print("• Балансы, монеты и донаты игроков НЕ перезаписывались и сохранены.")


if __name__ == "__main__":
    main()
