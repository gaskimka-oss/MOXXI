"""Система рангов модераторов (0–5), в системе MOXXI."""
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
            await db.execute("UPDATE staff SET rank=?, ts=? WHERE chat_id=? AND (user_id=? OR lower(username)=lower(?))", (rank, now, chat_id, user_id, username))
        else:
            await db.execute("UPDATE staff SET rank=?, ts=? WHERE chat_id=? AND user_id=?", (rank, now, chat_id, user_id))

        await db.execute(
            "INSERT INTO ranks (chat_id, user_id, rank, granted_by, ts) VALUES (?,?,?,?,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET rank=excluded.rank, "
            "granted_by=excluded.granted_by, ts=excluded.ts",
            (chat_id, user_id, rank, by, now))
    await db.execute(
        "INSERT INTO rank_log (chat_id, user_id, rank, by_id, ts) VALUES (?,?,?,?,?)",
        (chat_id, user_id, rank, by, now))
    invalidate_rank_cache(chat_id, user_id)


# Кэш статуса участников в Telegram: (chat_id, user_id) -> (effective_rank, timestamp)
_tg_rank_cache: dict[tuple[int, int], tuple[int, float]] = {}
TG_RANK_CACHE_TTL = 300.0  # 5 минут кэширования роли участника в Telegram

def invalidate_rank_cache(chat_id: int, user_id: int | None = None) -> None:
    """Сброс кэша при изменении ранга/прав."""
    if user_id is None:
        for k in list(_tg_rank_cache.keys()):
            if k[0] == chat_id:
                _tg_rank_cache.pop(k, None)
    else:
        _tg_rank_cache.pop((chat_id, user_id), None)


async def effective_rank(message: Message, bot: Bot) -> int:
    """Ранг с учётом базы данных ranks, ТГ-админки и создателя группы."""
    if hasattr(message, "_cached_effective_rank"):
        return message._cached_effective_rank

    if message.sender_chat and message.sender_chat.id == message.chat.id:
        message._cached_effective_rank = MAX_RANK
        return MAX_RANK  # анонимный админ группы = высший ранг
    if not message.from_user:
        return 0
    uid = message.from_user.id

    import config
    # Создатели и главные владельцы бота всегда имеют высший ранг везде
    if config.is_bot_owner(uid):
        message._cached_effective_rank = MAX_RANK
        return MAX_RANK

    if message.chat.type == "private":
        message._cached_effective_rank = 0
        return 0

    cid = message.chat.id
    cache_key = (cid, uid)
    now = time.monotonic()

    # 0. Проверяем оперативный кэш в памяти (устраняет 429 Too Many Requests от Telegram)
    if cache_key in _tg_rank_cache:
        cached_r, ts = _tg_rank_cache[cache_key]
        if now - ts < TG_RANK_CACHE_TTL:
            message._cached_effective_rank = cached_r
            return cached_r

    # 1. Сначала проверяем ранг, явно назначенный в чате (таблица ranks):
    r = await get_rank(cid, uid)
    if r is not None and r > 0:
        _tg_rank_cache[cache_key] = (r, now)
        message._cached_effective_rank = r
        return r

    # Также проверяем состав модерации чата (таблица staff):
    row_st = await db.fetchone(
        "SELECT rank FROM staff WHERE chat_id=? AND user_id=? AND left_chat=0",
        (cid, uid)
    )
    if row_st and row_st["rank"] and int(row_st["rank"]) > 0:
        st_r = int(row_st["rank"])
        _tg_rank_cache[cache_key] = (st_r, now)
        message._cached_effective_rank = st_r
        return st_r

    # 2. Создатель / администратор в Telegram (строго ОДИН сетевой запрос с кэшированием):
    res_rank = 0
    try:
        m = await bot.get_chat_member(cid, uid)
        if m.status == "creator":
            await set_rank(cid, uid, MAX_RANK, by=0)
            res_rank = MAX_RANK
        elif m.status == "administrator":
            res_rank = 5
    except Exception:
        pass

    _tg_rank_cache[cache_key] = (res_rank, now)
    message._cached_effective_rank = res_rank
    return res_rank


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
    r = await effective_rank(message, bot)
    if r >= need:
        return True

    # Фраза без префикса случайно совпала с командой («всем привет») —
    # молча пропускаем, ругаться на обычное сообщение нельзя.
    text = (message.text or message.caption or "").strip()
    if text and text[0] not in "!./+":
        low = text.lower()
        if not low.startswith(("мокси", "моккси", "moxxi", "бот")):
            return False

    cmd_name = (key or "").strip()
    if not cmd_name:
        txt = (message.text or message.caption or "").strip()
        if txt:
            cmd_name = txt.split()[0].lstrip("!./").lower()
    if not cmd_name:
        cmd_name = "этой команды"

    await message.reply(
        f"⛔️ <b>Недостаточно прав для команды «{cmd_name}»!</b>\n\n"
        f"🔒 Требуемый ранг: <b>{rank_label(need)}</b> (Ранг {need})\n"
        f"👤 Ваш текущий ранг: <b>{rank_label(r) if r else 'Участник'}</b> (Ранг {r})\n\n"
        f"💡 <b>Как настроить доступ к этой команде:</b>\n"
        f"• Разрешить команду всем: <code>дк {cmd_name} 0</code>\n"
        f"• Изменить ранг доступа: <code>дк {cmd_name} {need}</code>\n"
        f"• Выдать личный доступ игроку: <code>+пдк @юзер {cmd_name}</code>\n\n"
        f"ℹ️ <i>Если вы участник — обратитесь к администрации чата с просьбой открыть команду:</i> <code>дк {cmd_name} 0</code>"
    )
    return False
