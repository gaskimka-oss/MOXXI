"""Наказания: журнал, обязательная причина, проверка по правилам чата и защита."""
from __future__ import annotations

import html
import re
import time
from typing import Optional

from aiogram import Bot
from aiogram.types import Message

import db
from core_ranks import effective_rank, get_rank, rank_label
from core_registry import MAX_RANK, RANK_NAMES, stars
from core_resolve import human_period, parse_period
from utils import mention_id

KIND_NAMES = {"mute": "мут", "ban": "бан", "warn": "варн", "kick": "кик"}
KIND_EMOJI = {"mute": "🔇", "ban": "🔨", "warn": "⚠️", "kick": "👢"}

NEEDS_TIME = {"mute"}
MIN_REASON_LEN = 2


def explain_error(e: Exception, action: str = "выполнить действие") -> str:
    err_s = str(e).lower()
    if "not enough rights" in err_s or "rights" in err_s or "admin" in err_s:
        return f"⚠️ <b>Ошибка:</b> Недостаточно прав у бота, чтобы {action}.\nУбедитесь, что бот является администратором чата со всеми правами."
    if "user is an administrator" in err_s:
        return f"⚠️ <b>Ошибка:</b> Нельзя {action} — пользователь является администратором Telegram чата."
    return f"⚠️ Не удалось {action}: {html.escape(str(e))}"


def usage_hint(kind: str) -> str:
    """Подробная подсказка с точным синтаксисом."""
    if kind == "ban":
        return (
            "⚠️ <b>Чтобы выдать бан, напишите:</b>\n"
            "• <code>бан @username [причина]</code>\n"
            "• или ответьте на сообщение нарушителя: <code>бан [причина]</code>\n\n"
            "📌 <i>Бан выдается навсегда и строго с указанием причины!</i>\n"
            "<i>Пример: <code>бан @user 1.3</code> или <code>бан реклама</code></i>"
        )
    elif kind == "unban":
        return (
            "⚠️ <b>Чтобы снять бан (разбанить), напишите:</b>\n"
            "• <code>разбан @username [причина]</code>\n"
            "• или ответьте на сообщение: <code>разбан [причина]</code>\n\n"
            "📌 <i>Причина снятия бана обязательна!</i>\n"
            "<i>Пример: <code>разбан @user ошибка / амнистия</code></i>"
        )
    elif kind == "mute":
        return (
            "⚠️ <b>Чтобы выдать мут, напишите:</b>\n"
            "• <code>мут @username [срок] [причина]</code>\n"
            "• или ответьте на сообщение нарушителя: <code>мут [срок] [причина]</code>\n\n"
            "📌 <b>Примеры:</b>\n"
            "• <code>мут @user 1ч 1.1</code>\n"
            "• <code>мут 30м спам</code> <i>(в ответ на сообщение)</i>\n"
            "• <code>мут @user 2 часа оскорбления</code>\n\n"
            "⏱️ <b>Формат времени:</b> <code>10м</code>, <code>2ч</code>, <code>1д</code>, <code>30 минут</code>, <code>7 дней</code>"
        )
    elif kind == "unmute":
        return (
            "⚠️ <b>Чтобы снять мут (размутить), напишите:</b>\n"
            "• <code>размут @username [причина]</code>\n"
            "• или ответьте на сообщение: <code>размут [причина]</code>\n\n"
            "📌 <i>Причина снятия мута обязательна!</i>\n"
            "<i>Пример: <code>размут @user осознал вину</code> или <code>размут ошибка</code></i>"
        )
    elif kind == "warn":
        return (
            "⚠️ <b>Чтобы выдать предупреждение (варн), напишите:</b>\n"
            "• <code>варн @username [причина]</code>\n"
            "• или ответьте на сообщение нарушителя: <code>варн [причина]</code>\n\n"
            "📌 <i>Пример: <code>варн @user 1.2</code> или <code>варн флуд</code></i>"
        )
    elif kind == "unwarn":
        return (
            "⚠️ <b>Чтобы снять предупреждение (варн), напишите:</b>\n"
            "• <code>снять варн @username [причина]</code>\n"
            "• или ответьте на сообщение: <code>снять варн [причина]</code>\n\n"
            "📌 <i>Причина снятия варна обязательна!</i>\n"
            "<i>Пример: <code>снять варн @user амнистия</code> или <code>снять варн @user ошибка</code></i>"
        )
    elif kind == "kick":
        return (
            "⚠️ <b>Чтобы исключить участника (кик), напишите:</b>\n"
            "• <code>кик @username [причина]</code>\n"
            "• или ответьте на сообщение: <code>кик [причина]</code>\n\n"
            "📌 <i>Пример: <code>кик @user реклама</code></i>"
        )
    return f"⚠️ Укажите пользователя и причину для команды {kind}."


async def validate_chat_rules(chat_id: int, reason: str) -> tuple[bool, str]:
    """
    Проверяет причину наказания по установленным в чате правилам.
    Если правила не заданы — пропускает.
    Если заданы — проверяет наличие пункта (1.1, 1.2, п.1) или ключевых слов.
    """
    rules_text = await db.get_setting(chat_id, "rules_text", "")
    if not rules_text or not rules_text.strip():
        return True, ""

    r_clean = reason.strip().lower()
    rules_low = rules_text.lower()

    # 1. Проверка номера пункта (1.1, 1.2, 1, 2.3, п.1 и т.д.)
    rule_num_match = re.findall(r"\b\d+(?:\.\d+)?\b", r_clean)
    for num in rule_num_match:
        if num in rules_low:
            return True, ""

    # 2. Проверка совпадения слов из причины в тексте правил
    words = [w for w in re.split(r"[^\w]+", r_clean) if len(w) >= 3]
    for w in words:
        # Ищем корень слова или полное вхождение
        stem = w[:4] if len(w) >= 5 else w
        if stem in rules_low:
            return True, ""

    # Если причина совсем не соответствует правилам
    return False, (
        f"❌ <b>Наказание отклонено: такой причины нет в правилах чата!</b>\n\n"
        f"Вы указали: «<i>{html.escape(reason)}</i>»\n"
        f"Пожалуйста, укажите пункт из правил (например: <code>1.1</code>, <code>1.2</code>) или причину из текста правил (например: <i>оскорбление</i>, <i>спам</i>).\n\n"
        f"📖 <i>Посмотреть правила чата: <code>правила</code></i>"
    )


async def check_reason(message: Message, kind: str, reason: str,
                       seconds: int = 0) -> bool:
    """
    Строгая проверка параметров наказания:
    1. Причина обязательна для ВСЕХ (даже создателей).
    2. Срок обязателен для мута.
    3. Причина сверяется с правилами чата (если они настроены).
    """
    clean = (reason or "").strip()
    if not clean or clean.lower() in ("без причины", "причина", "-"):
        await message.reply(usage_hint(kind))
        return False

    if len(clean) < MIN_REASON_LEN:
        await message.reply(usage_hint(kind))
        return False

    if kind in NEEDS_TIME and not seconds:
        await message.reply(
            f"❗️ <b>Укажите срок мута и причину.</b>\n\n"
            f"<code>{KIND_NAMES[kind]} @юзер [срок] {html.escape(clean)}</code>\n\n"
            f"<i>Пример: <code>мут @user 1ч {html.escape(clean)}</code> или <code>мут 30м {html.escape(clean)}</code></i>"
        )
        return False

    # Проверка по правилам чата
    ok, err_msg = await validate_chat_rules(message.chat.id, clean)
    if not ok:
        await message.reply(err_msg)
        return False

    return True


def strip_forever(text: str) -> tuple[str, bool]:
    """Вырезает «навсегда» из причины."""
    low = (text or "").lower()
    for w in ("навсегда", "перманентно", "насовсем", "permanent", "forever"):
        if w in low:
            i = low.index(w)
            return (text[:i] + text[i + len(w):]).strip(" ,.-"), True
    return text, False


async def guard_target(message: Message, bot: Bot, uid: int,
                       action: str = "наказать") -> Optional[str]:
    """None — можно. Иначе текст отказа."""
    if not uid:
        return "Укажите пользователя: реплаем, @ником или id."

    me = await bot.me()
    if uid == me.id:
        return "🤖 Себя я наказывать не стану."

    actor = message.from_user.id if message.from_user else 0
    if uid == actor:
        return "🙂 Себя наказывать не нужно."

    if action in {"замутить", "забанить", "кикнуть"}:
        try:
            m = await bot.get_chat_member(message.chat.id, uid)
            if m.status in {"creator", "administrator"}:
                who = ("владелец чата" if m.status == "creator"
                       else "администратор чата")
                return (
                    f"⛔️ <b>Нельзя {action} — это {who} в Telegram</b>\n\n"
                    f"Telegram запрещает ботам ограничивать администраторов.\n\n"
                    f"<b>Что делать:</b>\n"
                    f"1️⃣ Снимите с него админку: <i>Управление группой → "
                    f"Администраторы</i>\n"
                    f"2️⃣ Повторите команду"
                )
        except Exception:
            pass

    target_rank = await get_rank(message.chat.id, uid)
    actor_rank = await effective_rank(message, bot)

    import config
    # 1. Защита Владельцев бота и Создателя чата (ранг 10)
    if config.is_bot_owner(uid) or target_rank >= 10:
        return (f"👑 <b>Создатель / Владелец бота</b> неприкосновенен.\n"
                f"Его нельзя {action}.")

    actor_is_owner = config.is_bot_owner(actor)

    if not actor_is_owner:
        if target_rank >= actor_rank:
            return (f"⛔️ Нельзя {action} равного или старшего по рангу.\n"
                    f"Цель: <b>{rank_label(target_rank) if target_rank else 'Участник'}</b>\n"
                    f"Вы: <b>{rank_label(actor_rank) if actor_rank else 'Участник'}</b>")
    return None


async def log_punish(chat_id: int, uid: int, kind: str, reason: str,
                     seconds: int, by_id: int) -> int:
    await db.execute(
        "INSERT INTO punishments (chat_id,user_id,kind,reason,seconds,by_id,ts,active) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (chat_id, uid, kind, reason or "", seconds, by_id, int(time.time())))
    row = await db.fetchone("SELECT last_insert_rowid() id")
    return row["id"] if row else 0


async def lift_punish(chat_id: int, uid: int, kind: str, by_id: int) -> None:
    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? "
        "WHERE chat_id=? AND user_id=? AND kind=? AND active=1",
        (by_id, int(time.time()), chat_id, uid, kind))


async def render_history(chat_id: int, uid: int, name: str) -> str:
    rows = await db.fetchall(
        "SELECT * FROM punishments WHERE chat_id=? AND user_id=? "
        "ORDER BY id DESC LIMIT 10", (chat_id, uid))
    if not rows:
        return f"📖 История наказаний {mention_id(uid, name)} чиста."
    lines = [f"📖 <b>История наказаний</b> {mention_id(uid, name)}:"]
    for r in rows:
        emoji = KIND_EMOJI.get(r["kind"], "•")
        dur = f" ({human_period(r['seconds'])})" if r["seconds"] else ""
        date = time.strftime("%d.%m.%Y", time.gmtime(r["ts"]))
        active = " [активно]" if r["active"] else ""
        lines.append(
            f"{emoji} <b>{KIND_NAMES.get(r['kind'], r['kind'])}</b>{dur} — "
            f"<i>{html.escape(r['reason'] or 'без причины')}</i> "
            f"({date}){active}")
    return "\n".join(lines)


async def render_list(chat_id: int, kind: str) -> str:
    table = "mutes" if kind == "mute" else ("bans" if kind == "ban" else "warns")
    rows = await db.fetchall(
        f"SELECT * FROM {table} WHERE chat_id=? ORDER BY ts DESC LIMIT 20",
        (chat_id,))
    if not rows:
        return f"Список {KIND_NAMES.get(kind, kind)} пуст."
    lines = [f"📋 <b>Список {KIND_NAMES.get(kind, kind)} ({len(rows)}):</b>"]
    now = int(time.time())
    for r in rows:
        u = await db.get_user(r["user_id"])
        name = u["first_name"] or f"id{r['user_id']}"
        rem = ""
        if r.get("until"):
            left = max(0, r["until"] - now)
            rem = f" (осталось {human_period(left)})" if left else " (истёк)"
        lines.append(f"• {mention_id(r['user_id'], name)}{rem} — "
                     f"<i>{html.escape(r.get('reason') or 'без причины')}</i>")
    return "\n".join(lines)
