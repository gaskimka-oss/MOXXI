"""Модуль гибкого автоудаления сообщений через заданное время.
Поддерживает автоудаление всех сообщений чата или сообщений конкретных пользователей.
Временные интервалы: 1с, 5с, 30с, 1м, 5м, 1ч, 1д и т.д.
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from typing import Optional

from aiogram import Bot, Router
from aiogram.types import Message

import db
from core_ranks import require
from core_registry import Cmd
from core_resolve import resolve_target
from utils import mention_id

router = Router(name="autodelete")
S = 6  # Раздел: Настройки чата


def parse_autodelete_time(text: str) -> Optional[int]:
    """Парсит строку времени: 1с, 10с, 1м, 5м, 1ч, 1д, 0с, сразу."""
    if not text:
        return None
    raw = text.strip().lower()
    if raw in ("0", "0с", "0s", "сразу", "моментально", "мгновенно"):
        return 0

    m = re.match(r"^(\d+)\s*(с|сек|секунд[ыа]?|s|sec|seconds?)$", raw)
    if m:
        return int(m.group(1))

    m = re.match(r"^(\d+)\s*(м|мин|минут[ыа]?|m|min|minutes?)$", raw)
    if m:
        return int(m.group(1)) * 60

    m = re.match(r"^(\d+)\s*(ч|час|часа|часов|h|hr|hours?)$", raw)
    if m:
        return int(m.group(1)) * 3600

    m = re.match(r"^(\d+)\s*(д|день|дня|дней|d|days?)$", raw)
    if m:
        return int(m.group(1)) * 86400

    if raw.isdigit():
        val = int(raw)
        return val if val >= 0 else None

    return None


def format_delay_str(seconds: int) -> str:
    """Форматирует задержку в удобный человекочитаемый вид."""
    if seconds <= 0:
        return "⚡ сразу (0 сек.)"
    if seconds < 60:
        return f"⏱ {seconds} сек."
    if seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"⏱ {mins} мин." + (f" {secs} с." if secs else "")
    if seconds < 86400:
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"⏱ {hrs} ч." + (f" {mins} м." if mins else "")
    days = seconds // 86400
    hrs = (seconds % 86400) // 3600
    return f"⏱ {days} дн." + (f" {hrs} ч." if hrs else "")


async def schedule_delete_message(bot: Bot, chat_id: int, message_id: int, delay_seconds: int) -> None:
    """Фоновая задача удаления сообщения с задержкой."""
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def check_and_trigger_autodelete(bot: Bot, message: Message) -> None:
    """Проверяет входящее сообщение на необходимость автоудаления."""
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        return
    if not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # 1. Проверяем персональное автоудаление для пользователя
    user_rule = await db.get_user_autodelete(chat_id, user_id)
    if user_rule:
        delay = user_rule.get("delay_seconds", 0)
        asyncio.create_task(schedule_delete_message(bot, chat_id, message.message_id, delay))
        return

    # 2. Проверяем общее автоудаление чата
    chat_rule = await db.get_chat_autodelete_setting(chat_id)
    if chat_rule and chat_rule.get("enabled"):
        delay = chat_rule.get("delay_seconds", 0)
        if delay >= 0:
            asyncio.create_task(schedule_delete_message(bot, chat_id, message.message_id, delay))


# ════════════════════════════ КОМАНДЫ ════════════════════════════

@router.message(Cmd("автоудаление", "автоудал", "удаление сообщений", section=S, group_only=True,
                    usage="автоудаление [время | @юзер время]", desc="Настройка автоудаления сообщений"))
async def cmd_autodelete(message: Message, bot: Bot, args: str = "", **kw):
    args_raw = (args or "").strip()

    # 1. Если аргументов нет и нет реплая — показываем текущий статус и помощь
    if not args_raw and not message.reply_to_message:
        chat_rule = await db.get_chat_autodelete_setting(message.chat.id)
        users = await db.get_chat_autodelete_users(message.chat.id)

        chat_status = "🔴 Отключено"
        if chat_rule and chat_rule.get("enabled"):
            chat_status = f"🟢 Включено ({format_delay_str(chat_rule.get('delay_seconds', 0))})"

        users_lines = []
        if users:
            for u in users:
                uname = f"@{u['username']}" if u.get("username") else (u.get("first_name") or f"ID:{u['user_id']}")
                delay_str = format_delay_str(u.get("delay_seconds", 0))
                users_lines.append(f"  • {uname} — <b>{delay_str}</b>")
        else:
            users_lines.append("  <i>Нет пользователей в списке</i>")

        text = (
            "🗑 <b>Система автоудаления сообщений MOXXI</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
            f"🌐 <b>Все сообщения чата:</b> {chat_status}\n\n"
            f"👤 <b>Персональное автоудаление:</b>\n" + "\n".join(users_lines) + "\n\n"
            "📖 <b>Команды управления (Ранг 3+):</b>\n"
            "• <code>автоудаление 10с</code> (или <code>1м</code>, <code>1ч</code>, <code>1д</code>) — для всех сообщений\n"
            "• <code>автоудаление @юзер 10с</code> — для сообщений конкретного участника\n"
            "• <code>автоудаление @юзер 0с</code> — удалять сообщения юзера сразу\n"
            "• <code>-автоудаление</code> — выключить общее автоудаление чата\n"
            "• <code>-автоудаление @юзер</code> — убрать участника из автоудаления\n\n"
            "💡 <i>Поддерживаются форматы: с (секунды), м (минуты), ч (часы), д (дни).</i>"
        )
        return await message.reply(text)

    # Для изменений требуется ранг 3+
    if not await require(message, bot, 3):
        return

    # Проверяем, есть ли запрос выключения через "выкл" / "откл" / "стоп"
    first_token = args_raw.split()[0].lower() if args_raw else ""
    if first_token in ("выкл", "откл", "отключить", "стоп", "off", "disable"):
        await db.disable_chat_autodelete(message.chat.id)
        return await message.reply("🛑 <b>Автоудаление всех сообщений чата отключено!</b>")

    # 2. Проверяем: это настройка пользователя или всего чата?
    target_uid = None
    target_name = None

    # Попытка извлечь цель через resolve_target
    possible_target_str = args_raw
    uid, name, rest = await resolve_target(message, possible_target_str, bot)
    if uid:
        target_uid = uid
        target_name = name
        time_arg = rest.strip()
    elif message.reply_to_message:
        target_uid = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        time_arg = args_raw
    else:
        time_arg = args_raw

    # Если цель не определена — это настройка для ВСЕХ сообщений чата
    if not target_uid:
        parsed_secs = parse_autodelete_time(time_arg)
        if parsed_secs is None:
            return await message.reply(
                "⚠️ <b>Укажите корректное время!</b>\n"
                "Примеры:\n"
                "• <code>автоудаление 10с</code> — через 10 секунд\n"
                "• <code>автоудаление 1м</code> — через 1 минуту\n"
                "• <code>автоудаление 1ч</code> — через 1 час\n"
                "• <code>автоудаление 1д</code> — через 1 день"
            )

        await db.set_chat_autodelete(message.chat.id, parsed_secs, enabled=True)
        return await message.reply(
            f"✅ <b>Автоудаление всех сообщений активировано!</b>\n\n"
            f"⏱ Сообщения чата будут удаляться через: <b>{format_delay_str(parsed_secs)}</b>\n\n"
            f"<i>Отключить: <code>-автоудаление</code></i>"
        )

    # Иначе это настройка для конкретного ПОЛЬЗОВАТЕЛЯ
    # Если время не указано, ставим 0 секунд (моментальное удаление)
    if not time_arg:
        parsed_secs = 0
    else:
        parsed_secs = parse_autodelete_time(time_arg)
        if parsed_secs is None:
            parsed_secs = 0

    await db.set_user_autodelete(
        message.chat.id,
        target_uid,
        parsed_secs,
        username=(message.reply_to_message.from_user.username if message.reply_to_message and message.reply_to_message.from_user else "") or "",
        first_name=target_name or ""
    )
    await message.reply(
        f"🎯 <b>Персональное автоудаление настроено!</b>\n\n"
        f"👤 Пользователь: {mention_id(target_uid, target_name)}\n"
        f"⏱ Задержка удаления: <b>{format_delay_str(parsed_secs)}</b>\n\n"
        f"<i>Убрать из автоудаления: <code>-автоудаление @ник</code></i>"
    )


@router.message(Cmd("-автоудаление", "автоудаление выкл", "автоудаление стоп", "автоудаление отключить",
                    section=S, group_only=True, usage="-автоудаление [@юзер]", desc="Отключить автоудаление"))
async def cmd_autodelete_disable(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid and message.reply_to_message:
        uid = message.reply_to_message.from_user.id
        name = message.reply_to_message.from_user.first_name

    if uid:
        removed = await db.remove_user_autodelete(message.chat.id, uid)
        if removed:
            return await message.reply(f"✅ Пользователь {mention_id(uid, name)} удалён из списка автоудаления.")
        else:
            return await message.reply(f"ℹ️ У {mention_id(uid, name)} не было активного автоудаления.")

    # Если цель не указана — отключаем для всего чата
    await db.disable_chat_autodelete(message.chat.id)
    await message.reply("🛑 <b>Автоудаление всех сообщений чата успешно отключено!</b>")


@router.message(Cmd("автоудаление список", "автоудаление инфо", section=S, group_only=True,
                    usage="автоудаление список", desc="Список автоудалений"))
async def cmd_autodelete_list(message: Message, bot: Bot, **kw):
    await cmd_autodelete(message, bot, args="", **kw)
