"""Система рангов модераторов (0–5), как в Боте."""
from __future__ import annotations

import time
from typing import Optional

from aiogram import Bot
from aiogram.types import Message

import db
from config import ADMINS, OWNER_ID
from core_registry import MAX_RANK, RANK_NAMES, RANK_TITLES, stars


async def get_rank(chat_id: int, user_id: int) -> int:
    """0 — участник … 8 — владелец чата.

    Ранг строго изолирован для каждого конкретного чата.
    """
    row = await db.fetchone(
        "SELECT rank FROM ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    r = int(row["rank"]) if row else 0
    srow = await db.fetchone(
        "SELECT rank FROM staff WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    if srow:
        r = max(r, int(srow["rank"]))
    return r


async def set_rank(chat_id: int, user_id: int, rank: int, by: int = 0) -> None:
    """Устанавливает ранг строго для указанного chat_id."""
    now = int(time.time())

    urow = await db.fetchone("SELECT username FROM users WHERE user_id=?", (user_id,))
    username = urow["username"] if urow and urow["username"] else None
    if not username:
        srow = await db.fetchone("SELECT username FROM staff WHERE user_id=?", (user_id,))
        username = srow["username"] if srow and srow["username"] else None

    if rank <= 0:
        await db.execute("DELETE FROM ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        if username:
            await db.execute("DELETE FROM staff WHERE chat_id=? AND (user_id=? OR lower(username)=lower(?))", (chat_id, user_id, username))
        else:
            await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    else:
        if username:
            await db.execute("UPDATE staff SET rank=?, ts=? WHERE chat_id=? AND (user_id=? OR lower(username)=lower(?)) AND rank > ?", (rank, now, chat_id, user_id, username, rank))
        else:
            await db.execute("UPDATE staff SET rank=?, ts=? WHERE chat_id=? AND user_id=? AND rank > ?", (rank, now, chat_id, user_id, rank))

        await db.execute(
            "INSERT INTO ranks (chat_id, user_id, rank, granted_by, ts) VALUES (?,?,?,?,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET rank=excluded.rank, "
            "granted_by=excluded.granted_by, ts=excluded.ts",
            (chat_id, user_id, rank, by, now))
    await db.execute(
        "INSERT INTO rank_log (chat_id, user_id, rank, by_id, ts) VALUES (?,?,?,?,?)",
        (chat_id, user_id, rank, by, now))


async def effective_rank(message: Message, bot: Bot) -> int:
    """Ранг с учётом ТГ-админки и создателя группы."""
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return MAX_RANK  # анонимный админ группы = высший ранг
    if not message.from_user:
        return 0
    uid = message.from_user.id
    if message.chat.type == "private":
        return MAX_RANK if uid == OWNER_ID else 0

    r = await get_rank(message.chat.id, uid)
    if r:
        return r

    # ТГ-создатель чата получает высший ранг (Владелец чата), админ - 3
    try:
        m = await bot.get_chat_member(message.chat.id, uid)
        if m.status == "creator":
            await set_rank(message.chat.id, uid, MAX_RANK, by=0)
            return MAX_RANK
        if m.status == "administrator":
            return 5
    except Exception:
        pass
    return 0


def rank_name(rank: int) -> str:
    return RANK_NAMES.get(rank, "Участник")


def rank_label(rank: int) -> str:
    """«👑 Владелец чата» — для ответов бота."""
    from core_registry import RANK_ICONS
    icon = RANK_ICONS.get(rank, "")
    name = RANK_NAMES.get(rank, "Участник")
    return f"{icon} {name}".strip()


async def require(message: Message, bot: Bot, need: int, key: str = "") -> bool:
    """Проверка ранга с автоответом. Учитывает переопределение ранга через ДК."""
    # ДК уже пропустил команду в middleware — не перепроверяем строже
    if getattr(message, "_dk_ok", False):
        return True
    import config
    sender_id = message.from_user.id if message.from_user else 0
    if sender_id and config.is_bot_owner(sender_id):
        return True
    r = await effective_rank(message, bot)
    if r >= need:
        return True

    await message.reply(
        f"⛔️ Недостаточно прав.\n"
        f"Нужен ранг: <b>{rank_label(need)}</b>\n"
        f"Ваш ранг: <b>{rank_label(r) if r else 'Участник'}</b>")
    return False
