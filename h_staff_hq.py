# -*- coding: utf-8 -*-
"""MOXXI Staff Headquarters & Duty & Automod Logger Module for Telegram.

Реализует полный функционал стафф-сервера Discord внутри Telegram:
1. Штаб стаффа: привязка рабочей группы команды через /set_staff_hq
2. Канал логов: привязка канала аудита через /set_mod_log
3. Система дежурств (На смене / На работе):
   - Интерактивная витрина (/duty, !дежурка, !смена) с кнопками выхода/завершения
   - Подсчет отработанного времени и прогресс до Ветерана (50 часов)
   - Анти-AFK Watchdog (автоснятие + выговор при неактивности > 45 минут)
   - Контроль работы: модераторы могут наказывать только будучи НА СМЕНЕ
4. Автомодерация оскорблений и мата с мгновенным мутом и удалением
5. Мгновенный лог всех действий и нарушений админам
"""
from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import core_toxicity as toxicity
import db
from utils import mention_id

log = logging.getLogger("moxxi-tg-staff")
router = Router(name="staff_hq")

# Константы
VETERAN_SECONDS = 50 * 3600  # 50 часов = 180,000 сек
AFK_TIMEOUT_SECONDS = 45 * 60  # 45 минут = 2700 сек

MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

UNMUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}ч {minutes}м"


def get_progress_bar(current_sec: int, target_sec: int = VETERAN_SECONDS) -> str:
    cur_h = current_sec // 3600
    target_h = target_sec // 3600
    pct = min(1.0, max(0.0, current_sec / target_sec)) if target_sec > 0 else 0.0
    filled = int(round(10 * pct))
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {int(pct * 100)}% ({cur_h}ч / {target_h}ч)"


# ---------------- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ БАЗЫ ДАННЫХ ----------------
async def init_staff_tables():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_hq_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_duty_members (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            is_on_duty INTEGER DEFAULT 0,
            duty_start_ts INTEGER DEFAULT 0,
            last_activity_ts INTEGER DEFAULT 0,
            total_duty_seconds INTEGER DEFAULT 0,
            swarns INTEGER DEFAULT 0,
            is_veteran INTEGER DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_duty_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            action TEXT,
            duration_sec INTEGER DEFAULT 0,
            total_sec INTEGER DEFAULT 0,
            ts INTEGER
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_action_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            admin_name TEXT,
            target_id INTEGER,
            target_name TEXT,
            action TEXT,
            reason TEXT,
            duration_sec INTEGER DEFAULT 0,
            chat_id INTEGER,
            chat_title TEXT,
            ts INTEGER
        )
    """)


# ---------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ЛОГИРОВАНИЯ ----------------
async def get_staff_hq_id() -> Optional[int]:
    row = await db.fetchone("SELECT value FROM staff_hq_settings WHERE key='staff_hq_chat_id'")
    return int(row["value"]) if row and row["value"] else None


async def get_ai_topic_info() -> tuple[Optional[int], Optional[int]]:
    """Возвращает (staff_hq_chat_id, staff_ai_topic_id)."""
    r_chat = await db.fetchone("SELECT value FROM staff_hq_settings WHERE key='staff_hq_chat_id'")
    r_topic = await db.fetchone("SELECT value FROM staff_hq_settings WHERE key='staff_ai_topic_id'")
    cid = int(r_chat["value"]) if r_chat and r_chat["value"] else None
    tid = int(r_topic["value"]) if r_topic and r_topic["value"] else None
    return cid, tid


async def get_log_channel_id() -> Optional[int]:
    row = await db.fetchone("SELECT value FROM staff_hq_settings WHERE key='staff_log_channel_id'")
    if row and row["value"]:
        return int(row["value"])
    return await get_staff_hq_id()


async def send_staff_log(bot: Bot, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Отправляет лог в канал аудита или группу штаба стаффа (с поддержкой топика логов)."""
    target_id = await get_log_channel_id()
    if not target_id:
        return
    r_topic = await db.fetchone("SELECT value FROM staff_hq_settings WHERE key='staff_log_topic_id'")
    log_tid = int(r_topic["value"]) if r_topic and r_topic["value"] else None
    try:
        await bot.send_message(
            target_id,
            text,
            message_thread_id=log_tid,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        log.warning("Не удалось отправить лог стаффа в %s: %s", target_id, e)


async def get_or_create_staff_member(user_id: int, user_name: str) -> dict:
    row = await db.fetchone("SELECT * FROM staff_duty_members WHERE user_id=?", (user_id,))
    if not row:
        await db.execute(
            "INSERT INTO staff_duty_members (user_id, user_name, is_on_duty, duty_start_ts, last_activity_ts, total_duty_seconds, swarns, is_veteran) "
            "VALUES (?, ?, 0, 0, 0, 0, 0, 0)",
            (user_id, user_name)
        )
        row = await db.fetchone("SELECT * FROM staff_duty_members WHERE user_id=?", (user_id,))
    return dict(row)


async def update_staff_activity(user_id: int):
    now = int(time.time())
    await db.execute(
        "UPDATE staff_duty_members SET last_activity_ts=? WHERE user_id=? AND is_on_duty=1",
        (now, user_id)
    )


async def is_user_on_duty(user_id: int) -> bool:
    if config.is_bot_owner(user_id):
        return True  # Владельцы всегда имеют полный доступ
    row = await db.fetchone("SELECT is_on_duty FROM staff_duty_members WHERE user_id=?", (user_id,))
    return bool(row and row["is_on_duty"])


# ---------------- КЛАВИАТУРЫ ДЕЖУРКИ ----------------
def get_duty_keyboard(is_on_duty: bool) -> InlineKeyboardMarkup:
    if is_on_duty:
        duty_btn = InlineKeyboardButton(text="🔴 Завершить смену", callback_data="hq_duty:end")
    else:
        duty_btn = InlineKeyboardButton(text="🟢 Выйти на смену", callback_data="hq_duty:start")

    return InlineKeyboardMarkup(inline_keyboard=[
        [duty_btn],
        [
            InlineKeyboardButton(text="📊 Моя смена & Стаж", callback_data="hq_duty:my_stats"),
            InlineKeyboardButton(text="👥 Кто на смене?", callback_data="hq_duty:who")
        ],
        [
            InlineKeyboardButton(text="🤖 ИИ-Копилот для тикетов", callback_data="hq_duty:ai_helper"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="hq_duty:refresh")
        ]
    ])


# ---------------- 1.2 АВТО-РАЗВЁРТЫВАНИЕ ШТАБА СТАФФА «ПОД КЛЮЧ» В 1 КЛИК ----------------
@router.message(F.text.lower().in_({"!автоштаб", "/setup_staff_group", "!настроить штаб", "/deploy_staff_hq", "!создать штаб"}))
async def cmd_auto_deploy_staff_hq(message: Message, bot: Bot):
    if not config.is_bot_owner(message.from_user.id):
        return await message.reply("⛔️ Команда доступна исключительно Главному Владельцу MOXXI.")

    chat_id = message.chat.id
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f"❌ Ошибка получения данных чата: {e}")

    if not getattr(chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>В этой группе ещё не включены «Темы» (Форум)!</b>\n\n"
            "Чтобы бот смог автоматически создать все 5 тем, включите одну настройку:\n"
            "1. Зайдите в <b>«Управление группой»</b> (клик по аватарке группы ➔ Редактировать / Карандаш).\n"
            "2. Найдите переключатель <b>«Темы» (Topics)</b> и включите его.\n"
            "3. После этого напишите <code>!автоштаб</code> ещё раз — и я создам всё сам за 2 секунды!"
        )

    status_msg = await message.reply("🚀 <b>Разворачиваю официальный Штаб Стаффа MOXXI «под ключ»...</b>")

    created_topics = {}
    topic_configs = [
        ("📌・устав-стаффа", 0xFFD67E, "rules"),
        ("⏱・дежурка", 0x8EEE98, "duty"),
        ("🤖・ии-подсказчик", 0x6FB9F0, "ai"),
        ("📊・логи-наказаний", 0xFB6F5F, "logs"),
        ("💬・чат-стаффа", 0xCB86DB, "chat"),
    ]

    for name, color, role_key in topic_configs:
        try:
            topic = await bot.create_forum_topic(chat_id=chat_id, name=name, icon_color=color)
            created_topics[role_key] = topic.message_thread_id
            await asyncio.sleep(0.4)
        except Exception as e:
            log.warning("Не удалось создать топик %s: %s", name, e)

    # 1. Наполняем топик Устава
    rules_tid = created_topics.get("rules")
    if rules_tid:
        try:
            r_msg = await bot.send_message(chat_id, """🏛 <b>ОФИЦИАЛЬНЫЙ УСТАВ & РЕГЛАМЕНТ АДМИНИСТРАЦИИ MOXXI</b>

Добро пожаловать в команду проекта MOXXI! Каждый сотрудник обязан неукоснительно соблюдать регламент:

1️⃣ <b>ДЕЖУРСТВА & ВЫХОД НА СМЕНУ:</b>
• Перед началом модерации обязательно заходите в тему <b>#⏱・дежурка</b> и нажимайте <b>«🟢 Выйти на смену»</b>.
• Наказывать игроков (мут, бан, варн) разрешено <b>СТРОГО НА СМЕНЕ</b>! Вне смены бот заблокирует команды.
• После работы нажимайте <b>«🔴 Завершить смену»</b>.
• ⚠️ <b>Анти-AFK Watchdog:</b> При отсутствии активности более <b>45 минут</b> на смене бот автоматически снимет вас и выпишет выговор (+1 сварн)!

2️⃣ <b>ЖЕЛЕЗНОЕ ПРАВИЛО: ЗАПРЕТ ОСКОРБЛЕНИЙ ИГРОКОВ:</b>
• Модератор — лицо проекта MOXXI. 
• 🚫 <b>СТРОЖАЙШЕ ЗАПРЕЩЕНО</b> оскорблять игроков, употреблять мат и проявлять агрессию в чатах игроков.
• ⚡️ <b>АВТО-НАКАЗАНИЕ:</b> Бот моментально удаляет сообщение, выдаёт модератору <b>мут на 30 минут</b>, принудительно <b>снимает со смены</b> и начисляет <b>+1 сварн</b>!

3️⃣ <b>СИСТЕМА ВЫГОВОРОВ (СВАРНЫ 3/3):</b>
• ⚠️ <b>1/3 сварн:</b> Опоздание, AFK на смене, мелкая грубость.
• ⚠️ <b>2/3 сварн:</b> Повторное дисциплинарное нарушение, халатность.
• ❌ <b>3/3 сварн:</b> <b>АВТОМАТИЧЕСКОЕ РАЗЖАЛОВАНИЕ И СНЯТИЕ ВСЕХ РОЛЕЙ</b> без права восстановления!

4️⃣ <b>РАБОТА С ТИКЕТАМИ & ИИ-ПОДСКАЗЧИК:</b>
• Если вам прилетел сложный тикет от игрока — скиньте его в тему <b>#🤖・ии-подсказчик</b>.
• Бот моментально выдаст готовый план действий и вежливый шаблон ответа для игрока в 1 клик!

5️⃣ <b>СТАТУС ВЕТЕРАНА СТАФФА (50 ЧАСОВ):</b>
• Отработайте <b>50 часов</b> на смене без выговоров, чтобы получить статус 🏅 <b>Ветеран MOXXI (50ч+)</b> и повышение в должности!""", message_thread_id=rules_tid)
            await bot.pin_chat_message(chat_id, r_msg.message_id)
        except Exception:
            pass

    # 2. Наполняем топик Дежурки
    duty_tid = created_topics.get("duty")
    if duty_tid:
        try:
            kb = get_duty_keyboard(False)
            duty_intro = (
                "🕒 <b>ПУЛЬТ УПРАВЛЕНИЯ СМЕНАМИ СТАФФА MOXXI</b>\n\n"
                "• Нажмите <b>«🟢 Выйти на смену»</b> перед началом модерации чатов.\n"
                "• Вне смены модераторские команды наказаний заблокированы!\n"
                "• По окончании работы нажмите <b>«🔴 Завершить смену»</b>.\n"
                "• ⚠️ <i>Анти-AFK: бездействие более 45 мин = автоснятие + сварн.</i>"
            )
            d_msg = await bot.send_message(chat_id, duty_intro, reply_markup=kb, message_thread_id=duty_tid)
            await bot.pin_chat_message(chat_id, d_msg.message_id)
        except Exception:
            pass

    # 3. Наполняем топик ИИ-подсказчика
    ai_tid = created_topics.get("ai")
    if ai_tid:
        try:
            ai_intro = (
                "🤖 <b>ИИ-КОПИЛОТ СЛУЖБЫ ПОДДЕРЖКИ & СТАФФА MOXXI</b>\n\n"
                "🔥 <b>В этой теме модераторы могут писать БЕЗ КАКИХ-ЛИБО КОМАНД!</b>\n"
                "• Пересылайте сюда тикеты или вопросы от игроков.\n"
                "• Задавайте любые вопросы по правилам и наказаниям.\n"
                "• Бот моментально выдаст действие и готовый шаблон ответа для игрока в 1 клик!\n"
                "🛡 <i>Автомод в этой теме отключен: цитаты нарушителей с матом безопасны.</i>"
            )
            ai_msg = await bot.send_message(chat_id, ai_intro, message_thread_id=ai_tid)
            await bot.pin_chat_message(chat_id, ai_msg.message_id)
        except Exception:
            pass

    # 4. Наполняем топик Логов
    logs_tid = created_topics.get("logs")
    if logs_tid:
        try:
            log_intro = (
                "📊 <b>ЖУРНАЛ АУДИТА & ЛОГОВ СТАФФА MOXXI</b>\n\n"
                "Сюда автоматически транслируются:\n"
                "• Все заступления и сдачи смен сотрудниками\n"
                "• Все выданные муты, баны, варны и кики\n"
                "• Дисциплинарные выговоры (сварны) и автоснятия Анти-AFK\n"
                "• Кнопки мгновенной отмены мута для руководства"
            )
            l_msg = await bot.send_message(chat_id, log_intro, message_thread_id=logs_tid)
            await bot.pin_chat_message(chat_id, l_msg.message_id)
        except Exception:
            pass

    # 5. Наполняем чат стаффа
    chat_tid = created_topics.get("chat")
    if chat_tid:
        try:
            c_msg = await bot.send_message(
                chat_id,
                "💬 <b>РАБОЧИЙ ЧАТ АДМИНИСТРАЦИИ MOXXI</b>\n\n"
                "Координация команды, передача смен и обсуждение рабочих вопросов. Приятной работы! 🛡️",
                message_thread_id=chat_tid
            )
        except Exception:
            pass

    # Сохраняем все привязки в базу данных
    await db.execute(
        "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_hq_chat_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(chat_id),)
    )
    if ai_tid:
        await db.execute(
            "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_ai_topic_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(ai_tid),)
        )
    if logs_tid:
        await db.execute(
            "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_log_channel_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(chat_id),)
        )
        await db.execute(
            "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_log_topic_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(logs_tid),)
        )

    res_text = (
        "🎉 <b>ШТАБ СТАФФА MOXXI ПОЛНОСТЬЮ РАЗВЁРНУТ «ПОД КЛЮЧ»!</b>\n\n"
        "✅ <b>5 тем создано автоматически:</b>\n"
        "• 📌 <code>#устав-стаффа</code> — правила, регламент и система 3/3 сварнов\n"
        "• ⏱ <code>#дежурка</code> — закреплён интерактивный пульт дежурства\n"
        "• 🤖 <code>#ии-подсказчик</code> — привязан ИИ-копилот без команд\n"
        "• 📊 <code>#логи-наказаний</code> — подключён поток аудита нарушений\n"
        "• 💬 <code>#чат-стаффа</code> — создана зона общения команды\n\n"
        "🛡 <i>Автомодерация и защита от оскорблений игроков активна на 100%!</i>"
    )
    try:
        await status_msg.edit_text(res_text)
    except Exception:
        await message.reply(res_text)


# ---------------- 1.3 АВТО-РАЗВЁРТЫВАНИЕ ЧАТА СООБЩЕСТВА «ПОД КЛЮЧ» В 1 КЛИК ----------------
@router.message(F.text.lower().in_({
    "!авточат", "/setup_community_chat", "/setup_chat",
    "!настроить чат", "!автонастройка_чата", "!автонастройка",
    "/deploy_community_chat", "!создать чат", "!создать темы"
}))
async def cmd_auto_deploy_community_chat(message: Message, bot: Bot):
    chat_id = message.chat.id

    # 1. Проверка прав: Владелец бота либо создатель/администратор группы
    is_owner = config.is_bot_owner(message.from_user.id)
    if not is_owner:
        try:
            cm = await bot.get_chat_member(chat_id, message.from_user.id)
            if cm.status not in ("creator", "administrator"):
                return await message.reply("⛔️ Команда настройки чата доступна только Владельцу бота или Создателю группы.")
        except Exception:
            return await message.reply("⛔️ Команда доступна исключительно Владельцу MOXXI.")

    # 2. Проверка включения режима «Темы» (Forum Supergroup)
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f"❌ Ошибка получения данных чата: {e}")

    if not getattr(chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>В этой группе ещё не включены «Темы» (Форум)!</b>\n\n"
            "Чтобы бот автоматически создал все 7 игровых разделов («Общение», «Босс», «Казино», «Правила», «Команды» и др.), включите темы:\n\n"
            "1. Зайдите в <b>«Управление группой»</b> (клик по аватарке чата ➔ Редактировать / Карандаш).\n"
            "2. Найдите переключатель <b>«Темы» (Topics)</b> и включите его.\n"
            "3. После этого напишите <code>!авточат</code> ещё раз — и я моментально настрою всю группу!"
        )

    # 3. Проверка прав бота на создание тем
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if getattr(bot_member, "status", "") not in ("administrator", "creator"):
            return await message.reply(
                "⚠️ <b>Бот не является администратором группы!</b>\n\n"
                "Выдайте боту права администратора с правом <b>«Управление темами»</b>, затем повторите команду <code>!авточат</code>."
            )
    except Exception:
        pass

    status_msg = await message.reply("🚀 <b>Разворачиваю официальный Чат Сообщества MOXXI «под ключ»...</b>")

    created_topics = {}
    topic_configs = [
        ("📌・правила-и-новости", 0xFFD67E, "rules"),
        ("💬・общение-и-флуд", 0x6FB9F0, "chat"),
        ("👾・рейды-и-боссы", 0xFB6F5F, "boss"),
        ("🎰・казино-и-игры", 0xCB86DB, "casino"),
        ("🤖・команды-и-бот", 0x8EEE98, "commands"),
        ("🤝・кланы-и-тимы", 0xFF93B2, "clans"),
        ("💡・идеи-и-поддержка", 0x6FB9F0, "support"),
    ]

    for name, color, role_key in topic_configs:
        try:
            topic = await bot.create_forum_topic(chat_id=chat_id, name=name, icon_color=color)
            created_topics[role_key] = topic.message_thread_id
            await asyncio.sleep(0.4)
        except Exception as e:
            log.warning("Не удалось создать топик сообщества %s: %s", name, e)

    # 1. Топик Правил и Новостей
    rules_tid = created_topics.get("rules")
    if rules_tid:
        try:
            rules_text = (
                "🏛 <b>ОФИЦИАЛЬНЫЙ РЕГЛАМЕНТ & ПРАВИЛА СООБЩЕСТВА MOXXI</b> 💜\n\n"
                "Добро пожаловать в официальный чат игроков и создателей групп проекта <b>MOXXI</b>! "
                "Чтобы наше общение оставалось комфортным, дружелюбным и честным для каждого, действуют простые правила:\n\n"
                "1️⃣ <b>УВАЖЕНИЕ И АДЕКВАТНОСТЬ:</b>\n"
                "• Запрещены любые проявления токсичности, травли, агрессии и переходов на личности.\n"
                "• 🚫 <b>Строжайше запрещены:</b> оскорбления родных, разжигание розни, дискриминация и шок-контент (мгновенный бан навсегда).\n\n"
                "2️⃣ <b>ЧИСТОТА ЧАТА & ЗАПРЕТ СПАМА:</b>\n"
                "• Запрещена несогласованная реклама сторонних каналов, ботов, чатов, рефералок и услуг.\n"
                "• Запрещён спам одинаковыми сообщениями, стикерами и командами вне игровых тем.\n"
                "• 🚫 Скам, фишинг и вредоносные ссылки караются перманентным баном бота во всей сети.\n\n"
                "3️⃣ <b>ТЕМАТИЧЕСКИЙ ПОРЯДОК:</b>\n"
                "• 🎰 <b>#казино-и-игры:</b> Все азартные ставки (казик, слоты, кости, рулетка).\n"
                "• 👾 <b>#рейды-и-боссы:</b> Все битвы с мировыми боссами и обсуждение рейдов.\n"
                "• 🤝 <b>#кланы-и-тимы:</b> Набор в кланы и поиск напарников.\n"
                "• 💬 <b>#общение-и-флуд:</b> Знакомства, обсуждения, мемы и тёплые беседы.\n\n"
                "4️⃣ <b>ЧЕСТНАЯ ИГРА:</b>\n"
                "• Запрещены любые попытки багоюза, накрутки и продажи виртуальных монет за реальные деньги вне официального магазина.\n\n"
                "5️⃣ <b>АВТОМАТИЧЕСКАЯ МОДЕРАЦИЯ 24/7:</b>\n"
                "• В чате круглосуточно работает ИИ-фильтр брани, защита от спам-атак и анти-рейд.\n\n"
                "<i>Соблюдайте правила и наслаждайтесь космическим общением в MOXXI!</i> ✨"
            )
            r_msg = await bot.send_message(chat_id, rules_text, message_thread_id=rules_tid)
            await bot.pin_chat_message(chat_id, r_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации правил: %s", e)

    # 2. Главный зал общения
    chat_tid = created_topics.get("chat")
    if chat_tid:
        try:
            chat_text = (
                "💬 <b>ГЛАВНЫЙ ЗАЛ ОБЩЕНИЯ СООБЩЕСТВА MOXXI</b> ✨\n\n"
                "Добро пожаловать в центральное место для общения всех игроков и администраторов!\n\n"
                "🎉 <b>Что здесь можно делать:</b>\n"
                "• Общаться на любые темы, делиться настроением и шутить.\n"
                "• Находить новых друзей, собеседников и обсуждать игровые тактики.\n"
                "• Задавать любые вопросы боту: напишите <code>ии [вопрос]</code> прямо в чат!\n"
                "• Спрашивать советы у опытных игроков и администрации проекта.\n\n"
                "🎁 <b>БОНУС ДЛЯ УЧАСТНИКОВ СООБЩЕСТВА:</b>\n"
                "Создатели выпустили специальный промокод на халявные монеты!\n"
                "Напишите прямо в чат: <code>промо ОБНОВА3.0</code> и заберите <b>+2,500,000 монет</b>! 💰"
            )
            c_msg = await bot.send_message(chat_id, chat_text, message_thread_id=chat_tid)
            await bot.pin_chat_message(chat_id, c_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации чата: %s", e)

    # 3. Топик Рейдов и Боссов
    boss_tid = created_topics.get("boss")
    if boss_tid:
        try:
            boss_text = (
                "👾 <b>АРЕНА РЕЙДОВ & МИРОВЫЕ БОССЫ MOXXI</b> ⚔️\n\n"
                "Здесь собираются храбрейшие воины проекта, чтобы дать отпор свирепым монстрам!\n\n"
                "🗡 <b>КАК УЧАСТВОВАТЬ В БИТВЕ:</b>\n"
                "• Напишите <code>босс</code> — бот выведет карточку текущего босса и его шкалу HP.\n"
                "• Напишите <code>ударить босса</code> — нанесите сокрушительный удар своим оружием!\n"
                "• Напишите <code>топ босса</code> — посмотрите рейтинг лидеров по нанесённому урону.\n\n"
                "🏆 <b>НАГРАДЫ ЗА ПОБЕДУ НАД БОССОМ:</b>\n"
                "• 💰 Миллионы монет и горы опыта в ваш профиль.\n"
                "• 🗝 Ключи от тайных подземелий и редкие сундуки сокровищ.\n"
                "• 🏅 Эксклюзивные трофеи и редчайшие артефакты в инвентарь!\n"
                "• 🛡 <b>Клановый бонус:</b> Совместные удары соклановцев прокачивают уровень вашего клана!\n\n"
                "<i>Объединяйте силы и побеждайте вместе! Нажмите кнопку ниже для быстрой атаки.</i> 🔥"
            )
            kb_boss = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⚔️ Напасть на босса", callback_data="comm_act:boss"),
                InlineKeyboardButton(text="🏆 Топ урона", callback_data="comm_act:boss_top")
            ]])
            b_msg = await bot.send_message(chat_id, boss_text, reply_markup=kb_boss, message_thread_id=boss_tid)
            await bot.pin_chat_message(chat_id, b_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации босса: %s", e)

    # 4. Топик Казино и Игр
    casino_tid = created_topics.get("casino")
    if casino_tid:
        try:
            casino_text = (
                "🎰 <b>ЗОЛОТОЕ КАЗИНО & АЗАРТНАЯ АРЕНА MOXXI</b> 🎲\n\n"
                "Добро пожаловать в официальную игорную зону проекта! Здесь разрешены любые ставки без ограничений по флуду:\n\n"
                "🎲 <b>ДОСТУПНЫЕ ИГРЫ:</b>\n"
                "• <code>казик [ставка]</code> или <code>казино [ставка]</code> — попытать удачу в джекпоте!\n"
                "• <code>слоты [ставка]</code> — вращение трёх барабанов (777, вишенки, бары)\n"
                "• <code>кости [ставка]</code> — бросить игральные кости против бота\n"
                "• <code>рулетка [красное/черное/число] [ставка]</code> — европейская рулетка\n"
                "• <code>монетка [орел/решка] [ставка]</code> — игра 50 на 50\n"
                "• <code>дуэль @игрок [ставка]</code> — вызвать соперника на поединок за монеты 1 на 1!\n\n"
                "⚠️ <i>Лимиты ставок зависят от вашего уровня и VIP-статуса. Играйте с азартом, но с умом!</i> 🍀"
            )
            kb_casino = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Крутить слоты", callback_data="comm_act:casino"),
                InlineKeyboardButton(text="🎲 Бросить кости", callback_data="comm_act:dice")
            ]])
            cas_msg = await bot.send_message(chat_id, casino_text, reply_markup=kb_casino, message_thread_id=casino_tid)
            await bot.pin_chat_message(chat_id, cas_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации казино: %s", e)

    # 5. Топик Команд и Справки
    cmd_tid = created_topics.get("commands")
    if cmd_tid:
        try:
            cmd_text = (
                "🤖 <b>БАЗА ЗНАНИЙ & СПРАВОЧНИК КОМАНД MOXXI</b> 📚\n\n"
                "Полный гид по ключевым возможностям игрового бота:\n\n"
                "💰 <b>ЭКОНОМИКА & ФИНАНСЫ:</b>\n"
                "• <code>профиль</code> / <code>баланс</code> — ваш персонаж, монеты и уровень\n"
                "• <code>бонус</code> — ежедневная бесплатная награда за визит\n"
                "• <code>работа</code> — заработать монеты честным трудом\n"
                "• <code>банк [сумма]</code> / <code>банк снять</code> — накопительный счёт под %\n"
                "• <code>передать @игрок [сумма]</code> — перевод монет другу\n\n"
                "👑 <b>РАЗВИТИЕ & ИМУЩЕСТВО:</b>\n"
                "• <code>бизнес</code> — покупка предприятий и пассивный доход\n"
                "• <code>магазин</code> — суперкары, яхты, замки и аксессуары\n"
                "• <code>инвентарь</code> — рюкзак ваших предметов и снаряжения\n"
                "• <code>топ</code> — таблица лидеров по монетам и уровню\n\n"
                "💍 <b>ОТНОШЕНИЯ & РОЛЕВЫЕ ДЕЙСТВИЯ:</b>\n"
                "• <code>брак @игрок</code> — сыграть свадьбу\n"
                "• <code>развод</code> — расторгнуть брак\n"
                "• <code>поцеловать @игрок</code>, <code>обнять @игрок</code> — душевные RP-действия\n\n"
                "🧠 <b>УМНЫЙ ИИ-АССИСТЕНТ:</b>\n"
                "• <code>ии [любой вопрос]</code> — искусственный интеллект ответит на всё!"
            )
            kb_cmd = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📖 Меню помощи", callback_data="comm_act:help"),
                InlineKeyboardButton(text="🎁 Промокод", callback_data="comm_act:promo")
            ]])
            cmd_msg = await bot.send_message(chat_id, cmd_text, reply_markup=kb_cmd, message_thread_id=cmd_tid)
            await bot.pin_chat_message(chat_id, cmd_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации команд: %s", e)

    # 6. Топик Кланов и Тим
    clans_tid = created_topics.get("clans")
    if clans_tid:
        try:
            clans_text = (
                "🤝 <b>КЛАНОВЫЙ ХАБ & ПОИСК КОМАНДЫ MOXXI</b> 🛡️\n\n"
                "Здесь собираются сильнейшие кланы проекта! Ищите напарников, создавайте альянсы и покоряйте рейтинги:\n\n"
                "🏰 <b>КОМАНДЫ ДЛЯ КЛАНОВ:</b>\n"
                "• <code>клан</code> — профиль и статистика вашего клана\n"
                "• <code>создать клан [название]</code> — основать собственное братство\n"
                "• <code>клан топ</code> — рейтинг лучших кланов по очкам\n"
                "• <code>клан казна [сумма]</code> — внести монеты в общую казну клана\n"
                "• <code>клан улучшить</code> — прокачать пассивные бонусы клана\n\n"
                "📢 <b>Лидеры кланов!</b> Вы можете публиковать здесь свои объявления о наборе бойцов, условиях вступления и клановых турнирах!"
            )
            clans_msg = await bot.send_message(chat_id, clans_text, message_thread_id=clans_tid)
            await bot.pin_chat_message(chat_id, clans_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации кланов: %s", e)

    # 7. Топик Идей и Поддержки
    supp_tid = created_topics.get("support")
    if supp_tid:
        try:
            supp_text = (
                "💡 <b>ПРЕДЛОЖЕНИЯ, БАГИ & ТЕХПОДДЕРЖКА MOXXI</b> 🆘\n\n"
                "Мы развиваем MOXXI вместе с нашим дружным комьюнити! Если у вас есть предложения или возникли трудности — пишите сюда:\n\n"
                "✨ <b>КАК СООБЩИТЬ ОБ ИДЕЕ ИЛИ ОШИБКЕ:</b>\n"
                "• <b>Идея:</b> Опишите новую механику, команду или предмет, который вы хотите видеть в боте.\n"
                "• <b>Баг:</b> Прикрепите скриншот и опишите шаги, как воспроизвести ошибку.\n\n"
                "🚨 <b>ЛИЧНАЯ ТЕХПОДДЕРЖКА & ПЛАТЕЖИ:</b>\n"
                "Если у вас возник вопрос по донату, покупке статусов или вам нужна помощь модератора — напишите прямо в чат:\n"
                "<code>поддержка [опишите вашу проблему]</code>\n\n"
                "<i>Ваш тикет моментально попадёт дежурным администраторам в закрытый Штаб Telegram и Discord!</i>"
            )
            supp_msg = await bot.send_message(chat_id, supp_text, message_thread_id=supp_tid)
            await bot.pin_chat_message(chat_id, supp_msg.message_id)
        except Exception as e:
            log.warning("Ошибка публикации поддержки: %s", e)

    # 4. Активация автомодерации и сохранение привязок в БД
    try:
        await db.set_setting(chat_id, "antimat", "1")
        await db.set_setting(chat_id, "antispam", "1")
        await db.set_setting(chat_id, "automod_allow_warn", "1")
        await db.set_setting(chat_id, "automod_allow_mute", "1")
        await db.set_setting(chat_id, "service_cleanup", "1")

        for k, tid in created_topics.items():
            await db.set_setting(chat_id, f"community_topic_{k}", str(tid))

        await db.execute(
            "INSERT INTO staff_hq_settings (key, value) VALUES ('community_chat_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(chat_id),)
        )
        await db.execute(
            "INSERT INTO chats (chat_id, title, added_at) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
            (chat_id, chat.title or "MOXXI Community", int(time.time()))
        )
    except Exception as e:
        log.warning("Ошибка сохранения настроек чата: %s", e)

    final_text = (
        "🎉 <b>ОФИЦИАЛЬНЫЙ ЧАТ СООБЩЕСТВА MOXXI УСПЕШНО РАЗВЁРНУТ «ПОД КЛЮЧ»!</b>\n\n"
        "✅ <b>Создано и оформлено 7 тематических разделов:</b>\n"
        "• 📌 <code>#правила-и-новости</code> — закреплены правила и регламент чата\n"
        "• 💬 <code>#общение-и-флуд</code> — главный зал общения с промокодом на +2,500,000 монет\n"
        "• 👾 <code>#рейды-и-боссы</code> — арена рейдов на мировых боссов с кнопками атак\n"
        "• 🎰 <code>#казино-и-игры</code> — азартная зона без строгих лимитов (казик, слоты, кости, рулетка)\n"
        "• 🤖 <code>#команды-и-бот</code> — интерактивный справочник по всем командам\n"
        "• 🤝 <code>#кланы-и-тимы</code> — площадка поиска напарников и набора в кланы\n"
        "• 💡 <code>#идеи-и-поддержка</code> — приём предложений, багов и связь со стаффом\n\n"
        "🛡 <b>Безопасность и автомодерация:</b>\n"
        "• Фильтр мата и оскорблений: <b>ВКЛЮЧЁН (АВТОМУТ)</b>\n"
        "• Защита от спам-ссылок и скама: <b>ВКЛЮЧЕНА</b>\n"
        "• Очистка системных сообщений: <b>ВКЛЮЧЕНА</b>\n\n"
        "<i>Приятного общения и космических побед в MOXXI!</i> 💜"
    )
    try:
        await status_msg.edit_text(final_text)
    except Exception:
        await message.reply(final_text)


# ---------------- 1.4 ОБРАБОТЧИК КНОПОК ТОПИКОВ СООБЩЕСТВА ----------------
@router.callback_query(F.data.startswith("comm_act:"))
async def cb_community_action(call: CallbackQuery):
    action = call.data.split(":", 1)[1]
    if action == "boss":
        await call.answer("⚔️ Напишите в чат команду «босс» или «ударить босса», чтобы атаковать монстра!", show_alert=True)
    elif action == "boss_top":
        await call.answer("🏆 Напишите в чат команду «топ босса», чтобы открыть таблицу лидеров по урону!", show_alert=True)
    elif action == "casino":
        await call.answer("🎰 Напишите в чат «казик [ставка]» или «слоты [ставка]» (например: слоты 50000)!", show_alert=True)
    elif action == "dice":
        await call.answer("🎲 Напишите в чат «кости [ставка]» (например: кости 100000)!", show_alert=True)
    elif action == "help":
        await call.answer("📚 Напишите в чат команду «помощь» или «команды», чтобы открыть интерактивное меню!", show_alert=True)
    elif action == "promo":
        await call.answer("🎁 Напишите в чат: «промо ОБНОВА3.0», чтобы получить +2,500,000 монет на баланс!", show_alert=True)
    else:
        await call.answer("MOXXI Community Hub ✨")


# ---------------- 1. ПРИВЯЗКА ШТАБА СТАФФА И ЛОГ-КАНАЛА ----------------
@router.message(F.text.lower().in_({"!штаб", "/set_staff_hq", "!привязать стафф", "/setup_staff_group"}))
async def cmd_set_staff_hq(message: Message, bot: Bot):
    if not config.is_bot_owner(message.from_user.id):
        return await message.reply("⛔️ Команда доступна только Главному Владельцу MOXXI.")

    chat_id = message.chat.id
    chat_title = message.chat.title or "Штаб Стаффа"

    await db.execute(
        "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_hq_chat_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(chat_id),)
    )

    kb = get_duty_keyboard(False)
    welcome_text = (
        f"🏛 <b>ОФИЦИАЛЬНЫЙ ШТАБ СТАФФА MOXXI УСПЕШНО АКТИВИРОВАН!</b>\n\n"
        f"📍 <b>Группа:</b> {html.escape(chat_title)} (<code>{chat_id}</code>)\n"
        f"⚡️ <b>Система дежурств:</b> Подключена и готова к работе.\n"
        f"🛡 <b>Автомодерация:</b> Мгновенный мут за мат и оскорбления активен.\n"
        f"⚠️ <b>Анти-AFK контроль:</b> Автоснятие через 45 минут неактивности.\n\n"
        f"<i>Закрепите это сообщение! Нажмите «🟢 Выйти на смену», чтобы начать дежурство.</i>"
    )

    sent = await message.reply(welcome_text, reply_markup=kb)
    try:
        await bot.pin_chat_message(chat_id, sent.message_id)
    except Exception:
        pass


@router.message(F.text.startswith("!лог канал") | F.text.startswith("/set_mod_log") | F.text.startswith("!привязать логи"))
async def cmd_set_log_channel(message: Message, bot: Bot):
    if not config.is_bot_owner(message.from_user.id):
        return await message.reply("⛔️ Команда доступна только Главному Владельцу MOXXI.")

    parts = message.text.split(maxsplit=1)
    target = parts[1].strip() if len(parts) > 1 else ""

    if not target:
        target_id = message.chat.id
        title = message.chat.title or "Текущий чат"
    else:
        try:
            ch_obj = await bot.get_chat(target)
            target_id = ch_obj.id
            title = ch_obj.title or target
        except Exception as e:
            return await message.reply(f"❌ Не удалось подключиться к каналу: {e}\nУбедитесь, что бот добавлен в канал администратором.")

    await db.execute(
        "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_log_channel_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(target_id),)
    )

    await message.reply(
        f"✅ <b>Канал аудита и логов стаффа успешно привязан!</b>\n"
        f"📢 <b>Канал:</b> {html.escape(title)} (<code>{target_id}</code>)\n"
        f"Сюда будут поступать все выходы на смену, муты, варны и нарушения!"
    )


# ---------------- 1.1 ПРИВЯЗКА ТЕМЫ ИИ-ПОДСКАЗЧИКА В ШТАБЕ СТАФФА ----------------
@router.message(F.text.startswith("!привязать ии") | F.text.startswith("/set_ai_topic") | F.text.startswith("!тема ии"))
async def cmd_set_ai_topic(message: Message, bot: Bot):
    if not config.is_bot_owner(message.from_user.id):
        staff_rank = await db.get_bot_staff_rank(message.from_user.id)
        if staff_rank < 3:
            return await message.reply("⛔️ Привязать тему ИИ может только Владелец или Старший Администратор MOXXI.")

    raw_text = message.text.strip()
    parts = raw_text.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    chat_id = message.chat.id
    thread_id = getattr(message, "message_thread_id", None)

    # Если передана ссылка t.me/c/XXXXX/YYYYY
    if arg and "t.me/c/" in arg:
        import re
        m = re.search(r"t\.me/c/(\d+)/(\d+)", arg)
        if m:
            raw_cid = int(m.group(1))
            chat_id = int(f"-100{raw_cid}") if not str(raw_cid).startswith("-100") else raw_cid
            thread_id = int(m.group(2))

    if not thread_id:
        return await message.reply(
            "⚠️ <b>Как привязать тему ИИ для стаффа:</b>\n\n"
            "<b>Способ 1 (самый простой):</b> Зайдите внутрь темы (топика) для ИИ и напишите там:\n"
            "👉 <code>!привязать ии</code>\n\n"
            "<b>Способ 2 (по ссылке):</b> Отправьте команду со ссылкой на тему:\n"
            "👉 <code>!привязать ии https://t.me/c/1234567890/42</code>"
        )

    await db.execute(
        "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_hq_chat_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(chat_id),)
    )
    await db.execute(
        "INSERT INTO staff_hq_settings (key, value) VALUES ('staff_ai_topic_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(thread_id),)
    )

    await message.reply(
        f"🤖 <b>ТЕМА ИИ-ПОДСКАЗЧИКА ДЛЯ СТАФФА УСПЕШНО ПРИВЯЗАНА!</b>\n\n"
        f"📍 <b>Группа:</b> <code>{chat_id}</code>\n"
        f"🧵 <b>ID Темы (топика):</b> <code>{thread_id}</code>\n\n"
        f"🔥 <b>Как это теперь работает:</b>\n"
        f"Модераторам <b>НЕ НУЖНО</b> писать никаких команд в этой теме!\n"
        f"Просто пересылайте сюда тикеты или пишите любой вопрос — ИИ моментально выдаст действие и готовый шаблон ответа для игрока!"
    )


# ---------------- 2. ПАНЕЛЬ ДЕЖУРКИ (/duty, !дежурка, !смена) ----------------
@router.message(F.text.lower().in_({"/duty", "!дежурка", "!смена", "дежурка", "смена", "!стафф", "/staff"}))
async def cmd_duty_panel(message: Message, bot: Bot):
    uid = message.from_user.id
    name = message.from_user.first_name or "Сотрудник"

    # 1. Защита: команды стаффа и дежурка работают строго в официальном Штабе
    hq_id = await get_staff_hq_id()
    if hq_id and message.chat.id != hq_id and not config.is_bot_owner(uid):
        return await message.reply("⛔️ Панель дежурств и функции стаффа доступны исключительно в официальном Штабе Стаффа MOXXI!")

    # 2. Защита: доступ имеют только одобренные сотрудники из базы данных MOXXI
    staff_rank = await db.get_bot_staff_rank(uid)
    if staff_rank <= 0 and not config.is_bot_owner(uid):
        s_row = await db.fetchone("SELECT rank FROM staff WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
        if not s_row or s_row["rank"] <= 0:
            return await message.reply("⛔️ Доступ запрещён! Вы не состоите в официальной команде администрации MOXXI.")

    member = await get_or_create_staff_member(uid, name)
    is_on = bool(member["is_on_duty"])

    status_icon = "🟢 НА СМЕНЕ" if is_on else "🔴 НЕ НА СМЕНЕ"
    cur_shift = ""
    if is_on and member["duty_start_ts"] > 0:
        elapsed = int(time.time()) - member["duty_start_ts"]
        cur_shift = f"⏱ <b>Текущая смена:</b> <code>{format_duration(elapsed)}</code>\n"

    bar = get_progress_bar(member["total_duty_seconds"])
    vet_badge = "🏅 Ветеран (50ч+)" if member["is_veteran"] else "Обычный"

    text = (
        f"🕒 <b>ПУЛЬТ ДЕЖУРСТВА & СТАФФА MOXXI</b>\n\n"
        f"👤 <b>Сотрудник:</b> {mention_id(uid, name)}\n"
        f"📌 <b>Статус:</b> <b>{status_icon}</b>\n"
        f"{cur_shift}"
        f"⏳ <b>Всего отработано:</b> <code>{format_duration(member['total_duty_seconds'])}</code>\n"
        f"📈 <b>Прогресс до Ветерана:</b>\n<code>{bar}</code>\n"
        f"⚠️ <b>Выговоры (сварны):</b> <code>{member['swarns']}/3</code>\n"
        f"🎖 <b>Статус:</b> <code>{vet_badge}</code>\n\n"
        f"<i>💡 Нажмите кнопку ниже, чтобы начать или завершить дежурство. "
        f"Помните: наказывать нарушителей разрешено строго НА СМЕНЕ!</i>"
    )

    kb = get_duty_keyboard(is_on)
    await message.reply(text, reply_markup=kb)


# ---------------- 3. ОБРАБОТЧИК КНОПОК ДЕЖУРКИ (CALLBACKS) ----------------
@router.callback_query(F.data.startswith("hq_duty:"))
async def cb_duty_actions(call: CallbackQuery, bot: Bot):
    action = call.data.split(":")[1]
    uid = call.from_user.id
    name = call.from_user.first_name or "Сотрудник"

    # 1. Защита: действия доступны только в официальном Штабе
    hq_id = await get_staff_hq_id()
    if hq_id and call.message and call.message.chat.id != hq_id and not config.is_bot_owner(uid):
        return await call.answer("⛔️ Действие доступно только в официальном Штабе Стаффа MOXXI!", show_alert=True)

    # 2. Защита: доступ имеют только одобренные сотрудники
    staff_rank = await db.get_bot_staff_rank(uid)
    if staff_rank <= 0 and not config.is_bot_owner(uid):
        s_row = await db.fetchone("SELECT rank FROM staff WHERE chat_id=? AND user_id=?", (call.message.chat.id if call.message else 0, uid))
        if not s_row or s_row["rank"] <= 0:
            return await call.answer("⛔️ Вы не состоите в команде администрации MOXXI!", show_alert=True)

    member = await get_or_create_staff_member(uid, name)
    now = int(time.time())

    if action == "start":
        if member["is_on_duty"]:
            return await call.answer("ℹ️ Вы уже находитесь на смене!", show_alert=True)

        await db.execute(
            "UPDATE staff_duty_members SET is_on_duty=1, duty_start_ts=?, last_activity_ts=?, user_name=? WHERE user_id=?",
            (now, now, name, uid)
        )
        await db.execute(
            "INSERT INTO staff_duty_logs (user_id, user_name, action, duration_sec, total_sec, ts) VALUES (?, ?, 'start', 0, ?, ?)",
            (uid, name, member["total_duty_seconds"], now)
        )

        await call.answer("🟢 Смена успешно начата! Доступ к модерации активен.", show_alert=True)

        # Лог админам
        log_text = (
            f"🟢 <b>[ЗАСТУПИЛ НА СМЕНУ]</b>\n"
            f"👤 Сотрудник: {mention_id(uid, name)} (ID: <code>{uid}</code>)\n"
            f"🕒 Время начала: {time.strftime('%H:%M:%S (%d.%m.%Y)', time.localtime(now))}\n"
            f"🏆 Общий стаж: <code>{format_duration(member['total_duty_seconds'])}</code>"
        )
        await send_staff_log(bot, log_text)

    elif action == "end":
        if not member["is_on_duty"]:
            return await call.answer("ℹ️ Вы сейчас не на смене.", show_alert=True)

        start_ts = member["duty_start_ts"] or now
        shift_duration = max(0, now - start_ts)
        new_total = member["total_duty_seconds"] + shift_duration

        await db.execute(
            "UPDATE staff_duty_members SET is_on_duty=0, duty_start_ts=0, total_duty_seconds=?, user_name=? WHERE user_id=?",
            (new_total, name, uid)
        )
        await db.execute(
            "INSERT INTO staff_duty_logs (user_id, user_name, action, duration_sec, total_sec, ts) VALUES (?, ?, 'end', ?, ?, ?)",
            (uid, name, shift_duration, new_total, now)
        )

        await call.answer(
            f"🔴 Смена завершена!\nОтработано за смену: {format_duration(shift_duration)}\nВсего в стаффе: {format_duration(new_total)}",
            show_alert=True
        )

        # Проверка 50 часов на Ветерана
        vet_notify = ""
        if new_total >= VETERAN_SECONDS and not member["is_veteran"] and member["swarns"] == 0:
            vet_notify = (
                f"\n\n🎉 <b>НОМИНАЦИЯ В ВЕТЕРАНЫ СТАФФА (50+ ЧАСОВ)!</b>\n"
                f"Модератор {mention_id(uid, name)} преодолел рубеж 50 часов без единого выговора!"
            )

        log_text = (
            f"🔴 <b>[СМЕНА ЗАВЕРШЕНА]</b>\n"
            f"👤 Сотрудник: {mention_id(uid, name)}\n"
            f"⏱ Отработано за смену: <code>{format_duration(shift_duration)}</code>\n"
            f"🏆 Общий стаж: <code>{format_duration(new_total)}</code>\n"
            f"📈 Прогресс: <code>{get_progress_bar(new_total)}</code>"
            f"{vet_notify}"
        )
        await send_staff_log(bot, log_text)

    elif action == "my_stats":
        bar = get_progress_bar(member["total_duty_seconds"])
        ans = (
            f"📊 ВАШЕ ДОСЬЕ ДЕЖУРСТВ:\n\n"
            f"• Статус: {'🟢 На смене' if member['is_on_duty'] else '🔴 Не на смене'}\n"
            f"• Отработано всего: {format_duration(member['total_duty_seconds'])}\n"
            f"• Прогресс 50ч: {bar}\n"
            f"• Выговоры (сварны): {member['swarns']}/3\n"
            f"• Звание Ветерана: {'Да 🏅' if member['is_veteran'] else 'В процессе'}"
        )
        return await call.answer(ans, show_alert=True)

    elif action == "who":
        rows = await db.fetchall("SELECT user_id, user_name, duty_start_ts FROM staff_duty_members WHERE is_on_duty=1")
        if not rows:
            return await call.answer("На смене сейчас никого нет. Будьте первым!", show_alert=True)

        lines = ["👥 СЕЙЧАС НА СМЕНЕ:"]
        for r in rows:
            t = format_duration(max(0, now - r["duty_start_ts"]))
            lines.append(f"• {r['user_name']} (на смене: {t})")

        return await call.answer("\n".join(lines), show_alert=True)

    elif action == "ai_helper":
        ans = (
            "🤖 ИИ-КОПИЛОТ МОДЕРАТОРА MOXXI:\n\n"
            "• Спам/флуд -> Мут от 15 минут до 1 часа.\n"
            "• Оскорбления/мат -> Мут от 30 минут до 2 часов.\n"
            "• Реклама/скам -> Вечный бан.\n"
            "• Багоюз -> Бан + обнуление.\n\n"
            "Команда для мута: мут [время] [причина]\n"
            "Пример: мут 30м оскорбления"
        )
        return await call.answer(ans, show_alert=True)

    # Обновляем сообщение пульта
    updated_member = await get_or_create_staff_member(uid, name)
    is_on_now = bool(updated_member["is_on_duty"])

    cur_shift = ""
    if is_on_now and updated_member["duty_start_ts"] > 0:
        elapsed = int(time.time()) - updated_member["duty_start_ts"]
        cur_shift = f"⏱ <b>Текущая смена:</b> <code>{format_duration(elapsed)}</code>\n"

    bar = get_progress_bar(updated_member["total_duty_seconds"])
    vet_badge = "🏅 Ветеран (50ч+)" if updated_member["is_veteran"] else "Обычный"

    text = (
        f"🕒 <b>ПУЛЬТ ДЕЖУРСТВА & СТАФФА MOXXI</b>\n\n"
        f"👤 <b>Сотрудник:</b> {mention_id(uid, name)}\n"
        f"📌 <b>Статус:</b> <b>{'🟢 НА СМЕНЕ' if is_on_now else '🔴 НЕ НА СМЕНЕ'}</b>\n"
        f"{cur_shift}"
        f"⏳ <b>Всего отработано:</b> <code>{format_duration(updated_member['total_duty_seconds'])}</code>\n"
        f"📈 <b>Прогресс до Ветерана:</b>\n<code>{bar}</code>\n"
        f"⚠️ <b>Выговоры (сварны):</b> <code>{updated_member['swarns']}/3</code>\n"
        f"🎖 <b>Статус:</b> <code>{vet_badge}</code>\n\n"
        f"<i>💡 Нажмите кнопку ниже, чтобы начать или завершить дежурство.</i>"
    )

    try:
        await call.message.edit_text(text, reply_markup=get_duty_keyboard(is_on_now))
    except Exception:
        pass


async def handle_staff_ai_topic_message(message: Message, bot: Bot):
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    chat_id = message.chat.id
    thread_id = getattr(message, "message_thread_id", None)

    try:
        await bot.send_chat_action(chat_id, "typing", message_thread_id=thread_id)
    except Exception:
        pass

    prompt = text
    if message.reply_to_message:
        r_text = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
        if r_text:
            prompt = f"Контекст обращения игрока:\n{r_text}\n\nВопрос/уточнение модератора:\n{text}"

    loop = asyncio.get_running_loop()
    raw_res = await loop.run_in_executor(None, _sync_query_gemini, prompt)

    if not raw_res:
        raw_res = (
            "💡 <b>ДЕЙСТВИЕ МОДЕРАТОРА:</b>\n"
            "Запросите детали ситуации у игрока (ID, никнейм, скриншот или чек оплаты).\n\n"
            "📋 <b>ГОТОВЫЙ ШАБЛОН ОТВЕТА ДЛЯ ИГРОКА:</b>\n"
            "<code>Здравствуйте! Пожалуйста, уточните ваш игровой ID и подробно опишите возникшую проблему. Мы обязательно поможем вам!</code>"
        )

    formatted = raw_res.replace("```text", "<code>").replace("```html", "<code>").replace("```", "</code>")
    await message.reply(formatted, message_thread_id=thread_id, disable_web_page_preview=True)


# ---------------- 4. АВТОМОДЕРАЦИЯ ОСКОРБЛЕНИЙ И МАТА С МГНОВЕННЫМ МУТОМ ----------------
@router.message(F.text, F.chat.type.in_({"group", "supergroup"}))
async def automod_filter_and_duty_check(message: Message, bot: Bot):
    if not message.from_user or message.from_user.is_bot:
        return

    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"
    text = message.text or ""
    chat_id = message.chat.id
    chat_title = message.chat.title or "Группа"

    # 0. ПРОВЕРКА НА ТЕМУ ИИ В ШТАБЕ СТАФФА (ОТВЕТ БЕЗ КОМАНД, АВТОМОД ОТКЛЮЧЕН):
    staff_cid, staff_tid = await get_ai_topic_info()
    msg_tid = getattr(message, "message_thread_id", None)
    if staff_cid and chat_id == staff_cid and staff_tid and msg_tid == staff_tid:
        if text.startswith("!") or text.startswith("/"):
            return  # Пропускаем команды к роутеру команд
        await handle_staff_ai_topic_message(message, bot)
        return

    # Если пишет сотрудник на смене — сбрасываем AFK-таймер
    await update_staff_activity(uid)

    # Проверка на команды модерации: если модератор пытается наказать, но не на смене
    lower_t = text.lower().strip()
    is_punish_cmd = any(lower_t.startswith(prefix) for prefix in ["мут ", "бан ", "варн ", "кик ", "/mute", "/ban", "/warn"])
    if is_punish_cmd and not config.is_bot_owner(uid):
        # Проверяем, является ли пользователь персоналом чата
        row = await db.fetchone("SELECT rank FROM staff WHERE chat_id=? AND (user_id=? OR username=?)",
                                (chat_id, uid, (message.from_user.username or "").lower()))
        rank = row["rank"] if row else 0
        if rank > 0:
            on_duty = await is_user_on_duty(uid)
            if not on_duty:
                return await message.reply(
                    f"⛔️ <b>Действие заблокировано!</b>\n\n"
                    f"Модератор {mention_id(uid, name)}, вы сейчас <b>НЕ НА СМЕНЕ</b>!\n"
                    f"Чтобы наказывать участников чата, сначала заступите на смену:\n"
                    f"👉 Отправьте <code>/duty</code> и нажмите <b>«🟢 Выйти на смену»</b>."
                )

    # Владельцев бота не проверяем на автомод (иммунитет создателя)
    if config.is_bot_owner(uid):
        return

    # Проверяем, является ли нарушитель сотрудником стаффа
    staff_row = await db.fetchone(
        "SELECT rank FROM staff WHERE chat_id=? AND (user_id=? OR username=?)",
        (chat_id, uid, (message.from_user.username or "").lower())
    )
    is_staff = bool(staff_row and staff_row["rank"] > 0)
    staff_rank = staff_row["rank"] if staff_row else 0

    # Проверка текста на токсичность, мат и оскорбления
    level, reason = toxicity.detect(text)
    if level >= 2:  # 2 = оскорбление, 3 = мат / угроза
        mute_seconds = 1800  # 30 минут
        until_date = int(time.time()) + mute_seconds

        # 1. Мгновенно применяем мут через Telegram API
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=uid,
                permissions=MUTE_PERMISSIONS,
                until_date=until_date
            )
            mute_applied = True
        except Exception as e:
            log.warning("Не удалось замутить пользователя %s в чате %s: %s", uid, chat_id, e)
            mute_applied = False

        # 2. Удаляем сообщение с оскорблением
        try:
            await message.delete()
        except Exception:
            pass

        # 3. ЕСЛИ НАРУШИТЕЛЬ — МОДЕРАТОР/СТАФФ (СТРОГО ЗАПРЕЩЕНО ОСКОРБЛЯТЬ ИГРОКОВ!):
        if is_staff:
            member = await get_or_create_staff_member(uid, name)
            new_swarns = member["swarns"] + 1

            # Принудительно завершаем смену, если был на смене
            shift_dur = 0
            if member["is_on_duty"] and member["duty_start_ts"] > 0:
                shift_dur = max(0, int(time.time()) - member["duty_start_ts"])
            new_total = member["total_duty_seconds"] + shift_dur

            await db.execute(
                "UPDATE staff_duty_members SET is_on_duty=0, duty_start_ts=0, total_duty_seconds=?, swarns=? WHERE user_id=?",
                (new_total, new_swarns, uid)
            )

            # Авто-снятие с должности при 3/3 выговорах (как в Discord!)
            dismissal_notice = ""
            if new_swarns >= 3:
                await db.execute("DELETE FROM ranks WHERE chat_id=? AND user_id=?", (chat_id, uid))
                await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (chat_id, uid))
                dismissal_notice = "\n❌ <b>СОТРУДНИК СНЯТ С ДОЛЖНОСТИ</b> за достижение лимита выговоров (3/3)!"

            # Публичное сообщение в чат
            if mute_applied:
                notify_msg = (
                    f"🔇 <b>Модератор {mention_id(uid, name)} отправлен в мут на 30 минут за оскорбление игрока!</b>\n"
                    f"⚡️ <b>Дисциплинарное взыскание:</b> Снят со смены + начислен выговор (<b>{new_swarns}/3</b> сварн)."
                    f"{dismissal_notice}\n"
                    f"🛡 <i>В MOXXI модераторам строго запрещено проявлять агрессию и оскорблять игроков!</i>"
                )
                try:
                    await bot.send_message(chat_id, notify_msg)
                except Exception:
                    pass

            # Экстренный лог руководству
            log_text = (
                f"🚨 <b>[ЧП: МОДЕРАТОР ОСКОРБИЛ ИГРОКА / МАТ В ЧАТЕ]</b>\n\n"
                f"👮 <b>Модератор:</b> {mention_id(uid, name)} (Ранг: <code>{staff_rank}</code>)\n"
                f"📍 <b>Чат:</b> {html.escape(chat_title)} (<code>{chat_id}</code>)\n"
                f"⏱ <b>Наказание:</b> Мут на 30 минут\n"
                f"⚡️ <b>Статус:</b> Принудительно снят со смены + выговор (<b>{new_swarns}/3</b>)"
                f"{dismissal_notice}\n"
                f"💬 <b>Цитата:</b>\n"
                f"<blockquote>{html.escape(text[:300])}</blockquote>\n"
                f"🕒 Время: {time.strftime('%H:%M:%S', time.localtime())}"
            )
            return await send_staff_log(bot, log_text)

        # 4. ОБЫЧНЫЙ ИГРОК (МАТ / ОСКОРБЛЕНИЯ):
        if mute_applied:
            notify_msg = (
                f"🔇 {mention_id(uid, name)} отправлен в <b>мут на 30 минут</b>.\n"
                f"📝 <b>Причина:</b> Оскорбления / Нецензурная брань\n"
                f"🛡 <i>Автомодерация MOXXI Shield</i>"
            )
            try:
                await bot.send_message(chat_id, notify_msg)
            except Exception:
                pass

        unmute_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔓 Снять мут (ошибка)", callback_data=f"hq_unmute:{chat_id}:{uid}")
        ]])

        log_text = (
            f"🚨 <b>[АВТОМОД: МУТ ЗА ОСКОРБЛЕНИЯ / МАТ]</b>\n\n"
            f"👤 <b>Нарушитель:</b> {mention_id(uid, name)} (ID: <code>{uid}</code>)\n"
            f"📍 <b>Чат:</b> {html.escape(chat_title)} (<code>{chat_id}</code>)\n"
            f"⏱ <b>Срок:</b> 30 минут\n"
            f"⚠️ <b>Тип:</b> {reason}\n"
            f"💬 <b>Текст нарушения:</b>\n"
            f"<blockquote>{html.escape(text[:300])}</blockquote>\n"
            f"🕒 Время: {time.strftime('%H:%M:%S', time.localtime())}"
        )
        await send_staff_log(bot, log_text, reply_markup=unmute_kb)


# ---------------- 5. СНЯТИЕ МУТА ИЗ ЛОГ-КАНАЛА ПО КНОПКЕ ----------------
@router.callback_query(F.data.startswith("hq_unmute:"))
async def cb_unmute_from_log(call: CallbackQuery, bot: Bot):
    if not config.is_bot_owner(call.from_user.id):
        return await call.answer("⛔️ Только Главное Руководство может отменять мут из лога.", show_alert=True)

    parts = call.data.split(":")
    chat_id = int(parts[1])
    target_uid = int(parts[2])

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_uid,
            permissions=UNMUTE_PERMISSIONS
        )
        await call.answer("✅ Мут успешно снят!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.reply(f"🟢 Мут снят администратором {mention_id(call.from_user.id, call.from_user.first_name)}.")
    except Exception as e:
        await call.answer(f"❌ Ошибка снятия мута: {e}", show_alert=True)


# ---------------- 6. АНТИ-AFK WATCHDOG (ФОНОВЫЙ ПРОЦЕСС) ----------------
async def staff_afk_watchdog_loop(bot: Bot):
    """Каждые 60 секунд проверяет сотрудников на смене. При AFK > 45 мин — автоснятие + сварн."""
    await asyncio.sleep(15)  # Пауза перед стартом
    while True:
        try:
            now = int(time.time())
            rows = await db.fetchall("SELECT * FROM staff_duty_members WHERE is_on_duty=1")
            for r in rows:
                last_act = r["last_activity_ts"] or r["duty_start_ts"] or now
                inactive_sec = now - last_act

                if inactive_sec >= AFK_TIMEOUT_SECONDS:
                    uid = r["user_id"]
                    name = r["user_name"]
                    shift_dur = max(0, now - r["duty_start_ts"])
                    new_total = r["total_duty_seconds"] + shift_dur
                    new_swarns = r["swarns"] + 1

                    await db.execute(
                        "UPDATE staff_duty_members SET is_on_duty=0, duty_start_ts=0, total_duty_seconds=?, swarns=? WHERE user_id=?",
                        (new_total, new_swarns, uid)
                    )
                    await db.execute(
                        "INSERT INTO staff_duty_logs (user_id, user_name, action, duration_sec, total_sec, ts) VALUES (?, ?, 'afk_kick', ?, ?, ?)",
                        (uid, name, shift_dur, new_total, now)
                    )

                    alert_text = (
                        f"⚠️ <b>[АНТИ-AFK: АВТОСНЯТИЕ СО СМЕНЫ]</b>\n\n"
                        f"👮 <b>Модератор:</b> {mention_id(uid, name)} (ID: <code>{uid}</code>)\n"
                        f"⏱ <b>Время неактивности:</b> <code>{format_duration(inactive_sec)}</code> (Лимит: 45м)\n"
                        f"⚡️ <b>Дисциплинарное взыскание:</b> Начислен выговор (+1 сварн)\n"
                        f"📊 <b>Всего выговоров:</b> <b>{new_swarns}/3</b>\n"
                        f"🕒 Время: {time.strftime('%H:%M:%S', time.localtime(now))}"
                    )
                    await send_staff_log(bot, alert_text)

        except Exception as e:
            log.error("Ошибка в staff_afk_watchdog_loop: %s", e)

        await asyncio.sleep(60)


# ---------------- 7. ИИ-КОПИЛОТ ДЛЯ ТИКЕТОВ И ВОПРОСОВ (!ии, /ai) ----------------
import json
import os
import re
import urllib.request
import urllib.error

_AI_KEY_IDX = 0
GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
]


def _get_api_keys() -> list[str]:
    raw = os.getenv("AI_API_KEY", "")
    return [k.strip() for k in re.split(r"[,;\s]+", raw) if k.strip()]


def _get_next_ai_key() -> str:
    global _AI_KEY_IDX
    keys = _get_api_keys()
    if not keys:
        return ""
    k = keys[_AI_KEY_IDX % len(keys)]
    _AI_KEY_IDX = (_AI_KEY_IDX + 1) % len(keys)
    return k


def _sync_query_gemini(prompt: str) -> Optional[str]:
    keys = _get_api_keys()
    if not keys:
        return None

    sys_text = (
        "Ты — официальный ИИ-ассистент (Staff AI Copilot) для команды модерации и службы поддержки игрового бота MOXXI.\n"
        "Сотрудник присылает тебе вопрос игрока или тему тикета. Отвечай СТРОГО в двух блоках:\n\n"
        "💡 <b>ДЕЙСТВИЕ МОДЕРАТОРА:</b>\n(кратко: что проверить)\n\n"
        "📋 <b>ГОТОВЫЙ ШАБЛОН ОТВЕТА ДЛЯ ИГРОКА:</b>\n"
        "<code>(вежливый, официальный ответ игроку от поддержки MOXXI на Вы, без грубости и оскорблений)</code>"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt[:3000]}]}],
        "system_instruction": {"parts": [{"text": sys_text}]},
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    for _ in range(len(keys)):
        k = _get_next_ai_key()
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
            req = urllib.request.Request(url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    cands = res_data.get("candidates") or []
                    if not cands:
                        continue
                    parts = cands[0].get("content", {}).get("parts") or []
                    clean_parts = [p for p in parts if not p.get("thought")]
                    if not clean_parts:
                        clean_parts = parts
                    text = "".join(p.get("text", "") for p in clean_parts).strip()
                    text = re.sub(r"<thought>[\s\S]*?</thought>", "", text, flags=re.IGNORECASE).strip()
                    if text:
                        return text
            except Exception:
                continue
    return None


@router.message(F.text.startswith("!ии") | F.text.startswith("/ai") | F.text.startswith("!копилот"))
async def cmd_ai_helper_tg(message: Message, bot: Bot):
    if not config.is_bot_owner(message.from_user.id):
        return await message.reply("⛔️ Команда «ии» доступна только Главному Владельцу проекта.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply(
            "🤖 <b>ИИ-Копилот (доступ Владельца):</b>\n\n"
            "Напишите вопрос или скиньте текст тикета игрока, на который нужно ответить:\n"
            "👉 <code>!ии игрок жалуется, что донат не зачислился на баланс</code>\n"
            "👉 <code>!ии как наказать за рекламу другого бота в чате?</code>"
        )

    query = parts[1].strip()
    status_msg = await message.reply("⏳ <i>ИИ-Копилот анализирует вопрос и готовит ответ...</i>")

    loop = asyncio.get_running_loop()
    raw_res = await loop.run_in_executor(None, _sync_query_gemini, query)

    if not raw_res:
        raw_res = (
            "💡 <b>ДЕЙСТВИЕ МОДЕРАТОРА:</b>\n"
            "Уточните игровой ID пользователя и запросите чек/скриншот.\n\n"
            "📋 <b>ГОТОВЫЙ ШАБЛОН ОТВЕТА ДЛЯ ИГРОКА:</b>\n"
            "<code>Здравствуйте! Пожалуйста, укажите ваш игровой ID и пришлите чек оплаты. Мы обязательно разберёмся в ситуации!</code>"
        )

    formatted = raw_res.replace("```text", "<code>").replace("```", "</code>")
    await status_msg.edit_text(formatted)
