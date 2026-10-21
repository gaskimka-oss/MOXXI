"""Разбор {ссылка}: реплай, @username, t.me/..., числовой id, text_mention."""
from __future__ import annotations

import re
from typing import Optional

from aiogram import Bot
from aiogram.types import Message

import db

LINK_RE = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]{4,})", re.I)
USER_RE = re.compile(r"@([^\s,;!?]+)")
ID_RE = re.compile(r"\b(\d{5,15})\b")


def real_reply(message: Message):
    """Настоящий ответ на чужое сообщение — или None.

    В форумах Telegram подставляет в reply_to_message служебное сообщение
    темы, даже если человек никому не отвечал. Из-за этого бот принимал
    автора темы за «того, кому ответили». Такие псевдо-ответы отсекаем.
    """
    r = getattr(message, "reply_to_message", None)
    if r is None:
        return None
    # служебное сообщение о создании темы — это не ответ
    if getattr(r, "forum_topic_created", None) is not None:
        return None
    # первое сообщение темы: его id совпадает с id ветки
    tid = getattr(message, "message_thread_id", None)
    if tid and getattr(r, "message_id", None) == tid:
        return None
    if not r.from_user:
        return None
    return r


async def _lookup_user_by_text(q: str) -> Optional[tuple[int, str]]:
    """Поиск пользователя в базе по нику, юзернейму, имени или анкете."""
    if not q:
        return None
    clean_q = q.strip().lstrip("@")
    if not clean_q:
        return None

    # 1. Точное совпадение в users
    row = await db.fetchone(
        "SELECT user_id, first_name, username, nick FROM users "
        "WHERE lower(username)=lower(?) OR lower(nick)=lower(?) OR lower(first_name)=lower(?) LIMIT 1",
        (clean_q, clean_q, clean_q))
    if row:
        return row["user_id"], (row["first_name"] or row["nick"] or row["username"] or str(row["user_id"]))

    # 2. Точное совпадение в profiles (поля hobby, real_name, nick2)
    p_row = await db.fetchone(
        "SELECT p.user_id, u.first_name, u.username, p.real_name, p.hobby, p.nick2 FROM profiles p "
        "LEFT JOIN users u ON u.user_id=p.user_id "
        "WHERE lower(p.hobby)=lower(?) OR lower(p.real_name)=lower(?) OR lower(p.nick2)=lower(?) LIMIT 1",
        (clean_q, clean_q, clean_q))
    if p_row and p_row["user_id"]:
        return p_row["user_id"], (p_row["first_name"] or p_row["real_name"] or p_row["hobby"] or str(p_row["user_id"]))

    # 3. Staff совпадение
    s_row = await db.fetchone(
        "SELECT user_id, name FROM staff "
        "WHERE (lower(username)=lower(?) OR lower(name)=lower(?)) AND user_id IS NOT NULL AND user_id<>0 LIMIT 1",
        (clean_q, clean_q))
    if s_row and s_row["user_id"]:
        return s_row["user_id"], (s_row["name"] or str(s_row["user_id"]))

    # 3.1 Поиск в chat_nicks
    cn_row = await db.fetchone(
        "SELECT user_id, nick FROM chat_nicks WHERE lower(nick)=lower(?) LIMIT 1",
        (clean_q,))
    if cn_row and cn_row["user_id"]:
        return cn_row["user_id"], (cn_row["nick"] or str(cn_row["user_id"]))

    # 3.2 Поиск в chat_profiles
    cp_row = await db.fetchone(
        "SELECT user_id, nick2, real_name, hobby FROM chat_profiles "
        "WHERE lower(nick2)=lower(?) OR lower(real_name)=lower(?) OR lower(hobby)=lower(?) LIMIT 1",
        (clean_q, clean_q, clean_q))
    if cp_row and cp_row["user_id"]:
        return cp_row["user_id"], (cp_row["nick2"] or cp_row["real_name"] or str(cp_row["user_id"]))

    # 4. Префиксное совпадение если длина >= 3
    if len(clean_q) >= 3:
        row = await db.fetchone(
            "SELECT user_id, first_name, username, nick FROM users "
            "WHERE lower(username) LIKE lower(?) || '%' OR lower(nick) LIKE lower(?) || '%' OR lower(first_name) LIKE lower(?) || '%' LIMIT 1",
            (clean_q, clean_q, clean_q))
        if row:
            return row["user_id"], (row["first_name"] or row["nick"] or row["username"] or str(row["user_id"]))

        p_row = await db.fetchone(
            "SELECT p.user_id, u.first_name, p.real_name, p.hobby FROM profiles p "
            "LEFT JOIN users u ON u.user_id=p.user_id "
            "WHERE lower(p.hobby) LIKE lower(?) || '%' OR lower(p.real_name) LIKE lower(?) || '%' LIMIT 1",
            (clean_q, clean_q))
        if p_row and p_row["user_id"]:
            return p_row["user_id"], (p_row["first_name"] or p_row["real_name"] or p_row["hobby"] or str(p_row["user_id"]))

    return None


async def resolve_target(message: Message, args: str, bot: Bot) -> tuple[Optional[int], Optional[str], str]:
    """-> (user_id, имя, остаток_текста). Поддерживает реплай/@ник/ссылку/id/никнейм."""
    rest = args or ""

    # 1) явное упоминание через кнопку/ссылку на профиль
    for ent in (message.entities or []):
        if ent.type == "text_mention" and ent.user:
            return ent.user.id, ent.user.first_name, rest.strip()

    # 2) явно написанный @ник или ссылка t.me
    m = LINK_RE.search(rest) or USER_RE.search(rest)
    if not m:
        # 3) ничего явного нет — тогда смотрим на ответ
        rep = real_reply(message)
        if rep is not None:
            u = rep.from_user
            return u.id, u.first_name, rest.strip()

    if m:
        uname = m.group(1)
        rest = (rest[:m.start()] + rest[m.end():]).strip()
        found = await _lookup_user_by_text(uname)
        if found:
            return found[0], found[1], rest

        # Telegram не разрешает искать обычного пользователя по @нику через
        # Bot API, но список администраторов текущего чата доступен.
        try:
            for member in await bot.get_chat_administrators(message.chat.id):
                user = member.user
                if user.username and user.username.lower() == uname.lower():
                    await db.touch_user(user.id, user.username, user.first_name)
                    return user.id, user.first_name or uname, rest
        except Exception:
            pass
        try:
            chat = await bot.get_chat(f"@{uname}")
            await db.touch_user(chat.id, chat.username, chat.first_name or chat.title)
            return chat.id, chat.first_name or chat.title, rest
        except Exception:
            return None, uname, rest

    m = ID_RE.search(rest)
    if m:
        uid = int(m.group(1))
        rest = (rest[:m.start()] + rest[m.end():]).strip()
        row = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (uid,))
        return uid, (row["first_name"] if row else str(uid)), rest

    # 4) Если аргумент передан текстом без @ (например, «описание Simba», «инфа Ксюша»)
    trimmed = rest.strip()
    if trimmed:
        # Сначала пробуем всю строку целиком
        found = await _lookup_user_by_text(trimmed)
        if found:
            return found[0], found[1], ""

        # Если строка из нескольких слов (например, «варн Simba 1ч спам»)
        words = trimmed.split()
        if len(words) >= 2:
            # Двухсловный ник (например, «zz Paradise»)
            two_words = f"{words[0]} {words[1]}"
            found = await _lookup_user_by_text(two_words)
            if found:
                return found[0], found[1], " ".join(words[2:]).strip()

            # Однословный ник (например, «Simba»)
            found = await _lookup_user_by_text(words[0])
            if found:
                return found[0], found[1], " ".join(words[1:]).strip()

    return None, None, rest.strip()


PERIOD_RE = re.compile(
    r"(\d+)\s*(минут\w*|мин|м|час\w*|ч|сут\w*|день|дня|дней|д|недел\w*|нед|н|месяц\w*|мес|год\w*|г)\b",
    re.I)

UNITS = {
    "м": 60, "мин": 60, "минут": 60,
    "ч": 3600, "час": 3600,
    "д": 86400, "сут": 86400, "день": 86400, "дня": 86400, "дней": 86400,
    "н": 604800, "нед": 604800, "недел": 604800,
    "мес": 2592000, "месяц": 2592000,
    "г": 31536000, "год": 31536000,
}


UNTIL_TIME_RE = re.compile(r"\bдо\s+([01]?\d|2[0-3])[:.]([0-5]\d)\b", re.I)


def parse_period(text: str) -> tuple[int, str]:
    """'2 часа спам' -> (7200, 'спам'). 'до 20:00 спам' -> (разница, 'спам'). Без периода -> (0, текст)."""
    if not text:
        return 0, ""

    m_until = UNTIL_TIME_RE.search(text)
    if m_until:
        from datetime import datetime
        target_h = int(m_until.group(1))
        target_m = int(m_until.group(2))
        now_dt = datetime.now()
        target_dt = now_dt.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        diff = int((target_dt - now_dt).total_seconds())
        if diff <= 0:
            diff += 86400  # на следующий день
        rest = (text[:m_until.start()] + text[m_until.end():]).strip()
        return diff, rest

    m = PERIOD_RE.search(text)
    if not m:
        return 0, text.strip()
    num = int(m.group(1))
    unit = m.group(2).lower()
    secs = 0
    for k in sorted(UNITS, key=len, reverse=True):
        if unit.startswith(k):
            secs = num * UNITS[k]
            break
    rest = (text[:m.start()] + text[m.end():]).strip()
    return secs, rest


def human_period(seconds: int) -> str:
    if seconds <= 0:
        return "навсегда"
    for label, size in (("г", 31536000), ("мес", 2592000), ("нед", 604800),
                        ("д", 86400), ("ч", 3600), ("мин", 60)):
        if seconds >= size:
            return f"{seconds // size} {label}"
    return f"{seconds} сек"
