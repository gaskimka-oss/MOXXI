"""Модуль зимнего сезона «Новый Год 2027»: Новогодняя Ёлка в группах, квесты со звёздами Stars, Битва за Буст 10 LVL и снежки."""
from __future__ import annotations

import asyncio
import html
import random
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message)

import config
import db
from core_registry import Cmd
from utils import mention, mention_id

router = Router(name="winter_event")

# Временные метки (Europe/Moscow, UTC+3)
# 1 декабря 2026, 00:00:00 MSK
WINTER_START_TS = 1796072400
# 1 января 2027, 00:00:00 MSK
WINTER_END_TS   = 1798750800

# Тестовый режим для владельца бота (Гасима)
_winter_test_mode: bool = False

# Кулдаун на броски снежками (user_id -> timestamp)
_snowball_cooldowns: dict[int, float] = {}


def is_winter_active() -> bool:
    """Проверяет, активен ли новогодний сезон (наступило 1 декабря 00:00 или включен тест владельца)."""
    if _winter_test_mode:
        return True
    return time.time() >= WINTER_START_TS


def time_until_str(target_ts: int) -> str:
    """Форматирует оставшееся время в днях, часах и минутах."""
    diff = int(target_ts - time.time())
    if diff <= 0:
        return "0 дн. 0 ч. 0 мин."
    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    return f"{days} дн. {hours} ч. {minutes} мин."


def _get_tree_art(level: int) -> str:
    """Генерирует визуальный рисунок ёлки в зависимости от уровня."""
    arts = {
        1: "     ⭐\n    / ❄️ \\\n   /  🎄  \\\n     |||",
        2: "     ⭐\n    / ❄️ \\\n   / 🔔 🎁 \\\n  /  🎄✨  \\\n     |||",
        3: "     🌟\n    / ❄️ 🔔 \\\n   / 🎁 🎄 ❄️ \\\n  / ✨ 🎀 💎 \\\n     |||",
        4: "     🌟\n    / ❄️ 🎀 \\\n   / 🎁 🎄 🔔 \\\n  / 💎 ✨ ❄️ 🎁 \\\n / 🌟 🎀 🎄 💎 \\\n     |||",
        5: "     ✨🌟✨\n    /  ❄️ 🎀  \\\n   / 🎁 🎄 🔔 \\\n  / 💎 ✨ ❄️ 🎁 \\\n / 🌟 🎀 🎄 💎 🔔 \\\n/ ❄️ 🎁 ✨ 🎄 🎀 💎 \\\n       |||",
    }
    return arts.get(min(level, 5), arts[5])


def _render_progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(round(length * min(current, total) / total)) if total > 0 else 0
    return "█" * filled + "░" * (length - filled)


# ═══════════════════════════════════════════════════════════════════════════
# УПРАВЛЕНИЕ ТЕСТОВЫМ РЕЖИМОМ (ДЛЯ ВЛАДЕЛЬЦА)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Cmd("нг тест вкл", "нг тест 1", "winter test on", section=32,
                    usage="нг тест вкл", desc="Включить тест зимнего сезона (для овнера)"))
async def cmd_winter_test_on(message: Message, **kw):
    if message.from_user.id != config.OWNER_ID and message.from_user.id not in getattr(config, "ADMINS", []):
        return
    global _winter_test_mode
    _winter_test_mode = True
    await message.reply(
        "🎄 <b>Зимний ивент ПРИНУДИТЕЛЬНО ВКЛЮЧЕН в тестовом режиме!</b>\n"
        "Теперь все новогодние команды (<code>елка</code>, <code>битва за буст</code>, <code>квесты</code>, <code>снежок</code>) активны для проверки."
    )


@router.message(Cmd("нг тест выкл", "нг тест 0", "winter test off", section=32,
                    usage="нг тест выкл", desc="Выключить тест зимнего сезона (для овнера)"))
async def cmd_winter_test_off(message: Message, **kw):
    if message.from_user.id != config.OWNER_ID and message.from_user.id not in getattr(config, "ADMINS", []):
        return
    global _winter_test_mode
    _winter_test_mode = False
    await message.reply(
        "🔒 <b>Тестовый режим выключен.</b>\n"
        f"Ивент вернётся в режим ожидания 1 декабря 00:00 по МСК (осталось: {time_until_str(WINTER_START_TS)})."
    )


# ═══════════════════════════════════════════════════════════════════════════
# НОВОГОДНЯЯ ЁЛКА В ГРУППАХ
# ═══════════════════════════════════════════════════════════════════════════

def _tree_keyboard(quests: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    # Кнопки скипа для незавершенных квестов
    for q in quests:
        if not q.get("completed"):
            qid = q["quest_id"]
            q_meta = next((x for x in db.DEFAULT_TREE_QUESTS if x["id"] == qid), None)
            stars = q_meta["stars"] if q_meta else 15
            buttons.append([InlineKeyboardButton(
                text=f"⭐️ Скип задания #{qid} ({stars} Stars)",
                callback_data=f"tree_skip:{qid}"
            )])
    buttons.append([
        InlineKeyboardButton(text="🏆 Битва за Буст 10 LVL", callback_data="tree_top"),
        InlineKeyboardButton(text="🔄 Обновить Ёлку", callback_data="tree_refresh")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _render_tree_card(chat_id: int, chat_title: str) -> tuple[str, InlineKeyboardMarkup]:
    tree_info = await db.get_chat_tree_info(chat_id)
    tree_lvl = tree_info["tree_level"]
    flakes = tree_info["snowflakes"]
    rank, _ = await db.get_winter_chat_rank(chat_id)
    quests = await db.init_chat_quests_if_empty(chat_id)
    art = _get_tree_art(tree_lvl)
    time_left = time_until_str(WINTER_END_TS)

    quest_lines = []
    for q in quests:
        qid = q["quest_id"]
        q_meta = next((x for x in db.DEFAULT_TREE_QUESTS if x["id"] == qid), None)
        desc = q_meta["desc"] if q_meta else f"Задание #{qid}"
        stars = q_meta["stars"] if q_meta else 15
        reward = q_meta["reward_flakes"] if q_meta else 50
        
        if q["completed"]:
            quest_lines.append(f"  ✅ <s>{desc}</s> (+{reward} ❄️)")
        else:
            bar = _render_progress_bar(q['progress'], q['goal'], length=6)
            quest_lines.append(f"  ⏳ <b>{desc}</b>\n      [{bar}] <code>{q['progress']}/{q['goal']}</code> (+{reward} ❄️ | скип: {stars} ⭐️)")

    tree_bar = _render_progress_bar(tree_lvl, 10, length=8)

    text = (
        f"🎄 <b>НОВОГОДНЯЯ ЁЛКА БЕСЕДЫ</b> 🎄\n"
        f"«<b>{html.escape(chat_title)}</b>»\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"<pre>{art}</pre>\n"
        f"⭐ <b>Уровень ёлки:</b> {tree_lvl}/10 [{tree_bar}]\n"
        f"❄️ <b>Снежинки беседы:</b> <b>{flakes:,} ❄️</b>\n"
        f"🏆 <b>Место в Битве за Буст:</b> <b>#{rank}</b>\n"
        f"⏳ <b>До финала:</b> <b>{time_left}</b> <i>(1 янв 00:00 МСК)</i>\n\n"
        f"📜 <b>ЗАДАНИЯ ТЕКУЩЕГО КРУГА:</b>\n"
        + "\n".join(quest_lines) + "\n\n"
        f"🎁 <b>Награда за круг:</b> +250 ❄️ Снежинок и +1 Уровень Ёлки!\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"⭐️ <i>Любой участник или админ может завершить задание мгновенно за Telegram Stars!</i>"
    )
    return text, _tree_keyboard(quests)


@router.message(Cmd("елка", "ёлка", "tree", "нг елка", section=32,
                    usage="елка", desc="Новогодняя ёлка беседы и задания"))
async def cmd_tree(message: Message, **kw):
    if message.chat.type == "private":
        return await message.reply(
            "🎄 Команда <code>елка</code> работает только в беседах (группах)!\n"
            "👉 В личке с ботом используй команду <code>реф</code>, чтобы получать награды за приглашенных друзей!"
        )

    if not is_winter_active():
        time_left = time_until_str(WINTER_START_TS)
        return await message.reply(
            f"❄️ <b>ЗИМНИЙ СЕЗОН MOXXI 2026-2027</b> ❄️\n"
            f"✦ ══════════════════════════════ ✦\n"
            f"🎄 <b>Новогодняя Ёлка и Битва за Буст 10 LVL</b>\n"
            f"стартуют <b>1 декабря в 00:00 по МСК</b>!\n\n"
            f"⏳ <b>До открытия сезона:</b> <b>{time_left}</b>\n\n"
            f"🎁 <b>Что откроется 1 декабря:</b>\n"
            f"├ 🎄 Командная Новогодняя Ёлка в вашей группе\n"
            f"├ 📜 Групповые новогодние квесты и задания\n"
            f"├ ⭐️ Пропуск заданий за официальные Telegram Stars\n"
            f"├ ❄️ Фарм Снежинок и снежные битвы\n"
            f"└ 🏆 <b>Буст Telegram 10 LVL</b> для победившей группы!\n"
            f"✦ ══════════════════════════════ ✦\n"
            f"🔔 <i>Собирайте активных участников в чат — 1 декабря начнется грандиозная битва!</i>"
        )

    text, kb = await _render_tree_card(message.chat.id, message.chat.title or "Беседа")
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data == "tree_refresh")
async def cb_tree_refresh(call: CallbackQuery):
    if not is_winter_active():
        return await call.answer("❄️ Сезон стартует 1 декабря в 00:00 по МСК!", show_alert=True)
    try:
        text, kb = await _render_tree_card(call.message.chat.id, call.message.chat.title or "Беседа")
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer("✅ Ёлка обновлена!")
    except Exception:
        await call.answer("Ёлка уже актуальна!")


@router.callback_query(F.data.startswith("tree_skip:"))
async def cb_tree_skip(call: CallbackQuery, bot: Bot):
    if not is_winter_active():
        return await call.answer("❄️ Сезон стартует 1 декабря!", show_alert=True)
    qid = int(call.data.split(":")[1])
    q_meta = next((x for x in db.DEFAULT_TREE_QUESTS if x["id"] == qid), None)
    if not q_meta:
        return await call.answer("Задание не найдено", show_alert=True)

    stars = q_meta["stars"]
    reward = q_meta["reward_flakes"]
    chat_id = call.message.chat.id
    title = f"⭐️ Скип квеста #{qid} Ёлки"
    desc = f"Завершает «{q_meta['desc']}» и начисляет чату +{reward} ❄️ Снежинок!"

    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=desc,
            payload=f"skip_quest:{chat_id}:{qid}",
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=stars)],
            reply_to_message_id=call.message.message_id
        )
        await call.answer("⭐️ Окно оплаты Telegram Stars отправлено в чат!")
    except Exception as e:
        await call.answer(f"Ошибка открытия оплаты: {str(e)[:100]}", show_alert=True)


# ═══════════════════════════════════════════════════════════════════════════
# БИТВА ЗА БУСТ TELEGRAM 10 LVL (ТОП ЧАТОВ ПО СНЕЖИНКАМ)
# ═══════════════════════════════════════════════════════════════════════════

async def _render_top_card(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    top_chats = await db.get_winter_top_chats(limit=10)
    current_rank, current_flakes = await db.get_winter_chat_rank(chat_id)
    time_left = time_until_str(WINTER_END_TS)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    rows = []
    if not top_chats:
        rows.append("<i>Пока ни одна беседа не набрала снежинки. Будьте первыми!</i>")
    else:
        for idx, c in enumerate(top_chats):
            m = medals[idx] if idx < len(medals) else f"#{idx+1}"
            title = html.escape(c.get("title") or "Беседа")
            flakes = c.get("snowflakes", 0)
            lvl = c.get("tree_level", 1)
            rows.append(f"{m} <b>{title}</b> — <b>{flakes:,} ❄️</b> <i>(Ёлка ур. {lvl})</i>")

    text = (
        f"🏆 <b>БИТВА ЗА БУСТ TELEGRAM 10 LVL</b> 🏆\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"🎁 <b>ГЛАВНЫЙ ПРИЗ ПОБЕДИВШЕЙ БЕСЕДЕ:</b>\n"
        f"🚀 <b>Прокачка вашего Telegram-канала / чата</b>\n"
        f"до <b>10 УРОВНЯ БУСТА</b> (Telegram Premium Boosts)!\n"
        f"💰 <i>Полная оплата бустов лично от создателя бота!</i>\n\n"
        f"⏳ <b>До финала:</b> <b>{time_left}</b>\n"
        f"📅 <b>Стоп ивента:</b> 1 января 00:00 (по МСК)\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"📊 <b>ТОП-10 БЕСЕД ПО СНЕЖИНКАМ:</b>\n"
        + "\n".join(rows) + "\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"📍 <b>Ваша беседа:</b> #{current_rank} ({current_flakes:,} ❄️)\n"
        f"👉 <i>Чтобы обогнать соперников, прокачивайте <code>елка</code> и выполняйте задания!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎄 Открыть Ёлку беседы", callback_data="tree_refresh")],
        [InlineKeyboardButton(text="🔄 Обновить Топ", callback_data="winter_top_refresh")]
    ])
    return text, kb


@router.message(Cmd("нг топ", "битва за буст", "топ нг", "буст топ", "снежинки топ", section=32,
                    usage="нг топ", desc="Таблица лидеров Битвы за Буст Telegram 10 LVL"))
async def cmd_winter_top(message: Message, **kw):
    if not is_winter_active():
        time_left = time_until_str(WINTER_START_TS)
        return await message.reply(
            f"❄️ <b>БИТВА ЗА БУСТ TELEGRAM 10 LVL</b> ❄️\n"
            f"✦ ══════════════════════════════ ✦\n"
            f"🏆 Рейтинг лучших бесед откроется <b>1 декабря в 00:00 по МСК</b>!\n\n"
            f"⏳ <b>До старта:</b> <b>{time_left}</b>\n\n"
            f"🚀 <b>Приз:</b> Создатель бота лично оплатит победившему чату прокачку до 10 уровня буста в Telegram!"
        )
    text, kb = await _render_top_card(message.chat.id)
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.in_({"tree_top", "winter_top_refresh"}))
async def cb_winter_top(call: CallbackQuery):
    if not is_winter_active():
        return await call.answer("❄️ Сезон стартует 1 декабря в 00:00 по МСК!", show_alert=True)
    try:
        text, kb = await _render_top_card(call.message.chat.id)
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
    except Exception:
        await call.answer("Топ уже актуален!")


# ═══════════════════════════════════════════════════════════════════════════
# ЗИМНЯЯ ИГРА: БРОСОК СНЕЖКОМ В ЧАТЕ
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Cmd("снежок", "кинуть снежок", "снежки", section=32,
                    usage="снежок @юзер", desc="Бросить снежок в участника беседы"))
async def cmd_snowball(message: Message, bot: Bot, **kw):
    if message.chat.type == "private":
        return await message.reply("❄️ Кидаться снежками можно только в беседах!")

    if not is_winter_active():
        return await message.reply("❄️ Снежные битвы откроются 1 декабря вместе со стартом зимнего сезона!")

    uid = message.from_user.id
    now = time.time()
    last = _snowball_cooldowns.get(uid, 0.0)
    if now - last < 45:
        left = int(45 - (now - last))
        return await message.reply(f"⏳ Руки замёрзли! Ты сможешь слепить следующий снежок через <b>{left} сек.</b> 🧤")

    # Ищем цель (ответ на сообщение или упоминание)
    target_id: Optional[int] = None
    target_name: str = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or "участника"
    elif message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name
                break

    if not target_id:
        return await message.reply("❄️ Чтобы бросить снежок, ответь на сообщение жертвы командой <code>снежок</code>!")

    if target_id == uid:
        return await message.reply("😅 Ты попытался кинуть снежок в самого себя, но он просто развалился у тебя в руках!")

    _snowball_cooldowns[uid] = now
    actor_m = mention(message.from_user)
    target_m = f'<a href="tg://user?id={target_id}">{html.escape(target_name)}</a>'

    # Шанс попадания 75%
    if random.random() < 0.75:
        earned_flakes = random.randint(1, 3)
        await db.add_user_snowflakes(uid, earned_flakes)
        await db.add_chat_snowflakes(message.chat.id, earned_flakes)
        # Продвигаем квест бесед
        try:
            await db.advance_chat_quest(message.chat.id, "games", 1)
        except Exception:
            pass
        await message.reply(
            f"❄️💥 <b>ТОЧНОЕ ПОПАДАНИЕ!</b>\n\n"
            f"{actor_m} метко зарядил ледяным снежком прямо в лоб {target_m}! 🎯\n"
            f"🥶 {target_m} весь в снегу и покрылся морозной коркой!\n\n"
            f"🎁 <b>Награда стрелку:</b> +{earned_flakes} ❄️ Снежинки!"
        )
    else:
        await message.reply(
            f"💨 <b>ПРОМАХ!</b>\n\n"
            f"{actor_m} запустил увесистый снежок в {target_m}, но тот ловко пригнулся, и снежок улетел в сугроб! ☃️"
        )


# ═══════════════════════════════════════════════════════════════════════════
# СПИСОК ОБНОВЛЕНИЙ И ЧЕНДЖЛОГ (ОБНОВА / НОВОСТИ)
# ═══════════════════════════════════════════════════════════════════════════

CHANGELOG_TEXT = (
    "🎄 <b>ГЛОБАЛЬНОЕ ЗИМНЕЕ ОБНОВЛЕНИЕ MOXXI: ЗИМА 2026-2027</b> 🎄\n"
    "✦ ══════════════════════════════════════ ✦\n\n"
    "🎉 <b>Добро пожаловать в зимний новогодний сезон!</b>\n\n"
    "🚀 <b>ГЛАВНЫЕ НОВИНКИ ОБНОВЛЕНИЯ:</b>\n\n"
    "1️⃣ <b>Новогодняя Ёлка в беседах (<code>/елка</code>):</b>\n"
    "├ Прокачивайте командную Ёлку вашей группы до 10 уровня!\n"
    "├ Выполняйте командные квесты (сообщения, игры, дуэли, друзья)\n"
    "└ Получайте сотни ❄️ Снежинок за каждый закрытый круг заданий!\n\n"
    "2️⃣ <b>Пропуск заданий за Telegram Stars (⭐️):</b>\n"
    "├ Лень делать квесты? Любой участник или админ может\n"
    "└ пропустить задание за официальные Telegram Stars в один клик!\n\n"
    "3️⃣ <b>Битва за Буст Telegram 10 LVL (<code>нг топ</code>):</b>\n"
    "├ Топ-1 беседа по снежинкам к 1 января 00:00 (МСК) получит\n"
    "└ <b>10 УРОВЕНЬ БУСТА TELEGRAM</b>, полностью оплаченный создателем бота!\n\n"
    "4️⃣ <b>Новая реферальная система в ЛС (<code>реф</code>):</b>\n"
    "├ Личная реф-ссылка для каждого игрока\n"
    "├ +10 ❄️ Снежинок за каждого нового друга\n"
    "└ <b>+50,000 ГРАММ НА БАЛАНС за каждые 20 приглашенных друзей!</b>\n\n"
    "5️⃣ <b>Снежные дуэли (<code>снежок @юзер</code>):</b>\n"
    "├ Бросайтесь снежками в беседе с шансом заморозить соперника\n"
    "└ Зарабатывайте дополнительные снежинки за меткие попадания!\n\n"
    "6️⃣ <b>Защита экономики и ребаланс:</b>\n"
    "├ Ограничение депозитов банка до 500кк и процентная ставка 1%\n"
    "├ Полный ребаланс всех 40 бизнесов против гиперинфляции\n"
    "└ Мультиязычность: выбор удобного языка на старте!\n\n"
    "✦ ══════════════════════════════════════ ✦\n"
    "<i>Желаем приятной игры и победы вашей беседе в Битве за Буст! ❄️✨</i>"
)


@router.message(Cmd("обнова", "обновление", "новости", "патчноут", "патч", "changelog", section=32,
                    usage="обнова", desc="Список нововведений зимнего глобального обновления"))
async def cmd_changelog(message: Message, **kw):
    if not is_winter_active():
        time_left = time_until_str(WINTER_START_TS)
        return await message.reply(
            f"❄️ <b>ГЛОБАЛЬНОЕ ЗИМНЕЕ ОБНОВЛЕНИЕ MOXXI 2026-2027</b> ❄️\n"
            f"✦ ══════════════════════════════ ✦\n"
            f"Полный список обновлений и все новые функции откроются\n"
            f"<b>1 декабря в 00:00 по МСК</b>!\n\n"
            f"⏳ <b>До выхода обновления:</b> <b>{time_left}</b>\n\n"
            f"🎁 <i>Вас ждёт Новогодняя Ёлка, квесты со звёздами Stars, рефералка с наградой 50,000 грамм и Битва за Буст 10 LVL!</i>"
        )
    await message.reply(CHANGELOG_TEXT)


# ═══════════════════════════════════════════════════════════════════════════
# НЕЙРО-ПОЗДРАВЛЕНИЯ ОТ ДЕДА МОРОЗА И СНЕГУРОЧКИ
# ═══════════════════════════════════════════════════════════════════════════

GREETING_TEMPLATES = [
    "🎅 <i>«О-хо-хо! {name}, Дедушка Мороз заглянул в твои логи и видит — в этом году ты фармил как зверь! Желаю сорвать джекпот в казино, держать баланс на максимуме и чтобы в 2027 твоя ёлка сияла ярче Кремля! Держи морозный сувенир: +3 ❄️!»</i>",
    "🎄 <i>«{name}, салам от Снегурочки! Пусть в Новом Году твои бизнесы приносят миллионы в минуту, дуэли заканчиваются онли победами, а хейтеры замерзают в сугробах! Лови праздничный бонус: +3 ❄️ Снежинки!»</i>",
    "❄️ <i>«Йоу, {name}! Дед Мороз зарядил свои сани и мчит на полной скорости! Пусть в 2027 у тебя будет столько монет, сколько снега в Сибири, а удача улыбается на каждом круге рулетки! Держи +3 ❄️!»</i>",
    "✨ <i>«{name}, слышишь звон бубенцов? Это твоя прибыль стучится в двери! Желаю топового клана, верных друзей по рефке и легкой победы в Битве за Буст 10 LVL! С наступающим! Лови +3 ❄️!»</i>",
    "☃️ <i>«Снеговик передает привет, {name}! В этом году ты был хорошим игроком (ну, почти, если не считать сливы в кости)! Пусть 2027 принесет тонны фарма, редкий шмот из кейсов и вечный кайф! +3 ❄️ тебе в карман!»</i>",
]


@router.message(Cmd("поздравь", "поздравление", "дед мороз", "снегурочка", section=32,
                    usage="поздравь [@юзер]", desc="🎅 Новогоднее поздравление от Деда Мороза со стихами и подарком"))
async def cmd_santa_greeting(message: Message, bot: Bot, **kw):
    target_id = message.from_user.id
    target_name = message.from_user.first_name or "Боец"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or "Друг"
    elif message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name
                break

    template = random.choice(GREETING_TEMPLATES)
    t_mention = f'<a href="tg://user?id={target_id}">{html.escape(target_name)}</a>'
    greeting_body = template.format(name=t_mention)

    # Дарим 3 снежинки цели
    await db.add_user_snowflakes(target_id, 3)

    res = (
        f"🎅 ✨ <b>ПРАЗДНИЧНОЕ ПОЗДРАВЛЕНИЕ ОТ MOXXI</b> ✨ 🎄\n"
        f"✦ ══════════════════════════════════════ ✦\n\n"
        f"{greeting_body}\n\n"
        f"✦ ══════════════════════════════════════ ✦\n"
        f"🎁 <i>Поздравьте друзей: <code>поздравь @юзер</code>!</i>"
    )
    await message.reply(res)


# ═══════════════════════════════════════════════════════════════════════════
# ЕДИНЫЙ ПРАЗДНИЧНЫЙ ХАБ «НОВЫЙ ГОД 2026-2027»
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Cmd("нг", "новый год", "зима", "новогоднее меню", "зима меню", "new year", section=32,
                    usage="нг", desc="🎄 Главный праздничный хаб Нового Года 2026-2027 в MOXXI"))
async def cmd_winter_hub(message: Message, bot: Bot, **kw):
    chat_id = message.chat.id
    uid = message.from_user.id
    u = await db.get_user(uid)
    u_flakes = int(u.get("snowflakes", 0) or 0)

    # Информация о ёлке в чате
    tree = await db.get_chat_tree(chat_id)
    tree_lvl = tree.get("tree_level", 1)

    time_left = time_until_str(WINTER_END_TS)

    text = (
        "❄️ ══ 🎄 ══ 🎁 <b>НОВЫЙ ГОД 2026-2027 В MOXXI</b> 🎁 ══ 🎄 ══ ❄️\n\n"
        "✨ <b>Добро пожаловать в зимнюю сказку MOXXI!</b>\n"
        "Праздничный сезон в самом разгаре: наряжайте ёлку беседы, забирайте подарки "
        "из Адвент-календаря, сражайтесь с Ледяным Сантой и бросайтесь снежками!\n\n"
        f"🎄 <b>Ёлка этой беседы:</b> <b>Уровень {tree_lvl}</b> (<code>елка</code>)\n"
        f"❄️ <b>Ваш запас снежинок:</b> <b>{u_flakes:,} ❄️</b>\n"
        f"⏳ <b>До завершения праздников:</b> <b>{time_left}</b>\n\n"
        "📜 <b>Все зимние команды под рукой:</b>\n"
        "• <code>елка</code> — полить и нарядить ёлку беседы\n"
        "• <code>адвент</code> — ежедневный сундучок с подарком\n"
        "• <code>санта</code> — рейд на Ледяного Санту\n"
        "• <code>снежок @юзер</code> — метнуть снежок в друга\n"
        "• <code>письмо санте [желание]</code> — отправить сокровенное желание\n"
        "• <code>купить снежинки</code> — магазин зимней валюты\n"
        "• <code>дизайн</code> — включить новогоднюю тему оформления"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎄 Ёлка беседы", callback_data=f"tree_info:{chat_id}"),
            InlineKeyboardButton(text="🎁 Адвент-подарок", callback_data="adv:open")
        ],
        [
            InlineKeyboardButton(text="🎅 Рейд на Санту", callback_data="santa:info"),
            InlineKeyboardButton(text="❄️ Магазин снежинок", callback_data="buy_snowflakes_menu")
        ],
        [
            InlineKeyboardButton(text="✉️ Написать Санте", callback_data="santa_letter_help")
        ]
    ])

    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data == "santa_letter_help")
async def cb_santa_letter_help(call: CallbackQuery):
    await call.answer()
    await call.message.reply(
        "✉️ <b>Как написать письмо Деду Морозу:</b>\n\n"
        "Отправьте команду:\n"
        "<code>письмо санте [ваше желание на 2026-2027 год]</code>\n\n"
        "💡 <i>Пример: <code>письмо санте Хочу накопить миллион грамм и найти верных друзей!</code></i>\n\n"
        "🎁 <b>За каждое отправленное письмо Дедушка Мороз дарит:</b>\n"
        "• <b>+25 ❄️ Снежинок</b>\n"
        "• <b>+10 000 грамм</b>"
    )


# ═══════════════════════════════════════════════════════════════════════════
# ПИСЬМО ДЕДУ МОРОЗУ С ПОДАРКАМИ
# ═══════════════════════════════════════════════════════════════════════════

async def _init_santa_letters_table():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS santa_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            wish TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)


@router.message(Cmd("письмо санте", "письмо деду морозу", "письмо дедушке морозу", "письмо морозу", section=32,
                    usage="письмо санте [желание]", desc="✉️ Отправить новогоднее письмо Деду Морозу с желанием и получить подарок"))
async def cmd_send_santa_letter(message: Message, bot: Bot, args: str = "", **kw):
    await _init_santa_letters_table()
    wish_text = (args or "").strip()

    if not wish_text:
        return await message.reply(
            "✉️ <b>Напишите ваше сокровенное желание!</b>\n\n"
            "Команда: <code>письмо санте [текст вашего желания]</code>\n\n"
            "💡 <i>Пример: <code>письмо санте Хочу в 2027 году стать лидером топа и купить Bugatti!</code></i>"
        )

    uid = message.from_user.id
    now = int(time.time())

    # Проверка на кулдаун (1 письмо в 20 часов)
    last_letter = await db.fetchone(
        "SELECT created_at FROM santa_letters WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)
    )
    if last_letter and (now - last_letter["created_at"]) < 72000:
        remain = int(72000 - (now - last_letter["created_at"]))
        hours = remain // 3600
        mins = (remain % 3600) // 60
        return await message.reply(
            f"⏳ <b>Вы уже отправили письмо Дедушке Морозу!</b>\n\n"
            f"Дедушка сейчас читает ваше послание. Следующее письмо можно будет отправить через <b>{hours} ч. {mins} мин.</b>"
        )

    u_name = message.from_user.first_name or f"Игрок {uid}"

    # Сохраняем письмо
    await db.execute(
        "INSERT INTO santa_letters (user_id, user_name, chat_id, wish, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, u_name, message.chat.id, wish_text, now)
    )

    # Начисляем щедрый новогодний подарок
    await db.add_user_snowflakes(uid, 25)
    await db.execute("UPDATE users SET balance = balance + 10000 WHERE user_id=?", (uid,))

    letter_card = (
        "📜 ══════════════════════════════════ 📜\n"
        "  ✨ <b>ПИСЬМО ДЕДУ МОРОЗУ ОТПРАВЛЕНО!</b> ✨\n"
        "📜 ══════════════════════════════════ 📜\n\n"
        f"✉️ <b>От кого:</b> {mention(message.from_user)}\n"
        f"🎅 <b>Куда:</b> <i>Великий Устюг, Резиденция Мороза</i>\n\n"
        f"📝 <b>Твоё новогоднее желание:</b>\n"
        f"«<i>{html.escape(wish_text)}</i>»\n\n"
        "🏮 <i>Почтовые голуби умчались с твоим свитком на Северный Полюс!</i>\n\n"
        "🎁 <b>Твой праздничный подарок за письмо:</b>\n"
        "• <b>+25 ❄️ Снежинок</b>\n"
        "• <b>+10 000 грамм</b>\n\n"
        "✨ <i>Пусть в 2027 году всё задуманное исполнится!</i>"
    )
    await message.reply(letter_card)


@router.message(Cmd("письма санте", "письма деду морозу", "почта санты", section=32,
                    usage="письма санте", desc="Просмотр писем Деду Морозу (для овнера бота)"))
async def cmd_admin_view_santa_letters(message: Message, bot: Bot, **kw):
    if message.from_user.id != config.OWNER_ID and message.from_user.id not in getattr(config, "ADMINS", []):
        return

    await _init_santa_letters_table()
    rows = await db.fetchall("SELECT * FROM santa_letters ORDER BY id DESC LIMIT 10")
    if not rows:
        return await message.reply("📬 <b>Пока нет отправленных писем Деду Морозу!</b>")

    lines = []
    for r in rows:
        dt = time.strftime("%d.%m %H:%M", time.localtime(r["created_at"]))
        lines.append(
            f"<b>#{r['id']}</b> | <b>{html.escape(r['user_name'])}</b> (ID: <code>{r['user_id']}</code>) | {dt}\n"
            f"✉️ <i>«{html.escape(r['wish'])}»</i>"
        )

    await message.reply("📬 <b>ПОСЛЕДНИЕ ПИСЬМА ДЕДУ МОРОЗУ ОТ ИГРОКОВ:</b>\n\n" + "\n\n".join(lines))

