"""Резервные копии базы прямо в Telegram.

Зачем: на хостинге без постоянного диска (Volume) папка приложения
очищается при каждом деплое — база и все настройки пропадают.
Решение, которому не нужен ни диск, ни внешний сервис:

  • раз в N минут бот делает копию базы, жмёт её и отправляет
    документом в личку владельцу, а сообщение закрепляет;
  • при старте, если базы нет или она пустая, бот берёт файл
    из закреплённого сообщения и восстанавливает всё как было.

Закреплённое сообщение живёт в Telegram вечно, поэтому данные
переживают любой перезапуск, пересборку и переезд хостинга.
"""
from __future__ import annotations

import asyncio
import gzip
import logging
import os
import shutil
import sqlite3
import time
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile

import config

log = logging.getLogger("moxxibot.backup")

ARCHIVE_NAME = "moxxi_backup.db.gz"
TAG = "#moxxi_backup"

# интервал создания бэкапов (минуты) — по умолчанию 5 минут
INTERVAL_MIN = int(os.getenv("BACKUP_INTERVAL_MIN", "5") or 5)

_last_backup_msg_id: int = 0
_quick_backup_task: asyncio.Task | None = None


def backup_chat() -> int:
    """Куда уходит файл базы. Всегда только владелец бота."""
    return int(getattr(config, "OWNER_ID", 0) or getattr(config, "DEFAULT_OWNER", 8036974481))


def schedule_quick_backup(bot: Bot, delay_sec: float = 5.0) -> None:
    """Запускает быстрый бэкап через N секунд с дебаунсом (после покупки бизнеса и т.д.)."""
    global _quick_backup_task
    if _quick_backup_task and not _quick_backup_task.done():
        return

    async def _runner():
        await asyncio.sleep(delay_sec)
        try:
            await save(bot, "⚡ автосохранение после операций")
        except Exception as e:
            log.warning("быстрое сохранение: %s", e)

    try:
        _quick_backup_task = asyncio.create_task(_runner())
    except RuntimeError:
        pass


# ---------------------------------------------------------------- снимок
def _snapshot() -> bytes | None:
    """Согласованная копия базы (учитывает WAL) в виде gzip-байтов."""
    src = Path(config.DB_PATH)
    if not src.exists() or src.stat().st_size == 0:
        return None
    tmp = src.with_suffix(".backup.tmp")
    try:
        con = sqlite3.connect(str(src))
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        dst = sqlite3.connect(str(tmp))
        with dst:
            con.backup(dst)
        dst.close()
        con.close()
        return gzip.compress(tmp.read_bytes(), 6)
    except Exception as e:
        log.warning("снимок базы не удался: %s", e)
        return None
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def _rows(path: Path) -> int:
    """Сколько всего значимых записей в базе (0 — база пустая)."""
    try:
        con = sqlite3.connect(str(path))
        n = 0
        for t in ("settings", "users", "staff", "ranks", "profiles", "user_businesses", "game_stats"):
            try:
                n += con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                pass
        con.close()
        return n
    except Exception:
        return 0


def db_is_empty() -> bool:
    p = Path(config.DB_PATH)
    if not p.exists() or p.stat().st_size == 0:
        return True
    return _rows(p) == 0


# ---------------------------------------------------------------- выгрузка
async def save(bot: Bot, note: str = "") -> bool:
    global _last_backup_msg_id
    chat = backup_chat()
    if not chat:
        return False
    blob = await asyncio.to_thread(_snapshot)
    if not blob:
        return False
    stamp = time.strftime("%d.%m.%Y %H:%M")
    size_kb = len(blob) / 1024
    size_str = f"{size_kb:.1f} КБ" if size_kb < 1024 else f"{size_kb / 1024:.2f} МБ"

    caption = (
        f"💾 ✨ <b>Резервная копия базы данных Moxxi</b> ✨ 💾\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🕒 Дата снимка: <b>{stamp}</b>\n"
        f"📦 Размер архива: <b>{size_str}</b> (сжатие gzip)\n"
        f"🚀 Хранилище: <b>Неограниченно</b> (до 2 ГБ в Telegram)\n\n"
        f"📌 <i>Это сообщение закреплено. Бот автоматически восстановит все балансы, ранги, инвентарь и рейды при перезапуске хостинга.</i>\n"
        f"{TAG}"
    )
    try:
        msg = await bot.send_document(
            chat, BufferedInputFile(blob, filename=ARCHIVE_NAME),
            caption=caption + (f"\n{note}" if note else ""),
            disable_notification=True)
    except Exception as e:
        log.warning("не отправил копию: %s", e)
        return False

    # Удаляем старое незакрепленное сообщение с копией, чтобы не захламлять личку
    old_id = _last_backup_msg_id
    _last_backup_msg_id = msg.message_id

    # закрепляем свежую, старую открепляем
    try:
        await bot.unpin_all_chat_messages(chat)
    except Exception:
        pass
    try:
        await bot.pin_chat_message(chat, msg.message_id, disable_notification=True)
    except Exception as e:
        log.warning("не закрепил копию: %s", e)

    if old_id and old_id != msg.message_id:
        try:
            await bot.delete_message(chat, old_id)
        except Exception:
            pass

    log.info("резервная копия сохранена (%s)", size_str)
    return True


# ------------------------------------------------------------ восстановление
async def restore_if_needed(bot: Bot) -> bool:
    """Вызывать ДО db.init(). True — база восстановлена из Telegram."""
    if not db_is_empty():
        return False

    chat_candidates: list[int] = []
    primary = backup_chat()
    if primary:
        chat_candidates.append(primary)
    for alt in (getattr(config, "DEFAULT_OWNER", 8036974481), 8036974481, 8412527198):
        if alt and alt not in chat_candidates:
            chat_candidates.append(alt)

    for chat in chat_candidates:
        try:
            info = await bot.get_chat(chat)
        except Exception as e:
            log.info("восстановление: чат %s недоступен (%s)", chat, e)
            continue
        msg = getattr(info, "pinned_message", None)
        doc = getattr(msg, "document", None) if msg else None
        if not doc or ARCHIVE_NAME not in (doc.file_name or ""):
            continue
        try:
            f = await bot.get_file(doc.file_id)
            buf = await bot.download_file(f.file_path)
            raw = gzip.decompress(buf.read())
            dst = Path(config.DB_PATH)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".old"))
            dst.write_bytes(raw)
            for suf in ("-wal", "-shm"):
                s = Path(str(dst) + suf)
                if s.exists():
                    s.unlink()
            log.info("база восстановлена из Telegram чата %s (%d КБ, записей: %d)",
                     chat, len(raw) / 1024, _rows(dst))
            return True
        except Exception as e:
            log.warning("восстановление из чата %s не удалось: %s", chat, e)

    log.info("восстановление: закреплённой копии не найдено — начинаю с чистой базы")
    return False


# ---------------------------------------------------------------- фоновая
async def worker(bot: Bot) -> None:
    await asyncio.sleep(20)          # дать боту быстро прогреться
    while True:
        try:
            await save(bot)
        except Exception as e:
            log.warning("worker: %s", e)
        await asyncio.sleep(max(3, INTERVAL_MIN) * 60)
