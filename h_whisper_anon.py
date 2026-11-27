"""
Модуль «Шёпот», «Анонимка» и «Детектор Лжи» — трендовые фишки для бесед Telegram.
1. `шепот @юзер текст` / `шёпот текст` (ответом) — секретное сообщение в чате.
   Оригинальное сообщение удаляется, в чат отправляется кнопка «📩 Читать шёпот».
   Текст видит ТОЛЬКО получатель и автор во всплывающем alert. Остальные получают отказ!
2. `анон шепот @юзер текст` — тайный шёпот, где автор скрыт («Аноним»).
3. `анонимка @юзер текст` — анонимное признание/валентинка в чат с кнопкой ответа.
4. `детектор` / `детектор лжи` (ответом на сообщение) — анализ правды/лжи с юмором.
"""
from __future__ import annotations

import html
import random
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_registry import Cmd
from core_resolve import resolve_target
from utils import mention, mention_id

router = Router(name="whisper_anon")
S = 18  # Раздел: Общение и развлечения

# Таблица для хранения шёпотов и анонимок
async def init_whisper_tables():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_whispers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            target_name TEXT NOT NULL,
            is_anon INTEGER NOT NULL DEFAULT 0,
            text TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_anon_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            target_name TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)


@router.message(Cmd("шепот", "шёпот", "секрет", "приват", section=S, group_only=True,
                    usage="шепот @юзер текст", desc="Отправить секретное сообщение, видимое только адресату"))
async def cmd_whisper(message: Message, bot: Bot, args: str = "", **kw):
    await init_whisper_tables()
    is_anon = False
    raw_args = (args or "").strip()

    # Проверяем цель
    target_id = 0
    target_name = ""
    whisper_text = ""

    # Если ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if target_user.id == message.from_user.id:
            return await message.reply("😅 Зачем шептать самому себе? Скажи это вслух!")
        target_id = target_user.id
        target_name = target_user.first_name or f"ID:{target_id}"
        whisper_text = raw_args
    else:
        # Парсим @юзер текст
        parts = raw_args.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply(
                "🤫 <b>Как отправить шёпот:</b>\n\n"
                "• Ответом на сообщение: <code>шепот твой секретный текст</code>\n"
                "• По юзернейму: <code>шепот @юзер твой секретный текст</code>\n"
                "• Анонимный шёпот: <code>анон шепот @юзер текст</code>\n\n"
                "💡 <i>Бот удалит ваше сообщение, а прочитать шёпот сможет ТОЛЬКО тот, кому вы написали!</i>"
            )
        uid, name, _ = await resolve_target(message, parts[0], bot)
        if not uid or uid == message.from_user.id:
            return await message.reply("⚠️ Не удалось найти получателя шёпота или вы указали себя.")
        target_id = uid
        target_name = name
        whisper_text = parts[1].strip()

    if not whisper_text:
        return await message.reply("⚠️ Напишите текст шёпота!")

    # Удаляем исходное сообщение отправителя для полной приватности
    try:
        await message.delete()
    except Exception:
        pass

    sender_name = message.from_user.first_name or f"ID:{message.from_user.id}"
    now = int(time.time())

    await db.execute(
        "INSERT INTO chat_whispers (chat_id, sender_id, target_id, sender_name, target_name, is_anon, text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (message.chat.id, message.from_user.id, target_id, sender_name, target_name, 0, whisper_text, now)
    )
    row = await db.fetchone("SELECT last_insert_rowid() as id")
    w_id = int(row["id"]) if row else 0

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤫 Читать шёпот 👁", callback_data=f"read_whisper:{w_id}")
        ]
    ])

    text = (
        f"🤫 <b>ШЁПОТ В БЕСЕДЕ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>От:</b> {mention(message.from_user)}\n"
        f"🎯 <b>Кому:</b> {mention_id(target_id, target_name)}\n\n"
        f"🔒 <i>Содержимое скрыто. Нажмите кнопку ниже, чтобы прочитать. "
        f"Только {html.escape(target_name)} и автор смогут увидеть текст!</i>"
    )
    await message.answer(text, reply_markup=kb)


@router.message(Cmd("анон шепот", "анонимный шепот", section=S, group_only=True,
                    usage="анон шепот @юзер текст", desc="Отправить секретный шёпот инкогнито"))
async def cmd_anon_whisper(message: Message, bot: Bot, args: str = "", **kw):
    await init_whisper_tables()
    raw_args = (args or "").strip()

    target_id = 0
    target_name = ""
    whisper_text = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.first_name or f"ID:{target_id}"
        whisper_text = raw_args
    else:
        parts = raw_args.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("🤫 Укажите получателя и текст: <code>анон шепот @юзер привет</code>")
        uid, name, _ = await resolve_target(message, parts[0], bot)
        if not uid or uid == message.from_user.id:
            return await message.reply("⚠️ Не удалось найти адресата.")
        target_id = uid
        target_name = name
        whisper_text = parts[1].strip()

    if not whisper_text:
        return await message.reply("⚠️ Напишите текст шёпота!")

    try:
        await message.delete()
    except Exception:
        pass

    now = int(time.time())
    await db.execute(
        "INSERT INTO chat_whispers (chat_id, sender_id, target_id, sender_name, target_name, is_anon, text, created_at) "
        "VALUES (?, ?, ?, 'Аноним', ?, 1, ?, ?)",
        (message.chat.id, message.from_user.id, target_id, target_name, whisper_text, now)
    )
    row = await db.fetchone("SELECT last_insert_rowid() as id")
    w_id = int(row["id"]) if row else 0

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎭 Читать анонимный шёпот 👁", callback_data=f"read_whisper:{w_id}")
        ]
    ])

    text = (
        f"🎭 <b>АНОНИМНЫЙ ШЁПОТ В БЕСЕДЕ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>От:</b> <i>Тайный доброжелатель (Аноним)</i>\n"
        f"🎯 <b>Кому:</b> {mention_id(target_id, target_name)}\n\n"
        f"🔒 <i>Только {html.escape(target_name)} сможет прочитать этот секрет!</i>"
    )
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("read_whisper:"))
async def on_read_whisper(cb: CallbackQuery):
    w_id = int(cb.data.split(":")[1])
    row = await db.fetchone("SELECT * FROM chat_whispers WHERE id = ?", (w_id,))
    if not row:
        return await cb.answer("⚠️ Этот шёпот устарел или был удалён.", show_alert=True)

    uid = cb.from_user.id
    sender_id = row["sender_id"]
    target_id = row["target_id"]

    if uid != target_id and uid != sender_id:
        # Другой участник чата пытается подсмотреть чужой секрет
        roasts = [
            "🚫 Любопытной варваре на базаре нос оторвали!",
            "❌ Этот шёпот предназначен не для твоих глаз!",
            "👀 Чужие секреты читать нехорошо! Шёпот закрыт.",
            "🔒 Доступ запрещен! Только адресат и автор могут открыть это сообщение.",
            "🤐 Тссс! Это личная тайна между ними, не подглядывай!"
        ]
        return await cb.answer(random.choice(roasts), show_alert=True)

    # Показываем шёпот в модальном окне Telegram (alert)
    author_label = "Анонимный отправитель" if row["is_anon"] else row["sender_name"]
    alert_text = (
        f"🤫 ШЁПОТ ДЛЯ {row['target_name'].upper()}:\n\n"
        f"«{row['text']}»\n\n"
        f"👤 Автор: {author_label}"
    )
    await cb.answer(alert_text, show_alert=True)


# ════════════════════════ 2. АНОНИМНЫЕ ПИСЬМА И ВАЛЕНТИНКИ ════════════════════════

@router.message(Cmd("анонимка", "валентинка", "тайное признание", "признание", section=S, group_only=True,
                    usage="анонимка @юзер текст", desc="Отправить анонимное признание в беседу с кнопкой ответа"))
async def cmd_anon_letter(message: Message, bot: Bot, args: str = "", **kw):
    await init_whisper_tables()
    raw_args = (args or "").strip()

    target_id = 0
    target_name = ""
    letter_text = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if target_user.id == message.from_user.id:
            return await message.reply("😅 Нельзя отправить анонимку самому себе.")
        target_id = target_user.id
        target_name = target_user.first_name or f"ID:{target_id}"
        letter_text = raw_args
    else:
        parts = raw_args.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply(
                "💌 <b>Как отправить анонимку в чат:</b>\n\n"
                "• <code>анонимка @юзер твой текст признания или вопрос</code>\n"
                "• Ответом на сообщение: <code>анонимка текст</code>\n\n"
                "✨ <i>Бот удалит ваше сообщение, опубликует красивую карточку в чате "
                "и даст адресату возможность анонимно ответить вам в ЛС!</i>"
            )
        uid, name, _ = await resolve_target(message, parts[0], bot)
        if not uid or uid == message.from_user.id:
            return await message.reply("⚠️ Не удалось найти адресата или вы указали себя.")
        target_id = uid
        target_name = name
        letter_text = parts[1].strip()

    if not letter_text:
        return await message.reply("⚠️ Напишите текст анонимного послания!")

    try:
        await message.delete()
    except Exception:
        pass

    now = int(time.time())
    await db.execute(
        "INSERT INTO chat_anon_letters (chat_id, sender_id, target_id, target_name, text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message.chat.id, message.from_user.id, target_id, target_name, letter_text, now)
    )
    row = await db.fetchone("SELECT last_insert_rowid() as id")
    letter_id = int(row["id"]) if row else 0

    bot_info = await bot.me()
    reply_url = f"https://t.me/{bot_info.username}?start=anon_reply_{letter_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💌 Ответить анониму в ЛС бота 💬", url=reply_url)
        ]
    ])

    text = (
        f"💌 <b>ТАЙНОЕ ПОСЛАНИЕ В БЕСЕДЕ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🎯 <b>Адресовано:</b> {mention_id(target_id, target_name)}\n"
        f"👤 <b>Отправитель:</b> <i>Тайный воздыхатель (Аноним)</i>\n\n"
        f"📝 <b>Текст послания:</b>\n"
        f"«<i>{html.escape(letter_text)}</i>»\n\n"
        f"💖 <i>Если хотите ответить тайному отправителю — нажмите кнопку ниже!</i>"
    )
    await message.answer(text, reply_markup=kb)


# ════════════════════════ 3. ДЕТЕКТОР ЛЖИ И ПОЛИГРАФ ════════════════════════

@router.message(Cmd("детектор лжи", "детектор", "полиграф", "проверить на ложь", section=S,
                    usage="детектор [ответом на сообщение]", desc="Проверить сообщение участника на детекторе лжи"))
async def cmd_lie_detector(message: Message, **kw):
    target_msg = message.reply_to_message
    if not target_msg or not target_msg.text:
        return await message.reply("🔎 Ответьте командой <code>детектор</code> на текстовое сообщение участника, чтобы проверить его на правду!")

    target_user = target_msg.from_user
    u_name = target_user.first_name if target_user else "Собеседник"

    # Анализируем текст
    t = target_msg.text.strip().lower()
    seed = (hash(t) + target_msg.message_id) % 101
    percent_truth = abs(seed)

    # Имитируем сканирование
    if percent_truth >= 85:
        verdict = "🟢 <b>КРИСТАЛЬНАЯ ПРАВДА!</b> (100% честность)"
        comment = "Пульс в норме, зрачки спокойные. Человек говорит чистую истину!"
    elif percent_truth >= 55:
        verdict = f"🟡 <b>СКОРЕЕ ПРАВДА ({percent_truth}%)</b>"
        comment = "Небольшие колебания голоса, но в целом факты сходятся."
    elif percent_truth >= 30:
        verdict = f"🟠 <b>ПОЛУПРАВДА / ПРИУКРАСИЛ ({percent_truth}%)</b>"
        comment = "Датчик давления зашкаливает. Тут явно приврали для красного словца!"
    else:
        verdict = f"🔴 <b>НАГЛЫЙ ПИЗДЁЖ! ({100 - percent_truth}% ЛЖИ)</b>"
        comment = "🚨 Полиграф задымился! Детектор фиксирует чудовищный уровень сказок."

    text = (
        f"🔬 <b>ПОЛИГРАФ MOXXI • ДЕТЕКТОР ЛЖИ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Подопытный: {mention(target_user)}\n"
        f"💬 Фраза: «<i>{html.escape(target_msg.text[:120])}</i>»\n\n"
        f"📊 <b>Результат анализа биометрии:</b>\n"
        f"• Достоверность: <b>{percent_truth}%</b>\n"
        f"• Вердикт: {verdict}\n"
        f"💡 <i>{comment}</i>"
    )
    await message.reply(text)
