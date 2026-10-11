import asyncio
from datetime import datetime, timedelta, timezone
import html
import logging
import platform
import sys
import time

from aiogram import Bot, Router
from aiogram.types import Message

import db
from core_registry import REGISTRY, Cmd

log = logging.getLogger("moxxibot.botinfo")
router = Router(name="botinfo")
S = 32

START_TS = time.time()


def uptime_str() -> str:
    d = int(time.time() - START_TS)
    days, rem = divmod(d, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    if days:
        return f"{days} д {h} ч {m} мин"
    if h:
        return f"{h} ч {m} мин"
    if m:
        return f"{m} мин {sec} сек"
    return f"{sec} сек"


def ping_grade(ms: float) -> tuple[str, str]:
    """Оценка качества связи."""
    if ms < 150:
        return "🟢", "отличный"
    if ms < 400:
        return "🟡", "хороший"
    if ms < 900:
        return "🟠", "средний"
    return "🔴", "медленный"


async def measure_ping(bot: Bot) -> float:
    """Пинг до Telegram API в миллисекундах."""
    t0 = time.perf_counter()
    try:
        await bot.get_me()
    except Exception:
        return -1.0
    return (time.perf_counter() - t0) * 1000


async def bot_status_text(bot: Bot, message: Message | None = None) -> str:
    me = await bot.me()
    ms = await measure_ping(bot)
    icon, grade = ping_grade(ms) if ms >= 0 else ("🔴", "нет связи")

    ping_line = f"{ms:.0f} мс ({grade})" if ms >= 0 else "нет связи"

    if message and message.chat and message.chat.type in ("group", "supergroup"):
        cid = message.chat.id
        try:
            members_cnt = await bot.get_chat_member_count(cid)
        except Exception:
            row = await db.fetchone("SELECT COUNT(DISTINCT user_id) c FROM chat_stats WHERE chat_id=?", (cid,))
            members_cnt = row["c"] if row else 0

        row_msg = await db.fetchone("SELECT COALESCE(SUM(messages),0) c FROM chat_stats WHERE chat_id=?", (cid,))
        chat_msgs = row_msg["c"] if row_msg else 0

        return (
            f"🤖 <b>{html.escape(me.first_name)}</b>\n"
            f"@{me.username}\n\n"
            f"🟢 <b>Статус: онлайн</b>\n"
            f"{icon} Пинг: <b>{ping_line}</b>\n"
            f"⏱ Аптайм: <b>{uptime_str()}</b>\n\n"
            f"⚙️ Команд: <b>{len(REGISTRY)}</b>\n"
            f"👥 Участников в группе: <b>{members_cnt}</b>\n"
            f"✉️ Сообщений в группе: <b>{chat_msgs}</b>\n\n"
            f"🐍 Python {platform.python_version()}\n"
            f"📖 Все команды — <code>команды</code>")
    else:
        return (
            f"🤖 <b>{html.escape(me.first_name)}</b>\n"
            f"@{me.username}\n\n"
            f"🟢 <b>Статус: онлайн</b>\n"
            f"{icon} Пинг: <b>{ping_line}</b>\n"
            f"⏱ Аптайм: <b>{uptime_str()}</b>\n\n"
            f"⚙️ Команд: <b>{len(REGISTRY)}</b>\n\n"
            f"🐍 Python {platform.python_version()}\n"
            f"📖 Все команды — <code>команды</code>")


@router.message(Cmd("бот", "статус", "бот статус", "status", section=S,
                    usage="бот", desc="Статус бота: онлайн, пинг, аптайм"))
async def cmd_bot(message: Message, bot: Bot, **kw):
    await message.reply(await bot_status_text(bot, message), disable_web_page_preview=True)


@router.message(Cmd("чаты", "список чатов", "все чаты", "chats", section=S, rank=8, hidden=True,
                    usage="чаты", desc="Список всех групп бота (только для владельца)"))
async def cmd_chats(message: Message, bot: Bot, **kw):
    import config
    is_owner = bool(message.from_user and message.from_user.id == config.OWNER_ID)
    if not is_owner:
        return await message.reply("🔒 <b>Команда «чаты» доступна только владельцу/создателю бота!</b>")

    rows = await db.fetchall("SELECT chat_id, title, added_at FROM chats WHERE chat_id < 0 ORDER BY added_at DESC")
    stat_rows = await db.fetchall("SELECT DISTINCT chat_id FROM chat_stats WHERE chat_id < 0")

    chat_dict = {}
    for r in rows:
        chat_dict[r["chat_id"]] = {"title": r["title"] or f"Группа {r['chat_id']}", "added_at": r["added_at"]}
    for sr in stat_rows:
        cid = sr["chat_id"]
        if cid not in chat_dict:
            chat_dict[cid] = {"title": f"Группа {cid}", "added_at": 0}

    if not chat_dict:
        return await message.reply("💬 <b>Бот пока не добавлен ни в одну группу.</b>")

    lines = [f"💬 <b>Список всех подключённых групп ({len(chat_dict)}):</b>\n"]
    idx = 1
    for cid, info in chat_dict.items():
        title = info["title"]
        members_str = "—"
        msgs_str = "0"
        link_str = ""

        try:
            c_info = await bot.get_chat(cid)
            if c_info.title:
                title = c_info.title
            if c_info.username:
                link_str = f" • @{c_info.username}"
            elif c_info.invite_link:
                link_str = f" • <a href=\"{c_info.invite_link}\">ссылка</a>"
        except Exception:
            pass

        try:
            cnt = await bot.get_chat_member_count(cid)
            members_str = str(cnt)
        except Exception:
            pass

        row_msg = await db.fetchone("SELECT COALESCE(SUM(messages),0) c FROM chat_stats WHERE chat_id=?", (cid,))
        if row_msg and row_msg["c"]:
            msgs_str = str(row_msg["c"])

        lines.append(
            f"<b>{idx}. {html.escape(title)}</b>{link_str}\n"
            f"   • ID: <code>{cid}</code>\n"
            f"   • 👥 Участников: <b>{members_str}</b> | ✉️ СМС: <b>{msgs_str}</b>"
        )
        idx += 1

    text = "\n\n".join(lines)
    if len(text) > 3900:
        chunks = []
        cur_chunk = ""
        for item in lines:
            if len(cur_chunk) + len(item) > 3700:
                chunks.append(cur_chunk)
                cur_chunk = item + "\n\n"
            else:
                cur_chunk += item + "\n\n"
        if cur_chunk:
            chunks.append(cur_chunk)
        for ch in chunks:
            await message.reply(ch, disable_web_page_preview=True)
    else:
        await message.reply(text, disable_web_page_preview=True)


@router.message(Cmd("пинг", "ping", "задержка", section=S, usage="пинг",
                    desc="Проверить скорость отклика бота"))
async def cmd_ping(message: Message, bot: Bot, **kw):
    t0 = time.perf_counter()
    m = await message.reply("🏓 Измеряю…")
    reply_ms = (time.perf_counter() - t0) * 1000
    api_ms = await measure_ping(bot)
    icon, grade = ping_grade(api_ms) if api_ms >= 0 else ("🔴", "нет связи")
    try:
        await m.edit_text(
            f"🏓 <b>Понг!</b>\n\n"
            f"{icon} API Telegram: <b>{api_ms:.0f} мс</b> ({grade})\n"
            f"💬 Ответ в чат: <b>{reply_ms:.0f} мс</b>\n"
            f"⏱ Аптайм: <b>{uptime_str()}</b>")
    except Exception:
        pass


@router.message(Cmd("аптайм", "uptime", "время работы", section=S, usage="аптайм",
                    desc="Сколько бот работает без перезапуска"))
async def cmd_uptime(message: Message, **kw):
    await message.reply(
        f"⏱ Бот работает без перезапуска: <b>{uptime_str()}</b>\n"
        f"🕒 Запущен: {time.strftime('%d.%m.%Y %H:%M', time.localtime(START_TS))}")


UPDATE_TEXT = (
    "🚀 ✨ <b>MOXXI CLAN BOT ВНОВЬ В СТРОЮ!</b> ✨ 🚀\n"
    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    "✅ Технические работы завершены, бот успешно перезапущен и готов к работе!\n\n"
    "👑 <b>Новые возможности и улучшения:</b>\n"
    "• 🐉 <b>Рейдовые Боссы:</b> нокауты, контратаки, лечение союзников и <code>+тема босс</code>!\n"
    "• ⚔️ <b>PvP-Дуэли:</b> смертельные дуэли на ставки со снаряжением (<code>дуэль</code>)\n"
    "• 🎣 <b>Рыбалка и Крафт:</b> 8 видов рыбы, сундуки и верстак предметов (<code>рыбалка</code> / <code>крафт</code>)\n"
    "• 🏰 <b>База Клана:</b> прокачка Оружейной, Банка и Форпоста (<code>база клана</code>)\n"
    "• 📜 <b>Квесты и Ачивки:</b> ежедневные дейлики и 11+ наград (<code>квесты</code> / <code>достижения</code>)\n"
    "• ⭐️ <b>Репутация 2.0:</b> благодарности (<code>+реп</code>), титулы и рейтинг уважения\n"
    "• 🪄 <b>Автонастройка:</b> создание и привязка тем за 1 секунду (<code>автонастройка</code>)!\n\n"
    "✦ ══════════════════════════════ ✦\n"
    "🔥 <i>Приятного общения и ярких побед!</i>"
)


RESTART_MAINTENANCE_TEXT = (
    "🛠 ✨ <b>ТЕХНИЧЕСКИЕ РАБОТЫ И ПЕРЕЗАГРУЗКА</b> ✨ 🛠\n"
    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    "⚠️ Внимание! Бот уходит на быструю перезагрузку / техническое обслуживание.\n"
    "⏱ <b>Ориентировочное время:</b> ~1–2 минуты.\n"
    "📌 <i>Все балансы, статистика, рейды и ранги сохранены в безопасности!</i>\n\n"
    "🚀 Скоро вернемся в строй!"
)


@router.message(Cmd("обновление", "обновления", "что нового", "changelog", section=S,
                    usage="обновление", desc="Что нового в последней версии бота"))
async def cmd_updates(message: Message, **kw):
    await message.reply(UPDATE_TEXT, disable_web_page_preview=True)


async def announce_update_on_startup(bot: Bot) -> None:
    """Одноразово рассылает анонс обновления в чаты при первом запуске новой версии."""
    marker = "update_announced_moxxi_v2_launch"
    if await db.get_setting(0, marker, "") == "1":
        return
    await db.set_setting(0, marker, "1")

    from core_seed import MAIN_CHAT
    from h_chatset import get_sms_topic

    target_ids = set()
    target_ids.add(MAIN_CHAT)
    try:
        rows = await db.fetchall("SELECT chat_id FROM chats WHERE chat_id < 0")
        for r in rows:
            target_ids.add(r["chat_id"])
    except Exception:
        pass
    try:
        rows2 = await db.fetchall("SELECT DISTINCT chat_id FROM chat_stats WHERE chat_id < 0")
        for r in rows2:
            target_ids.add(r["chat_id"])
    except Exception:
        pass

    for cid in target_ids:
        sms_tid = await get_sms_topic(cid)
        sent = False
        if sms_tid:
            try:
                await bot.send_message(cid, UPDATE_TEXT, message_thread_id=sms_tid, disable_web_page_preview=True)
                sent = True
            except Exception:
                sent = False
        if not sent:
            try:
                await bot.send_message(cid, UPDATE_TEXT, disable_web_page_preview=True)
            except Exception:
                pass
        await asyncio.sleep(0.15)


async def broadcast_notice(bot: Bot, text: str) -> int:
    """Рассылает сообщение во все подключённые чаты в тему СМС / общения (или в основной чат)."""
    target_ids = set()
    from core_seed import MAIN_CHAT
    from h_chatset import get_sms_topic
    target_ids.add(MAIN_CHAT)
    try:
        rows = await db.fetchall("SELECT chat_id FROM chats WHERE chat_id < 0")
        for r in rows:
            target_ids.add(r["chat_id"])
    except Exception:
        pass
    try:
        rows2 = await db.fetchall("SELECT DISTINCT chat_id FROM chat_stats WHERE chat_id < 0")
        for r in rows2:
            target_ids.add(r["chat_id"])
    except Exception:
        pass

    sent = 0
    for cid in target_ids:
        tid = await get_sms_topic(cid)
        done = False
        if tid:
            try:
                await bot.send_message(cid, text, message_thread_id=tid, disable_web_page_preview=True)
                done = True
            except Exception:
                done = False
        if not done:
            try:
                await bot.send_message(cid, text, disable_web_page_preview=True)
                done = True
            except Exception:
                pass
        if done:
            sent += 1
        await asyncio.sleep(0.1)

    return sent


async def broadcast_restart(bot: Bot, reason: str = "Перезагрузка") -> int:
    """Рассылает оповещение о перезагрузке во все чаты в тему СМС / общения и делает бэкап."""
    sent = await broadcast_notice(bot, RESTART_MAINTENANCE_TEXT)

    import core_backup
    try:
        await core_backup.save(bot, note=reason)
    except Exception:
        pass

    return sent


async def auto_restart_worker(bot: Bot) -> None:
    """Фоновый воркер: оповещает за 30 минут и автоматически перезагружает бота каждые 12 часов (в 00:00 и 12:00 МСК)."""
    restart_hours = {0, 12}
    warn_hours = {23, 11}
    last_restarted_hour = -1
    last_warned_hour = -1

    while True:
        try:
            await asyncio.sleep(25)
            now = datetime.now(timezone(timedelta(hours=3)))  # МСК

            # 1. Оповещение за 30 минут до перезагрузки (в 23:30 и 11:30 МСК)
            if now.hour in warn_hours and now.minute == 30 and now.hour != last_warned_hour:
                if time.time() - START_TS >= 300:
                    last_warned_hour = now.hour
                    target_restart_time = "00:00" if now.hour == 23 else "12:00"
                    log.info("📢 Отправка оповещения о перезагрузке за 30 минут (до %s МСК)...", target_restart_time)
                    warn_text = (
                        "⏳ ✨ <b>СКОРО ПЛАНОВЫЙ ПЕРЕЗАПУСК БОТА</b> ✨ ⏳\n"
                        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                        f"⚠️ Внимание! Через <b>30 минут</b> (в <b>{target_restart_time} МСК</b>) бот будет кратковременно перезагружен для планового технического обслуживания.\n"
                        "⏱ <b>Время техработ:</b> ~1–2 минуты.\n"
                        "📌 <i>Все балансы, статистика, рейды и ранги сохраняются в безопасности!</i>\n\n"
                        "🔔 Пожалуйста, завершите важные дуэли, игры и операции заранее!"
                    )
                    await broadcast_notice(bot, warn_text)

            # 2. Непосредственная перезагрузка в 00:00 и 12:00 МСК
            if now.hour in restart_hours and now.minute == 0 and now.hour != last_restarted_hour:
                # Проверяем, что бот проработал хотя бы 5 минут, чтобы избежать перезапуска сразу при старте
                if time.time() - START_TS < 300:
                    continue
                last_restarted_hour = now.hour
                log.info("⏰ Плановая перезагрузка каждые 12 часов (%02d:00 МСК)...", now.hour)
                await broadcast_restart(bot, reason=f"Авто-перезагрузка 12ч ({now.hour:02d}:00 МСК)")
                log.info("Оповещения отправлены, бэкап сохранен. Завершение процесса для перезапуска...")
                await asyncio.sleep(1.0)
                import subprocess
                try:
                    subprocess.Popen([sys.executable] + sys.argv)
                except Exception:
                    pass
                sys.exit(0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("auto_restart_worker error: %s", e)


@router.message(Cmd("перезагрузка", "рестарт", "ребут", "техработы", "техраб", "выключение",
                    section=S, rank=8, hidden=True, usage="перезагрузка",
                    desc="👑 Оповестить чаты и перезагрузить бота (только создатель)"))
async def cmd_restart_bot(message: Message, bot: Bot, **kw):
    import config
    is_owner = bool(message.from_user and message.from_user.id == config.OWNER_ID)
    if not is_owner:
        return await message.reply("🔒 <b>Команда «перезагрузка» доступна исключительно владельцу/создателю бота!</b>")

    m = await message.reply("📢 <b>Отправляю оповещение о техработах во все беседы...</b>")
    sent = await broadcast_restart(bot, reason="Ручная перезагрузка владельцем")
    await m.edit_text(f"✅ Оповещение о перезагрузке отправлено в <b>{sent}</b> чат(ов)!\n💾 Резервная копия сохранена.\nБот уходит на перезагрузку...")
    
    def _do_restart():
        import subprocess
        try:
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception:
            pass
        sys.exit(0)

    asyncio.get_event_loop().call_later(2.0, _do_restart)



@router.message(Cmd("разослать обновление", "анонс обновления", section=S, rank=8, hidden=True,
                    usage="разослать обновление", desc="Разослать анонс обновления по всем чатам (только создатель)"))
async def cmd_broadcast_updates(message: Message, bot: Bot, **kw):
    import config
    is_owner = bool(message.from_user and message.from_user.id == config.OWNER_ID)
    if not is_owner:
        return await message.reply("🔒 <b>Команда «разослать обновление» доступна исключительно владельцу/создателю бота!</b>")

    m = await message.reply("📢 Начинаю рассылку обновления по чатам…")
    sent = 0
    target_ids = set()
    from core_seed import MAIN_CHAT
    from h_chatset import get_sms_topic
    target_ids.add(MAIN_CHAT)
    try:
        rows = await db.fetchall("SELECT chat_id FROM chats WHERE chat_id < 0")
        for r in rows:
            target_ids.add(r["chat_id"])
    except Exception:
        pass
    try:
        rows2 = await db.fetchall("SELECT DISTINCT chat_id FROM chat_stats WHERE chat_id < 0")
        for r in rows2:
            target_ids.add(r["chat_id"])
    except Exception:
        pass

    for cid in target_ids:
        tid = await get_sms_topic(cid)
        done = False
        if tid:
            try:
                await bot.send_message(cid, UPDATE_TEXT, message_thread_id=tid, disable_web_page_preview=True)
                done = True
            except Exception:
                done = False
        if not done:
            try:
                await bot.send_message(cid, UPDATE_TEXT, disable_web_page_preview=True)
                done = True
            except Exception:
                pass
        if done:
            sent += 1
        await asyncio.sleep(0.1)
    await m.edit_text(f"✅ Анонс обновления успешно отправлен в {sent} чат(ов)!")


# ---------------- ХРАНИЛИЩЕ И РЕЗЕРВНЫЕ КОПИИ ----------------
# Файл базы — личные данные участников. Доступ только у владельца бота.
async def _owner_only(message: Message) -> bool:
    from config import OWNER_ID
    if message.from_user and message.from_user.id == OWNER_ID:
        return True
    await message.reply(
        "🔒 Эта команда только для владельца бота.\n"
        "База данных содержит личные данные участников.")
    return False

@router.message(Cmd("хранилище", "база", "диск", "storage", section=S, rank=8, hidden=True,
                    usage="хранилище",
                    desc="Где лежит база и переживает ли она перезапуск"))
async def cmd_storage(message: Message, bot: Bot, **kw):
    if not await _owner_only(message):
        return
    import core_storage as storage
    import core_backup as backup

    txt = storage.report()
    chat = backup.backup_chat()
    txt += (f"\n\n💾 <b>Копии в Telegram</b>\n"
            f"Куда шлём: <code>{chat}</code>\n"
            f"Как часто: раз в <b>{backup.INTERVAL_MIN} мин</b>\n"
            f"Сделать сейчас: <code>бэкап</code>\n"
            f"Восстановить: <code>восстановить базу</code>")
    if not storage.INFO["persistent"]:
        txt += ("\n\n⚠️ Хостинг очищает папку при перезапуске. "
                "Данные держатся на копиях в Telegram — не удаляйте "
                "закреплённое сообщение в личке с ботом.")
    await message.reply(txt)


@router.message(Cmd("бэкап", "бекап", "сделать бэкап", "backup", section=S, rank=8, hidden=True,
                    usage="бэкап", desc="Сохранить копию базы в Telegram"))
async def cmd_backup(message: Message, bot: Bot, **kw):
    if not await _owner_only(message):
        return
    import core_backup as backup
    m = await message.reply("💾 Делаю копию базы…")
    ok = await backup.save(bot, "📥 копия по команде")
    try:
        await m.edit_text(
            "✅ Копия сохранена и закреплена в личке с ботом.\n"
            "После перезапуска бот поднимет из неё все настройки."
            if ok else
            "❌ Не вышло сохранить копию.\n"
            "Проверьте: бот должен уметь писать вам в личку — "
            "напишите ему <code>/start</code>.")
    except Exception:
        pass


@router.message(Cmd("восстановить базу", "восстановить настройки", "restore",
                    section=S, rank=8, hidden=True, usage="восстановить базу",
                    desc="Поднять базу из последней копии в Telegram"))
async def cmd_restore(message: Message, bot: Bot, **kw):
    if not await _owner_only(message):
        return
    import core_seed as seed
    try:
        await seed.apply()
    except Exception:
        pass
    await message.reply(
        "♻️ Базовые настройки чата возвращены "
        "(тема описаний, тема граммов, состав).\n\n"
        "Полное восстановление из копии происходит автоматически при "
        "запуске бота, если база пустая.\n"
        "Проверить состояние: <code>хранилище</code>")


# ---------------- РАСШИФРОВКА ГОЛОСОВЫХ ----------------
@router.message(Cmd("расшифровка", "голосовые в текст", "стт", "stt",
                    "распознавание речи", section=S, rank=4,
                    usage="расшифровка", desc="🎙 Голосовые и кружки в текст"))
async def cmd_stt(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 4):
        return
    import core_stt as stt
    a = (args or "").strip().lower()
    cid = message.chat.id

    if a in {"вкл", "on", "включить", "да"}:
        await db.set_setting(cid, "stt", "1")
        extra = ("" if stt.available() else
                 "\n\n⚠️ <i>Ключ не задан — напишите </i><code>расшифровка</code>"
                 "<i>, там инструкция.</i>")
        return await message.reply(
            f"🎙 Расшифровка голосовых: <b>включена</b>{extra}")

    if a in {"выкл", "off", "выключить", "нет"}:
        await db.set_setting(cid, "stt", "0")
        return await message.reply(
            "🎙 Расшифровка голосовых: <b>выключена</b> в этом чате.")

    txt = stt.status()
    if stt.available():
        on = await db.get_setting(cid, "stt", "1") == "1"
        txt += f"\n\nВ этом чате: <b>{'🟢 включена' if on else '🔴 выключена'}</b>"
    await message.reply(txt, disable_web_page_preview=True)
