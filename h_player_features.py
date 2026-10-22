"""🎰 Игровые развлечения для игроков: Рулетка Удачи, Ежедневные Квесты и Статистика Активности.

Включает:
1. 🎡 Ежедневная «Рулетка Удачи» (Колесо Фортуны с призами от монет до кейсов и джекпота);
2. 📋 Система ежедневных квестов («дейлики») с прогресс-барами и получением наград;
3. 📈 Статистика суточной активности бота («активность», «онлайн»).
"""
from __future__ import annotations

import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
from core_registry import Cmd
from utils import hms, mention, mention_id, money

router = Router(name="player_features")
S_ENTERTAINMENT = 42  # Раздел развлечений и квестов

ROULETTE_PRIZES = [
    {"type": "coins", "val": 10000, "title": "🍬 10 000 монет", "weight": 30},
    {"type": "coins", "val": 25000, "title": "🎁 25 000 монет", "weight": 25},
    {"type": "coins", "val": 50000, "title": "💎 50 000 монет", "weight": 15},
    {"type": "xp", "val": 150, "title": "⚡️ +150 Опыта (XP)", "weight": 10},
    {"type": "rep", "val": 5, "title": "⭐️ +5 Репутации", "weight": 8},
    {"type": "item", "val": "bronze_case", "title": "📦 Бронзовый кейс", "weight": 6},
    {"type": "item", "val": "shield", "title": "🛡 Щит от варна (1 шт)", "weight": 4},
    {"type": "jackpot", "val": 250000, "title": "👑 ДЖЕКПОТ 250 000 МОНЕТ!", "weight": 2},
]


def _progress_bar(current: int, target: int, length: int = 10) -> str:
    target = max(1, target)
    ratio = min(1.0, max(0.0, current / target))
    filled = int(round(ratio * length))
    return "█" * filled + "░" * (length - filled)


# ═══════════════════════════════════════════════════════════════
# 1. 🎡 ЕЖЕДНЕВНАЯ РУЛЕТКА УДАЧИ (КОЛЕСО ФОРТУНЫ)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("рулетка", "колесо", "спин", "рулетка удачи", "крутить колесо", "wheel",
                    section=S_ENTERTAINMENT, usage="рулетка",
                    desc="Крутить бесплатное ежедневное Колесо Фортуны Moxxi"))
async def cmd_roulette(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Игрок"

    cd_left = await db.check_roulette_cooldown(uid)
    if cd_left > 0:
        lvl, _, active = await db.get_vip_info(uid)
        vip_note = "<i>💡 Для VIP кулдаун сокращён до 12ч, для VIP+ — до 6ч!</i>" if not active else ""
        return await message.reply(
            f"⏳ <b>Рулетка Удачи уже была использована!</b>\n\n"
            f"Следующее бесплатное вращение доступно через: <b>{hms(cd_left)}</b>.\n\n"
            f"{vip_note}"
        )

    # Крутим рулетку
    await db.record_roulette_spin(uid)

    weights = [p["weight"] for p in ROULETTE_PRIZES]
    prize = random.choices(ROULETTE_PRIZES, weights=weights, k=1)[0]

    # Начисление приза
    p_type = prize["type"]
    if p_type in ("coins", "jackpot"):
        await db.add_balance(uid, prize["val"], "roulette_prize")
    elif p_type == "xp":
        await db.add_xp(uid, prize["val"])
    elif p_type == "rep":
        await db.add_rep(uid, prize["val"])
    elif p_type == "item":
        if prize["val"] == "bronze_case":
            try:
                from h_cases import add_case
                await add_case(uid, "bronze", 1)
            except Exception:
                await db.add_balance(uid, 30000, "roulette_fallback")
        elif prize["val"] == "shield":
            try:
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, count) VALUES (?, 'shield', 1) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid,)
                )
            except Exception:
                await db.add_balance(uid, 50000, "roulette_fallback")

    # Обновляем квест, если такой есть
    await db.update_quest_progress(uid, "spin_roulette", 1)

    lvl, _, active = await db.get_vip_info(uid)
    next_spin_txt = "6 часов" if (active and lvl >= 2) else ("12 часов" if (active and lvl >= 1) else "24 часа")

    result_card = (
        f"🎡 ✨ <b>НЕОНОВОЕ КОЛЕСО ФОРТУНЫ MOXXI</b> ✨ 🎡\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👤 Игрок: {mention_id(uid, name)}\n"
        f"🎯 Стрелка остановилась на секторе:\n\n"
        f"🎉 <b>{prize['title']}</b> 🎉\n\n"
        f"💎 Награда моментально начислена на ваш аккаунт!\n"
        f"⏱ Следующий бесплатный спин: через <b>{next_spin_txt}</b>.\n\n"
        f"<i>Удачи в следующих играх и рейдах!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои ежедневные квесты", callback_data="open_quests_menu")],
        [InlineKeyboardButton(text="🛍 Открыть Магазин", callback_data="buy_vip_menu")]
    ])
    await message.reply(result_card, reply_markup=kb)


# ═══════════════════════════════════════════════════════════════
# 2. 📋 ЕЖЕДНЕВНЫЕ КВЕСТЫ («ДЕЙЛИКИ»)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("квесты", "дейлики", "задания", "ежедневные квесты", "daily",
                    section=S_ENTERTAINMENT, usage="квесты",
                    desc="Ежедневные задания с наградами за активность"))
async def cmd_quests(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Игрок"
    quests = await db.get_or_create_daily_quests(uid)

    lines = []
    kb_rows = []
    for q in quests:
        p_bar = _progress_bar(q["progress"], q["target"], 8)
        is_done = q["progress"] >= q["target"]
        if q["claimed"]:
            status_txt = "✅ <b>Забрано!</b>"
        elif is_done:
            status_txt = "🎁 <b>ГОТОВО К ПОЛУЧЕНИЮ!</b>"
            kb_rows.append([InlineKeyboardButton(
                text=f"🎁 Забрать награду за «{q['title'][:20]}...»",
                callback_data=f"claim_q:{q['quest_id']}"
            )])
        else:
            status_txt = f"⏳ В процессе ({q['progress']}/{q['target']})"

        lines.append(
            f"• <b>{q['title']}</b>\n"
            f"  Прогресс: <code>[{p_bar}]</code> {q['progress']}/{q['target']}\n"
            f"  Награда: <b>+{money(q['reward_coins'])}</b> | <b>+{q['reward_xp']} XP</b>\n"
            f"  Статус: {status_txt}"
        )

    kb_rows.append([InlineKeyboardButton(text="🎡 Крутить Рулетку Удачи", callback_data="spin_roulette_btn")])
    kb_rows.append([InlineKeyboardButton(text="🔄 Обновить квесты", callback_data="refresh_quests")])

    text = (
        f"📋 ✨ <b>ЕЖЕДНЕВНЫЕ КВЕСТЫ MOXXI</b> ✨ 📋\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👤 Боец: {mention_id(uid, name)}\n"
        f"📅 Задания на сегодня ({time.strftime('%d.%m.%Y')}):\n\n"
        + "\n\n".join(lines) + "\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Квесты обновляются каждый день в полночь. Выполняйте их, чтобы зарабатывать монеты и прокачивать уровень!</i>"
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("claim_q:"))
async def cb_claim_quest(call: CallbackQuery):
    uid = call.from_user.id
    qid = call.data.split(":", 1)[1]
    res = await db.claim_daily_quest(uid, qid)
    if not res:
        return await call.answer("Награда уже получена или задание ещё не завершено!", show_alert=True)

    await call.answer(f"🎉 Получено: +{money(res['coins'])} и +{res['xp']} XP!", show_alert=True)
    # Перерисовываем меню квестов
    quests = await db.get_or_create_daily_quests(uid)
    lines = []
    kb_rows = []
    for q in quests:
        p_bar = _progress_bar(q["progress"], q["target"], 8)
        if q["claimed"]:
            status_txt = "✅ <b>Забрано!</b>"
        elif q["progress"] >= q["target"]:
            status_txt = "🎁 <b>ГОТОВО К ПОЛУЧЕНИЮ!</b>"
            kb_rows.append([InlineKeyboardButton(
                text=f"🎁 Забрать за «{q['title'][:20]}...»",
                callback_data=f"claim_q:{q['quest_id']}"
            )])
        else:
            status_txt = f"⏳ В процессе ({q['progress']}/{q['target']})"

        lines.append(
            f"• <b>{q['title']}</b>\n"
            f"  Прогресс: <code>[{p_bar}]</code> {q['progress']}/{q['target']}\n"
            f"  Награда: <b>+{money(q['reward_coins'])}</b> | <b>+{q['reward_xp']} XP</b>\n"
            f"  Статус: {status_txt}"
        )

    kb_rows.append([InlineKeyboardButton(text="🎡 Крутить Рулетку Удачи", callback_data="spin_roulette_btn")])
    kb_rows.append([InlineKeyboardButton(text="🔄 Обновить квесты", callback_data="refresh_quests")])

    text = (
        f"📋 ✨ <b>ЕЖЕДНЕВНЫЕ КВЕСТЫ MOXXI</b> ✨ 📋\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👤 Боец: {mention_id(uid, call.from_user.first_name)}\n"
        f"📅 Задания на сегодня ({time.strftime('%d.%m.%Y')}):\n\n"
        + "\n\n".join(lines) + "\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🎉 <i>Награда за «{res['title']}» успешно зачислена!</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    except Exception:
        pass


@router.callback_query(F.data == "refresh_quests")
async def cb_refresh_quests(call: CallbackQuery):
    uid = call.from_user.id
    quests = await db.get_or_create_daily_quests(uid)
    lines = []
    kb_rows = []
    for q in quests:
        p_bar = _progress_bar(q["progress"], q["target"], 8)
        if q["claimed"]:
            status_txt = "✅ <b>Забрано!</b>"
        elif q["progress"] >= q["target"]:
            status_txt = "🎁 <b>ГОТОВО К ПОЛУЧЕНИЮ!</b>"
            kb_rows.append([InlineKeyboardButton(
                text=f"🎁 Забрать за «{q['title'][:20]}...»",
                callback_data=f"claim_q:{q['quest_id']}"
            )])
        else:
            status_txt = f"⏳ В процессе ({q['progress']}/{q['target']})"

        lines.append(
            f"• <b>{q['title']}</b>\n"
            f"  Прогресс: <code>[{p_bar}]</code> {q['progress']}/{q['target']}\n"
            f"  Награда: <b>+{money(q['reward_coins'])}</b> | <b>+{q['reward_xp']} XP</b>\n"
            f"  Статус: {status_txt}"
        )

    kb_rows.append([InlineKeyboardButton(text="🎡 Крутить Рулетку Удачи", callback_data="spin_roulette_btn")])
    kb_rows.append([InlineKeyboardButton(text="🔄 Обновить квесты", callback_data="refresh_quests")])

    text = (
        f"📋 ✨ <b>ЕЖЕДНЕВНЫЕ КВЕСТЫ MOXXI</b> ✨ 📋\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👤 Боец: {mention_id(uid, call.from_user.first_name)}\n"
        f"📅 Задания на сегодня ({time.strftime('%d.%m.%Y')}):\n\n"
        + "\n\n".join(lines) + "\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Квесты обновляются каждый день в полночь.</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    except Exception:
        pass
    await call.answer("✅ Квесты обновлены")


@router.callback_query(F.data == "open_quests_menu")
async def cb_open_quests(call: CallbackQuery):
    await cb_refresh_quests(call)


@router.callback_query(F.data == "spin_roulette_btn")
async def cb_spin_roulette_btn(call: CallbackQuery, bot: Bot):
    # Запуск логики рулетки через кнопку
    uid = call.from_user.id
    cd_left = await db.check_roulette_cooldown(uid)
    if cd_left > 0:
        return await call.answer(f"⏳ Рулетка на перезарядке! Осталось: {hms(cd_left)}", show_alert=True)

    await db.record_roulette_spin(uid)
    weights = [p["weight"] for p in ROULETTE_PRIZES]
    prize = random.choices(ROULETTE_PRIZES, weights=weights, k=1)[0]
    p_type = prize["type"]
    if p_type in ("coins", "jackpot"):
        await db.add_balance(uid, prize["val"], "roulette_prize")
    elif p_type == "xp":
        await db.add_xp(uid, prize["val"])
    elif p_type == "rep":
        await db.add_rep(uid, prize["val"])

    await call.answer(f"🎯 ВЫПАЛО: {prize['title']}!", show_alert=True)
    await call.message.reply(
        f"🎡 ✨ <b>РУЛЕТКА УДАЧИ!</b> ✨ 🎡\n\n"
        f"🎯 Сектор: <b>{prize['title']}</b>!\n"
        f"💎 Награда начислена на ваш аккаунт!"
    )


# ═══════════════════════════════════════════════════════════════
# 3. 📈 СТАТИСТИКА АКТИВНОСТИ БОТА («АКТИВНОСТЬ», «ОНЛАЙН»)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("активность", "стата бота", "онлайн", "статистика бота", "онлайн бота",
                    section=S_ENTERTAINMENT, usage="активность",
                    desc="Посмотреть статистику активности и посещаемости бота за сегодня"))
async def cmd_activity_stats(message: Message, bot: Bot, **kw):
    act = await db.get_daily_activity()
    text = (
        f"📈 ✨ <b>АКТИВНОСТЬ И ОНЛАЙН MOXXI BOT</b> ✨ 📈\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"📅 <b>Статистика за сегодня ({act['date']}):</b>\n\n"
        f"👥 <b>Посетили бота:</b> <b>{act['unique_users']}</b> чел.\n"
        f"🚀 <b>Запустили бота (/start):</b> <b>{act['bot_starts']}</b> чел.\n"
        f"➕ <b>Добавлений в новые беседы:</b> <b>{act['group_adds']}</b> чатов\n"
        f"⚡️ <b>Команд выполнено:</b> <b>{act['commands_count']}</b>\n"
        f"💬 <b>Сообщений обработано:</b> <b>{act['messages_count']}</b>\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🌐 <b>Всего в проекте Moxxi:</b>\n"
        f"• Игроков в базе: <b>{act['total_users']}</b>\n"
        f"• Активных чатов: <b>{act['total_chats']}</b>\n\n"
        f"🚀 <i>Присоединяйтесь к игре и приглашайте бота в свои чаты!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Крутить Рулетку Удачи", callback_data="spin_roulette_btn")],
        [InlineKeyboardButton(text="📋 Ежедневные Квесты", callback_data="open_quests_menu")]
    ])
    await message.reply(text, reply_markup=kb)
