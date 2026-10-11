"""Разделы 2 и 5: баны, муты, предупреждения, списки, чистка чата.

Все наказания требуют причину (и срок для мута/бана), пишутся в журнал
punishments и защищают Лидера клана (7 ранг) от любого воздействия.
"""
from __future__ import annotations

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
from core_punish import (KIND_NAMES, check_reason, explain_error, guard_target,
                         lift_punish, log_punish, render_history, render_list,
                         strip_forever)
from core_ranks import effective_rank, get_rank, rank_label, require, set_rank
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
        if had_prefix or not in_group:
            return await message.reply(usage_hint("mute"))
        return
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
        if had_prefix or not in_group:
            return await message.reply(usage_hint("ban"))
        return
    err = await guard_target(message, bot, uid, "забанить")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    reason, _ = strip_forever(reason)
    reason = reason.strip()
    if not reason:
        if had_prefix or not in_group:
            return await message.reply(usage_hint("ban"))
        return
    if not await check_reason(message, "ban", reason, 0):
        return

    try:
        await bot.ban_chat_member(message.chat.id, uid)
    except Exception as e:
        return await message.reply(explain_error(e, "забанить"))
    await members.remember_member(message.chat.id, uid, "kicked", False)
    # Очищаем анкету, описание и ник забаненного игрока
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


@router.message(Cmd("кик", "кикнуть", "выгнать", "kick", section=S_BAN, rank=2,
                    usage="кик {ссылка} {причина}", desc="Исключить из чата"))
async def cmd_kick(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not await require(message, bot, 2):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        if had_prefix or not in_group:
            return await message.reply(usage_hint("kick"))
        return
    err = await guard_target(message, bot, uid, "кикнуть")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    if not reason:
        if had_prefix or not in_group:
            return await message.reply(usage_hint("kick"))
        return
    if not await check_reason(message, "kick", reason):
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
@router.message(Cmd("варн", "пред", "предупреждение", "warn", section=S_BAN, rank=2,
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
        if had_prefix or not in_group:
            return await message.reply(usage_hint("warn"))
        return
    err = await guard_target(message, bot, uid, "предупредить")
    if err:
        return await message.reply(err)
    reason = rest.strip()
    if not reason:
        if had_prefix or not in_group:
            return await message.reply(usage_hint("warn"))
        return
    if not await check_reason(message, "warn", reason):
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


# ---------------- ИСТОРИЯ (для техадмина) ----------------
@router.message(Cmd("история", "история наказаний", "досье", "инфо о наказаниях",
                    section=S_BAN, rank=6, usage="история {ссылка}",
                    desc="Полная история наказаний (техадмин)"))
async def cmd_history(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем, @ником или id.")
    await message.reply(await render_history(message.chat.id, uid, name),
                        disable_web_page_preview=True)


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
    await message.answer(f"🧹 Удалено сообщений: <b>{deleted}</b>")


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


@router.message(Cmd("кик неактив", "чистка неактив", section=S_CLEAN, rank=4,
                    usage="кик неактив {период}", desc="Кик неактивных участников"))
async def cmd_kick_inactive(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
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
                    rank=4, usage="кик удалённых", desc="Кик удалённых аккаунтов"))
async def cmd_kick_deleted(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
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
