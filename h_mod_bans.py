"""Разделы 2 и 5: баны, муты, предупреждения, списки, чистка чата.

Все наказания требуют причину (и срок для мута/бана), пишутся в журнал
punishments и защищают Лидера клана (7 ранг) от любого воздействия.
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import (ChatPermissions, CallbackQuery,
                           InlineKeyboardButton, InlineKeyboardMarkup, Message)

import db
import core_members as members
from config import WARN_LIMIT, WARN_MUTE_HOURS
import core_modlog as modlog
from core_punish import (KIND_NAMES, KIND_EMOJI, check_reason, explain_error, guard_target,
                         lift_punish, log_punish, render_history, render_list,
                         strip_forever, usage_hint)
from core_ranks import effective_rank, get_rank, rank_label, rank_name, require, set_rank
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from utils import mention_id

router = Router(name="mod_bans")
S_BAN, S_CLEAN = 2, 5

MUTE_OFF = ChatPermissions(can_send_messages=False, can_send_audios=False,
                           can_send_documents=False, can_send_photos=False,
                           can_send_videos=False, can_send_video_notes=False,
                           can_send_voice_notes=False, can_send_polls=False,
                           can_send_other_messages=False, can_add_web_page_previews=False)
MUTE_ON = ChatPermissions(can_send_messages=True, can_send_audios=True,
                          can_send_documents=True, can_send_photos=True,
                          can_send_videos=True, can_send_video_notes=True,
                          can_send_voice_notes=True, can_send_polls=True,
                          can_send_other_messages=True, can_add_web_page_previews=True)

# Лимит предупреждений на текущей должности. После достижения человек
# понижается на одну ступень, а счётчик для новой ступени начинается с нуля.
RANK_WARN_LIMITS = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
WARN_IMMUNE_FROM = 6
USERNAME_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")


async def _autodel_msg(msg, delay: int = 5):
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ---------------- АНТИ-СЛИВ БЕСЕДЫ (ЛИМИТЫ СОСТАВА ПО РАНГАМ) ----------------
# Лимиты действий за 10 минут (600 сек) для каждого ранга модерации
RANK_DRAIN_LIMITS = {
    1: {"ban": 0, "mute_warn": 3, "title": "Стажёр"},
    2: {"ban": 0, "mute_warn": 5, "title": "Мл. Модератор"},
    3: {"ban": 3, "mute_warn": 7, "title": "Ст. Модератор"},
    4: {"ban": 5, "mute_warn": 10, "title": "Гл. Модератор"},
    5: {"ban": 7, "mute_warn": 15, "title": "Мл. Админ"},
}
ANTI_DRAIN_ACTIONS: dict[tuple[int, int, str], list[float]] = {}
ANTI_DRAIN_WINDOW = 600  # 10 минут


async def check_anti_drain(message: Message, bot: Bot, action_name: str = "наказание",
                           action_type: str = "ban") -> bool:
    """Защита от слива беседы: дифференцированные лимиты по рангам модерации."""
    if not message.from_user:
        return True
    chat_id = message.chat.id
    actor_id = message.from_user.id
    me = await effective_rank(message, bot)
    import config
    # Старшая администрация (ранг 6+), владельцы чата и тех-админы имеют полный иммунитет
    if me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481):
        return True

    # 1. Запрет действия для ранга
    # Кик участников доступен строго со Старшей администрации (ранг 6+)
    if action_name in ("кик",) or action_type == "kick":
        await message.reply(
            f"⛔️ <b>Действие «{action_name}» запрещено для вашей должности!</b>\n\n"
            f"Исключать (кикать) участников разрешено только <b>Старшей администрации (6+ ранг)</b>.\n"
            f"Рангам 1–5 команда «кик» недоступна."
        )
        return False

    if action_name in ("бан", "тихий бан") and me < 3:
        await message.reply(
            f"⛔️ <b>Действие «{action_name}» запрещено для вашей должности!</b>\n\n"
            f"Банить разрешено только с <b>3 ранга (Ст. Модератор)</b> и выше."
        )
        return False

    lim_info = RANK_DRAIN_LIMITS.get(me, RANK_DRAIN_LIMITS[1])
    max_limit = lim_info.get(action_type, 3)
    if max_limit == 0:
        await message.reply(
            f"⛔️ <b>Действие «{action_name}» запрещено для вашей должности!</b>\n\n"
            f"🍃 <b>{lim_info['title']}</b> может выдавать только муты и предупреждения (варны).\n"
            f"Баны разрешены с <b>3 ранга (Ст. Модератор)</b>, а кики — с <b>6 ранга</b>."
        )
        return False

    # 2. Проверка лимита действий за 10 минут
    now = time.time()
    key = (chat_id, actor_id, action_type)
    history = ANTI_DRAIN_ACTIONS.get(key, [])
    history = [t for t in history if now - t < ANTI_DRAIN_WINDOW]
    ANTI_DRAIN_ACTIONS[key] = history

    if len(history) >= max_limit:
        type_label = "банов" if action_type == "ban" else "мутов/варнов"
        from core_registry import stars, rank_name
        r_lbl = f"{stars(me)} {rank_name(me)}"
        await message.reply(
            f"🚨 <b>Сработала защита от слива беседы (Анти-слив)!</b>\n\n"
            f"👮 <b>Ваш статус:</b> {r_lbl} (Ранг {me})\n"
            f"⛔️ Вы исчерпали лимит: максимум <b>{max_limit} {type_label} за 10 минут</b>.\n"
            f"🔒 Действие «{action_name}» заблокировано для защиты чата.\n\n"
            f"<i>Для проведения массовых наказаний обратитесь к Старшей администрации (ранг 6+).</i>"
        )
        return False

    history.append(now)
    ANTI_DRAIN_ACTIONS[key] = history
    return True


async def _queue_unknown_target(message: Message, args: str, kind: str) -> bool:
    """Сохраняет мут/бан/варн по нику до момента, когда станет известен user_id."""
    match = USERNAME_RE.search(args or "")
    if not match:
        return False
    username = match.group(1)
    rest = ((args or "")[:match.start()] + (args or "")[match.end():]).strip()
    seconds, reason = parse_period(rest)
    reason, forever = strip_forever(reason)
    if forever or kind == "warn":
        seconds = 0
    reason = reason.strip() or "Без причины"
    import core_pending_punish as pending
    await pending.schedule(message.chat.id, username, kind, reason, seconds,
                           message.from_user.id if message.from_user else 0)
    action = "предупреждение" if kind == "warn" else ("мут" if kind == "mute" else "бан")
    period_str = f"⏱ Срок: <b>{human_period(seconds)}</b>\n" if kind != "warn" else ""
    await message.reply(
        f"⏳ <b>{action.capitalize()} сохранено для @{html.escape(username)}</b>\n\n"
        "Telegram пока не передал его числовой ID. Наказание автоматически "
        "применится при его следующем сообщении, входе или событии участника.\n"
        f"{period_str}"
        f"📝 Причина: {html.escape(reason)}\n\n"
        "Для немедленного применения можно указать числовой ID или ответить "
        "командой на сообщение пользователя.")
    return True


# ---------------- МУТ ----------------
@router.message(Cmd("мут", "замутить", "ro", "молчать", section=S_BAN, rank=1,
                    usage="мут {ссылка} {время} {причина}",
                    desc="Запретить писать (нужны срок и причина)"))
async def cmd_mute(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not await require(message, bot, 1):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        if await _queue_unknown_target(message, args, "mute"):
            return
        return await message.reply(usage_hint("mute"))
    err = await guard_target(message, bot, uid, "замутить")
    if err:
        return await message.reply(err)
    secs, reason = parse_period(rest)
    reason, forever = strip_forever(reason)
    if forever:
        secs = 0
    reason = reason.strip()
    if not secs or not reason:
        return await message.reply(usage_hint("mute"))
    if not await check_reason(message, "mute", reason, secs):
        return

    actor_rank = await effective_rank(message, bot)
    if actor_rank == 1 and (secs == 0 or secs > 86400):
        return await message.reply(
            "⛔️ <b>Стажёр не может выдавать мут дольше, чем на 24 часа!</b>\n"
            "Максимальный срок для стажёра — 24 часа (1 день). Навсегда мутить запрещено."
        )

    if not await check_anti_drain(message, bot, "мут", action_type="mute_warn"):
        return

    until = datetime.now(timezone.utc) + timedelta(seconds=secs)
    try:
        await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
    except Exception as e:
        return await message.reply(explain_error(e, "замутить"))
    pid = await log_punish(message.chat.id, uid, "mute", reason, secs,
                           message.from_user.id if message.from_user else 0)
    await db.execute(
        "INSERT INTO mutes (chat_id,user_id,reason,by_id,until,ts) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(chat_id,user_id) DO UPDATE SET reason=excluded.reason, until=excluded.until",
        (message.chat.id, uid, reason, message.from_user.id if message.from_user else 0,
         int(time.time()) + secs if secs else 0, int(time.time())))
    ctx = await modlog.build_context(message.chat.id, uid)
    await modlog.write(message.chat.id, pid, uid, name,
                       message.from_user.id, message.from_user.first_name,
                       "mute", reason, secs, "админ", ctx, bot=bot)

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("mute", reason, name, message.from_user.first_name or "модератор", is_unpunish=False, seconds=secs, context=ctx)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    sent = await message.reply(
        f"🔇 <b>Мут выдан</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"⏱ Срок: <b>{human_period(secs)}</b>\n"
        f"📝 Причина: {html.escape(reason)}\n"
        f"👮 Модератор: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
        f"<code>#{pid}</code>{ai_note}")
    modlog.schedule_autodelete(bot, sent)


@router.message(Cmd("размут", "размутить", "unmute", section=S_BAN, rank=1,
                    usage="размут {ссылка} {причина}", desc="Снять мут (нужна причина)"))
async def cmd_unmute(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(usage_hint("unmute"))
    reason = (rest or "").strip()
    if not reason or len(reason) < 2 or reason.lower() in ("без причины", "причина", "-"):
        return await message.reply(usage_hint("unmute"))

    try:
        await bot.restrict_chat_member(message.chat.id, uid, MUTE_ON)
    except Exception as e:
        return await message.reply(explain_error(e, "размутить"))
    await db.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await lift_punish(message.chat.id, uid, "mute", message.from_user.id)

    # Журнал снятий
    await db.execute(
        "INSERT INTO lift_log (chat_id, log_id, punish_id, target_id, target_name, "
        "kind, reason, by_id, by_name, lifted_by, lifted_name, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (message.chat.id, 0, 0, uid, name, "mute", reason, 0, "",
         message.from_user.id, message.from_user.first_name, int(time.time())))

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("mute", reason, name, message.from_user.first_name or "модератор", is_unpunish=True)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    await message.reply(
        f"🔊 <b>Мут снят</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"📝 Причина снятия: {html.escape(reason)}\n"
        f"👮 Модератор: {mention_id(message.from_user.id, message.from_user.first_name)}{ai_note}")


@router.message(Cmd("мутлист", "мут лист", "список мутов", "муты", section=S_BAN, rank=1,
                    usage="мутлист", desc="Список замученных с причинами"))
async def cmd_mutelist(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    await message.reply(await render_list(message.chat.id, "mute"),
                        disable_web_page_preview=True)


# ---------------- БАН ----------------
@router.message(Cmd("бан", "забанить", "ban", section=S_BAN, rank=3,
                    usage="бан {ссылка} {причина}",
                    desc="Заблокировать навсегда (нужна причина)"))
async def cmd_ban(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not await require(message, bot, 3):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        if await _queue_unknown_target(message, args, "ban"):
            return
        return await message.reply(usage_hint("ban"))
    err = await guard_target(message, bot, uid, "забанить")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    reason, _ = strip_forever(reason)
    reason = reason.strip()
    if not reason:
        return await message.reply(usage_hint("ban"))
    if not await check_reason(message, "ban", reason, 0):
        return

    if not await check_anti_drain(message, bot, "бан"):
        return

    try:
        await bot.ban_chat_member(message.chat.id, uid)
    except Exception as e:
        return await message.reply(explain_error(e, "забанить"))
    await members.remember_member(message.chat.id, uid, "kicked", False)
    # Очищаем анкету, описание и ник забаненного игрока для этого чата
    await db.execute("DELETE FROM chat_profiles WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await db.execute("DELETE FROM chat_nicks WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await db.execute("DELETE FROM profiles WHERE user_id=?", (uid,))
    await db.execute("UPDATE users SET nick=NULL WHERE user_id=?", (uid,))

    pid = await log_punish(message.chat.id, uid, "ban", reason, 0,
                           message.from_user.id if message.from_user else 0)
    await db.execute(
        "INSERT INTO bans (chat_id,user_id,reason,by_id,until,ts) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(chat_id,user_id) DO UPDATE SET reason=excluded.reason, until=excluded.until",
        (message.chat.id, uid, reason, message.from_user.id if message.from_user else 0,
         0, int(time.time())))
    ctx = await modlog.build_context(message.chat.id, uid)
    await modlog.write(message.chat.id, pid, uid, name,
                       message.from_user.id, message.from_user.first_name,
                       "ban", reason, 0, "админ", ctx, bot=bot)

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("ban", reason, name, message.from_user.first_name or "администратор", is_unpunish=False, seconds=0, context=ctx)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    sent = await message.reply(
        f"🔨 <b>Бан выдан (навсегда)</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"📝 Причина: {html.escape(reason)}\n"
        f"👮 Администратор: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
        f"<code>#{pid}</code>{ai_note}")
    modlog.schedule_autodelete(bot, sent)


@router.message(Cmd("разбан", "разбанить", "unban", section=S_BAN, rank=3,
                    usage="разбан {ссылка} {причина}", desc="Снять блокировку (нужна причина)"))
async def cmd_unban(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(usage_hint("unban"))
    reason = (rest or "").strip()
    if not reason or len(reason) < 2 or reason.lower() in ("без причины", "причина", "-"):
        return await message.reply(usage_hint("unban"))

    try:
        await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
    except Exception as e:
        return await message.reply(explain_error(e, "разбанить"))
    await db.execute("DELETE FROM bans WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await members.remember_member(message.chat.id, uid, "left", False)
    await lift_punish(message.chat.id, uid, "ban", message.from_user.id)

    # Журнал снятий
    await db.execute(
        "INSERT INTO lift_log (chat_id, log_id, punish_id, target_id, target_name, "
        "kind, reason, by_id, by_name, lifted_by, lifted_name, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (message.chat.id, 0, 0, uid, name, "ban", reason, 0, "",
         message.from_user.id, message.from_user.first_name, int(time.time())))

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("ban", reason, name, message.from_user.first_name or "администратор", is_unpunish=True)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    await message.reply(
        f"✅ <b>Бан снят (разблокирован)</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"📝 Причина снятия: {html.escape(reason)}\n"
        f"👮 Администратор: {mention_id(message.from_user.id, message.from_user.first_name)}{ai_note}")


@router.message(Cmd("банлист", "бан лист", "список банов", "баны", section=S_BAN, rank=2,
                    usage="банлист", desc="Список забаненных с причинами"))
async def cmd_banlist(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return
    await message.reply(await render_list(message.chat.id, "ban"),
                        disable_web_page_preview=True)


@router.message(Cmd("бан вышедших", "забанить вышедших", "бан вышедшых", "очистить вышедших",
                    section=S_BAN, rank=4, usage="бан вышедших",
                    desc="Забанить и снести анкеты/ники всех участников, покинувших чат"))
async def cmd_ban_left(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    cid = message.chat.id
    status_msg = await message.reply("🔍 <b>Проверяю список участников и анкеты...</b>")

    rows_cp = await db.fetchall("SELECT DISTINCT user_id FROM chat_profiles WHERE chat_id=?", (cid,))
    rows_p = await db.fetchall("SELECT DISTINCT user_id FROM profiles")
    rows_r = await db.fetchall("SELECT DISTINCT user_id FROM ranks WHERE chat_id=?", (cid,))
    rows_s = await db.fetchall("SELECT DISTINCT user_id FROM chat_stats WHERE chat_id=?", (cid,))
    rows_m = await db.fetchall("SELECT DISTINCT user_id FROM chat_members WHERE chat_id=?", (cid,))
    rows_cn = await db.fetchall("SELECT DISTINCT user_id FROM chat_nicks WHERE chat_id=?", (cid,))

    all_uids = list({r["user_id"] for r in (rows_cp + rows_p + rows_r + rows_s + rows_m + rows_cn) if r.get("user_id") and r["user_id"] > 0})
    banned_count = 0
    now = int(time.time())

    from config import OWNER_ID
    for uid in all_uids:
        if uid == OWNER_ID or uid == message.from_user.id:
            continue
        try:
            m = await bot.get_chat_member(cid, uid)
            if m.status in {"left", "kicked"}:
                try:
                    await bot.ban_chat_member(cid, uid)
                except Exception:
                    pass
                await db.execute("DELETE FROM chat_profiles WHERE chat_id=? AND user_id=?", (cid, uid))
                await db.execute("DELETE FROM chat_nicks WHERE chat_id=? AND user_id=?", (cid, uid))
                await db.execute("DELETE FROM ranks WHERE chat_id=? AND user_id=? AND rank < 10", (cid, uid))
                await db.execute(
                    "INSERT INTO chat_members (chat_id, user_id, status, is_member, updated_at) "
                    "VALUES (?, ?, 'kicked', 0, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET is_member=0, status='kicked', updated_at=excluded.updated_at",
                    (cid, uid, now)
                )
                await db.execute(
                    "INSERT INTO bans (chat_id,user_id,reason,by_id,until,ts) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(chat_id,user_id) DO UPDATE SET reason=excluded.reason, until=excluded.until",
                    (cid, uid, "Выход из группы", message.from_user.id, 0, now)
                )
                banned_count += 1
                await asyncio.sleep(0.05)
            elif m.status in {"member", "administrator", "creator", "restricted"}:
                await db.execute(
                    "INSERT INTO chat_members (chat_id, user_id, status, is_member, updated_at) "
                    "VALUES (?, ?, ?, 1, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET is_member=1, status=excluded.status, updated_at=excluded.updated_at",
                    (cid, uid, m.status, now)
                )
        except Exception:
            continue

    await status_msg.edit_text(
        f"🧹 <b>Очистка вышедших завершена!</b>\n\n"
        f"• Найдено и обработано: <b>{banned_count} чел.</b>\n"
        f"• Выдан бан (Выход из группы)\n"
        f"• Анкеты и ники этого чата очищены\n"
        f"• Ранги модерации сброшены"
    )


@router.message(Cmd("кик", "кикнуть", "выгнать", "kick", section=S_BAN, rank=6,
                    usage="кик {ссылка} {причина}", desc="Исключить из чата (ранг 6+)"))
async def cmd_kick(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(usage_hint("kick"))
    err = await guard_target(message, bot, uid, "кикнуть")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    if not reason:
        return await message.reply(usage_hint("kick"))
    if not await check_reason(message, "kick", reason):
        return
    if not await check_anti_drain(message, bot, "кик", action_type="kick"):
        return
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        await bot.unban_chat_member(message.chat.id, uid)
    except Exception as e:
        return await message.reply(explain_error(e, "кикнуть"))
    await members.remember_member(message.chat.id, uid, "left", False)
    pid = await log_punish(message.chat.id, uid, "kick", reason, 0, message.from_user.id)
    ctx = await modlog.build_context(message.chat.id, uid)
    await modlog.write(message.chat.id, pid, uid, name,
                       message.from_user.id, message.from_user.first_name,
                       "kick", reason, 0, "админ", ctx, bot=bot)

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("kick", reason, name, message.from_user.first_name or "модератор", is_unpunish=False, seconds=0, context=ctx)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    sent = await message.reply(f"👢 <b>Исключён</b>\n👤 {mention_id(uid, name)}\n"
                               f"📝 Причина: {html.escape(reason)}\n<code>#{pid}</code>{ai_note}")
    modlog.schedule_autodelete(bot, sent)


# ---------------- ПРЕДУПРЕЖДЕНИЯ ----------------
@router.message(Cmd("варн", "пред", "предупреждение", "warn", section=S_BAN, rank=1,
                    usage="варн {ссылка} {причина}", desc="Выдать предупреждение"))
async def cmd_warn(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not await require(message, bot, 1):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        if await _queue_unknown_target(message, args, "warn"):
            return
        return await message.reply(usage_hint("warn"))
    err = await guard_target(message, bot, uid, "предупредить")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    if not reason:
        return await message.reply(usage_hint("warn"))
    if not await check_reason(message, "warn", reason):
        return

    if not await check_anti_drain(message, bot, "варн", action_type="mute_warn"):
        return

    target_rank = await get_rank(message.chat.id, uid)
    if target_rank >= WARN_IMMUNE_FROM:
        return await message.reply(
            f"🛡 <b>{rank_label(target_rank)}</b> имеет иммунитет к варнам.\n"
            "Техническим администраторам, заместителям и лидерам варны не выдаются.")

    # Проверка щита от варна из инвентаря
    try:
        import h_items
        if await h_items.check_and_consume_warn_shield(uid):
            return await message.reply(
                f"🛡️ <b>Сработал Щит от варна!</b>\n\n"
                f"👤 {mention_id(uid, name)} был защищён автоматическим щитом из инвентаря.\n"
                f"⚠️ Предупреждение отменено, 1 щит израсходован."
            )
    except Exception:
        pass

    await db.execute("INSERT INTO warns (chat_id,user_id,admin_id,reason,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, uid, message.from_user.id, reason, int(time.time())))
    pid = await log_punish(message.chat.id, uid, "warn", reason, 0, message.from_user.id)
    row = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?",
                            (message.chat.id, uid))

    limit = int(await db.get_setting(message.chat.id, "warn_limit", str(WARN_LIMIT)))
    if limit < 1:
        limit = 3
    cur_count = int(row["c"])
    bar_squares = " ".join("🟥" if i < cur_count else "⬜️" for i in range(limit))
    scale_text = f"[ {bar_squares} ] ({cur_count}/{limit})"

    text = (f"⚠️ <b>Предупреждение выдано!</b>\n"
            f"👤 {mention_id(uid, name)}\n"
            f"📊 <b>Шкала:</b> <code>{scale_text}</code>\n"
            f"🎖 Статус: <b>{rank_label(target_rank) if target_rank else 'Игрок'}</b>\n"
            f"📝 Причина: {html.escape(reason)}\n"
            f"👮 Администратор: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
            f"<code>#{pid}</code>")
    if cur_count >= limit:
        until = datetime.now(timezone.utc) + timedelta(hours=WARN_MUTE_HOURS)
        try:
            await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
            await log_punish(message.chat.id, uid, "mute",
                             f"автомут: {limit} предупреждений", WARN_MUTE_HOURS * 3600, 0)
            text += f"\n\n🔇 <b>Лимит предупреждений ({limit}/{limit}) достигнут!</b> Автомут на {WARN_MUTE_HOURS} ч."
        except Exception as e:
            if "administrator" in str(e).lower():
                text += "\n\n<i>(автомут не применён: пользователь — админ Telegram)</i>"
            else:
                text += "\n\n<i>(не хватило прав для автомута)</i>"
        await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?",
                         (message.chat.id, uid))
    ctx = await modlog.build_context(message.chat.id, uid)
    await modlog.write(message.chat.id, pid, uid, name,
                       message.from_user.id, message.from_user.first_name,
                       "warn", reason, 0, "админ", ctx, bot=bot)

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("warn", reason, name, message.from_user.first_name or "модератор", is_unpunish=False, seconds=0, context=ctx)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    sent = await message.reply(text + ai_note)
    modlog.schedule_autodelete(bot, sent)


@router.message(Cmd("лимит варнов", "варн лимит", "настройка варнов", section=S_BAN, rank=3,
                    usage="лимит варнов [2-10]", desc="⚙️ Установить максимум варнов для чата (от 2 до 10)"))
async def cmd_set_warn_limit(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    cid = message.chat.id
    val = (args or "").strip()
    if not val.isdigit() or int(val) < 2 or int(val) > 10:
        cur = await db.get_setting(cid, "warn_limit", str(WARN_LIMIT))
        return await message.reply(
            f"⚙️ <b>Настройка лимита варнов для этой группы:</b>\n"
            f"Текущий лимит: <b>{cur} варнов</b> до автомута.\n\n"
            f"Чтобы изменить, укажите число от 2 до 10:\n"
            f"👉 <code>лимит варнов 5</code> (шкала из 5 квадратов)\n"
            f"👉 <code>лимит варнов 3</code> (шкала из 3 квадратов)"
        )
    new_limit = int(val)
    await db.set_setting(cid, "warn_limit", str(new_limit))
    sample_bar = " ".join("⬜️" for _ in range(new_limit))
    await message.reply(
        f"✅ <b>Лимит варнов для этого чата установлен: {new_limit}!</b>\n\n"
        f"Новая шкала в чате: <code>[ {sample_bar} ] (0/{new_limit})</code>\n"
        f"При получении {new_limit}-го варна участник получит автомут на {WARN_MUTE_HOURS} ч."
    )


@router.message(Cmd("снять варн", "снять пред", "минус варн", "unwarn", section=S_BAN, rank=2,
                    usage="снять варн {ссылка} {причина}", desc="Снять предупреждение (нужна причина)"))
async def cmd_unwarn(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(usage_hint("unwarn"))
    reason = (rest or "").strip()
    if not reason or len(reason) < 2 or reason.lower() in ("без причины", "причина", "-"):
        return await message.reply(usage_hint("unwarn"))

    latest = await db.fetchone(
        "SELECT id FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
        (message.chat.id, uid))
    if not latest:
        return await message.reply(
            f"ℹ️ У {mention_id(uid, name)} <b>отсутствуют предупреждения</b> — "
            "снимать нечего.")
    await db.execute("DELETE FROM warns WHERE id=?", (latest["id"],))
    await db.execute("UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE id="
                     "(SELECT id FROM punishments WHERE chat_id=? AND user_id=? AND kind='warn' "
                     "AND active=1 ORDER BY id DESC LIMIT 1)",
                     (message.from_user.id, int(time.time()), message.chat.id, uid))

    # Журнал снятий
    await db.execute(
        "INSERT INTO lift_log (chat_id, log_id, punish_id, target_id, target_name, "
        "kind, reason, by_id, by_name, lifted_by, lifted_name, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (message.chat.id, 0, 0, uid, name, "warn", reason, 0, "",
         message.from_user.id, message.from_user.first_name, int(time.time())))

    left = await db.fetchone(
        "SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?",
        (message.chat.id, uid))

    ai_note = ""
    try:
        import core_ai as ai
        rev = await ai.evaluate_action("warn", reason, name, message.from_user.first_name or "модератор", is_unpunish=True)
        ai_note = ai.format_ai_verdict(rev)
    except Exception:
        pass

    left_c = int(left['c']) if left else 0
    limit = int(await db.get_setting(message.chat.id, "warn_limit", str(WARN_LIMIT)))
    if limit < 1:
        limit = 3
    bar_squares = " ".join("🟥" if i < left_c else "⬜️" for i in range(limit))
    scale_text = f"[ {bar_squares} ] ({left_c}/{limit})"

    await message.reply(
        f"✅ <b>Снято одно предупреждение</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"📝 Причина снятия: {html.escape(reason)}\n"
        f"📊 <b>Текущая шкала:</b> <code>{scale_text}</code>\n"
        f"👮 Модератор: {mention_id(message.from_user.id, message.from_user.first_name)}{ai_note}")


@router.message(Cmd("варнлист", "варн лист", "список варнов", "все варны",
                    section=S_BAN, rank=1, usage="варнлист",
                    desc="Список всех предупреждений чата (модерация)"))
async def cmd_warnlist(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    await message.reply(await render_list(message.chat.id, "warn"),
                        disable_web_page_preview=True)


@router.message(Cmd("преды", "варны", "мои варны", "мои преды", "предупреждения",
                    section=S_BAN, usage="преды",
                    desc="Посмотреть свои предупреждения"))
async def cmd_warns(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    own = False
    if not uid and message.from_user:
        uid, name = message.from_user.id, message.from_user.first_name
        own = True

    rows = await db.fetchall(
        "SELECT reason, ts, admin_id FROM warns WHERE chat_id=? AND user_id=? "
        "ORDER BY id DESC", (message.chat.id, uid))
    target_rank = await get_rank(message.chat.id, uid)
    if target_rank >= WARN_IMMUNE_FROM:
        return await message.reply(
            f"🛡 {mention_id(uid, name)} — <b>{rank_label(target_rank)}</b>.\n"
            "Для этой должности действует иммунитет к варнам.")
    limit = RANK_WARN_LIMITS.get(target_rank) or int(await db.get_setting(
        message.chat.id, "warn_limit", str(WARN_LIMIT)))
    if limit < 1:
        limit = 3

    cur_c = len(rows)
    bar_squares = " ".join("🟥" if i < cur_c else "⬜️" for i in range(limit))
    scale_text = f"[ {bar_squares} ] ({cur_c}/{limit})"

    if not rows:
        return await message.reply(
            f"✅ {'У вас' if own else f'У {mention_id(uid, name)}'} "
            f"<b>нет предупреждений</b>.\n"
            f"📊 Шкала: <code>{scale_text}</code> (Лимит: {limit})")

    left = limit - len(rows)
    head = (f"⚠️ <b>{'Ваши предупреждения' if own else 'Предупреждения'}</b>"
            f"{'' if own else ' ' + mention_id(uid, name)}\n"
            f"📊 <b>Шкала:</b> <code>{scale_text}</code>")
    if left > 0:
        head += f" · до наказания осталось: <b>{left}</b>"
    else:
        head += " · <b>лимит достигнут</b>"

    lines = [head, ""]
    for i, r in enumerate(rows, 1):
        who = ""
        if r["admin_id"]:
            a = await db.get_user(r["admin_id"])
            who = f" · 👮 {mention_id(r['admin_id'], a['first_name'])}"
        else:
            who = " · 👮 Кузя"
        lines.append(
            f"{i}. {html.escape(r['reason'] or 'без причины')}\n"
            f"   🕒 {time.strftime('%d.%m.%Y %H:%M', time.localtime(r['ts']))}{who}")

    await message.reply("\n".join(lines)[:3800], disable_web_page_preview=True)


@router.message(Cmd("лимит варнов", "варнлимит", section=S_BAN, rank=3,
                    usage="лимит варнов {число}", desc="Настроить лимит предупреждений"))
async def cmd_warn_limit(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    if not args.strip().isdigit():
        cur = await db.get_setting(message.chat.id, "warn_limit", str(WARN_LIMIT))
        return await message.reply(f"Текущий лимит: <b>{cur}</b>\n"
                                   f"Изменить: <code>лимит варнов 5</code>")
    await db.set_setting(message.chat.id, "warn_limit", args.strip())
    await message.reply(f"✅ Лимит предупреждений: <b>{args.strip()}</b>")


# ---------------- ИСТОРИЯ НАКАЗАНИЙ ----------------
@router.message(Cmd("история", "история наказаний", "история нарушений", "моя история", "нарушения",
                    section=S_BAN, rank=0, usage="история [@юзер]",
                    desc="История наказаний участника"))
async def cmd_history(message: Message, bot: Bot, args: str = "", **kw):
    from core_resolve import real_reply
    a = (args or "").strip()
    me = message.from_user.id if message.from_user else 0

    if a or real_reply(message) is not None:
        if not await require(message, bot, 1):
            return
        uid, name, _ = await resolve_target(message, a, bot)
        if not uid:
            return await message.reply("Укажите пользователя: реплаем, @ником или id.")
    else:
        uid, name = me, (message.from_user.first_name if message.from_user else str(me))

    await message.reply(await render_history(message.chat.id, uid, name),
                        disable_web_page_preview=True)


# ---------------- ДОСЬЕ / ЧЕК УЧАСТНИКА (МОДЕРАЦИЯ) ----------------
async def _render_user_dossier(cid: int, uid: int, bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    u = await db.get_user(uid)
    p = await db.fetchone("SELECT * FROM profiles WHERE user_id=?", (uid,)) or {}
    st = await db.fetchone("SELECT * FROM chat_stats WHERE chat_id=? AND user_id=?", (cid, uid)) or {}
    rank = await get_rank(cid, uid)
    r_name = rank_label(rank)

    in_chat = "Неизвестно"
    try:
        cm = await bot.get_chat_member(cid, uid)
        if cm.status in {"creator", "administrator"}:
            in_chat = "👑 Администратор TG"
        elif cm.status in {"member", "restricted"}:
            in_chat = "🟢 Участник"
        elif cm.status in {"left", "kicked"}:
            in_chat = "🔴 Не в чате"
    except Exception:
        in_chat = "Не в чате / Недоступен"

    m_row = await db.fetchone("SELECT * FROM mutes WHERE chat_id=? AND user_id=?", (cid, uid))
    now = int(time.time())
    is_muted = bool(m_row and (not m_row.get("until") or m_row["until"] > now))
    mute_str = f"🔇 Активен (до {time.strftime('%d.%m %H:%M', time.localtime(m_row['until']))})" if (is_muted and m_row and m_row.get("until")) else ("🔇 Бессрочно" if is_muted else "🔊 Нет")

    warns = await db.fetchall("SELECT * FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
    warn_cnt = len(warns)
    limit = RANK_WARN_LIMITS.get(rank) or 3
    warn_str = f"⚠️ {warn_cnt}/{limit}"

    b_row = await db.fetchone("SELECT * FROM bans WHERE chat_id=? AND user_id=?", (cid, uid))
    is_banned = bool(b_row and (not b_row.get("until") or b_row["until"] > now))
    ban_str = "🔨 Да (Забанен)" if is_banned else "⚪️ Нет"

    tot_p = await db.fetchone("SELECT COUNT(*) c FROM punishments WHERE chat_id=? AND user_id=?", (cid, uid))
    all_infractions = tot_p["c"] if tot_p else 0

    nick = u["nick"] or p.get("hobby") or p.get("nick2") or "—"
    rname = p.get("real_name") or u["first_name"] or str(uid)
    age = p.get("age") or "—"
    country = p.get("country") or "—"

    msgs = st.get("messages", 0)
    coins = u["balance"] if "balance" in u.keys() else 0

    disp_name = html.escape(u["first_name"] or str(uid))
    uname = f"@{u['username']}" if u["username"] else "нет"

    text = (
        f"🕵️ <b>ДОСЬЕ УЧАСТНИКА: {mention_id(uid, disp_name)}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🆔 ID: <code>{uid}</code> | Юзернейм: {uname}\n"
        f"▫️ <b>Ранг:</b> {r_name} (ур. {rank})\n"
        f"▫️ <b>Статус в TG:</b> {in_chat}\n\n"
        f"⚖️ <b>НАРУШЕНИЯ И ОГРАНИЧЕНИЯ:</b>\n"
        f"• Предупреждения: <b>{warn_str}</b>\n"
        f"• Мут: <b>{mute_str}</b>\n"
        f"• Бан: <b>{ban_str}</b>\n"
        f"• Всего записей в базе нарушений: <b>{all_infractions}</b>\n\n"
        f"📋 <b>ДАННЫЕ И АКТИВНОСТЬ:</b>\n"
        f"• Ник: <b>{html.escape(str(nick))}</b>\n"
        f"• Имя: <b>{html.escape(str(rname))}</b> (возраст: {age}, страна: {country})\n"
        f"• Сообщений в группе: <b>{msgs}</b>\n"
        f"• Баланс: <b>{coins}</b> монет\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"⚡ <i>Быстрые действия модерации:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔇 Мут 30м", callback_data=f"adm:m:{cid}:{uid}:1800"),
            InlineKeyboardButton(text="⚠️ Варн", callback_data=f"adm:w:{cid}:{uid}"),
            InlineKeyboardButton(text="🔨 Бан", callback_data=f"adm:b:{cid}:{uid}"),
        ],
        [
            InlineKeyboardButton(text="🧹 Снять варны", callback_data=f"adm:uw:{cid}:{uid}"),
            InlineKeyboardButton(text="🔊 Размут", callback_data=f"adm:um:{cid}:{uid}"),
        ],
        [
            InlineKeyboardButton(text="📖 История", callback_data=f"adm:h:{cid}:{uid}"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"adm:rf:{cid}:{uid}"),
        ]
    ])
    return text, kb


@router.message(Cmd("чек", "проверить", "досье", "чек юзера", "досье игрока", "проверить игрока",
                    section=S_BAN, rank=2, usage="чек [@юзер]",
                    desc="Карточка модератора с быстрыми действиями"))
async def cmd_dossier(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    a = (args or "").strip()
    from core_resolve import real_reply
    had_prefix = kw.get("had_prefix", False)
    is_reply = bool(real_reply(message))
    if not had_prefix and not is_reply:
        # Без префикса и не реплаем реагируем только на явные идентификаторы (@user, ID, t.me)
        if not a or not (a.startswith("@") or a.isdigit() or "t.me/" in a):
            return

    if not a and not is_reply:
        return await message.reply("🕵️ Укажите участника для проверки:\n<code>чек @username</code> или ответом на сообщение.")

    uid, name, _ = await resolve_target(message, a, bot)
    if not uid:
        if not had_prefix and not is_reply:
            return
        return await message.reply(f"🤔 Не удалось найти участника {html.escape(a[:32])}.")

    text, kb = await _render_user_dossier(message.chat.id, uid, bot)
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin_dossier_action(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    act = parts[1]
    cid = int(parts[2])
    uid = int(parts[3])
    mod_id = call.from_user.id

    from core_ranks import get_rank
    import config
    mod_rank = 8 if (mod_id == config.OWNER_ID or mod_id in config.ADMINS) else await get_rank(cid, mod_id)

    if act == "rf":
        text, kb = await _render_user_dossier(cid, uid, bot)
        try:
            await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        return await call.answer("Досье обновлено!")

    if act == "h":
        u = await db.get_user(uid)
        hist = await render_history(cid, uid, u["first_name"] or str(uid))
        return await call.message.reply(hist, disable_web_page_preview=True)

    if mod_rank < 2:
        return await call.answer("🔒 Действие доступно только модераторам (ранг 2+)!", show_alert=True)

    target_rank = await get_rank(cid, uid)
    if target_rank >= mod_rank and mod_id != config.OWNER_ID:
        return await call.answer("🛡 Нельзя применить действие к участнику равного или старшего ранга!", show_alert=True)

    now = int(time.time())
    if act == "m":
        secs = int(parts[4]) if len(parts) > 4 else 1800
        until = datetime.now(timezone.utc) + timedelta(seconds=secs)
        try:
            await bot.restrict_chat_member(cid, uid, MUTE_OFF, until_date=until)
            await db.execute("INSERT OR REPLACE INTO mutes (chat_id, user_id, reason, by_id, until, ts) VALUES (?,?,?,?,?,?)",
                            (cid, uid, "Быстрое наказание модерации", mod_id, now + secs, now))
            await log_punish(cid, uid, "mute", "Быстрое наказание модерации", secs, mod_id)
            await call.answer("🔇 Пользователь замучен на 30 мин!")
        except Exception as e:
            return await call.answer(f"Ошибка: {e}", show_alert=True)

    elif act == "w":
        limit = RANK_WARN_LIMITS.get(target_rank) or 3
        await db.execute("INSERT INTO warns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
                        (cid, uid, mod_id, "Быстрое предупреждение модерации", now))
        await log_punish(cid, uid, "warn", "Быстрое предупреждение модерации", 0, mod_id)
        w_count = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
        cur_w = int(w_count["c"]) if w_count else 1
        if cur_w >= limit:
            until = datetime.now(timezone.utc) + timedelta(hours=WARN_MUTE_HOURS)
            try:
                await bot.restrict_chat_member(cid, uid, MUTE_OFF, until_date=until)
                await log_punish(cid, uid, "mute", f"автомут: {limit} предупреждений", WARN_MUTE_HOURS * 3600, 0)
                await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
            except Exception:
                pass
            await call.answer(f"⚠️ Варн выдан! Лимит ({limit}) достигнут — выдан автомут!", show_alert=True)
        else:
            await call.answer(f"⚠️ Варн выдан ({cur_w}/{limit})!")

    elif act == "b":
        if mod_rank < 3:
            return await call.answer("🔒 Выдача бана доступна с ранга 3+!", show_alert=True)
        try:
            await bot.ban_chat_member(cid, uid)
            await db.execute("INSERT OR REPLACE INTO bans (chat_id, user_id, reason, by_id, ts) VALUES (?,?,?,?,?)",
                            (cid, uid, "Быстрый бан модерации", mod_id, now))
            await log_punish(cid, uid, "ban", "Быстрый бан модерации", 0, mod_id)
            await call.answer("🔨 Пользователь заблокирован!", show_alert=True)
        except Exception as e:
            return await call.answer(f"Ошибка бана: {e}", show_alert=True)

    elif act == "uw":
        await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
        await lift_punish(cid, uid, "warn", mod_id)
        await call.answer("🧹 Предупреждения сняты!")

    elif act == "um":
        try:
            await bot.restrict_chat_member(cid, uid, MUTE_ON)
            await db.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (cid, uid))
            await lift_punish(cid, uid, "mute", mod_id)
            await call.answer("🔊 Мут снят!")
        except Exception as e:
            return await call.answer(f"Ошибка размута: {e}", show_alert=True)

    text, kb = await _render_user_dossier(cid, uid, bot)
    try:
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass


# ---------------- СТАТИСТИКА АДМИНИСТРАЦИИ (АКТИВ) ----------------
@router.message(Cmd("актив админов", "стафф актив", "модеры актив", "актив стаффа", "админы актив",
                    section=S_BAN, rank=2, group_only=True,
                    usage="актив админов", desc="Статистика работы администрации чата"))
async def cmd_staff_activity(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return

    cid = message.chat.id
    now = int(time.time())
    week_ago = now - (7 * 86400)

    staff_rows = await db.fetchall(
        "SELECT r.user_id, r.rank, u.first_name, u.username, u.nick, cs.last_seen, cs.messages "
        "FROM ranks r "
        "LEFT JOIN users u ON r.user_id = u.user_id "
        "LEFT JOIN chat_stats cs ON cs.chat_id = r.chat_id AND cs.user_id = r.user_id "
        "WHERE r.chat_id = ? AND r.rank > 0 "
        "ORDER BY r.rank DESC, cs.messages DESC",
        (cid,)
    )

    if not staff_rows:
        return await message.reply("📋 В этом чате ещё не назначены модераторы.")

    from core_registry import RANK_ICONS
    lines = [
        "🛡️ <b>СТАТИСТИКА И АКТИВНОСТЬ АДМИНИСТРАЦИИ (7 ДНЕЙ)</b>",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    ]

    for idx, s in enumerate(staff_rows, 1):
        uid = s["user_id"]
        rank = s["rank"]
        icon = RANK_ICONS.get(rank, "▫️")
        r_title = rank_name(rank)
        name = s["first_name"] or s["nick"] or (f"@{s['username']}" if s["username"] else str(uid))

        p_cnt = await db.fetchone(
            "SELECT COUNT(*) c FROM punishments WHERE chat_id=? AND by_id=? AND ts > ?",
            (cid, uid, week_ago)
        )
        actions = p_cnt["c"] if p_cnt else 0

        last_seen = s["last_seen"]
        if last_seen:
            days_ago = max(0, (now - last_seen) // 86400)
            seen_str = f"{days_ago} дн. назад" if days_ago > 0 else "сегодня"
        else:
            seen_str = "неизвестно"

        lines.append(
            f"<b>{idx}.</b> {icon} <b>{html.escape(name)}</b> [{r_title}]\n"
            f"   ⚖️ Наказаний выдано: <b>{actions}</b>\n"
            f"   💬 Сообщений: <b>{s['messages'] or 0}</b> | Был в сети: <i>{seen_str}</i>\n"
        )

    lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    lines.append("💡 <i>Учитываются муты, варны, баны и кики за последние 7 дней.</i>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)


# ---------------- ВСЕОБЩАЯ АМНИСТИЯ (РАЗБАН ВСЕХ) ----------------
@router.message(Cmd("амнистия", "разбан всех", "снять все баны", "разбанить всех",
                    section=S_BAN, rank=7, group_only=True,
                    usage="амнистия", desc="Разбанить всех заблокированных участников (ранг 7+)"))
async def cmd_amnesty(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 7):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='ban' AND active=1",
        (message.chat.id,)
    )
    unbanned = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
            unbanned += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='ban' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unbanned == 0 and not rows:
        return await message.reply("🕊 В этом чате нет активных банов в базе данных бота.")

    await message.reply(
        f"🕊 <b>ВСЕОБЩАЯ АМНИСТИЯ!</b>\n\n"
        f"👑 Решением руководства чата блокировки сняты.\n"
        f"👥 Разбанено участников: <b>{max(unbanned, len(rows))}</b>.\n"
        f"✨ Теперь они могут вернуться в чат по пригласительной ссылке."
    )


# ---------------- ВСЕОБЩИЙ РАЗМУТ (СНЯТЬ ВСЕ МУТЫ) ----------------
@router.message(Cmd("размут всех", "снять все муты", "размутить всех", "муты сброс",
                    section=S_BAN, rank=6, group_only=True,
                    usage="размут всех", desc="Снять мут со всех участников чата (ранг 6+)"))
async def cmd_unmute_all(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 6):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='mute' AND active=1",
        (message.chat.id,)
    )
    unmuted = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.restrict_chat_member(message.chat.id, uid, MUTE_ON)
            unmuted += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='mute' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unmuted == 0 and not rows:
        return await message.reply("🔊 В этом чате нет активных мутов в базе данных бота.")

    await message.reply(
        f"🔊 <b>ВСЕОБЩИЙ РАЗМУТ!</b>\n\n"
        f"🛡 Сняты ограничения на отправку сообщений.\n"
        f"👥 Размучено участников: <b>{max(unmuted, len(rows))}</b>."
    )


# ---------------- ИСТОРИЯ ВАРНОВ (ВАРНЛОГ) ----------------
@router.message(Cmd("варнлог", "варн лог", "история варнов", "список варнов",
                    section=S_BAN, rank=2, usage="варнлог {ссылка}",
                    desc="История предупреждений участника (ранг 2+)"))
async def cmd_user_warn_log(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")

    rows = await db.fetchall(
        "SELECT * FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC",
        (message.chat.id, uid)
    )
    if not rows:
        return await message.reply(f"📜 У {mention_id(uid, name)} нет активных предупреждений.")

    lines = [f"📜 <b>АКТИВНЫЕ ПРЕДУПРЕЖДЕНИЯ</b> {mention_id(uid, name)} (всего: {len(rows)}):\n"]
    for idx, r in enumerate(rows, 1):
        by_user = await db.get_user(r["by_id"]) if r.get("by_id") else None
        by_name = by_user["first_name"] if by_user else "Модератор"
        dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
        reason = html.escape(r.get("reason") or "Без причины")
        lines.append(f"<b>{idx}.</b> ⚠️ <i>{dt}</i> от {mention_id(r.get('by_id', 0), by_name)}\n   Причина: <i>{reason}</i>")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)


# ---------------- АНТИРЕЙД РЕЖИМ ----------------
@router.message(Cmd("антирейд", "+антирейд", "-антирейд", "антирейд вкл", "антирейд выкл", "антирейд статус",
                    section=S_BAN, rank=4, group_only=True,
                    usage="антирейд [вкл/выкл]", desc="Управление режимом защиты от рейдов"))
async def cmd_antiraid(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return

    cid = message.chat.id
    cmd_text = (message.text or "").strip().lower()
    a = (args or "").strip().lower()

    if cmd_text.startswith(("-антирейд", "антирейд выкл")) or a in {"выкл", "off", "0", "disable"}:
        await db.set_setting(cid, "antiraid", "0")
        return await message.reply("🛡️ <b>Режим «Антирейд» ВЫКЛЮЧЕН.</b>\nСтандартный режим работы чата восстановлен.")

    if cmd_text.startswith(("+антирейд", "антирейд вкл")) or a in {"вкл", "on", "1", "enable"}:
        await db.set_setting(cid, "antiraid", "1")
        return await message.reply(
            "🛡️ <b>Режим «Антирейд» ВКЛЮЧЕН!</b>\n\n"
            "🚨 Чат переведён в режим повышенной защиты.\n"
            "• Новые входы участников отслеживаются.\n"
            "• Спам-аккаунты и рейдеры блокируются мгновенно.\n\n"
            "<i>Отключить режим: <code>-антирейд</code> или <code>антирейд выкл</code></i>"
        )

    cur = await db.get_setting(cid, "antiraid", "0")
    status_str = "🟢 <b>АКТИВЕН (защита включена)</b>" if cur == "1" else "⚪️ <b>ОТКЛЮЧЕН (обычный режим)</b>"
    await message.reply(
        f"🛡️ <b>СИСТЕМА ЗАЩИТЫ ОТ РЕЙДОВ (АНТИРЕЙД)</b>\n\n"
        f"Текущий статус: {status_str}\n\n"
        f"• Включить: <code>+антирейд</code> или <code>антирейд вкл</code>\n"
        f"• Отключить: <code>-антирейд</code> или <code>антирейд выкл</code>"
    )


@router.message(Cmd("наказание", "инфо наказание", section=S_BAN, rank=6,
                    usage="наказание {номер}", desc="Детали наказания по номеру"))
async def cmd_punish_info(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    a = (args or "").strip().lstrip("#")
    if not a.isdigit():
        return await message.reply("Формат: <code>наказание 42</code>")
    r = await db.fetchone("SELECT * FROM punishments WHERE id=?", (int(a),))
    if not r:
        return await message.reply("Наказание с таким номером не найдено.")
    u = await db.get_user(r["user_id"])
    by = await db.get_user(r["by_id"]) if r["by_id"] else None
    by_str = mention_id(r["by_id"], by["first_name"]) if by else "Кузя"
    await message.reply(
        f"📋 <b>Наказание #{r['id']}</b>\n"
        f"Тип: <b>{KIND_NAMES.get(r['kind'], r['kind'])}</b>\n"
        f"👤 Кому: {mention_id(r['user_id'], u['first_name'])}\n"
        f"👮 Кем: {by_str}\n"
        f"📝 Причина: {html.escape(r['reason'] or '—')}\n"
        f"⏱ Срок: {human_period(r['seconds']) if r['seconds'] else 'навсегда/разовое'}\n"
        f"🕒 Выдано: {time.strftime('%d.%m.%Y %H:%M', time.localtime(r['ts']))}\n"
        f"Статус: {'🟢 активно' if r['active'] else '⚪️ снято'}")


@router.message(Cmd("статистика модерации", "стата модерации", section=S_BAN, rank=4,
                    usage="статистика модерации", desc="Кто сколько наказаний выдал"))
async def cmd_mod_stats(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    rows = await db.fetchall(
        "SELECT by_id, COUNT(*) c FROM punishments WHERE chat_id=? AND by_id<>0 "
        "GROUP BY by_id ORDER BY c DESC LIMIT 15", (message.chat.id,))
    if not rows:
        return await message.reply("Наказаний ещё не выдавали.")
    lines = []
    for i, r in enumerate(rows):
        u = await db.get_user(r["by_id"])
        det = await db.fetchall(
            "SELECT kind, COUNT(*) c FROM punishments WHERE chat_id=? AND by_id=? GROUP BY kind",
            (message.chat.id, r["by_id"]))
        d = " · ".join(f"{KIND_NAMES.get(x['kind'], x['kind'])}: {x['c']}" for x in det)
        lines.append(f"{i+1}. {mention_id(r['by_id'], u['first_name'])} — "
                     f"<b>{r['c']}</b>\n   <i>{d}</i>")
    await message.reply("📊 <b>Статистика модерации</b>\n\n" + "\n".join(lines))


@router.message(Cmd("причина обязательна", "требовать причину", section=S_BAN, rank=4,
                    usage="причина обязательна вкл|выкл",
                    desc="Требовать причину для наказаний"))
async def cmd_reason_req(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip().lower()
    if a in {"вкл", "on", "да"}:
        await db.set_setting(message.chat.id, "reason_required", "1")
        return await message.reply("✅ Причина для мута/бана/варна обязательна.")
    if a in {"выкл", "off", "нет"}:
        await db.set_setting(message.chat.id, "reason_required", "0")
        return await message.reply("⚠️ Причину теперь можно не указывать.")
    cur = await db.get_setting(message.chat.id, "reason_required", "1")
    await message.reply(f"Сейчас: <b>{'обязательна' if cur == '1' else 'необязательна'}</b>\n"
                        f"Изменить: <code>причина обязательна выкл</code>")


# ---------------- ЧИСТКА ----------------
@router.message(Cmd("удалить", "del", "уд", section=S_CLEAN, rank=1,
                    usage="удалить (реплаем)", desc="Удалить сообщение"))
async def cmd_del(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    if not message.reply_to_message:
        return await message.reply("Используйте реплаем на сообщение.")
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception as e:
        await message.reply(f"⚠️ {html.escape(str(e))}")


@router.message(Cmd("чистка", "очистить", "purge", section=S_CLEAN, rank=2,
                    usage="чистка {число}", desc="Удалить N последних сообщений"))
async def cmd_purge(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    n = int(args.strip()) if args.strip().isdigit() else 0
    if not n and not message.reply_to_message:
        return await message.reply("Укажите количество: <code>чистка 20</code> "
                                   "или ответьте на сообщение.")
    start = message.reply_to_message.message_id if message.reply_to_message \
        else message.message_id - n
    ids = list(range(start, message.message_id))
    deleted = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            await bot.delete_messages(message.chat.id, chunk)
            deleted += len(chunk)
        except Exception:
            for mid in chunk:
                try:
                    await bot.delete_message(message.chat.id, mid)
                    deleted += 1
                except Exception:
                    pass
    try:
        await message.delete()
    except Exception:
        pass
    sent = await message.answer(f"🧹 Удалено сообщений: <b>{deleted}</b>")
    async def _later_del():
        await asyncio.sleep(5)
        try:
            await sent.delete()
        except Exception:
            pass
    asyncio.create_task(_later_del())


@router.message(Cmd("неактив", "неактивные", "список неактива", "кто не актив", "молчуны",
                    "неактив чата", "неактивные участники", "неактив лист", "лист неактива",
                    section=S_CLEAN, rank=0,
                    usage="неактив [период]", desc="Список неактивных участников чата"))
async def cmd_inactive_list(message: Message, bot: Bot, args: str = "", **kw):
    from core_resolve import human_period, parse_period
    secs, _ = parse_period(args) if args else (0, "")
    secs = secs or 14 * 86400  # по умолчанию 14 дней
    border = int(time.time()) - secs

    rows = await db.fetchall(
        "SELECT s.user_id, s.last_seen, s.messages, u.username, u.first_name, u.nick "
        "FROM chat_stats s "
        "LEFT JOIN users u ON u.user_id=s.user_id "
        "WHERE s.chat_id=? AND (s.last_seen < ? OR s.last_seen = 0) "
        "ORDER BY s.last_seen ASC, s.messages ASC LIMIT 30",
        (message.chat.id, border))

    if not rows:
        return await message.reply(f"🟢 Неактивных участников (более {human_period(secs)}) не найдено!")

    now = int(time.time())
    lines = [f"💤 <b>Неактивные участники (не писали более {human_period(secs)}):</b>\n"]
    for idx, r in enumerate(rows, 1):
        nm = r["nick"] or r["first_name"] or (f"@{r['username']}" if r["username"] else f"ID:{r['user_id']}")
        if r["last_seen"]:
            days = max(1, (now - r["last_seen"]) // 86400)
            seen_str = f"{days} дн. назад"
        else:
            seen_str = "очень давно"
        lines.append(f"<b>{idx}.</b> {mention_id(r['user_id'], html.escape(nm))} — актив: <b>{seen_str}</b> (сообщений: {r['messages']})")

    total_cnt = await db.fetchone(
        "SELECT COUNT(*) c FROM chat_stats WHERE chat_id=? AND last_seen < ?",
        (message.chat.id, border))
    tot = total_cnt["c"] if total_cnt else len(rows)
    if tot > len(rows):
        lines.append(f"\n<i>…и ещё {tot - len(rows)} неактивных</i>")

    lines.append(f"\nВсего неактивных: <b>{tot}</b>")
    lines.append(f"💡 Исключить неактивных: <code>кик неактив {human_period(secs)}</code>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)


# ---------------- ВСЕОБЩАЯ АМНИСТИЯ (РАЗБАН ВСЕХ) ----------------
@router.message(Cmd("амнистия", "разбан всех", "снять все баны", "разбанить всех",
                    section=S_BAN, rank=7, group_only=True,
                    usage="амнистия", desc="Разбанить всех заблокированных участников (ранг 7+)"))
async def cmd_amnesty(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 7):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='ban' AND active=1",
        (message.chat.id,)
    )
    unbanned = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
            unbanned += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='ban' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unbanned == 0 and not rows:
        return await message.reply("🕊 В этом чате нет активных банов в базе данных бота.")

    await message.reply(
        f"🕊 <b>ВСЕОБЩАЯ АМНИСТИЯ!</b>\n\n"
        f"👑 Решением руководства чата блокировки сняты.\n"
        f"👥 Разбанено участников: <b>{max(unbanned, len(rows))}</b>.\n"
        f"✨ Теперь они могут вернуться в чат по пригласительной ссылке."
    )


# ---------------- ВСЕОБЩИЙ РАЗМУТ (СНЯТЬ ВСЕ МУТЫ) ----------------
@router.message(Cmd("размут всех", "снять все муты", "размутить всех", "муты сброс",
                    section=S_BAN, rank=6, group_only=True,
                    usage="размут всех", desc="Снять мут со всех участников чата (ранг 6+)"))
async def cmd_unmute_all(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 6):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='mute' AND active=1",
        (message.chat.id,)
    )
    unmuted = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.restrict_chat_member(message.chat.id, uid, MUTE_ON)
            unmuted += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='mute' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unmuted == 0 and not rows:
        return await message.reply("🔊 В этом чате нет активных мутов в базе данных бота.")

    await message.reply(
        f"🔊 <b>ВСЕОБЩИЙ РАЗМУТ!</b>\n\n"
        f"🛡 Сняты ограничения на отправку сообщений.\n"
        f"👥 Размучено участников: <b>{max(unmuted, len(rows))}</b>."
    )


# ---------------- ИСТОРИЯ ВАРНОВ (ВАРНЛОГ) ----------------
@router.message(Cmd("варнлог", "варн лог", "история варнов", "список варнов",
                    section=S_BAN, rank=2, usage="варнлог {ссылка}",
                    desc="История предупреждений участника (ранг 2+)"))
async def cmd_user_warn_log(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")

    rows = await db.fetchall(
        "SELECT * FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC",
        (message.chat.id, uid)
    )
    if not rows:
        return await message.reply(f"📜 У {mention_id(uid, name)} нет активных предупреждений.")

    lines = [f"📜 <b>АКТИВНЫЕ ПРЕДУПРЕЖДЕНИЯ</b> {mention_id(uid, name)} (всего: {len(rows)}):\n"]
    for idx, r in enumerate(rows, 1):
        by_user = await db.get_user(r["by_id"]) if r.get("by_id") else None
        by_name = by_user["first_name"] if by_user else "Модератор"
        dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
        reason = html.escape(r.get("reason") or "Без причины")
        lines.append(f"<b>{idx}.</b> ⚠️ <i>{dt}</i> от {mention_id(r.get('by_id', 0), by_name)}\n   Причина: <i>{reason}</i>")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)


@router.message(Cmd("варн неактив", "варн неактивным", "варн всех кто неактив", "варн неактива",
                    "преды неактив", "пред неактив", "предупреждения неактив",
                    section=S_BAN, rank=3, usage="варн неактив [период]",
                    desc="Выдать варн на 30 дней всем неактивным участникам (ранг 3+ / тех.админ)"))
async def cmd_warn_inactive(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    secs, _ = parse_period(args)
    secs = secs or 14 * 86400  # по умолчанию 14 дней
    border = int(time.time()) - secs
    rows = await db.fetchall(
        "SELECT user_id FROM chat_stats WHERE chat_id=? AND (last_seen < ? OR last_seen = 0)",
        (message.chat.id, border))
    if not rows:
        return await message.reply(f"🟢 Неактивных участников (более {human_period(secs)}) не найдено!")

    now = int(time.time())
    warn_duration = 30 * 86400  # 30 дней
    reason = f"Неактив в чате более {human_period(secs)}. Обжаловать можно у администрации в ЛС."

    limit = int(await db.get_setting(message.chat.id, "warn_limit", str(WARN_LIMIT)))
    warned = 0
    muted = 0

    for r in rows:
        uid = int(r["user_id"])
        if await get_rank(message.chat.id, uid) > 0:
            continue
        is_tg_admin = False
        try:
            m = await bot.get_chat_member(message.chat.id, uid)
            if m.status in {"creator", "administrator"}:
                is_tg_admin = True
        except Exception:
            pass
        if is_tg_admin:
            continue

        await db.execute(
            "INSERT INTO warns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
            (message.chat.id, uid, 0, reason, now))
        await log_punish(message.chat.id, uid, "warn", reason, warn_duration, 0)
        warned += 1

        w_count = await db.fetchone(
            "SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?",
            (message.chat.id, uid))
        if w_count and int(w_count["c"]) >= limit:
            until = datetime.now(timezone.utc) + timedelta(hours=WARN_MUTE_HOURS)
            try:
                await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
                await log_punish(message.chat.id, uid, "mute",
                                 f"автомут: {limit} предупреждений (неактив)", WARN_MUTE_HOURS * 3600, 0)
                await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
                muted += 1
            except Exception:
                pass

    if warned == 0:
        return await message.reply("Не найдено подходящих участников для выдачи варна за неактив.")

    mute_note = f"\n🔇 Автоматически замучено за превышение лимита варнов: <b>{muted}</b>" if muted else ""
    text = (
        f"⚠️ <b>Массовая выдача предупреждений за неактив завершена!</b>\n\n"
        f"👥 Предупреждения получили: <b>{warned}</b> участников\n"
        f"👮 Выдано от имени: <b>Кузя</b>\n"
        f"⏱ Срок действия варна: <b>30 дней</b>\n"
        f"📝 Причина: <i>Неактив в чате более {human_period(secs)}</i>{mute_note}\n\n"
        f"💬 <b>Обжаловать или снять предупреждение можно у администрации в ЛС.</b>"
    )
    await message.reply(text)


@router.message(Cmd("кик неактив", "чистка неактив", section=S_CLEAN, rank=6,
                    usage="кик неактив {период}", desc="Кик неактивных участников (ранг 6+)"))
async def cmd_kick_inactive(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    secs, _ = parse_period(args)
    secs = secs or 30 * 86400
    border = int(time.time()) - secs
    rows = await db.fetchall(
        "SELECT user_id FROM chat_stats WHERE chat_id=? AND last_seen < ?",
        (message.chat.id, border))
    if not rows:
        return await message.reply("Неактивных не найдено.")
    kicked = 0
    for r in rows[:50]:
        if await get_rank(message.chat.id, r["user_id"]) > 0:
            continue
        try:
            await bot.ban_chat_member(message.chat.id, r["user_id"])
            await bot.unban_chat_member(message.chat.id, r["user_id"])
            kicked += 1
        except Exception:
            continue
    await message.reply(f"🧹 Исключено неактивных (более {human_period(secs)}): <b>{kicked}</b>")


@router.message(Cmd("кик удаленных", "кик удалённых", "чистка удаленных", section=S_CLEAN,
                    rank=6, usage="кик удалённых", desc="Кик удалённых аккаунтов (ранг 6+)"))
async def cmd_kick_deleted(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 6):
        return
    rows = await db.fetchall("SELECT user_id FROM chat_stats WHERE chat_id=?", (message.chat.id,))
    kicked = 0
    for r in rows[:100]:
        try:
            m = await bot.get_chat_member(message.chat.id, r["user_id"])
            u = m.user
            if not u.first_name and not u.username:
                await bot.ban_chat_member(message.chat.id, u.id)
                await bot.unban_chat_member(message.chat.id, u.id)
                kicked += 1
        except Exception:
            continue
    await message.reply(f"🧹 Удалённых аккаунтов исключено: <b>{kicked}</b>")


# ══════════════════ УМНАЯ ЧИСТКА НЕАКТИВА (ИЗОЛИРОВАННАЯ) ══════════════════

async def _build_inactive_candidates_view(cid: int, days: int = 7) -> tuple[str, list[int], InlineKeyboardMarkup]:
    border = int(time.time()) - (days * 86400)
    # Выбираем СТРОГО участников текущей группы cid!
    rows = await db.fetchall(
        "SELECT cs.user_id, cs.messages, cs.last_seen, u.first_name, u.username "
        "FROM chat_stats cs "
        "LEFT JOIN users u ON cs.user_id = u.user_id "
        "WHERE cs.chat_id=? AND cs.last_seen < ? "
        "ORDER BY cs.last_seen ASC LIMIT 40",
        (cid, border)
    )

    voters = set()
    try:
        v_rows = await db.fetchall(
            "SELECT DISTINCT user_id FROM announcement_votes WHERE chat_id=? AND ts > ?",
            (cid, border)
        )
        for vr in v_rows:
            voters.add(vr["user_id"])
    except Exception:
        pass

    candidates = []
    now = int(time.time())
    for r in rows:
        uid = r["user_id"]
        if uid in voters:
            continue
        if await get_rank(cid, uid) > 0:
            continue
        days_silent = max(1, (now - r["last_seen"]) // 86400) if r["last_seen"] else days
        candidates.append({
            "uid": uid,
            "name": r["first_name"] or r["username"] or f"id{uid}",
            "username": f"@{r['username']}" if r["username"] else "",
            "days": days_silent,
            "msgs": r["messages"] or 0
        })

    count = len(candidates)
    short_cid = abs(cid) % 100000
    if count == 0:
        text = (
            f"🧹 ✨ <b>ПРОВЕРКА АКТИВА • ЧАТ #{short_cid}</b> ✨ 🧹\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Критерий: молчат более <b>{days} дн.</b> и не участвовали в перекличках.\n\n"
            f"🎉 <b>Неактивных участников не обнаружено!</b> Все в строю."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"cln_r:{cid}:{days}")]
        ])
        return text, [], kb

    lines = [
        f"🧹 ✨ <b>КАНДИДАТЫ НА ЧИСТКУ • ЧАТ #{short_cid}</b> ✨ 🧹",
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Критерий: молчат более <b>{days} дн.</b> и не голосовали в перекличках.",
        f"Найдено неактивных: <b>{count}</b> чел.\n"
    ]

    for i, c in enumerate(candidates[:20], 1):
        tag = f" ({c['username']})" if c['username'] else ""
        lines.append(f"<b>{i}.</b> {html.escape(c['name'])}{tag} — молчит <b>{c['days']} дн.</b> (смс: {c['msgs']})")

    if count > 20:
        lines.append(f"\n<i>... и ещё {count - 20} участников.</i>")

    lines.append("\n⚠️ <i>Чистка затронет ТОЛЬКО этот чат! Другие группы не будут затронуты.</i>")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👢 Исключить неактивных ({count})", callback_data=f"cln_k:{cid}:{days}")],
        [InlineKeyboardButton(text="🔄 Обновить список", callback_data=f"cln_r:{cid}:{days}")]
    ])
    return "\n".join(lines), [c["uid"] for c in candidates], kb


@router.message(Cmd("кто неактив", "неактив", "чистка кандидаты", "кандидаты на кик", "список неактива",
                    section=S_CLEAN, rank=3, group_only=True,
                    usage="кто неактив [дни=7]", desc="📋 Показать список неактивных участников чата"))
async def cmd_inactive_candidates(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    days = 7
    a = (args or "").strip()
    if a.isdigit() and 1 <= int(a) <= 180:
        days = int(a)
    elif "14" in a:
        days = 14
    elif "30" in a:
        days = 30

    text, _, kb = await _build_inactive_candidates_view(message.chat.id, days)
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("cln_r:"))
async def cb_clean_refresh(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[1])
    days = int(parts[2])
    from core_ranks import get_rank
    import config
    uid = call.from_user.id
    if not (uid == config.OWNER_ID or uid in config.ADMINS or await get_rank(cid, uid) >= 3):
        return await call.answer("🔒 Доступно только модераторам и админам чата!", show_alert=True)
    text, _, kb = await _build_inactive_candidates_view(cid, days)
    try:
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass
    await call.answer("Список обновлен!")


@router.callback_query(F.data.startswith("cln_k:"))
async def cb_clean_kick(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[1])
    days = int(parts[2])
    from core_ranks import get_rank
    import config
    uid = call.from_user.id
    if not (uid == config.OWNER_ID or uid in config.ADMINS or await get_rank(cid, uid) >= 4):
        return await call.answer("🔒 Исключать участников могут только администраторы чата (ранг 4+)!", show_alert=True)

    text, uids, _ = await _build_inactive_candidates_view(cid, days)
    if not uids:
        return await call.answer("Неактивных кандидатов не найдено!", show_alert=True)

    await call.answer("Начинаю исключение неактивных участников...")
    kicked = 0
    for user_to_kick in uids:
        try:
            await bot.ban_chat_member(cid, user_to_kick)
            await bot.unban_chat_member(cid, user_to_kick)
            kicked += 1
            await asyncio.sleep(0.08)
        except Exception:
            continue

    await call.message.edit_text(
        f"🧹 ✨ <b>ЧИСТКА НЕАКТИВА ЗАВЕРШЕНА!</b> ✨ 🧹\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 Исключено неактивных из этой группы: <b>{kicked}</b> чел.\n"
        f"👮 Администратор: {mention_id(call.from_user.id, call.from_user.first_name)}\n\n"
        f"<i>Беседа очищена от неактива и готова к новым победам!</i>"
    )


# ---------------- МЕДЛЕННЫЙ РЕЖИМ (SLOWMODE) ----------------
@router.message(Cmd("медленный режим", "медленный", "слоумод", "slowmode",
                    section=S_CLEAN, rank=3, group_only=True,
                    usage="медленный режим [10/30/60/выкл]", desc="Установить задержку отправки сообщений"))
async def cmd_slowmode(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return

    a = (args or "").strip().lower()
    if not a or a in ("статус", "инфо", "?"):
        try:
            chat = await bot.get_chat(message.chat.id)
            cur = getattr(chat, "slow_mode_delay", 0) or 0
            cur_str = f"<b>{cur} сек.</b>" if cur > 0 else "<b>выключен</b>"
            return await message.reply(
                f"⏱ <b>Медленный режим (Slowmode)</b>\n\n"
                f"Текущая задержка: {cur_str}\n\n"
                f"• Включить: <code>медленный режим 10</code> (10с, 30с, 60с, 300с)\n"
                f"• Отключить: <code>медленный режим выкл</code>"
            )
        except Exception as e:
            return await message.reply(f"⚠️ Ошибка получения статуса: {e}")

    if a in ("0", "выкл", "off", "disable", "нет"):
        try:
            await bot.set_chat_slow_mode_delay(message.chat.id, 0)
            return await message.reply("🟢 <b>Медленный режим отключен.</b> Участники могут писать без ограничений.")
        except Exception as e:
            return await message.reply(f"⚠️ Не удалось отключить медленный режим: {e}")

    secs = 0
    if a.isdigit():
        secs = int(a)
    else:
        from core_resolve import parse_period
        p_secs, _ = parse_period(a)
        secs = p_secs or 10

    valid_delays = [10, 30, 60, 300, 900, 21600]
    delay = min(valid_delays, key=lambda x: abs(x - secs))

    try:
        await bot.set_chat_slow_mode_delay(message.chat.id, delay)
        await message.reply(
            f"⏱ <b>Медленный режим установлен: {delay} сек.!</b>\n\n"
            f"Участники могут отправлять сообщения не чаще одного раза в {delay} секунд.\n"
            f"Отключить: <code>медленный режим выкл</code>"
        )
    except Exception as e:
        await message.reply(f"⚠️ Не удалось установить медленный режим: {e}\n(Проверьте права бота на изменение настроек группы)")


# ---------------- ТИХИЙ МУТ И ТИХИЙ БАН ----------------
@router.message(Cmd("тихий мут", "тмут", section=S_BAN, rank=1,
                    usage="тихий мут {ссылка} {время} {причина}",
                    desc="Замутить нарушителя с удалением его сообщения"))
async def cmd_silent_mute(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")
    err = await guard_target(message, bot, uid, "замутить")
    if err:
        return await message.reply(err)
    secs, reason = parse_period(rest)
    reason, forever = strip_forever(reason)
    if forever:
        secs = 0
    secs = secs or 1800
    reason = reason.strip() or "Нарушение порядка"

    actor_rank = await effective_rank(message, bot)
    if actor_rank == 1 and (secs == 0 or secs > 86400):
        return await message.reply(
            "⛔️ <b>Стажёр не может выдавать тихий мут дольше, чем на 24 часа!</b>\n"
            "Максимальный срок для стажёра — 24 часа (1 день)."
        )

    if not await check_anti_drain(message, bot, "тихий мут", action_type="mute_warn"):
        return

    now = int(time.time())
    until = (datetime.now(timezone.utc) + timedelta(seconds=secs)) if secs else None
    try:
        await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
    except Exception as e:
        return await message.reply(explain_error(e, "замутить"))

    await db.execute(
        "INSERT OR REPLACE INTO mutes (chat_id, user_id, reason, by_id, until, ts) VALUES (?,?,?,?,?,?)",
        (message.chat.id, uid, reason, message.from_user.id, (now + secs if secs else 0), now))
    await log_punish(message.chat.id, uid, "mute", reason, secs, message.from_user.id)

    if message.reply_to_message:
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    sent = await message.answer(f"🤫 <b>Тихий мут:</b> {mention_id(uid, name)} на {human_period(secs)}.")
    asyncio.create_task(_autodel_msg(sent, 7))


@router.message(Cmd("тихий бан", "тбан", section=S_BAN, rank=3,
                    usage="тихий бан {ссылка} {причина}",
                    desc="Заблокировать нарушителя с удалением его сообщения"))
async def cmd_silent_ban(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")
    err = await guard_target(message, bot, uid, "забанить")
    if err:
        return await message.reply(err)
    reason = rest.strip() or "Грубое нарушение"
    if not await check_anti_drain(message, bot, "тихий бан"):
        return

    try:
        await bot.ban_chat_member(message.chat.id, uid)
    except Exception as e:
        return await message.reply(explain_error(e, "забанить"))

    now = int(time.time())
    await db.execute(
        "INSERT OR REPLACE INTO bans (chat_id, user_id, reason, by_id, until, ts) VALUES (?,?,?,?,?,?)",
        (message.chat.id, uid, reason, message.from_user.id, 0, now))
    await log_punish(message.chat.id, uid, "ban", reason, 0, message.from_user.id)

    if message.reply_to_message:
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    sent = await message.answer(f"🤫 <b>Тихий бан:</b> {mention_id(uid, name)} заблокирован.")
    asyncio.create_task(_autodel_msg(sent, 7))


# ---------------- ОЧИСТКА ВСЕХ ВАРНОВ ----------------
@router.message(Cmd("снять все варны", "очистить варны", "сброс варнов", "варны очистить", "варны сброс",
                    section=S_BAN, rank=2, usage="снять все варны {ссылка}",
                    desc="Снять все предупреждения участнику (ранг 2+)"))
async def cmd_clear_all_warns(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")

    cnt_row = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?",
                                (message.chat.id, uid))
    count = cnt_row["c"] if cnt_row else 0
    if count == 0:
        return await message.reply(f"У {mention_id(uid, name)} нет активных предупреждений.")

    await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await lift_punish(message.chat.id, uid, "warn", message.from_user.id)
    await message.reply(f"🧹 Сняты все предупреждения (<b>{count} шт.</b>) с {mention_id(uid, name)}.")


# ---------------- ЖУРНАЛ НАКАЗАНИЙ (МОДЛОГ) ----------------
@router.message(Cmd("модлог", "журнал наказаний", "последние наказания", "лог наказаний", "мод лог",
                    section=S_BAN, rank=2, group_only=True,
                    usage="модлог [число]", desc="Последние действия модерации"))
async def cmd_recent_modlog(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return

    limit = 10
    a = (args or "").strip()
    if a.isdigit() and 1 <= int(a) <= 30:
        limit = int(a)

    rows = await db.fetchall(
        "SELECT * FROM punishments WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (message.chat.id, limit)
    )

    if not rows:
        return await message.reply("📋 В журнале модерации этого чата пока нет записей.")

    lines = [f"📋 <b>ПОСЛЕДНИЕ ДЕЙСТВИЯ МОДЕРАЦИИ ({len(rows)}):</b>\n"]
    for r in rows:
        target = await db.get_user(r["user_id"])
        t_name = target["first_name"] or str(r["user_id"])
        by = await db.get_user(r["by_id"]) if r["by_id"] else None
        b_name = by["first_name"] if by else "Кузя"

        k_emoji = KIND_EMOJI.get(r["kind"], "•")
        k_name = KIND_NAMES.get(r["kind"], r["kind"])
        dur = f" ({human_period(r['seconds'])})" if r["seconds"] else ""
        date = time.strftime("%d.%m %H:%M", time.localtime(r["ts"]))

        lines.append(
            f"{k_emoji} <b>#{r['id']} {k_name.upper()}{dur}</b> · <i>{date}</i>\n"
            f"   👤 Кому: {mention_id(r['user_id'], html.escape(t_name))}\n"
            f"   👮 Кто: {mention_id(r['by_id'], html.escape(b_name)) if r['by_id'] else 'Кузя'}\n"
            f"   📝 Причина: <i>{html.escape(r['reason'] or 'без причины')}</i>\n"
        )

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)


# ---------------- ВСЕОБЩАЯ АМНИСТИЯ (РАЗБАН ВСЕХ) ----------------
@router.message(Cmd("амнистия", "разбан всех", "снять все баны", "разбанить всех",
                    section=S_BAN, rank=7, group_only=True,
                    usage="амнистия", desc="Разбанить всех заблокированных участников (ранг 7+)"))
async def cmd_amnesty(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 7):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='ban' AND active=1",
        (message.chat.id,)
    )
    unbanned = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
            unbanned += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='ban' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unbanned == 0 and not rows:
        return await message.reply("🕊 В этом чате нет активных банов в базе данных бота.")

    await message.reply(
        f"🕊 <b>ВСЕОБЩАЯ АМНИСТИЯ!</b>\n\n"
        f"👑 Решением руководства чата блокировки сняты.\n"
        f"👥 Разбанено участников: <b>{max(unbanned, len(rows))}</b>.\n"
        f"✨ Теперь они могут вернуться в чат по пригласительной ссылке."
    )


# ---------------- ВСЕОБЩИЙ РАЗМУТ (СНЯТЬ ВСЕ МУТЫ) ----------------
@router.message(Cmd("размут всех", "снять все муты", "размутить всех", "муты сброс",
                    section=S_BAN, rank=6, group_only=True,
                    usage="размут всех", desc="Снять мут со всех участников чата (ранг 6+)"))
async def cmd_unmute_all(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 6):
        return

    rows = await db.fetchall(
        "SELECT DISTINCT user_id FROM punishments WHERE chat_id=? AND kind='mute' AND active=1",
        (message.chat.id,)
    )
    unmuted = 0
    now = int(time.time())
    actor_id = message.from_user.id if message.from_user else 0

    for r in rows:
        uid = r["user_id"]
        try:
            await bot.restrict_chat_member(message.chat.id, uid, MUTE_ON)
            unmuted += 1
        except Exception:
            pass

    await db.execute(
        "UPDATE punishments SET active=0, lifted_by=?, lifted_ts=? WHERE chat_id=? AND kind='mute' AND active=1",
        (actor_id, now, message.chat.id)
    )

    if unmuted == 0 and not rows:
        return await message.reply("🔊 В этом чате нет активных мутов в базе данных бота.")

    await message.reply(
        f"🔊 <b>ВСЕОБЩИЙ РАЗМУТ!</b>\n\n"
        f"🛡 Сняты ограничения на отправку сообщений.\n"
        f"👥 Размучено участников: <b>{max(unmuted, len(rows))}</b>."
    )


# ---------------- ИСТОРИЯ ВАРНОВ (ВАРНЛОГ) ----------------
@router.message(Cmd("варнлог", "варн лог", "история варнов", "список варнов",
                    section=S_BAN, rank=2, usage="варнлог {ссылка}",
                    desc="История предупреждений участника (ранг 2+)"))
async def cmd_user_warn_log(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")

    rows = await db.fetchall(
        "SELECT * FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC",
        (message.chat.id, uid)
    )
    if not rows:
        return await message.reply(f"📜 У {mention_id(uid, name)} нет активных предупреждений.")

    lines = [f"📜 <b>АКТИВНЫЕ ПРЕДУПРЕЖДЕНИЯ</b> {mention_id(uid, name)} (всего: {len(rows)}):\n"]
    for idx, r in enumerate(rows, 1):
        by_user = await db.get_user(r["by_id"]) if r.get("by_id") else None
        by_name = by_user["first_name"] if by_user else "Модератор"
        dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
        reason = html.escape(r.get("reason") or "Без причины")
        lines.append(f"<b>{idx}.</b> ⚠️ <i>{dt}</i> от {mention_id(r.get('by_id', 0), by_name)}\n   Причина: <i>{reason}</i>")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- СТАТУС АНТИ-СЛИВА БЕСЕДЫ ----------------
@router.message(Cmd("антислив", "анти слив", "лимиты состава", "лимиты",
                    section=S_BAN, rank=1, usage="антислив",
                    desc="Статус защиты чата от слива модераторами"))
async def cmd_anti_drain_status(message: Message, bot: Bot, **kw):
    now = time.time()
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    from core_registry import stars, rank_name
    my_status = f"{stars(me)} {rank_name(me)} (Ранг {me})" if me > 0 else "👤 Участник (Ранг 0)"

    ban_key = (chat_id, actor_id, "ban")
    mw_key = (chat_id, actor_id, "mute_warn")
    ban_history = [t for t in ANTI_DRAIN_ACTIONS.get(ban_key, []) if now - t < ANTI_DRAIN_WINDOW]
    mw_history = [t for t in ANTI_DRAIN_ACTIONS.get(mw_key, []) if now - t < ANTI_DRAIN_WINDOW]

    import config
    has_immunity = (me >= 6 or actor_id == config.OWNER_ID or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481))

    if has_immunity:
        cur_limits_str = "👑 <b>Ваши лимиты:</b> Полный иммунитет (Кики, Баны и Муты без ограничений)"
    elif me in RANK_DRAIN_LIMITS:
        lim = RANK_DRAIN_LIMITS[me]
        ban_max = lim["ban"]
        mw_max = lim["mute_warn"]
        ban_rem = max(0, ban_max - len(ban_history))
        mw_rem = max(0, mw_max - len(mw_history))
        ban_part = f"Баны: <b>{len(ban_history)}/{ban_max}</b> (осталось {ban_rem})" if ban_max > 0 else "Баны: ❌ <b>Запрещены</b>"
        mw_part = f"Муты/Варны: <b>{len(mw_history)}/{mw_max}</b> (осталось {mw_rem})"
        cur_limits_str = f"📊 <b>Ваш расход за 10 мин:</b>\n   • {ban_part}\n   • {mw_part}\n   • Кики: ❌ <b>Запрещены (доступны с 6 ранга)</b>"
    else:
        cur_limits_str = "ℹ️ Вы не состоите в администрации чата."

    text = (
        "🛡 <b>СИСТЕМА ЗАЩИТЫ ОТ СЛИВА БЕСЕДЫ (АНТИ-СЛИВ)</b>\n\n"
        "✅ <b>Статус:</b> Активна (защищает чат 24/7)\n"
        "⏱ <b>Окно контроля:</b> 10 минут\n"
        f"👮 <b>Ваш статус:</b> {my_status}\n"
        f"{cur_limits_str}\n\n"
        "📋 <b>ДИФФЕРЕНЦИРОВАННЫЕ ЛИМИТЫ ПО РАНГАМ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "▫️ <b>Ранг 1 (Стажёр):</b>\n"
        "   • Муты/Варны: <b>макс. 3 за 10 мин.</b> (мут макс. до 24 ч.)\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 2 (Мл. Модератор):</b>\n"
        "   • Муты/Варны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Баны и Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 3 (Ст. Модератор):</b>\n"
        "   • Баны: <b>макс. 3 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 4 (Гл. Модератор):</b>\n"
        "   • Баны: <b>макс. 5 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 10 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "▫️ <b>Ранг 5 (Мл. Админ):</b>\n"
        "   • Баны: <b>макс. 7 за 10 мин.</b>\n"
        "   • Муты/Варны: <b>макс. 15 за 10 мин.</b>\n"
        "   • Кики: ❌ <b>Запрещены</b>\n\n"
        "👑 <b>Ранги 6–10 (Ст. Админ, ГА, Техадмин, Зам, Владелец):</b>\n"
        "   • 🌟 <b>Полные права:</b> Кики, баны и любые наказания без ограничений\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>При превышении лимита или попытке несанкционированного действия бот мгновенно блокирует команду.</i>"
    )
    await message.reply(text)
