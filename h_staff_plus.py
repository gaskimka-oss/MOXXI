"""Модуль расширенного управления персоналом:
3. Лог-канал модерации
11. Статистика активности модераторов (стафф стата)
12. Выговоры персоналу
13. Отпуск модератора
14. Настраиваемая норма модератора (с включением/выключением)
15. Админ-рация
16. Личное досье модератора
56. Еженедельный дайджест активности чата
"""
from __future__ import annotations

import html
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import Message

import db
from core_ranks import effective_rank, get_rank, rank_label, rank_name, require
from core_registry import Cmd, stars
from core_resolve import human_period, parse_period, resolve_target
from utils import mention_id

router = Router(name="staff_plus")


# ---------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------------
async def send_to_mod_log(bot: Bot, chat_id: int, text: str):
    """Отправляет событие в привязанный канал логов (если настроен)."""
    channel_id = await db.get_setting(chat_id, "log_channel", None)
    if not channel_id:
        return
    try:
        await bot.send_message(int(channel_id), text, disable_web_page_preview=True)
    except Exception:
        pass


# ---------------- 3. ЛОГ-КАНАЛ МОДЕРАЦИИ ----------------
@router.message(Cmd("лог канал", "канал логов", "логканал", rank=7,
                    usage="лог канал [@канал / id / выкл]", desc="📢 Привязать Telegram-канал для аудита модерации"))
async def cmd_log_channel(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 7):
        return
    a = (args or "").strip()
    if not a:
        cur = await db.get_setting(message.chat.id, "log_channel", None)
        if cur:
            return await message.reply(
                f"📢 <b>Привязанный лог-канал:</b> <code>{cur}</code>\n"
                f"Отвязать: <code>лог канал выкл</code>"
            )
        return await message.reply(
            "📢 <b>Канал логов не привязан.</b>\n\n"
            "Добавьте бота в ваш приватный канал администратором и отправьте:\n"
            "<code>лог канал @username_канала</code> или <code>лог канал -100123456789</code>"
        )

    if a.lower() in ("выкл", "off", "0", "удалить"):
        await db.set_setting(message.chat.id, "log_channel", "")
        return await message.reply("🟢 <b>Лог-канал отвязан.</b> Логирование в канал отключено.")

    target_channel = a
    if not target_channel.startswith("-100") and not target_channel.startswith("@"):
        target_channel = "@" + target_channel

    try:
        chat_obj = await bot.get_chat(target_channel)
        channel_id = str(chat_obj.id)
        await bot.send_message(chat_obj.id, f"✅ <b>Лог-канал успешно привязан к чату {html.escape(message.chat.title or '')}!</b>")
    except Exception as e:
        return await message.reply(f"⚠️ Не удалось подключиться к каналу: {e}\n(Убедитесь, что бот добавлен в канал администратором с правом публикации)")

    await db.set_setting(message.chat.id, "log_channel", channel_id)
    await message.reply(f"📢 <b>Лог-канал успешно подключен!</b>\nID: <code>{channel_id}</code> ({html.escape(chat_obj.title or '')})")


# ---------------- 11. СТАТИСТИКА АКТИВНОСТИ МОДЕРАТОРОВ ----------------
@router.message(Cmd("стафф стата", "актив админов", "актив модерации", "стафф статистика", rank=4,
                    usage="стафф стата", desc="📊 Статистика наказаний каждого модератора за 7 дней"))
async def cmd_staff_stats(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    staff_rows = await db.fetchall(
        "SELECT user_id, rank FROM staff WHERE chat_id=? AND rank > 0 ORDER BY rank DESC",
        (message.chat.id,)
    )
    if not staff_rows:
        return await message.reply("В чате нет назначенного персонала в базе данных.")

    week_ago = int(time.time()) - (7 * 86400)
    lines = ["📊 <b>АКТИВНОСТЬ МОДЕРАЦИИ (ЗА 7 ДНЕЙ):</b>\n"]

    for r in staff_rows:
        uid = r["user_id"]
        rk = r["rank"]
        u = await db.get_user(uid)
        name = u["first_name"] if u else f"ID {uid}"

        stats = await db.fetchone(
            "SELECT COUNT(*) as cnt, "
            "SUM(CASE WHEN kind='mute' THEN 1 ELSE 0 END) as mutes, "
            "SUM(CASE WHEN kind='warn' THEN 1 ELSE 0 END) as warns, "
            "SUM(CASE WHEN kind='ban' THEN 1 ELSE 0 END) as bans "
            "FROM punishments WHERE chat_id=? AND admin_id=? AND ts >= ?",
            (message.chat.id, uid, week_ago)
        )
        cnt = stats["cnt"] if stats and stats["cnt"] else 0
        mutes = stats["mutes"] if stats and stats["mutes"] else 0
        warns = stats["warns"] if stats and stats["warns"] else 0
        bans = stats["bans"] if stats and stats["bans"] else 0

        # Проверка отпуска
        vac = await db.fetchone("SELECT until_ts FROM staff_vacations WHERE chat_id=? AND user_id=? AND until_ts > ?",
                                (message.chat.id, uid, int(time.time())))
        vac_badge = " 🏖 <i>(в отпуске)</i>" if vac else ""

        lines.append(
            f"<b>{stars(rk)} {html.escape(name)}</b> [{rank_name(rk)}]{vac_badge}\n"
            f"   • Всего действий: <b>{cnt}</b> (🔇 {mutes} мут | ⚠️ {warns} варн | 🔨 {bans} бан)\n"
        )

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- 12. ВЫГОВОРЫ ПЕРСОНАЛУ ----------------
@router.message(Cmd("+выговор", "дать выговор", "выговор выдать", rank=6,
                    usage="+выговор {ссылка} {причина}", desc="⚠️ Выдать дисциплинарный выговор модератору"))
async def cmd_give_reprimand(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, reason = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: реплаем или @ником.")
    if uid == message.from_user.id:
        return await message.reply("⛔️ Нельзя выдать выговор самому себе.")
    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank == 0:
        return await message.reply(
            "ℹ️ Сварн (супер-варн) предназначен строго для персонала (ранги 1–9: от Стажёра до Заместителя).\n"
            "Для обычных участников используйте команду: <code>варн</code>."
        )
    me = await effective_rank(message, bot)
    if tgt_rank >= me and me < 10:
        return await message.reply("⛔️ Нельзя выдавать выговор равному или старшему по рангу.")

    reason = reason.strip() or "Неисполнение обязанностей"
    now = int(time.time())
    await db.execute(
        "INSERT INTO warns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
        (message.chat.id, uid, message.from_user.id, f"[ВЫГОВОР] {reason}", now)
    )

    row = await db.fetchone(
        "SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=? AND reason LIKE '[ВЫГОВОР]%'",
        (message.chat.id, uid)
    )
    c_warns = row["c"] if row else 1

    await message.reply(
        f"⚠️ <b>ВЫГОВОР ВЫДАН!</b>\n\n"
        f"👮 Модератор: {mention_id(uid, name)} (Ранг {tgt_rank})\n"
        f"📝 Причина: <i>{html.escape(reason)}</i>\n"
        f"📊 Всего выговоров: <b>{c_warns}/3</b>\n"
        f"👤 Выдал: {mention_id(message.from_user.id, message.from_user.first_name)}"
    )


@router.message(Cmd("снять выговор", "-выговор", "выговор снять", "удалить выговор", rank=6,
                    usage="снять выговор {ссылка}", desc="Снять дисциплинарный выговор модератору"))
async def cmd_remove_reprimand(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: <code>снять выговор @user</code> или реплаем.")
    tgt_rank = await get_rank(message.chat.id, uid)
    me = await effective_rank(message, bot)
    if tgt_rank >= me and me < 10:
        return await message.reply("⛔️ Нельзя снимать выговор равному или старшему по рангу.")

    row = await db.fetchone(
        "SELECT id FROM warns WHERE chat_id=? AND user_id=? AND reason LIKE '[ВЫГОВОР]%' ORDER BY id DESC LIMIT 1",
        (message.chat.id, uid)
    )
    if not row:
        return await message.reply(f"ℹ️ У {mention_id(uid, name)} нет активных выговоров.")

    await db.execute("DELETE FROM warns WHERE id=?", (row["id"],))

    c_row = await db.fetchone(
        "SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=? AND reason LIKE '[ВЫГОВОР]%'",
        (message.chat.id, uid)
    )
    left_c = c_row["c"] if c_row else 0

    await message.reply(
        f"✅ <b>ВЫГОВОР СНЯТ!</b>\n\n"
        f"👮 Модератор: {mention_id(uid, name)} (Ранг {tgt_rank})\n"
        f"📊 Оставшиеся выговоры: <b>{left_c}/3</b>\n"
        f"👤 Снял: {mention_id(message.from_user.id, message.from_user.first_name)}"
    )



# ---------------- 12.1 СУПЕР-ВАРНЫ (СВАРН ДЛЯ СОСТАВА 1-9 РАНГА) ----------------

async def _init_staff_tables():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_superwarns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            ts INTEGER
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS rank_action_cooldowns (
            chat_id INTEGER,
            rank INTEGER,
            action TEXT,
            cooldown_sec INTEGER,
            PRIMARY KEY (chat_id, rank, action)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_action_history (
            chat_id INTEGER,
            user_id INTEGER,
            action TEXT,
            last_ts INTEGER,
            PRIMARY KEY (chat_id, user_id, action)
        )
    """)


@router.message(Cmd("+сварн", "сварн", "супер варн", "суперварн", "swarn", "superwarn", "+суперварн",
                    rank=6, usage="сварн {ссылка} {причина}",
                    desc="⚡️ Выдать дисциплинарный супер-варн модератору (ранги 1–9)"))
async def cmd_give_superwarn(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, reason = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: реплаем или <code>сварн @username [причина]</code>.")
    if uid == message.from_user.id:
        return await message.reply("⛔️ Нельзя выдать супер-варн самому себе.")

    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank >= 10:
        return await message.reply("👑 <b>Лидеру чата нельзя выдать варн или сварн!</b>")
    if tgt_rank == 0:
        return await message.reply(
            "ℹ️ Сварн (супер-варн) предназначен строго для персонала (ранги 1–9: от Стажёра до Заместителя).\n"
            "Для обычных участников используйте команду: <code>варн</code>."
        )
    me = await effective_rank(message, bot)
    if tgt_rank >= me and me < 10:
        return await message.reply("⛔️ Нельзя выдавать супер-варн равному или старшему по рангу.")

    reason = reason.strip() or "Нарушение обязанностей модератора"
    await _init_staff_tables()
    now = int(time.time())

    await db.execute(
        "INSERT INTO staff_superwarns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
        (message.chat.id, uid, message.from_user.id, reason, now)
    )

    row = await db.fetchone(
        "SELECT COUNT(*) c FROM staff_superwarns WHERE chat_id=? AND user_id=?",
        (message.chat.id, uid)
    )
    c_warns = row["c"] if row else 1
    limit = 3

    if c_warns >= limit:
        # Автоматическое снятие с должности!
        from core_ranks import set_rank
        await set_rank(message.chat.id, uid, 0, by=message.from_user.id)
        await db.execute("DELETE FROM staff_superwarns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))

        demote_text = (
            f"🚨 <b>МОДЕРАТОР СНЯТ С ДОЛЖНОСТИ!</b>\n\n"
            f"👮 <b>Сотрудник:</b> {mention_id(uid, name)} [{rank_name(tgt_rank)}]\n"
            f"📝 <b>Причина 3-го сварна:</b> <i>{html.escape(reason)}</i>\n"
            f"📊 <b>Шкала нарушений:</b> [ 🟥 🟥 🟥 ] (3/3)\n\n"
            f"❌ <b>Лимит исчерпан!</b> Пользователь автоматически разжалован и исключён из состава администрации (ранг 0).\n"
            f"👤 <b>Действие зафиксировал:</b> {mention_id(message.from_user.id, message.from_user.first_name)}"
        )
        await message.reply(demote_text)
        await send_to_mod_log(bot, message.chat.id, demote_text)
        return

    scale = " ".join("🟥" if i < c_warns else "⬜️" for i in range(limit))
    warn_text = (
        f"⚡️ <b>СУПЕР-ВАРН ВЫДАН!</b>\n\n"
        f"👮 <b>Модератор:</b> {mention_id(uid, name)} ({stars(tgt_rank)} {rank_name(tgt_rank)}, ранг {tgt_rank})\n"
        f"📝 <b>Причина:</b> <i>{html.escape(reason)}</i>\n"
        f"📊 <b>Шкала:</b> [ {scale} ] (<b>{c_warns}/{limit}</b>)\n"
        f"👤 <b>Выдал:</b> {mention_id(message.from_user.id, message.from_user.first_name)}\n\n"
        f"⚠️ <i>При получении 3/3 супер-варнов следует автоматическое снятие с должности!</i>"
    )
    await message.reply(warn_text)
    await send_to_mod_log(bot, message.chat.id, warn_text)


@router.message(Cmd("-сварн", "снять сварн", "снять супер варн", "снять суперварн", "-суперварн", "unswarn",
                    rank=6, usage="снять сварн {ссылка}", desc="Снять супер-варн с модератора"))
async def cmd_remove_superwarn(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: <code>снять сварн @user</code> или реплаем.")

    tgt_rank = await get_rank(message.chat.id, uid)
    me = await effective_rank(message, bot)
    if tgt_rank >= me and me < 10:
        return await message.reply("⛔️ Нельзя снимать супер-варн равному или старшему по рангу.")

    await _init_staff_tables()
    row = await db.fetchone(
        "SELECT id FROM staff_superwarns WHERE chat_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
        (message.chat.id, uid)
    )
    if not row:
        return await message.reply(f"ℹ️ У {mention_id(uid, name)} нет активных супер-варнов.")

    await db.execute("DELETE FROM staff_superwarns WHERE id=?", (row["id"],))

    c_row = await db.fetchone(
        "SELECT COUNT(*) c FROM staff_superwarns WHERE chat_id=? AND user_id=?",
        (message.chat.id, uid)
    )
    left_c = c_row["c"] if c_row else 0
    limit = 3
    scale = " ".join("🟥" if i < left_c else "⬜️" for i in range(limit))

    msg_text = (
        f"✅ <b>СУПЕР-ВАРН СНЯТ!</b>\n\n"
        f"👮 <b>Модератор:</b> {mention_id(uid, name)} ({stars(tgt_rank)} {rank_name(tgt_rank)})\n"
        f"📊 <b>Осталось супер-варнов:</b> [ {scale} ] (<b>{left_c}/{limit}</b>)\n"
        f"👤 <b>Снял:</b> {mention_id(message.from_user.id, message.from_user.first_name)}"
    )
    await message.reply(msg_text)
    await send_to_mod_log(bot, message.chat.id, msg_text)


@router.message(Cmd("сварны", "суперварны", "список сварнов", "сварн лист", "сварнлист",
                    rank=1, usage="сварны [{ссылка}]", desc="Список активных супер-варнов персонала"))
async def cmd_superwarns_list(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    await _init_staff_tables()
    uid, name, _ = await resolve_target(message, args, bot)

    if uid:
        tgt_rank = await get_rank(message.chat.id, uid)
        rows = await db.fetchall(
            "SELECT * FROM staff_superwarns WHERE chat_id=? AND user_id=? ORDER BY id ASC",
            (message.chat.id, uid)
        )
        if not rows:
            return await message.reply(f"🌟 У {mention_id(uid, name)} нет активных супер-варнов!")

        limit = 3
        count = len(rows)
        scale = " ".join("🟥" if i < count else "⬜️" for i in range(limit))

        lines = [
            f"⚡️ <b>СУПЕР-ВАРНЫ МОДЕРАТОРА:</b>\n"
            f"👤 {mention_id(uid, name)} [{rank_name(tgt_rank)}]\n"
            f"📊 Шкала: [ {scale} ] (<b>{count}/{limit}</b>)\n"
        ]
        for idx, r in enumerate(rows, 1):
            admin_u = await db.get_user(r["admin_id"])
            admin_name = admin_u["first_name"] if admin_u else f"ID {r['admin_id']}"
            dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
            lines.append(f"{idx}. <b>Причина:</b> <i>{html.escape(r['reason'])}</i>\n   👤 Выдал: {mention_id(r['admin_id'], admin_name)} ({dt})")

        return await message.reply("\n".join(lines))

    # Общий список по всему чату
    rows = await db.fetchall(
        "SELECT user_id, COUNT(*) c FROM staff_superwarns WHERE chat_id=? GROUP BY user_id ORDER BY c DESC",
        (message.chat.id,)
    )
    if not rows:
        return await message.reply(
            "🌟 <b>В этом чате у состава нет активных супер-варнов!</b>\n"
            "Все модераторы работают безупречно."
        )

    lines = ["⚡️ <b>СПИСОК АКТИВНЫХ СУПЕР-ВАРНОВ СОСТАВА:</b>\n"]
    for r in rows:
        u_id = r["user_id"]
        c = r["c"]
        u = await db.get_user(u_id)
        u_name = u["first_name"] if u else f"ID {u_id}"
        rk = await get_rank(message.chat.id, u_id)
        scale = " ".join("🟥" if i < c else "⬜️" for i in range(3))
        lines.append(f"• <b>{mention_id(u_id, u_name)}</b> [{rank_name(rk)}]: [ {scale} ] (<b>{c}/3</b>)")

    lines.append("\n💡 <i>Подробнее по конкретному модератору: <code>сварны @user</code></i>")
    await message.reply("\n".join(lines))


@router.message(Cmd("мои сварны", "мой сварн", rank=1, usage="мои сварны", desc="Проверить свои супер-варны"))
async def cmd_my_superwarns(message: Message, bot: Bot, **kw):
    await _init_staff_tables()
    uid = message.from_user.id
    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank == 0:
        return await message.reply("Вы не состоите в составе администрации этого чата.")

    rows = await db.fetchall(
        "SELECT * FROM staff_superwarns WHERE chat_id=? AND user_id=? ORDER BY id ASC",
        (message.chat.id, uid)
    )
    if not rows:
        return await message.reply("🌟 <b>У вас нет активных супер-варнов!</b> Спасибо за безупречную службу!")

    count = len(rows)
    scale = " ".join("🟥" if i < count else "⬜️" for i in range(3))
    lines = [
        f"⚡️ <b>ВАШИ СУПЕР-ВАРНЫ:</b>\n"
        f"📊 Шкала: [ {scale} ] (<b>{count}/3</b>)\n"
    ]
    for idx, r in enumerate(rows, 1):
        dt = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
        lines.append(f"{idx}. <b>Причина:</b> <i>{html.escape(r['reason'])}</i> ({dt})")

    lines.append("\n⚠️ <i>Будьте внимательны: при 3/3 супер-варнов происходит автоматическое снятие с должности!</i>")
    await message.reply("\n".join(lines))


# ---------------- 12.2 КУЛДАУНЫ НАКАЗАНИЙ ПО РАНГАМ (КДКИК, КДМУТ, КДБАН) ----------------

RANK_NAMES_MAP = {
    "1": 1, "стажер": 1, "стажёр": 1,
    "2": 2, "мл модер": 2, "мл модератор": 2, "младший модератор": 2,
    "3": 3, "ст модер": 3, "ст модератор": 3, "старший модератор": 3,
    "4": 4, "гл модер": 4, "гл модератор": 4, "главный модератор": 4,
    "5": 5, "мл админ": 5, "мл администратор": 5, "младший админ": 5,
    "6": 6, "ст админ": 6, "ст администратор": 6, "старший админ": 6,
    "7": 7, "гл админ": 7, "гл администратор": 7, "главный админ": 7,
    "8": 8, "тех": 8, "тех админ": 8, "техник": 8, "технический администратор": 8,
    "9": 9, "зам": 9, "заместитель": 9,
}


def parse_cooldown_args(args: str) -> tuple[int | None, int | None, str | None]:
    parts = (args or "").strip().split()
    if not parts:
        return None, None, "Укажите ранг и время. Пример: <code>кдкик 1 1м</code>"

    raw_rank = parts[0].lower()
    target_rank = int(raw_rank) if raw_rank.isdigit() else RANK_NAMES_MAP.get(raw_rank)

    if target_rank is None or target_rank < 1 or target_rank > 9:
        return None, None, "⚠️ Ранг должен быть числом от <b>1</b> (Стажёр) до <b>9</b> (Заместитель)."

    if len(parts) < 2:
        return target_rank, None, "Укажите время кулдауна. Пример: <code>1м</code>, <code>30с</code>, <code>2ч</code> или <code>0</code> (выкл)."

    raw_time = parts[1].lower()
    if raw_time in ("0", "выкл", "off", "откл", "нет"):
        return target_rank, 0, None

    import re
    m = re.match(r"^(\d+)([сsсмчhhdд]?)$", raw_time)
    if not m:
        return None, None, "⚠️ Неверный формат времени! Используйте: <code>30с</code> (секунды), <code>1м</code> (минуты), <code>2ч</code> (часы), <code>1д</code> (дни) или <code>0</code> (выкл)."

    val = int(m.group(1))
    unit = m.group(2)

    if unit in ("с", "s"):
        sec = val
    elif unit in ("м", "m"):
        sec = val * 60
    elif unit in ("ч", "h"):
        sec = val * 3600
    elif unit in ("д", "d"):
        sec = val * 86400
    else:
        # Если число без суффикса (например "кдкик 1 1"), считаем как минуты:
        sec = val * 60

    if sec > 30 * 86400:
        return None, None, "⚠️ Кулдаун не может превышать 30 дней."

    return target_rank, sec, None


async def set_rank_cooldown(chat_id: int, rank: int, action: str, sec: int) -> None:
    await _init_staff_tables()
    if sec <= 0:
        await db.execute(
            "DELETE FROM rank_action_cooldowns WHERE chat_id=? AND rank=? AND action=?",
            (chat_id, rank, action)
        )
    else:
        await db.execute(
            "INSERT INTO rank_action_cooldowns (chat_id, rank, action, cooldown_sec) VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, rank, action) DO UPDATE SET cooldown_sec=excluded.cooldown_sec",
            (chat_id, rank, action, sec)
        )


async def get_rank_cooldown(chat_id: int, rank: int, action: str) -> int:
    await _init_staff_tables()
    row = await db.fetchone(
        "SELECT cooldown_sec FROM rank_action_cooldowns WHERE chat_id=? AND rank=? AND action=?",
        (chat_id, rank, action)
    )
    return int(row["cooldown_sec"]) if row and row["cooldown_sec"] else 0


async def get_all_rank_cooldowns(chat_id: int) -> list[dict]:
    await _init_staff_tables()
    return await db.fetchall(
        "SELECT rank, action, cooldown_sec FROM rank_action_cooldowns WHERE chat_id=? AND cooldown_sec > 0 ORDER BY rank ASC, action ASC",
        (chat_id,)
    )


async def check_and_apply_rank_cooldown(message: Message, bot: Bot, action: str) -> tuple[bool, int, int]:
    if not message.from_user or not message.chat or message.chat.type not in ("group", "supergroup"):
        return True, 0, 0

    actor_id = message.from_user.id
    chat_id = message.chat.id

    import config
    if config.is_bot_owner(actor_id) or actor_id in config.ADMINS or actor_id in (8412527198, 8297844640, 8036974481):
        return True, 0, 0

    me = await effective_rank(message, bot)
    if me >= 10:
        return True, 0, 0

    cd_sec = await get_rank_cooldown(chat_id, me, action)
    if cd_sec <= 0:
        return True, 0, 0

    await _init_staff_tables()
    row = await db.fetchone(
        "SELECT last_ts FROM staff_action_history WHERE chat_id=? AND user_id=? AND action=?",
        (chat_id, actor_id, action)
    )
    last_ts = int(row["last_ts"]) if row and row["last_ts"] else 0
    now = int(time.time())
    elapsed = now - last_ts

    if elapsed < cd_sec:
        rem_sec = cd_sec - elapsed
        return False, rem_sec, cd_sec

    return True, 0, cd_sec


async def record_rank_action(chat_id: int, user_id: int, action: str) -> None:
    await _init_staff_tables()
    now = int(time.time())
    await db.execute(
        "INSERT INTO staff_action_history (chat_id, user_id, action, last_ts) VALUES (?,?,?,?) "
        "ON CONFLICT(chat_id, user_id, action) DO UPDATE SET last_ts=excluded.last_ts",
        (chat_id, user_id, action, now)
    )


async def _handle_set_cd(message: Message, bot: Bot, action_key: str, action_title: str, args: str):
    if not await require(message, bot, 7):
        return
    rank, sec, err = parse_cooldown_args(args)
    if err:
        return await message.reply(err)

    await set_rank_cooldown(message.chat.id, rank, action_key, sec)

    if sec == 0:
        return await message.reply(
            f"🟢 <b>Кулдаун на «{action_title}» для ранга {rank} ({rank_name(rank)}) ОТКЛЮЧЁН.</b>"
        )

    await message.reply(
        f"⏱ <b>КУЛДАУН НА «{action_title.upper()}» УСТАНОВЛЕН!</b>\n\n"
        f"👮 <b>Должность:</b> {stars(rank)} {rank_name(rank)} (Ранг {rank})\n"
        f"⏳ <b>Интервал между действиями:</b> <b>{human_period(sec)}</b>\n\n"
        f"🔒 <i>Теперь модераторы ранга {rank} обязаны выжидать {human_period(sec)} перед каждым использованием команды «{action_title}».</i>"
    )


@router.message(Cmd("кдкик", "кд кик", "кд_кик", rank=7,
                    usage="кдкик [ранг] [время]", desc="⏱ Установить кулдаун на кик для ранга (1-9)"))
async def cmd_cd_kick(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_set_cd(message, bot, "kick", "кик", args)


@router.message(Cmd("кдмут", "кд мут", "кд_мут", rank=7,
                    usage="кдмут [ранг] [время]", desc="⏱ Установить кулдаун на мут для ранга (1-9)"))
async def cmd_cd_mute(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_set_cd(message, bot, "mute", "мут", args)


@router.message(Cmd("кдбан", "кд бан", "кд_бан", rank=7,
                    usage="кдбан [ранг] [время]", desc="⏱ Установить кулдаун на бан для ранга (1-9)"))
async def cmd_cd_ban(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_set_cd(message, bot, "ban", "бан", args)


@router.message(Cmd("кдварн", "кд варн", "кд_варн", rank=7,
                    usage="кдварн [ранг] [время]", desc="⏱ Установить кулдаун на варн для ранга (1-9)"))
async def cmd_cd_warn(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_set_cd(message, bot, "warn", "варн", args)


@router.message(Cmd("кд", "кд команд", "кд наказаний", "кд список", "кд лист", "кд инфо",
                    rank=1, usage="кд [действие] [ранг] [время]",
                    desc="⏱ Таблица кулдаунов модерации по рангам"))
async def cmd_cd_general(message: Message, bot: Bot, args: str = "", **kw):
    parts = (args or "").strip().split()
    action_map = {
        "кик": "kick", "kick": "kick",
        "мут": "mute", "mute": "mute",
        "бан": "ban", "ban": "ban",
        "варн": "warn", "warn": "warn",
    }

    if parts and parts[0].lower() in action_map:
        act_key = action_map[parts[0].lower()]
        rest_args = " ".join(parts[1:])
        return await _handle_set_cd(message, bot, act_key, parts[0].lower(), rest_args)

    if parts and parts[0].lower() not in ("список", "лист", "инфо", "помощь", "хелп", ""):
        # Случайное слово, не относящееся к КД
        return

    # Отображаем текущую таблицу кулдаунов
    all_cds = await get_all_rank_cooldowns(message.chat.id)
    cd_by_rank: dict[int, dict[str, int]] = {}
    for r in all_cds:
        cd_by_rank.setdefault(r["rank"], {})[r["action"]] = r["cooldown_sec"]

    lines = [
        f"⏱ <b>ТАБЛИЦА КУЛДАУНОВ НАКАЗАНИЙ ПО РАНГАМ</b>\n"
        f"💬 Чат: <b>{html.escape(message.chat.title or '')}</b>\n"
    ]

    has_any = False
    for rk in range(1, 10):
        m = cd_by_rank.get(rk, {})
        if not m:
            continue
        has_any = True
        act_parts = []
        if "mute" in m:
            act_parts.append(f"🔇 Мут: <b>{human_period(m['mute'])}</b>")
        if "kick" in m:
            act_parts.append(f"👢 Кик: <b>{human_period(m['kick'])}</b>")
        if "ban" in m:
            act_parts.append(f"🔨 Бан: <b>{human_period(m['ban'])}</b>")
        if "warn" in m:
            act_parts.append(f"⚠️ Варн: <b>{human_period(m['warn'])}</b>")

        lines.append(f"• <b>[{rk}] {rank_name(rk)}:</b> " + " | ".join(act_parts))

    if not has_any:
        lines.append("<i>Кулдауны на наказания ещё не настроены (действуют стандартные лимиты анти-слива).</i>\n")

    lines.append(
        "\n⚙️ <b>Команды настройки (для Главного админа / Лидера):</b>\n"
        "• <code>кдкик 1 1м</code> — кик для Стажёра (1 минута)\n"
        "• <code>кдмут 1 30с</code> — мут для Стажёра (30 секунд)\n"
        "• <code>кдбан 3 2ч</code> — бан для Ст. Модератора (2 часа)\n"
        "• <code>кдкик 1 0</code> — отключить КД на кик\n"
        "<i>Суффиксы времени: <b>с</b> (секунды), <b>м</b> (минуты), <b>ч</b> (часы), <b>д</b> (дни).</i>"
    )

    await message.reply("\n".join(lines))



# ---------------- 13. ОТПУСК МОДЕРАТОРА ----------------
@router.message(Cmd("отпуск", "в отпуск", rank=6,
                    usage="отпуск {ссылка} [срок]", desc="🏖 Отправить модератора в отпуск"))
async def cmd_set_vacation(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: реплаем или @ником.")
    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank == 0:
        return await message.reply(
            "ℹ️ Сварн (супер-варн) предназначен строго для персонала (ранги 1–9: от Стажёра до Заместителя).\n"
            "Для обычных участников используйте команду: <code>варн</code>."
        )
    if tgt_rank == 0:
        return await message.reply(
            "ℹ️ Сварн (супер-варн) предназначен строго для персонала (ранги 1–9: от Стажёра до Заместителя).\n"
            "Для обычных участников используйте команду: <code>варн</code>."
        )
