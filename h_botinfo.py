from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import html
import logging
import platform
import sys
import time

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

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
        await asyncio.wait_for(bot.get_me(), timeout=2.5)
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
            members_cnt = await asyncio.wait_for(bot.get_chat_member_count(cid), timeout=2.0)
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


@router.message(Cmd("бот", "мокси", "статус", "бот статус", "status", section=S,
                    usage="бот", desc="Статус бота: онлайн, пинг, аптайм"))
async def cmd_bot(message: Message, bot: Bot, args: str = "", had_prefix: bool = False, **kw):
    args_clean = (args or "").strip().lower()
    in_group = getattr(message.chat, "type", "") in {"group", "supergroup"}
    # В беседах без префикса принимаем только строгое "бот" или "статус", а не фразы вроде "бот норм или не"
    if in_group and not had_prefix and args_clean:
        return
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


UPDATE_PART_1 = (
    "🚀 🌟 <b>ГЛОБАЛЬНЫЙ РЕЛИЗ MOXXI 3.0 MULTIPLATFORM!</b> 🌟 🚀\n"
    "✦ ══ • ⊰ ⚡️ 🎮 🎰 💎 👑 🐉 🏢 📱 ⊱ • ══ ✦\n\n"
    "🔥 <b>Свершилось! MOXXI 3.0 официально открыт и стал МУЛЬТИПЛАТФОРМЕННЫМ!</b>\n"
    "<i>Теперь легендарный бот доступен одновременно на 4 крупнейших платформах с единой мощью, играми и экономикой!</i>\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🌐 <b>1. MOXXI ТЕПЕРЬ НА ВСЕХ ПЛАТФОРМАХ:</b>\n"
    "• ✈️ <b>Telegram:</b> @moxxichat_bot\n"
    "• 🟦 <b>ВКонтакте:</b> https://vk.me/club243066051 (ЛС и беседы)\n"
    "• 🟣 <b>Discord:</b> https://discord.com/oauth2/authorize?client_id=1568910980002619402&permissions=8&scope=bot%20applications.commands\n"
    "• 🟢 <b>MAX:</b> https://max.ru/se14948893_bot (поддержка каналов и групп)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "👑 <b>2. ИЕРАРХИЯ ВЛАСТИ И РАНГИ (1–10):</b>\n"
    "• 10 должностных ступеней: от <code>[1] Стажёр</code> до <code>[10] Владелец чата</code> со звёздами!\n"
    "• <code>состав</code> — полный табель действующей администрации беседы.\n"
    "• <code>сварн @юзер</code> — супер-варны для персонала (при 3/3 автоматическое снятие с должности).\n"
    "• <code>кдкик</code>, <code>кдмут</code>, <code>кдбан</code> — гибкая настройка кулдаунов модерации.\n"
    "• Команды <code>чек @юзер</code> и <code>досье @юзер</code> — карточка игрока, варны и репутация.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🎰 <b>3. КАЗИНО 3.0 И АЗАРТНЫЙ МИР:</b>\n"
    "• 🚀 <b>Краш (Ракета):</b> Растущий множитель до <b>x35.0</b>! Успей катапультироваться по кнопке <code>[💰 ЗАБРАТЬ КУШ]</code> до взрыва! (<code>краш [ставка]</code>)\n"
    "• 🃏 <b>Блэкджек (21 очко):</b> Карточная битва против дилера Мокси с кнопками <code>[Еще]</code> и <code>[Стоп]</code>! (<code>21 [ставка]</code>)\n"
    "• 🎡 <b>Европейская Рулетка:</b> Ставки на красное, черное, чет, нечет и точные числа с выплатой <b>до x36</b>!\n"
    "• 🎯 <b>Спортивные дуэли Dice:</b> <code>дартс</code> (до x3.0), <code>боулинг</code> со страйком (x3.0), <code>футбол</code> (пенальти x2.0) и <code>баскетбол</code> (x2.2)!\n"
    "• 🔐 <b>Сейф беседы:</b> Подбирайте код от 1 до 100 и срывайте накопительный джекпот чата! (<code>сейф [код]</code>)\n\n"
    "👉 <i>Нажмите кнопку ниже для перехода ко 2-й части (Бизнесы, Кланы, Рейд-боссы, Промокод)!</i>"
)

UPDATE_PART_2 = (
    "🚀 🌟 <b>ГЛОБАЛЬНЫЙ РЕЛИЗ MOXXI 3.0 (ЧАСТЬ 2/2)</b> 🌟 🚀\n"
    "✦ ══ • ⊰ 🏢 💼 🐉 ⚔️ 🛡 🎁 💎 📈 ⊱ • ══ ✦\n\n"
    "🏢 <b>4. БИЗНЕС-ИМПЕРИИ (40 УРОВНЕЙ), РАБОТЫ И АВТО:</b>\n"
    "• <b>40 уровней предприятий:</b> От уютной Кофейни до Межгалактического Трона Архитектора! (<code>бизнесы</code>, <code>купить бизнес</code>, <code>прибыль</code>)\n"
    "• <b>10 профессий:</b> Карьерная лестница от Дворника до Космонавта со стажем смен и премиями от шефа до 15 000 🪙! (<code>работы</code>, <code>работать</code>, <code>премия</code>)\n"
    "• <b>Автосалон и Недвижимость:</b> Покупайте тачки в гараж (Lada Vesta, BMW M5, Bugatti) и дома от Коробки до Личного Острова! (<code>автосалон</code>, <code>дома</code>)\n"
    "• <b>Зоомагазин:</b> Приручайте Котиков, Псов, Драконов и Кибер-Пантер с боевыми баффами! (<code>зоомагазин</code>, <code>питомец</code>)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🐉 <b>5. КЛАНЫ, РЕЙД-БОССЫ И АУКЦИОНЫ:</b>\n"
    "• <b>Кланы и Кланвары:</b> Создавайте свои синдикаты, пополняйте общак казны и воюйте за банк! (<code>создать клан</code>, <code>кланвар</code>, <code>казна</code>)\n"
    "• <b>Рейдовые Боссы (50 000 HP):</b> Собирайте всю беседу, наносите сокрушительные удары и забирайте редкий дроп! (<code>босс</code>, <code>атака</code>, <code>призвать босса</code>)\n"
    "• <b>Открытые Аукционы:</b> Выставляйте лоты, перебивайте ставки соперников с системой антиснайпера +2 мин! (<code>аукцион</code>, <code>ставка [лот] [сумма]</code>)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "⚔️ <b>6. ДАНЖИ, ШАХТЫ, РЫБАЛКА И КРАФТ:</b>\n"
    "• <b>5 уровней подземелий:</b> Рейды от Гоблинского Леса до Цитадели Тьмы за ценным лутом и артефактами! (<code>данжи</code>, <code>поход [номер]</code>)\n"
    "• <b>Шахты и Кирки:</b> Добыча драгоценных минералов и самоцветов острой киркой. (<code>шахта</code>, <code>копать</code>)\n"
    "• <b>Рыбалка и Улов:</b> Ловите редкую рыбу и вытаскивайте затонувшие сундуки со дна! (<code>рыбалка</code>, <code>улов</code>)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🛡 <b>7. НЕПРОБИВАЕМЫЙ АНТИРЕЙД И НЕЙРОСЕТЕВОЙ STT:</b>\n"
    "• <code>антимат</code>, <code>антиспам</code>, <code>антиссылка</code>, <code>карантин</code> для новичков и чистка сервисных входов!\n"
    "• 🎙 <b>AI Расшифровка голоса:</b> Бот на лету переводит любые голосовые сообщения и видео-кружочки в текст!\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🎁 <b>8. СЕКРЕТНЫЙ ПРОМОКОД НА СТАРТ:</b>\n"
    "В честь грандиозного открытия мы активировали бонусный код:\n"
    "👉 Напишите в чат: <code>промо ОБНОВА3.0</code>\n"
    "💰 И мгновенно получите <b>+2 500 000 монет</b> на баланс!\n\n"
    "✦ ══ • ⊰ 🍸 ДОБРО ПОЖАЛОВАТЬ В MOXXI 3.0! ⊱ • ══ ✦"
)

UPDATE_PARTS = [UPDATE_PART_1, UPDATE_PART_2]
UPDATE_TEXT = UPDATE_PART_1


def _updates_kb(part: int = 1) -> InlineKeyboardMarkup:
    bot_user = "moxxichat_bot"
    support_btn = InlineKeyboardButton(text="💬 Поддержка & Вопросы", url=f"https://t.me/{bot_user}?start=support")
    if part == 1:
        row = [
            InlineKeyboardButton(text="➡️ Часть 2: Бизнесы, Боссы и Промо", callback_data="updates:p2"),
            InlineKeyboardButton(text="📖 Все 415+ команд", callback_data="h:p:0"),
        ]
    else:
        row = [
            InlineKeyboardButton(text="⬅️ Часть 1: Мультиплатформа, Ранги, Казино", callback_data="updates:p1"),
            InlineKeyboardButton(text="📖 Все 415+ команд", callback_data="h:p:0"),
        ]
    return InlineKeyboardMarkup(inline_keyboard=[[support_btn], row])

RESTART_MAINTENANCE_TEXT = (
    "🛠 ✨ <b>ТЕХНИЧЕСКИЕ РАБОТЫ И ПЕРЕЗАГРУЗКА</b> ✨ 🛠\n"
    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    "⚠️ Внимание! Бот уходит на быструю перезагрузку / техническое обслуживание.\n"
    "⏱ <b>Ориентировочное время:</b> ~1–2 минуты.\n"
    "📌 <i>Все балансы, статистика, рейды и ранги сохранены в безопасности!</i>\n\n"
    "🚀 Скоро вернемся в строй!"
)


@router.message(Cmd("обновление", "обновления", "анонс обновлений", "анонс обновления", "список обновлений", "новые обновления", "что нового", "changelog", "патчноут", section=S,
                    usage="анонс обновлений", desc="Что нового в последней версии бота"))
async def cmd_updates(message: Message, **kw):
    await message.reply(UPDATE_PART_1, reply_markup=_updates_kb(1), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("updates:"))
async def cb_updates(cq: CallbackQuery):
    part = cq.data.split(":", 1)[1]
    if part == "p2":
        await cq.message.edit_text(UPDATE_PART_2, reply_markup=_updates_kb(2), disable_web_page_preview=True)
    else:
        await cq.message.edit_text(UPDATE_PART_1, reply_markup=_updates_kb(1), disable_web_page_preview=True)
    await cq.answer()


async def announce_update_on_startup(bot: Bot) -> None:
    """Одноразово рассылает анонс обновления в чаты при первом запуске новой версии."""
    marker = "update_announced_moxxi_v2_launch_official"
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
        for t in UPDATE_PARTS:
            try:
                if sms_tid:
                    await bot.send_message(cid, t, message_thread_id=sms_tid, disable_web_page_preview=True)
                else:
                    await bot.send_message(cid, t, disable_web_page_preview=True)
            except Exception:
                pass
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.15)
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


async def is_service_or_silent_chat(chat_id: int, bot: Bot | None = None) -> bool:
    """Проверяет, является ли чат сервисным каналом (Идеи, Отзывы, Поддержка) или чатом с выключенными оповещениями."""
    # 1. Проверка в таблице chats
    row = await db.fetchone("SELECT silent FROM chats WHERE chat_id=?", (chat_id,))
    if row and row["silent"] == 1:
        return True

    # 2. Проверка персональных настроек чата
    if await db.get_setting(chat_id, "bot_broadcasts", "1") == "0":
        return True

    # 3. Проверка сервисных групп по ID или ссылкам
    service_keys = [
        "global_ideas_chat_id", "global_reviews_chat_id", "global_support_chat_id",
        "global_ideas_chat", "global_reviews_chat", "global_support_chat"
    ]
    cid_str = str(chat_id)
    for k in service_keys:
        val = await db.get_global_setting(k, "")
        if val and (val == cid_str or val.lstrip("-") == cid_str.lstrip("-")):
            return True

    # 4. Проверка известных постоянных ID групп идей и отзывов
    if chat_id in {-1004292137436, -1004373090684}:
        return True

    return False


async def broadcast_notice(bot: Bot, text: str) -> int:
    """Рассылает сообщение в активные чаты, строго исключая сервисные каналы (Идеи, Отзывы, Поддержка) и чаты с silent=1."""
    target_ids = set()
    from core_seed import MAIN_CHAT
    from h_chatset import get_sms_topic
    target_ids.add(MAIN_CHAT)
    try:
        rows = await db.fetchall("SELECT chat_id FROM chats WHERE chat_id < 0 AND silent=0")
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
        # Проверяем, не сервисный ли это чат и не отключены ли авто-оповещения
        if await is_service_or_silent_chat(cid, bot):
            continue

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
    """Фоновый воркер: плановое фоновое обслуживание каждые 12 часов (в 00:00 и 12:00 МСК).
    Выполняет оптимизацию SQLite, сборку мусора и бэкап базы данных без отключения бота."""
    maintenance_hours = {0, 12}
    last_done_hour = -1

    while True:
        try:
            await asyncio.sleep(25)
            now = datetime.now(timezone(timedelta(hours=3)))  # МСК

            if now.hour in maintenance_hours and now.minute == 0 and now.hour != last_done_hour:
                if time.time() - START_TS < 300:
                    continue
                last_done_hour = now.hour
                log.info("⏰ Плановое фоновое обслуживание (12ч, %02d:00 МСК)...", now.hour)
                import gc
                gc.collect()

                try:
                    await db.execute("PRAGMA optimize")
                    await db.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception as e:
                    log.warning("PRAGMA optimize error: %s", e)

                import core_backup
                try:
                    await core_backup.save(bot, note=f"Плановый бэкап ({now.hour:02d}:00 МСК)")
                except Exception as e:
                    log.warning("Плановый бэкап error: %s", e)

                log.info("✅ Плановое фоновое обслуживание успешно завершено без перезапуска бота.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("auto_restart_worker error: %s", e)

@router.message(Cmd("-сообщения бота", "-оповещения", "-рассылка", "-боссы", "тихий чат вкл",
                    section=S, rank=0, group_only=False,
                    usage="-сообщения бота", desc="Выключить все автоматические сообщения бота в группе (только Владелец)"))
async def cmd_mute_bot_messages(message: Message, bot: Bot, **kw):
    import config
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid):
        return  # Тихий пропуск для игроков и модераторов групп

    cid = message.chat.id
    await db.set_setting(cid, "bot_broadcasts", "0")
    await db.set_setting(cid, "boss_spawns", "0")
    await db.execute(
        "INSERT INTO chats (chat_id, title, added_at, silent) VALUES (?, ?, 0, 1) "
        "ON CONFLICT(chat_id) DO UPDATE SET silent=1",
        (cid, message.chat.title or "Чат")
    )

    await message.reply(
        "🔇 <b>Все автоматические оповещения бота в этой группе выключены!</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "В этот чат больше <b>НЕ</b> будут приходить:\n"
        "• ⏳ Оповещения о плановом перезапуске и техработах;\n"
        "• 🐲 Рейды боссов и напоминания о боссах;\n"
        "• 📢 Глобальные рассылки и авто-новости.\n\n"
        "Чат переведён в сервисный тихий режим.\n"
        "🔄 <i>Включить обратно: <code>+сообщения бота</code></i>"
    )


@router.message(Cmd("+сообщения бота", "+оповещения", "+рассылка", "+боссы", "тихий чат выкл",
                    section=S, rank=0, group_only=False,
                    usage="+сообщения бота", desc="Включить автоматические сообщения бота в группе (только Владелец)"))
async def cmd_unmute_bot_messages(message: Message, bot: Bot, **kw):
    import config
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid):
        return  # Тихий пропуск

    cid = message.chat.id
    await db.set_setting(cid, "bot_broadcasts", "1")
    await db.set_setting(cid, "boss_spawns", "1")
    await db.execute(
        "INSERT INTO chats (chat_id, title, added_at, silent) VALUES (?, ?, 0, 0) "
        "ON CONFLICT(chat_id) DO UPDATE SET silent=0",
        (cid, message.chat.title or "Чат")
    )

    await message.reply(
        "🔔 <b>Автоматические оповещения бота в этой группе включены!</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Чат снова будет получать важные обновления и оповещения бота."
    )


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
    
    async def _do_restart_async():
        await asyncio.sleep(2.0)
        try:
            await bot.session.close()
        except Exception:
            pass
        if not os.getenv("CONTAINER") and not os.getenv("DOCKER"):
            try:
                import subprocess
                subprocess.Popen([sys.executable] + sys.argv)
            except Exception:
                pass
        sys.exit(0)

    asyncio.create_task(_do_restart_async())



@router.message(Cmd("разослать обновление", "рассылка обновления", "обновить чаты", "разослать анонс",
                    section=S, rank=8, hidden=True,
                    usage="разослать обновление [текст]", desc="Разослать анонс обновления по всем чатам (только создатель и админы)"))
async def cmd_broadcast_updates(message: Message, bot: Bot, args: str = "", **kw):
    import config
    uid = message.from_user.id if message.from_user else 0
    is_owner = bool(uid == config.OWNER_ID or uid in config.ADMINS)
    if not is_owner:
        return await message.reply("🔒 <b>Команда «разослать обновление» доступна исключительно владельцу и администраторам бота!</b>")

    texts_to_send = [args.strip()] if (args and args.strip()) else UPDATE_PARTS

    m = await message.reply(
        "📢 <b>Начинаю мультиплатформенную рассылку обновления 3.0…</b>\n"
        "📡 Отправка в: ✈️ Telegram • 🟦 ВКонтакте • 🟣 Discord • 🟢 MAX\n"
        "Пожалуйста, подождите завершения отправки."
    )

    from core_cross_broadcast import cross_broadcast_update
    stats = await cross_broadcast_update(bot, texts_to_send)

    await m.edit_text(
        f"✅ <b>МУЛЬТИПЛАТФОРМЕННЫЙ АНОНС ОБНОВЛЕНИЯ РАЗОСЛАН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>СТАТИСТИКА ДОСТАВКИ:</b>\n"
        f"• ✈️ Telegram: <b>{stats.get('telegram', 0)} групп</b>\n"
        f"• 🟦 ВКонтакте: <b>{stats.get('vk', 0)} бесед</b>\n"
        f"• 🟣 Discord: <b>{stats.get('discord', 0)} серверов</b>\n"
        f"• 🟢 MAX: <b>{stats.get('max', 0)} чатов</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <i>Анонс 3.0 успешно опубликован на всех 4 платформах!</i>"
    )


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
