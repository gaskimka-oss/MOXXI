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
        return await message.reply("Этот пользователь не состоит в составе администрации чата.")
    if tgt_rank >= 10:
        return await message.reply("👑 Владельцу чата нельзя выдать выговор.")
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
        return await message.reply("Пользователь не состоит в модерации чата.")

    sec, reason = parse_period(rest)
    sec = sec or 7 * 86400  # по умолчанию неделя
    reason = reason.strip() or "Плановый отпуск"
    now = int(time.time())
    until = now + sec

    await db.execute(
        "INSERT INTO staff_vacations (chat_id, user_id, until_ts, reason) VALUES (?,?,?,?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET until_ts=excluded.until_ts, reason=excluded.reason",
        (message.chat.id, uid, until, reason)
    )

    await message.reply(
        f"🏖 <b>МОДЕРАТОР ОТПРАВЛЕН В ОТПУСК!</b>\n\n"
        f"👮 {mention_id(uid, name)} [{rank_name(tgt_rank)}]\n"
        f"⏱ Срок: <b>{human_period(sec)}</b> (до {time.strftime('%d.%m.%Y', time.localtime(until))})\n"
        f"📝 Причина: <i>{html.escape(reason)}</i>\n\n"
        f"<i>Во время отпуска модератор освобождён от выполнения нормы.</i>"
    )


@router.message(Cmd("снять отпуск", "отпуск снять", rank=6,
                    usage="снять отпуск {ссылка}", desc="Вернуть модератора из отпуска"))
async def cmd_remove_vacation(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: реплаем или @ником.")

    await db.execute("DELETE FROM staff_vacations WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await message.reply(f"✅ {mention_id(uid, name)} <b>отозван из отпуска</b> и вернулся к обязанностям.")


# ---------------- 14. НАСТРАИВАЕМАЯ НОРМА МОДЕРАТОРА ----------------
@router.message(Cmd("норма", "модер норма", "норма модераторов", rank=6,
                    usage="норма [число / вкл / выкл]", desc="📝 Настройка недельной нормы для модерации"))
async def cmd_staff_norm(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 6):
        return
    a = (args or "").strip().lower()
    row = await db.fetchone("SELECT * FROM staff_norms WHERE chat_id=?", (message.chat.id,))
    cur_enabled = row["enabled"] if row else 0
    cur_quota = row["quota"] if row else 5

    if a in ("вкл", "on", "1"):
        await db.execute(
            "INSERT INTO staff_norms (chat_id, enabled, quota) VALUES (?, 1, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET enabled=1",
            (message.chat.id, cur_quota)
        )
        return await message.reply(f"📝 <b>Система нормы ВКЛЮЧЕНА!</b> Текущая норма: <b>{cur_quota} наказаний в неделю</b>.")
    elif a in ("выкл", "off", "0"):
        await db.execute(
            "INSERT INTO staff_norms (chat_id, enabled, quota) VALUES (?, 0, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET enabled=0",
            (message.chat.id, cur_quota)
        )
        return await message.reply("🟢 <b>Система нормы ОТКЛЮЧЕНА.</b>")
    elif a.isdigit():
        val = int(a)
        if val < 1 or val > 100:
            return await message.reply("Укажите число от 1 до 100.")
        await db.execute(
            "INSERT INTO staff_norms (chat_id, enabled, quota) VALUES (?, 1, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET quota=?, enabled=1",
            (message.chat.id, val, val)
        )
        return await message.reply(f"✅ <b>Норма модератора установлена: {val} наказаний в неделю!</b> Система автоматически активирована.")

    st = "🟢 Включена" if cur_enabled else "🔴 Выключена"
    await message.reply(
        f"📝 <b>НОРМА МОДЕРАЦИИ</b>\n\n"
        f"• Статус: <b>{st}</b>\n"
        f"• Требование: <b>{cur_quota} наказаний / неделю</b>\n\n"
        f"Управление:\n"
        f"• <code>норма 10</code> — задать норму 10 действий\n"
        f"• <code>норма вкл</code> / <code>норма выкл</code>\n"
        f"• <code>проверка нормы</code> — отчет по составу"
    )


@router.message(Cmd("проверка нормы", "отчет нормы", rank=5,
                    usage="проверка нормы", desc="Показать выполнение нормы модераторами"))
async def cmd_check_norms(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    norm_row = await db.fetchone("SELECT * FROM staff_norms WHERE chat_id=?", (message.chat.id,))
    quota = norm_row["quota"] if norm_row else 5
    week_ago = int(time.time()) - (7 * 86400)

    staff_rows = await db.fetchall(
        "SELECT user_id, rank FROM staff WHERE chat_id=? AND rank BETWEEN 1 AND 5 ORDER BY rank DESC",
        (message.chat.id,)
    )
    if not staff_rows:
        return await message.reply("В чате нет модераторов (1–5 ранга).")

    lines = [f"📋 <b>ОТЧЁТ ВЫПОЛНЕНИЯ НОРМЫ (Минимум: {quota} действ./нед):</b>\n"]
    for r in staff_rows:
        uid = r["user_id"]
        rk = r["rank"]
        u = await db.get_user(uid)
        name = u["first_name"] if u else f"ID {uid}"

        # Проверка отпуска
        vac = await db.fetchone("SELECT until_ts FROM staff_vacations WHERE chat_id=? AND user_id=? AND until_ts > ?",
                                (message.chat.id, uid, int(time.time())))
        if vac:
            lines.append(f"🏖 <b>{mention_id(uid, name)}</b> [{rank_name(rk)}] — <i>В отпуске</i>")
            continue

        cnt_row = await db.fetchone(
            "SELECT COUNT(*) c FROM punishments WHERE chat_id=? AND admin_id=? AND ts >= ?",
            (message.chat.id, uid, week_ago)
        )
        c = cnt_row["c"] if cnt_row else 0
        status = "✅ Выполнена" if c >= quota else f"❌ Не выполнена ({c}/{quota})"
        lines.append(f"• <b>{mention_id(uid, name)}</b> [{rank_name(rk)}]: <b>{c}/{quota}</b> — {status}")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


async def _autodel(msg, delay: int = 4):
    try:
        import asyncio
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ---------------- 15. АДМИН-РАЦИЯ ----------------
@router.message(Cmd("рация", "а", "a", "!а", "!a", rank=1,
                    usage="!а [сообщение]", desc="📻 Быстрое секретное сообщение составу модерации"))
async def cmd_admin_radio(message: Message, bot: Bot, args: str = "", **kw):
    cmd_name = kw.get("cmd_name", "")
    had_prefix = kw.get("had_prefix", False)
    if cmd_name in ("а", "a") and not had_prefix:
        return
    if not await require(message, bot, 1):
        return
    txt = (args or "").strip()
    if not txt:
        return await message.reply("Введите сообщение для рации: <code>!а Требуется помощь в чате!</code>")

    # Сразу удаляем сообщение модератора из общего чата, чтобы обычные игроки его не видели
    try:
        await message.delete()
    except Exception:
        pass

    staff = await db.fetchall(
        "SELECT DISTINCT user_id FROM ranks WHERE chat_id=? AND rank > 0 "
        "UNION SELECT DISTINCT user_id FROM staff WHERE chat_id=? AND rank > 0",
        (message.chat.id, message.chat.id)
    )
    sender_name = message.from_user.first_name if message.from_user else "Модератор"
    me_rank = await effective_rank(message, bot)

    msg_text = (
        f"📻 <b>[РАЦИЯ МОДЕРАЦИИ]</b>\n"
        f"💬 Чат: <b>{html.escape(message.chat.title or '')}</b>\n"
        f"👮 От: {mention_id(message.from_user.id, sender_name)} [{rank_name(me_rank)}]\n\n"
        f"📢 <i>{html.escape(txt)}</i>"
    )

    delivered = 0

    # 1. Отправляем в привязанный админ-чат клана (если есть)
    admin_group = await db.fetchone("SELECT chat_id FROM clan_groups WHERE role='admin'")
    if admin_group and admin_group["chat_id"] != message.chat.id:
        try:
            await bot.send_message(admin_group["chat_id"], msg_text)
            delivered += 1
        except Exception:
            pass

    # 2. Отправляем в лог-канал (если настроен)
    await send_to_mod_log(bot, message.chat.id, msg_text)

    # 3. Отправляем модераторам в ЛС
    for s in staff:
        if s["user_id"] == message.from_user.id:
            continue
        try:
            await bot.send_message(s["user_id"], msg_text)
            delivered += 1
        except Exception:
            pass

    try:
        conf = await message.answer(f"📻 Сообщение передано в админ-рацию (доставлено: <b>{delivered}</b>).")
        import asyncio
        asyncio.create_task(_autodel(conf, 4))
    except Exception:
        pass


# ---------------- 16. ЛИЧНОЕ ДОСЬЕ МОДЕРАТОРА ----------------
@router.message(Cmd("досье", "досье модератора", rank=3,
                    usage="досье {ссылка}", desc="🎯 Полное досье модератора со всей статистикой"))
async def cmd_mod_dossier(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите модератора: реплаем или @ником.")

    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank == 0:
        return await message.reply(f"{mention_id(uid, name)} не является модератором чата.")

    st_row = await db.fetchone("SELECT ts FROM staff WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    appointed_ts = st_row["ts"] if st_row else 0
    appointed_date = time.strftime("%d.%m.%Y", time.localtime(appointed_ts)) if appointed_ts else "Неизвестно"

    all_punish = await db.fetchone(
        "SELECT COUNT(*) total, "
        "SUM(CASE WHEN kind='mute' THEN 1 ELSE 0 END) mutes, "
        "SUM(CASE WHEN kind='warn' THEN 1 ELSE 0 END) warns, "
        "SUM(CASE WHEN kind='ban' THEN 1 ELSE 0 END) bans "
        "FROM punishments WHERE chat_id=? AND admin_id=?",
        (message.chat.id, uid)
    )
    tot = all_punish["total"] if all_punish and all_punish["total"] else 0
    m = all_punish["mutes"] if all_punish and all_punish["mutes"] else 0
    w = all_punish["warns"] if all_punish and all_punish["warns"] else 0
    b = all_punish["bans"] if all_punish and all_punish["bans"] else 0

    vac = await db.fetchone("SELECT until_ts FROM staff_vacations WHERE chat_id=? AND user_id=? AND until_ts > ?",
                            (message.chat.id, uid, int(time.time())))
    vac_status = f"🏖 В отпуске до {time.strftime('%d.%m.%Y', time.localtime(vac['until_ts']))}" if vac else "🟢 На посту"

    warns_cnt = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    wc = warns_cnt["c"] if warns_cnt else 0

    text = (
        f"🎯 <b>ЛИЧНОЕ ДОСЬЕ МОДЕРАТОРА</b>\n\n"
        f"👤 <b>Сотрудник:</b> {mention_id(uid, name)}\n"
        f"🎖 <b>Должность:</b> {stars(tgt_rank)} {rank_name(tgt_rank)} (Ранг {tgt_rank})\n"
        f"📅 <b>Дата назначения:</b> {appointed_date}\n"
        f"📌 <b>Статус:</b> {vac_status}\n"
        f"⚠️ <b>Дисциплинарные выговоры:</b> {wc}/3\n\n"
        f"📊 <b>СТАТИСТИКА НАКАЗАНИЙ ЗА ВСЁ ВРЕМЯ:</b>\n"
        f"• Всего действий: <b>{tot}</b>\n"
        f"• Выдано мутов: <b>{m}</b>\n"
        f"• Выдано варнов: <b>{w}</b>\n"
        f"• Выдано банов: <b>{b}</b>"
    )
    await message.reply(text)


# ---------------- 56. ЕЖЕНЕДЕЛЬНЫЙ ДАЙДЖЕСТ АКТИВНОСТИ ----------------
@router.message(Cmd("дайджест недели", "дайджест", "итоги недели", rank=5,
                    usage="дайджест недели", desc="📋 Еженедельный отчет по активности чата"))
async def cmd_weekly_digest(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    week_ago = int(time.time()) - (7 * 86400)

    # 1. Топ болтунов
    top_speakers = await db.fetchall(
        "SELECT user_id, messages FROM chat_stats WHERE chat_id=? ORDER BY messages DESC LIMIT 3",
        (message.chat.id,)
    )
    # 2. Самый активный модератор
    best_mod = await db.fetchone(
        "SELECT admin_id, COUNT(*) c FROM punishments WHERE chat_id=? AND ts >= ? GROUP BY admin_id ORDER BY c DESC LIMIT 1",
        (message.chat.id, week_ago)
    )

    lines = [
        f"📰 <b>ДАЙДЖЕСТ ИТОГОВ НЕДЕЛИ ДЛЯ {html.escape(message.chat.title or '')}</b>\n",
        "🏆 <b>ТОП-3 САМЫХ АКТИВНЫХ УЧАСТНИКА:</b>"
    ]
    medals = ["🥇", "🥈", "🥉"]
    for idx, sp in enumerate(top_speakers):
        u = await db.get_user(sp["user_id"])
        u_name = u["first_name"] if u else f"ID {sp['user_id']}"
        lines.append(f"{medals[idx]} {mention_id(sp['user_id'], u_name)} — <b>{sp['messages']}</b> сообщ.")

    if best_mod and best_mod["admin_id"]:
        b_u = await db.get_user(best_mod["admin_id"])
        b_name = b_u["first_name"] if b_u else "Модератор"
        lines.append(f"\n👮 <b>Герой недели среди модераторов:</b>\n🌟 {mention_id(best_mod['admin_id'], b_name)} — <b>{best_mod['c']}</b> пресечённых нарушений!")

    lines.append("\n🎉 Спасибо всем за общение и поддержание порядка в беседе!")
    await message.reply("\n".join(lines))
