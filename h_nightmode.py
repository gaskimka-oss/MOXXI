"""🌙 Ночной режим («Тихий час»): автоматическое ограничение медиа/стикеров и кулдаун сообщений ночью."""
from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import Message

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from utils import mention

router = Router(name="nightmode")
S = 6  # Раздел настроек чата

TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.\s]?([0-5]\d)?\b")

# Кэш последнего сообщения пользователя в чате: {chat_id: {user_id: timestamp}}
_LAST_MSG: dict[int, dict[int, float]] = {}


def parse_time_pair(text: str) -> tuple[str, str] | None:
    """'23:00 07:00', '00:00-08:00', '22 6' -> ('23:00', '07:00')."""
    matches = list(TIME_RE.finditer(text or ""))
    if len(matches) < 2:
        return None
    
    def _to_hhmm(m) -> str:
        h = int(m.group(1))
        mnt = int(m.group(2) or 0)
        return f"{h:02d}:{mnt:02d}"

    return _to_hhmm(matches[0]), _to_hhmm(matches[1])


def is_night_active(start_str: str, end_str: str, tz_offset: int = 3) -> bool:
    """Проверяет, попадает ли текущий момент в ночной интервал."""
    try:
        now = datetime.now(timezone(timedelta(hours=tz_offset)))
        cur_min = now.hour * 60 + now.minute

        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em

        if start_min <= end_min:
            return start_min <= cur_min < end_min
        else:
            return cur_min >= start_min or cur_min < end_min
    except Exception:
        return False


async def check_night_restrictions(message: Message, bot: Bot) -> bool:
    """
    Проверяет сообщение на правила ночного режима.
    Возвращает True, если сообщение заблокировано/удалено.
    """
    if message.chat.type in {"private", "channel"}:
        return False
    if not message.from_user or message.from_user.is_bot:
        return False

    cid = message.chat.id
    uid = message.from_user.id

    # Включен ли ночной режим
    enabled = await db.get_setting(cid, "night_enabled", "0") == "1"
    if not enabled:
        return False

    # Параметры времени
    start_time = await db.get_setting(cid, "night_start", "23:00")
    end_time = await db.get_setting(cid, "night_end", "07:00")
    tz = int(await db.get_setting(cid, "night_tz", "3"))

    if not is_night_active(start_time, end_time, tz):
        return False

    # Администрация и модераторы (ранг 1+) имеют полный иммунитет
    rank = await effective_rank(message, bot)
    if rank >= 1:
        return False

    is_media = bool(
        message.sticker or message.animation or message.video or
        message.voice or message.video_note or message.photo or
        message.audio or message.document
    )

    block_media = await db.get_setting(cid, "night_block_media", "1") == "1"
    cooldown = int(await db.get_setting(cid, "night_cooldown", "20"))

    # 1. Проверка запрета медиа и стикеров
    if is_media and block_media:
        try:
            await message.delete()
        except Exception:
            pass

        if not await db.cooldown_left(uid, "night_warn_media", 45):
            await db.set_cooldown(uid, "night_warn_media")
            try:
                warn = await message.answer(
                    f"🌙 {mention(message.from_user)}, в чате действует <b>«Тихий час»</b> ({start_time} – {end_time}).\n"
                    f"🚫 Отправка стикеров и медиа ночью отключена, чтобы не шуметь."
                )
                asyncio.create_task(_delete_delayed(warn, 15))
            except Exception:
                pass
        return True

    # 2. Проверка ночного кулдауна (slowmode)
    if cooldown > 0:
        now = time.time()
        chat_last = _LAST_MSG.setdefault(cid, {})
        last_time = chat_last.get(uid, 0.0)
        elapsed = now - last_time

        if elapsed < cooldown:
            try:
                await message.delete()
            except Exception:
                pass

            left = int(cooldown - elapsed) + 1
            if not await db.cooldown_left(uid, "night_warn_cd", 20):
                await db.set_cooldown(uid, "night_warn_cd")
                try:
                    warn = await message.answer(
                        f"🌙 {mention(message.from_user)}, в чате <b>«Тихий час»</b>.\n"
                        f"⏱️ Кулдаун между сообщениями: <b>{cooldown} сек</b> (подождите ещё {left} сек)."
                    )
                    asyncio.create_task(_delete_delayed(warn, 10))
                except Exception:
                    pass
            return True

        chat_last[uid] = now

    return False


async def _delete_delayed(msg: Message, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# ══════════════════ КОМАНДЫ НАСТРОЙКИ ══════════════════

@router.message(Cmd("ночной режим", "тихий час", "ночь", section=S, rank=4,
                    usage="ночной режим [вкл|выкл|инфо|время]",
                    desc="🌙 Настройка ночного режима («Тихий час»)"))
async def cmd_night_mode(message: Message, bot: Bot, args: str = "", **kw):
    """Управление ночным режимом беседы."""
    if not await require(message, bot, 4):
        return

    cid = message.chat.id
    a = (args or "").strip().lower()

    if a in {"вкл", "on", "1", "старт", "включить"}:
        await db.set_setting(cid, "night_enabled", "1")
        return await message.reply(
            "🌙 <b>Ночной режим («Тихий час») ВКЛЮЧЕН!</b>\n\n"
            "• Ночью включается кулдаун на сообщения\n"
            "• Ограничиваются стикеры и медиа\n"
            "• Модерация и администраторы пишут без ограничений.\n\n"
            "⚙️ <i>Настройки:</i> <code>ночной режим инфо</code>"
        )

    if a in {"выкл", "off", "0", "стоп", "выключить"}:
        await db.set_setting(cid, "night_enabled", "0")
        return await message.reply("☀️ <b>Ночной режим («Тихий час») ВЫКЛЮЧЕН.</b>")

    pair = parse_time_pair(args)
    if pair:
        start_str, end_str = pair
        await db.set_setting(cid, "night_start", start_str)
        await db.set_setting(cid, "night_end", end_str)
        await db.set_setting(cid, "night_enabled", "1")
        return await message.reply(
            f"🌙 <b>Время ночного режима обновлено!</b>\n\n"
            f"⏰ Интервал: <b>{start_str} – {end_str}</b> (МСК)\n"
            f"✅ Статус: <b>включен</b>"
        )

    # Инфо / Статус
    enabled = await db.get_setting(cid, "night_enabled", "0") == "1"
    start_str = await db.get_setting(cid, "night_start", "23:00")
    end_str = await db.get_setting(cid, "night_end", "07:00")
    tz = int(await db.get_setting(cid, "night_tz", "3"))
    cooldown = int(await db.get_setting(cid, "night_cooldown", "20"))
    block_media = await db.get_setting(cid, "night_block_media", "1") == "1"
    now_active = is_night_active(start_str, end_str, tz) if enabled else False

    status_icon = "🌙 <b>АКТИВЕН ПРЯМО СЕЙЧАС</b>" if now_active else ("🟢 Включен (ждёт ночи)" if enabled else "🔴 Выключен")

    text = (
        f"🌙 ✨ <b>НОЧНОЙ РЕЖИМ («ТИХИЙ ЧАС»)</b> ✨ 🌙\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"Состояние: {status_icon}\n"
        f"⏰ Интервал: <b>{start_str} – {end_str}</b> (UTC+{tz})\n"
        f"⏱️ Кулдаун сообщений: <b>{cooldown} сек</b>\n"
        f"🚫 Запрет стикеров и медиа: <b>{'да' if block_media else 'нет'}</b>\n"
        f"👑 Иммунитет: <b>Администрация (1+ ранг)</b>\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"<b>Команды управления:</b>\n"
        f"• <code>ночной режим вкл / выкл</code>\n"
        f"• <code>ночной режим 00:00 08:00</code> — изменить интервал\n"
        f"• <code>ночной кулдаун 30</code> — интервал между репликами\n"
        f"• <code>ночные медиа вкл / выкл</code> — запрет медиа ночью"
    )
    await message.reply(text)


@router.message(Cmd("ночной кулдаун", "ночная задержка", section=S, rank=4,
                    usage="ночной кулдаун {секунды}",
                    desc="⏱️ Задержка между сообщениями в ночном режиме"))
async def cmd_night_cooldown(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip()
    if not a.isdigit():
        return await message.reply("Формат: <code>ночной кулдаун 20</code> (секунд)")
    val = max(0, min(int(a), 300))
    await db.set_setting(message.chat.id, "night_cooldown", str(val))
    await message.reply(f"⏱️ Ночной кулдаун установлен на <b>{val} сек</b>.")


@router.message(Cmd("ночные медиа", "ночной медиаблок", section=S, rank=4,
                    usage="ночные медиа вкл|выкл",
                    desc="🚫 Запрет стикеров и медиа ночью"))
async def cmd_night_media(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip().lower()
    if a in {"вкл", "on", "да", "1"}:
        await db.set_setting(message.chat.id, "night_block_media", "1")
        return await message.reply("🚫 <b>Запрет медиа и стикеров ночью: ВКЛЮЧЕН.</b>")
    if a in {"выкл", "off", "нет", "0"}:
        await db.set_setting(message.chat.id, "night_block_media", "0")
        return await message.reply("✅ <b>Запрет медиа ночью: ВЫКЛЮЧЕН (медиа разрешены).</b>")
    cur = await db.get_setting(message.chat.id, "night_block_media", "1") == "1"
    await message.reply(f"🚫 Запрет медиа ночью: <b>{'включен' if cur else 'выключен'}</b>")
