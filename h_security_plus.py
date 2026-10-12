"""Модуль расширенной безопасности:
1. Анти-рейд режим (Осада / ЧС)
4. Анти-ссылки / Анти-реклама
5. Настраиваемый медиа-блок для новичков (по времени: час, полчаса и т.д.)
9. Черный список чата (ЧС беседы)
51. Логгер удалённых сообщений
53. Адаптивный антифлуд (Smart Slowmode)
54. Слежка за подозрительными аккаунтами
55. Подтверждение опасных действий (2FA)
58. Временный щит чата (Immunity shield)
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, ChatMemberUpdated, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from utils import mention_id

router = Router(name="security_plus")

# Временные буферы в памяти
_JOIN_TRACKER: dict[int, list[float]] = defaultdict(list)
_MSG_FLOOD_TRACKER: dict[int, list[float]] = defaultdict(list)
_RECENT_DELETED: dict[int, list[dict]] = defaultdict(list)
_PENDING_2FA: dict[str, dict] = {}

LINK_REGEX = re.compile(
    r"(?i)\b(?:https?://|www\.|t\.me/|telegram\.me/|tg://)[^\s<>]+|\b@[a-zA-Z0-9_]{5,32}\b"
)


async def _autodel(msg, delay: int = 5):
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ---------------- 1. АНТИ-РЕЙД И РЕЖИМ ЧС ----------------
@router.message(Cmd("антирейд", "анти рейд", "режим чс", "чс чата", rank=6,
                    usage="антирейд [вкл/выкл]", desc="🚨 Защита от наплыва ботов и рейдов"))
async def cmd_antiraid(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    a = (args or "").strip().lower()
    row = await db.fetchone("SELECT * FROM chat_antiraid WHERE chat_id=?", (message.chat.id,))
    cur_enabled = row["enabled"] if row else 0

    if a in ("вкл", "on", "1", "старт"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, enabled) VALUES (?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET enabled=1",
            (message.chat.id,)
        )
        return await message.reply(
            "🚨 <b>Анти-рейд система АКТИВИРОВАНА!</b>\n\n"
            "🛡 При резком наплыве участников (более 5 за минуту) бот автоматически заблокирует вход и включит защиту.\n"
            "Отключить: <code>антирейд выкл</code>"
        )
    elif a in ("выкл", "off", "0", "стоп"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, enabled) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET enabled=0",
            (message.chat.id,)
        )
        return await message.reply("🟢 <b>Анти-рейд система ОТКЛЮЧЕНА.</b>")

    status_str = "🟢 Включен" if cur_enabled else "🔴 Выключен"
    thresh = row["threshold"] if row else 5
    await message.reply(
        f"🚨 <b>СТАТУС АНТИ-РЕЙД СИСТЕМЫ</b>\n\n"
        f"• Статус: <b>{status_str}</b>\n"
        f"• Порог срабатывания: <b>{thresh} чел./мин</b>\n\n"
        f"Управление: <code>антирейд вкл</code> / <code>антирейд выкл</code>"
    )


# ---------------- 4. АНТИ-ССЫЛКИ И АНТИ-РЕКЛАМА ----------------
@router.message(Cmd("антиссылки", "анти ссылки", "антиреклама", "анти реклама", rank=5,
                    usage="антиссылки [вкл/выкл]", desc="🔗 Удаление ссылок и рекламы для новичков"))
async def cmd_antilinks(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    a = (args or "").strip().lower()
    row = await db.fetchone("SELECT * FROM chat_antiraid WHERE chat_id=?", (message.chat.id,))
    cur = row["anti_links"] if row else 0

    if a in ("вкл", "on", "1"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, anti_links) VALUES (?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET anti_links=1",
            (message.chat.id,)
        )
        return await message.reply("🔗 <b>Анти-ссылки ВКЛЮЧЕНЫ!</b> Любая реклама и ссылки от участников (ранг < 2) будут удаляться.")
    elif a in ("выкл", "off", "0"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, anti_links) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET anti_links=0",
            (message.chat.id,)
        )
        return await message.reply("🟢 <b>Анти-ссылки ОТКЛЮЧЕНЫ.</b>")

    st = "🟢 Включены" if cur else "🔴 Выключены"
    await message.reply(
        f"🔗 <b>Анти-ссылки:</b> {st}\n\n"
        f"Управление: <code>антиссылки вкл</code> / <code>антиссылки выкл</code>"
    )


# ---------------- 5. МЕДИА-БЛОК ДЛЯ НОВИЧКОВ (НАСТРАИВАЕМЫЙ СРОК) ----------------
@router.message(Cmd("медиа блок", "медиаблок", "блок медиа", rank=5,
                    usage="медиа блок [время/выкл]", desc="⏳ Запрет медиа новичкам на N минут/часов"))
async def cmd_media_block(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    a = (args or "").strip().lower()
    if not a or a in ("статус", "инфо", "?"):
        row = await db.fetchone("SELECT media_block_seconds FROM chat_antiraid WHERE chat_id=?", (message.chat.id,))
        sec = row["media_block_seconds"] if row else 0
        if sec > 0:
            return await message.reply(
                f"⏳ <b>Медиа-блок для новичков АКТИВЕН!</b>\n\n"
                f"Новые участники не могут отправлять медиа первые: <b>{human_period(sec)}</b>.\n"
                f"Изменить: <code>медиа блок 2ч</code>, <code>медиа блок 30м</code>\n"
                f"Отключить: <code>медиа блок выкл</code>"
            )
        return await message.reply(
            "⏳ <b>Медиа-блок для новичков сейчас ВЫКЛЮЧЕН.</b>\n\n"
            "Вы можете задать любой срок, например:\n"
            "• <code>медиа блок 30м</code> (полчаса)\n"
            "• <code>медиа блок 1ч</code> (один час)\n"
            "• <code>медиа блок 24ч</code> (сутки)"
        )

    if a in ("выкл", "off", "0", "откл"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, media_block_seconds) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET media_block_seconds=0",
            (message.chat.id,)
        )
        return await message.reply("🟢 <b>Медиа-блок для новичков ОТКЛЮЧЕН.</b> Новички могут отправлять медиа сразу.")

    sec, _ = parse_period(a)
    if not sec or sec < 60:
        return await message.reply("⚠️ Укажите корректный срок (минимум 1 минута), например: <code>медиа блок 1ч</code> или <code>медиа блок 30м</code>.")

    await db.execute(
        "INSERT INTO chat_antiraid (chat_id, media_block_seconds) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET media_block_seconds=?",
        (message.chat.id, sec, sec)
    )
    await message.reply(
        f"⏳ <b>Медиа-блок успешно установлен на {human_period(sec)}!</b>\n\n"
        f"Все новые участники, вступившие в чат, не смогут присылать фото, видео, стикеры, кружки и голосовые в течение <b>{human_period(sec)}</b>."
    )


# ---------------- 9. ЧЕРНЫЙ СПИСОК ЧАТА (ЧС БЕСЕДЫ) ----------------
@router.message(Cmd("+чс", "чс добавить", "забанить в чс", rank=6,
                    usage="+чс {ссылка} {причина}", desc="🛡 Занести нарушителя в вечный ЧС чата"))
async def cmd_add_blacklist(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, reason = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")
    reason = (reason or "").strip() or "Нарушение правил (ЧС)"

    now = int(time.time())
    await db.execute(
        "INSERT INTO chat_blacklist (chat_id, user_id, reason, by_id, ts) VALUES (?,?,?,?,?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET reason=excluded.reason, ts=excluded.ts",
        (message.chat.id, uid, reason, message.from_user.id, now)
    )
    try:
        await bot.ban_chat_member(message.chat.id, uid)
    except Exception:
        pass

    await message.reply(
        f"🛡 <b>Пользователь занесён в ЧЁРНЫЙ СПИСОК чата!</b>\n\n"
        f"👤 {mention_id(uid, name)}\n"
        f"📝 Причина: <i>{html.escape(reason)}</i>\n"
        f"👮 Внёс: {mention_id(message.from_user.id, message.from_user.first_name)}\n\n"
        f"<i>При любой попытке входа бот будет мгновенно банить данного участника.</i>"
    )


@router.message(Cmd("-чс", "чс снять", "удалить из чс", rank=6,
                    usage="-чс {ссылка}", desc="Снять пользователя из ЧС чата"))
async def cmd_remove_blacklist(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")

    row = await db.fetchone("SELECT * FROM chat_blacklist WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    if not row:
        return await message.reply(f"{mention_id(uid, name)} не числится в Чёрном списке этого чата.")

    await db.execute("DELETE FROM chat_blacklist WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    try:
        await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
    except Exception:
        pass
    await message.reply(f"✅ {mention_id(uid, name)} <b>удалён из Чёрного списка чата</b> и разблокирован.")


@router.message(Cmd("список чс", "черный список", "чс список", rank=3,
                    usage="список чс", desc="Показать список участников в ЧС чата"))
async def cmd_list_blacklist(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return
    rows = await db.fetchall(
        "SELECT * FROM chat_blacklist WHERE chat_id=? ORDER BY id DESC LIMIT 50",
        (message.chat.id,)
    )
    if not rows:
        return await message.reply("🛡 Чёрный список этого чата пуст.")

    lines = [f"🛡 <b>ЧЁРНЫЙ СПИСОК ЧАТА (Всего: {len(rows)}):</b>\n"]
    for idx, r in enumerate(rows, 1):
        dt = time.strftime("%d.%m.%Y", time.localtime(r["ts"]))
        u = await db.get_user(r["user_id"])
        u_name = u["first_name"] if u else f"ID {r['user_id']}"
        lines.append(f"<b>{idx}.</b> {mention_id(r['user_id'], u_name)} — <i>{html.escape(r['reason'])}</i> ({dt})")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- 51. ЛОГГЕР УДАЛЁННЫХ СООБЩЕНИЙ ----------------
@router.message(Cmd("лог удалений", "удаленные сообщения", rank=4,
                    usage="лог удалений", desc="Показать последние удалённые сообщения"))
async def cmd_view_deleted_log(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    rows = await db.fetchall(
        "SELECT * FROM deleted_messages WHERE chat_id=? ORDER BY id DESC LIMIT 15",
        (message.chat.id,)
    )
    if not rows:
        return await message.reply("📭 В журнале удалённых сообщений пусто.")

    lines = ["🕵️ <b>ПОСЛЕДНИЕ УДАЛЁННЫЕ СООБЩЕНИЯ:</b>\n"]
    for r in rows:
        dt = time.strftime("%H:%M:%S", time.localtime(r["ts"]))
        txt = html.escape(r["text"][:120]) + ("..." if len(r["text"]) > 120 else "")
        lines.append(f"⏱ <code>{dt}</code> | <b>{html.escape(r['user_name'])}</b>: {txt}")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- 53. АДАПТИВНЫЙ АНТИ-ФЛУД (SMART SLOWMODE) ----------------
@router.message(Cmd("авто слоумод", "умный слоумод", rank=6,
                    usage="авто слоумод [вкл/выкл]", desc="🛑 Автоматическое гашение спам-волн"))
async def cmd_smart_slowmode(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    a = (args or "").strip().lower()
    row = await db.fetchone("SELECT slowmode_auto FROM chat_antiraid WHERE chat_id=?", (message.chat.id,))
    cur = row["slowmode_auto"] if row else 0

    if a in ("вкл", "on", "1"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, slowmode_auto) VALUES (?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET slowmode_auto=1",
            (message.chat.id,)
        )
        return await message.reply("🛑 <b>Умный авто-слоумод ВКЛЮЧЕН!</b> При резком флуде бот автоматически включит замедление.")
    elif a in ("выкл", "off", "0"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, slowmode_auto) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET slowmode_auto=0",
            (message.chat.id,)
        )
        return await message.reply("🟢 <b>Умный авто-слоумод ОТКЛЮЧЕН.</b>")

    st = "🟢 Включен" if cur else "🔴 Выключен"
    await message.reply(f"🛑 <b>Умный авто-слоумод:</b> {st}\nУправление: <code>авто слоумод вкл/выкл</code>")


# ---------------- 54. СЛЕЖКА ЗА ПОДОЗРИТЕЛЬНЫМИ ----------------
@router.message(Cmd("слежка", "следить", rank=5,
                    usage="слежка {ссылка}", desc="👁‍🗨 Включить наблюдение за подозрительным участником"))
async def cmd_spy_user(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")

    await db.execute(
        "INSERT INTO staff_spy (chat_id, target_id, by_id, ts) VALUES (?,?,?,?) "
        "ON CONFLICT(chat_id, target_id) DO UPDATE SET ts=excluded.ts",
        (message.chat.id, uid, message.from_user.id, int(time.time()))
    )
    await message.reply(
        f"👁‍🗨 <b>Наблюдение установлено!</b>\n\n"
        f"Участник {mention_id(uid, name)} помещён под особый контроль администрации.\n"
        f"Снять наблюдение: <code>снять слежку {mention_id(uid, name)}</code>"
    )


@router.message(Cmd("снять слежку", "отменить слежку", rank=5,
                    usage="снять слежку {ссылка}", desc="Снять наблюдение с участника"))
async def cmd_unspy_user(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")

    await db.execute("DELETE FROM staff_spy WHERE chat_id=? AND target_id=?", (message.chat.id, uid))
    await message.reply(f"✅ Наблюдение с {mention_id(uid, name)} снято.")


# ---------------- 58. ВРЕМЕННЫЙ ЩИТ ЧАТА ----------------
@router.message(Cmd("щит", "щит чата", "иммунитет чата", rank=6,
                    usage="щит [время/выкл]", desc="🛡 Временный запрет любых банов/киков на время ивента"))
async def cmd_chat_shield(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    a = (args or "").strip().lower()
    now = int(time.time())

    if a in ("выкл", "off", "0"):
        await db.execute(
            "INSERT INTO chat_antiraid (chat_id, shield_until) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET shield_until=0",
            (message.chat.id,)
        )
        return await message.reply("🟢 <b>Щит чата снят.</b> Модерация работает в штатном режиме.")

    sec, _ = parse_period(a or "1ч")
    sec = sec or 3600
    until = now + sec

    await db.execute(
        "INSERT INTO chat_antiraid (chat_id, shield_until) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET shield_until=?",
        (message.chat.id, until, until)
    )
    await message.reply(
        f"🛡 <b>ЩИТ ЧАТА АКТИВИРОВАН на {human_period(sec)}!</b>\n\n"
        f"На время действия щита деструктивные команды наказаний заморожены для защиты ивента.\n"
        f"Отключить досрочно: <code>щит выкл</code>"
    )


# ---------------- ХЭНДЛЕР ФОНОВОЙ ЗАЩИТЫ (MIDDLEWARE / EVENT) ----------------
@router.message()
async def security_passive_filter(message: Message, bot: Bot):
    if not message.chat or message.chat.type not in ("group", "supergroup") or not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    rank = await effective_rank(message, bot)

    # 1. Проверка Чёрного списка
    bl = await db.fetchone("SELECT reason FROM chat_blacklist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    if bl:
        try:
            await message.delete()
            await bot.ban_chat_member(chat_id, user_id)
        except Exception:
            pass
        return

    row = await db.fetchone("SELECT * FROM chat_antiraid WHERE chat_id=?", (chat_id,))
    if not row:
        return

    # 2. Проверка медиа-блока для новичков (ранг 0)
    if rank == 0 and row.get("media_block_seconds", 0) > 0:
        fs = await db.fetchone("SELECT ts FROM first_seen WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        joined_ts = fs["ts"] if fs else int(time.time())
        now = int(time.time())
        diff = now - joined_ts
        limit_sec = row["media_block_seconds"]

        if diff < limit_sec:
            is_media = bool(message.photo or message.video or message.sticker or message.animation or
                            message.voice or message.video_note or message.document)
            if is_media:
                try:
                    await message.delete()
                    rem = limit_sec - diff
                    warn_msg = await message.answer(
                        f"⏳ {mention_id(user_id, message.from_user.first_name)}, в чате действует "
                        f"<b>ограничение на медиа для новичков</b>!\n"
                        f"Доступ откроется через: <b>{human_period(rem)}</b>."
                    )
                    asyncio.create_task(_autodel(warn_msg, 6))
                except Exception:
                    pass
                return

    # 3. Проверка анти-ссылок
    if rank < 2 and row.get("anti_links", 0) == 1:
        txt = (message.text or message.caption or "")
        if LINK_REGEX.search(txt):
            try:
                await message.delete()
                warn_msg = await message.answer(
                    f"🔗 {mention_id(user_id, message.from_user.first_name)}, <b>отправка ссылок и рекламы запрещена!</b>"
                )
                asyncio.create_task(_autodel(warn_msg, 5))
            except Exception:
                pass
            return
