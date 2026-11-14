"""🎮 МЕГА-МОДУЛЬ НОВЫХ ИГР ДЛЯ MOXXI 🎮

Включает самые популярные чат-игры:
1. 🪨✂️📄 «КНБ» (Камень, Ножницы, Бумага) — Соло против Мокси и PvP дуэль со скрытыми ходами.
2. 🥤 «Напёрстки» — Угадай, под каким из 3 стаканчиков спрятан шарик (множитель x2.8).
3. 🔫 «Русская рулетка» — Револьвер на 6 камор, 1 патрон, поочередный спуск курка на выбывание.
4. 🤠 «Ковбой» — Дуэль на скорость реакции с фиксацией миллисекунд и штрафом за фальстарт.
5. 🎲 «Кости PvP» — Дуэль двух игроков на нативных анимированных кубиках Telegram.
6. 🧠 «Квиз / Викторина» — Интеллектуальная битва чата на 4 кнопки с призовым фондом.
"""
from __future__ import annotations

import asyncio
import html
import random
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_game_lock import is_in_game, lock_game, unlock_game
from core_ranks import require
from core_registry import Cmd
from core_resolve import resolve_target
from utils import mention, money, parse_amount

router = Router(name="mega_games")
S_GAMES = 44  # Раздел 44: Мега-игры и PvP развлечения
MIN_BET = 50

# ══════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════

async def _check_casino_allowed(message: Message) -> bool:
    """Проверка, разрешены ли игры в чате."""
    try:
        from h_grams import topic_ok
        return await topic_ok(message)
    except Exception:
        return True


def _mention_u(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'


def _parse_bet_arg(args: str, user_balance: int) -> int:
    tokens = (args or "").split()
    for tok in tokens:
        clean = tok.replace("k", "000").replace("к", "000").replace("m", "000000").replace("м", "000000")
        if clean.isdigit():
            return int(clean)
        val = parse_amount(tok, user_balance, MIN_BET)
        if val and val >= MIN_BET:
            return val
    return 0


# ══════════════════════════════════════════════════════════════════
# 1. 🪨✂️📄 КАМЕНЬ, НОЖНИЦЫ, БУМАГА (КНБ)
# ══════════════════════════════════════════════════════════════════

# RPS Сессии: gid -> dict
RPS_GAMES: dict[str, dict] = {}

RPS_NAMES = {"rock": "🪨 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}
RPS_BEATS = {
    ("rock", "scissors"): "Камень разбивает ножницы!",
    ("scissors", "paper"): "Ножницы разрезают бумагу!",
    ("paper", "rock"): "Бумага заворачивает камень!",
}


@router.message(Cmd("кнб", "цуефа", "rps", section=S_GAMES,
                    usage="кнб [@юзер] [ставка]", desc="🪨✂️📄 Камень, Ножницы, Бумага (соло или PvP)"))
async def cmd_rps(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    target_id, target_name, rem_args = await resolve_target(message, args, bot)
    bet = _parse_bet_arg(rem_args, u_bal)

    if bet > 0 and u_bal < bet:
        return await message.reply(f"💰 <b>Недостаточно средств для ставки!</b>\nБаланс: {money(u_bal)} 🪙\nСтавка: {money(bet)} 🪙")

    # Соло-режим против Мокси
    if not target_id or target_id == uid:
        gid = f"rps_s_{uid}_{int(time.time()*1000)%100000}"
        RPS_GAMES[gid] = {
            "mode": "solo",
            "p1_id": uid,
            "p1_name": uname,
            "bet": bet,
            "chat_id": message.chat.id,
            "created_at": time.time(),
        }
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps:solo:{gid}:rock"),
                InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps:solo:{gid}:scissors"),
                InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps:solo:{gid}:paper"),
            ]
        ])
        bet_txt = f"\n💰 <b>Ставка:</b> <code>{bet:,}</code> 🪙 (Выигрыш: x2)" if bet > 0 else "\n🎮 <i>Тренировочный раунд без ставки</i>"
        return await message.reply(
            f"🪨✂️📄 <b>КАМЕНЬ, НОЖНИЦЫ, БУМАГА ПРОТИВ МОКСИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Сделайте ваш тайный выбор кнопки ниже:{bet_txt}",
            reply_markup=kb
        )

    # PvP Режим
    me = await bot.me()
    if target_id == me.id:
        return await message.reply("🤖 Со мной можно сыграть без тега: <code>кнб [ставка]</code>!")

    t_data = await db.get_user(target_id)
    t_bal = int(t_data.get("balance", 0) or 0)
    if bet > 0 and t_bal < bet:
        return await message.reply(f"❌ У соперника <b>{html.escape(target_name)}</b> недостаточно монет для ставки ({money(t_bal)} 🪙).")

    gid = f"rps_p_{uid}_{target_id}_{int(time.time()*1000)%100000}"
    RPS_GAMES[gid] = {
        "mode": "pvp",
        "p1_id": uid,
        "p1_name": uname,
        "p2_id": target_id,
        "p2_name": target_name,
        "p1_pick": None,
        "p2_pick": None,
        "bet": bet,
        "accepted": False,
        "chat_id": message.chat.id,
        "created_at": time.time(),
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Принять вызов", callback_data=f"rps:accept:{gid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rps:decline:{gid}"),
        ]
    ])
    bet_txt = f"\n💰 <b>Банк игры:</b> <code>{bet*2:,}</code> 🪙 (по {bet:,} 🪙 с каждого)" if bet > 0 else "\n🎮 <i>Дружеская битва (без ставки)</i>"
    await message.reply(
        f"🪨✂️📄 <b>ДУЭЛЬ: КАМЕНЬ, НОЖНИЦЫ, БУМАГА!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Вызывающий:</b> {_mention_u(uid, uname)}\n"
        f"🎯 <b>Противник:</b> {_mention_u(target_id, target_name)}{bet_txt}\n\n"
        f"{_mention_u(target_id, target_name)}, вы принимаете вызов?",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("rps:solo:"))
async def cb_rps_solo(call: CallbackQuery):
    parts = call.data.split(":")
    gid, choice = parts[2], parts[3]
    game = RPS_GAMES.get(gid)
    if not game:
        return await call.answer("⏳ Игра завершена или устарела.", show_alert=True)
    if call.from_user.id != game["p1_id"]:
        return await call.answer("Это не ваша игра!", show_alert=True)

    RPS_GAMES.pop(gid, None)
    bot_choice = random.choice(["rock", "scissors", "paper"])
    bet = game["bet"]
    uid = game["p1_id"]

    p_txt = RPS_NAMES.get(choice, choice)
    b_txt = RPS_NAMES.get(bot_choice, bot_choice)

    if choice == bot_choice:
        res = "🤝 <b>НИЧЬЯ!</b>"
        payout_txt = "Ставка возвращена." if bet > 0 else "Победила дружба!"
    elif (choice, bot_choice) in RPS_BEATS:
        desc = RPS_BEATS[(choice, bot_choice)]
        res = f"🏆 <b>ВЫ ПОБЕДИЛИ!</b>\n<i>{desc}</i>"
        if bet > 0:
            bal = await db.add_balance(uid, bet, "rps_solo_win")
            await db.add_game_xp(uid, 1, is_win=True)
            payout_txt = f"💰 <b>Выигрыш:</b> +<code>{bet*2:,}</code> 🪙\nБаланс: {money(bal)}"
        else:
            payout_txt = "Отличная интуиция!"
    else:
        desc = RPS_BEATS[(bot_choice, choice)]
        res = f"💀 <b>МОКСИ ПОБЕДИЛА!</b>\n<i>{desc}</i>"
        if bet > 0:
            bal = await db.add_balance(uid, -bet, "rps_solo_lose")
            await db.add_game_xp(uid, 1, is_win=False)
            payout_txt = f"📉 <b>Проигрыш:</b> −<code>{bet:,}</code> 🪙\nБаланс: {money(bal)}"
        else:
            payout_txt = "В следующий раз повезёт!"

    await call.message.edit_text(
        f"🪨✂️📄 <b>РЕЗУЛЬТАТ КНБ ПРОТИВ МОКСИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ваш выбор: <b>{p_txt}</b>\n"
        f"🍸 Выбор Мокси: <b>{b_txt}</b>\n\n"
        f"{res}\n{payout_txt}"
    )


@router.callback_query(F.data.startswith("rps:accept:"))
async def cb_rps_accept(call: CallbackQuery):
    gid = call.data.split(":")[2]
    game = RPS_GAMES.get(gid)
    if not game:
        return await call.answer("Игра устарела.", show_alert=True)
    if call.from_user.id != game["p2_id"]:
        return await call.answer("Только приглашённый игрок может принять вызов!", show_alert=True)

    game["accepted"] = True
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps:pick:{gid}:rock"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps:pick:{gid}:scissors"),
            InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps:pick:{gid}:paper"),
        ]
    ])
    await call.message.edit_text(
        f"🪨✂️📄 <b>ВЫЗОВ ПРИНЯТ! СДЕЛАЙТЕ СЕКРЕТНЫЙ ХОД</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Игрок 1:</b> {_mention_u(game['p1_id'], game['p1_name'])}\n"
        f"👤 <b>Игрок 2:</b> {_mention_u(game['p2_id'], game['p2_name'])}\n\n"
        f"👉 <i>Нажмите кнопку с вашим жестом (выбор останется скрытым от соперника!):</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("rps:decline:"))
async def cb_rps_decline(call: CallbackQuery):
    gid = call.data.split(":")[2]
    game = RPS_GAMES.pop(gid, None)
    if not game:
        return await call.answer("Игра уже не активна.")
    if call.from_user.id not in (game["p1_id"], game["p2_id"]):
        return await call.answer("Это не ваша дуэль!", show_alert=True)
    await call.message.edit_text(f"🛑 <b>Дуэль в КНБ отменена игроком {call.from_user.first_name}.</b>")


@router.callback_query(F.data.startswith("rps:pick:"))
async def cb_rps_pick(call: CallbackQuery):
    parts = call.data.split(":")
    gid, choice = parts[2], parts[3]
    game = RPS_GAMES.get(gid)
    if not game:
        return await call.answer("Игра завершена.", show_alert=True)

    uid = call.from_user.id
    if uid == game["p1_id"]:
        if game["p1_pick"]:
            return await call.answer("Вы уже сделали выбор!", show_alert=True)
        game["p1_pick"] = choice
        await call.answer(f"✅ Ваш выбор принят: {RPS_NAMES.get(choice)}!", show_alert=True)
    elif uid == game["p2_id"]:
        if game["p2_pick"]:
            return await call.answer("Вы уже сделали выбор!", show_alert=True)
        game["p2_pick"] = choice
        await call.answer(f"✅ Ваш выбор принят: {RPS_NAMES.get(choice)}!", show_alert=True)
    else:
        return await call.answer("Вы не участник этой дуэли!", show_alert=True)

    # Если оба сделали выбор — подводим итоги
    if game["p1_pick"] and game["p2_pick"]:
        RPS_GAMES.pop(gid, None)
        c1, c2 = game["p1_pick"], game["p2_pick"]
        p1_name, p2_name = game["p1_name"], game["p2_name"]
        p1_id, p2_id = game["p1_id"], game["p2_id"]
        bet = game["bet"]

        t1 = RPS_NAMES.get(c1, c1)
        t2 = RPS_NAMES.get(c2, c2)

        if c1 == c2:
            res_txt = "🤝 <b>БОЕВАЯ НИЧЬЯ!</b>\nСтавки сохранены."
        elif (c1, c2) in RPS_BEATS:
            reason = RPS_BEATS[(c1, c2)]
            pot = bet * 2
            if bet > 0:
                await db.add_balance(p1_id, bet, "rps_win")
                await db.add_balance(p2_id, -bet, "rps_lose")
                await db.add_game_xp(p1_id, 1, is_win=True)
                await db.add_game_xp(p2_id, 1, is_win=False)
                res_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p1_id, p1_name)}!</b>\n<i>{reason}</i>\n💰 Выигрыш: +<code>{pot:,}</code> 🪙"
            else:
                res_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p1_id, p1_name)}!</b>\n<i>{reason}</i>"
        else:
            reason = RPS_BEATS[(c2, c1)]
            pot = bet * 2
            if bet > 0:
                await db.add_balance(p2_id, bet, "rps_win")
                await db.add_balance(p1_id, -bet, "rps_lose")
                await db.add_game_xp(p2_id, 1, is_win=True)
                await db.add_game_xp(p1_id, 1, is_win=False)
                res_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p2_id, p2_name)}!</b>\n<i>{reason}</i>\n💰 Выигрыш: +<code>{pot:,}</code> 🪙"
            else:
                res_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p2_id, p2_name)}!</b>\n<i>{reason}</i>"

        await call.message.edit_text(
            f"🪨✂️📄 <b>ИТОГИ ДУЭЛИ В КНБ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {_mention_u(p1_id, p1_name)} выбрал: <b>{t1}</b>\n"
            f"👤 {_mention_u(p2_id, p2_name)} выбрал: <b>{t2}</b>\n\n"
            f"{res_txt}"
        )


# ══════════════════════════════════════════════════════════════════
# 2. 🥤 НАПЁРСТКИ (THIMBLES)
# ══════════════════════════════════════════════════════════════════

THIMBLE_GAMES: dict[str, dict] = {}

@router.message(Cmd("наперстки", "напёрстки", "стаканчики", "thimbles", section=S_GAMES,
                    usage="наперстки [ставка]", desc="🥤 Игра в Напёрстки с шариком (множитель x2.8)"))
async def cmd_thimbles(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    u = await db.get_user(uid)
    u_bal = int(u.get("balance", 0) or 0)
    bet = _parse_bet_arg(args, u_bal)

    if bet < MIN_BET:
        return await message.reply(
            f"🥤 <b>ИГРА В НАПЁРСТКИ</b>\n"
            f"Укажите ставку от {MIN_BET} 🪙: <code>наперстки 1000</code>\n"
            f"Под одним из трёх стаканчиков спрятан 💎 шарик. Коэффициент: <b>x2.8</b>!"
        )

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно средств! Баланс: {money(u_bal)} 🪙")

    gid = f"th_{uid}_{int(time.time()*1000)%100000}"
    ball_pos = random.randint(1, 3)

    THIMBLE_GAMES[gid] = {
        "uid": uid,
        "bet": bet,
        "ball": ball_pos,
        "created_at": time.time(),
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥤 Стаканчик №1", callback_data=f"th:pick:{gid}:1"),
            InlineKeyboardButton(text="🥤 Стаканчик №2", callback_data=f"th:pick:{gid}:2"),
            InlineKeyboardButton(text="🥤 Стаканчик №3", callback_data=f"th:pick:{gid}:3"),
        ]
    ])

    await message.reply(
        f"🥤 <b>КРУЧУ-ВЕРЧУ, ЗАПУТАТЬ ХОЧУ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Шарик спрятан под одним из трёх стаканчиков.\n"
        f"💰 Ставка: <code>{bet:,}</code> 🪙 · Приз: <code>{int(bet*2.8):,}</code> 🪙 (x2.8)\n\n"
        f"👇 <i>Угадайте, где спрятан шарик:</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("th:pick:"))
async def cb_thimble_pick(call: CallbackQuery):
    parts = call.data.split(":")
    gid, pick = parts[2], int(parts[3])
    game = THIMBLE_GAMES.pop(gid, None)
    if not game:
        return await call.answer("Игра уже завершена.", show_alert=True)

    if call.from_user.id != game["uid"]:
        return await call.answer("Это не ваши напёрстки!", show_alert=True)

    uid = game["uid"]
    bet = game["bet"]
    ball = game["ball"]

    cups = ["🥤", "🥤", "🥤"]
    cups[ball - 1] = "💎"

    if pick == ball:
        payout = int(bet * 2.8)
        bal = await db.add_balance(uid, payout - bet, "thimbles_win")
        await db.add_game_xp(uid, 1, is_win=True)
        res_txt = (
            f"🎉 <b>ПОБЕДА! ВЫ УГАДАЛИ!</b>\n"
            f"Шарик действительно был под стаканчиком №{pick}!\n\n"
            f"💰 <b>Выигрыш (x2.8):</b> +<code>{payout:,}</code> 🪙\n"
            f"💳 Баланс: {money(bal)}"
        )
    else:
        bal = await db.add_balance(uid, -bet, "thimbles_lose")
        await db.add_game_xp(uid, 1, is_win=False)
        res_txt = (
            f"💨 <b>МИМО! ПУСТО!</b>\n"
            f"Вы выбрали стаканчик №{pick}, а шарик был под №{ball}!\n\n"
            f"📉 <b>Проигрыш:</b> −<code>{bet:,}</code> 🪙\n"
            f"💳 Баланс: {money(bal)}"
        )

    cups_visual = f"{cups[0]} [1]    {cups[1]} [2]    {cups[2]} [3]"
    await call.message.edit_text(
        f"🥤 <b>ИТОГИ ИГРЫ В НАПЁРСТКИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{cups_visual}\n\n"
        f"{res_txt}"
    )


# ══════════════════════════════════════════════════════════════════
# 3. 🔫 РУССКАЯ РУЛЕТКА (RUSSIAN ROULETTE PVP)
# ══════════════════════════════════════════════════════════════════

ROULETTE_GAMES: dict[str, dict] = {}

@router.message(Cmd("русская рулетка", "гусарская рулетка", "револьвер", section=S_GAMES,
                    usage="русская рулетка @юзер [ставка]", desc="🔫 Русская рулетка с револьвером на 6 камор"))
async def cmd_russian_roulette(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u = await db.get_user(uid)
    u_bal = int(u.get("balance", 0) or 0)

    target_id, target_name, rem_args = await resolve_target(message, args, bot)
    if not target_id or target_id == uid:
        return await message.reply("🔫 <b>Русская рулетка проводится вдвоём!</b>\nУкажите оппонента: <code>русская рулетка @юзер [ставка]</code>")

    bet = _parse_bet_arg(rem_args, u_bal)
    if bet > 0 and u_bal < bet:
        return await message.reply(f"💰 Недостаточно средств для ставки! Баланс: {money(u_bal)} 🪙")

    t_data = await db.get_user(target_id)
    t_bal = int(t_data.get("balance", 0) or 0)
    if bet > 0 and t_bal < bet:
        return await message.reply(f"❌ У соперника недостаточно монет ({money(t_bal)} 🪙).")

    gid = f"rr_{uid}_{target_id}_{int(time.time()*1000)%100000}"
    bullet_slot = random.randint(1, 6)

    ROULETTE_GAMES[gid] = {
        "p1_id": uid,
        "p1_name": uname,
        "p2_id": target_id,
        "p2_name": target_name,
        "current_turn": uid,
        "chambers_left": 6,
        "bullet_chamber": bullet_slot,
        "cur_slot": 1,
        "bet": bet,
        "accepted": False,
        "chat_id": message.chat.id,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔫 Принять вызов", callback_data=f"rr:accept:{gid}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"rr:decline:{gid}"),
        ]
    ])

    bet_txt = f"\n💰 <b>Банк на кону:</b> <code>{bet*2:,}</code> 🪙" if bet > 0 else "\n💀 <i>Игра на честь и репутацию</i>"
    await message.reply(
        f"🔫 <b>ВЫЗОВ В РУССКУЮ РУЛЕТКУ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {_mention_u(uid, uname)} заряжает 1 боевой патрон в барабан на 6 камор и бросает вызов {_mention_u(target_id, target_name)}!{bet_txt}\n\n"
        f"Готовы ли вы испытать судьбу?",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("rr:accept:"))
async def cb_rr_accept(call: CallbackQuery):
    gid = call.data.split(":")[2]
    game = ROULETTE_GAMES.get(gid)
    if not game:
        return await call.answer("Игра устарела.")
    if call.from_user.id != game["p2_id"]:
        return await call.answer("Только оппонент может принять вызов!", show_alert=True)

    game["accepted"] = True
    shooter_name = game["p1_name"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔫 Спустить курок", callback_data=f"rr:trigger:{gid}")]
    ])
    await call.message.edit_text(
        f"🔫 <b>БАРАБАН РАСКРУЧЕН! 1 ПАТРОН ИЗ 6</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 Первым спускает курок: <b>{html.escape(shooter_name)}</b>\n"
        f"Осталось камор: <b>6</b> (Шанс выстрела: ~17%)\n\n"
        f"<i>Приложите ствол к виску и нажмите кнопку...</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("rr:decline:"))
async def cb_rr_decline(call: CallbackQuery):
    gid = call.data.split(":")[2]
    game = ROULETTE_GAMES.pop(gid, None)
    if not game:
        return await call.answer("Игра уже не активна.")
    if call.from_user.id not in (game["p1_id"], game["p2_id"]):
        return await call.answer("Это не ваша дуэль!", show_alert=True)
    await call.message.edit_text(f"🛑 <b>{call.from_user.first_name} побоялся рисковать жизнью и отклонил рулетку.</b>")


@router.callback_query(F.data.startswith("rr:trigger:"))
async def cb_rr_trigger(call: CallbackQuery):
    gid = call.data.split(":")[2]
    game = ROULETTE_GAMES.get(gid)
    if not game:
        return await call.answer("Игра завершена.", show_alert=True)

    uid = call.from_user.id
    if uid != game["current_turn"]:
        return await call.answer("Сейчас не ваша очередь спускать курок!", show_alert=True)

    cur_slot = game["cur_slot"]
    bullet = game["bullet_chamber"]
    chambers = game["chambers_left"]
    bet = game["bet"]

    # Проверка выстрела
    if cur_slot == bullet:
        # ВЫСТРЕЛ!
        ROULETTE_GAMES.pop(gid, None)
        dead_id = uid
        dead_name = game["p1_name"] if uid == game["p1_id"] else game["p2_name"]
        winner_id = game["p2_id"] if uid == game["p1_id"] else game["p1_id"]
        winner_name = game["p2_name"] if uid == game["p1_id"] else game["p1_name"]

        pot_txt = ""
        if bet > 0:
            await db.add_balance(winner_id, bet, "rr_win")
            await db.add_balance(dead_id, -bet, "rr_lose")
            await db.add_game_xp(winner_id, 2, is_win=True)
            pot_txt = f"\n💰 <b>Банк игры:</b> +<code>{bet*2:,}</code> 🪙 зачислен выжившему!"

        return await call.message.edit_text(
            f"💥 <b>БА-БАХ! РАЗДАЛСЯ РОКОВОЙ ВЫСТРЕЛ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💀 <b>{html.escape(dead_name)}</b> спустил курок и словил пулю!\n"
            f"🏆 Победитель и выживший: {_mention_u(winner_id, winner_name)}!{pot_txt}\n\n"
            f"🪦 <i>Медики уносят проигравшего на носилках...</i>"
        )
    else:
        # ОСЕЧКА! ПУСТО!
        game["cur_slot"] += 1
        game["chambers_left"] -= 1
        # Передаем ход
        next_id = game["p2_id"] if uid == game["p1_id"] else game["p1_id"]
        next_name = game["p2_name"] if uid == game["p1_id"] else game["p1_name"]
        game["current_turn"] = next_id

        chance = int(100 / game["chambers_left"])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔫 Спустить курок", callback_data=f"rr:trigger:{gid}")]
        ])
        await call.message.edit_text(
            f"💨 <b>*ЩЁЛК* — ПАТРОННИК ПУСТ! ПОВЕЗЛО!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{call.from_user.first_name}</b> остаётся в живых!\n"
            f"Осталось камор: <b>{game['chambers_left']}</b> (Шанс выстрела: <b>{chance}%</b>)\n\n"
            f"👉 Револьвер переходит к: {_mention_u(next_id, next_name)}!\n"
            f"<i>Ваша очередь нажать на курок...</i>",
            reply_markup=kb
        )


# ══════════════════════════════════════════════════════════════════
# 4. 🤠 КОВБОЙ / ДУЭЛЬ НА РЕАКЦИЮ (QUICK DRAW)
# ══════════════════════════════════════════════════════════════════

COWBOY_GAMES: dict[str, dict] = {}

@router.message(Cmd("ковбой", "дуэль реакция", "стрелок", section=S_GAMES,
                    usage="ковбой @юзер [ставка]", desc="🤠 Ковбойская дуэль на скорость реакции"))
async def cmd_cowboy(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u = await db.get_user(uid)
    u_bal = int(u.get("balance", 0) or 0)

    target_id, target_name, rem_args = await resolve_target(message, args, bot)
    if not target_id or target_id == uid:
        return await message.reply("🤠 <b>Ковбойская дуэль требует соперника!</b>\nИспользование: <code>ковбой @юзер [ставка]</code>")

    bet = _parse_bet_arg(rem_args, u_bal)
    if bet > 0 and u_bal < bet:
        return await message.reply(f"💰 Недостаточно средств для ставки! Баланс: {money(u_bal)} 🪙")

    t_data = await db.get_user(target_id)
    t_bal = int(t_data.get("balance", 0) or 0)
    if bet > 0 and t_bal < bet:
        return await message.reply(f"❌ У соперника недостаточно монет ({money(t_bal)} 🪙).")

    gid = f"cb_{uid}_{target_id}_{int(time.time()*1000)%100000}"
    COWBOY_GAMES[gid] = {
        "p1_id": uid,
        "p1_name": uname,
        "p2_id": target_id,
        "p2_name": target_name,
        "bet": bet,
        "state": "waiting_accept",
        "signal_time": 0.0,
        "chat_id": message.chat.id,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤠 Принять дуэль", callback_data=f"cb:accept:{gid}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"cb:decline:{gid}"),
        ]
    ])

    bet_txt = f"\n💰 <b>Банк на кону:</b> <code>{bet*2:,}</code> 🪙" if bet > 0 else "\n🏆 <i>Стрельба на звание быстрейшего на Диком Западе</i>"
    await message.reply(
        f"🌵 <b>КОВБОЙСКАЯ ДУЭЛЬ НА РЕАКЦИЮ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤠 {_mention_u(uid, uname)} вызывает на перестрелку {_mention_u(target_id, target_name)}!{bet_txt}\n\n"
        f"Кто первым выстрелит по сигналу «ОГОНЬ» — тот и победит!\n"
        f"⚠️ <i>Нажатие ДО сигнала считается фальстартом и мгновенным поражением!</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("cb:accept:"))
async def cb_cowboy_accept(call: CallbackQuery, bot: Bot):
    gid = call.data.split(":")[2]
    game = COWBOY_GAMES.get(gid)
    if not game:
        return await call.answer("Игра устарела.")
    if call.from_user.id != game["p2_id"]:
        return await call.answer("Только вызванный игрок может принять вызов!", show_alert=True)

    game["state"] = "standoff"
    kb_standby = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 ЖДИТЕ СИГНАЛА...", callback_data=f"cb:shot:{gid}:false")]
    ])

    await call.message.edit_text(
        f"🌵 <b>ПОЛДЕНЬ НА ДИКОМ ЗАПАДЕ...</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Дуэлянты положили руки на кобуру.\n"
        f"Ветер гоняет перекати-поле...\n\n"
        f"⏳ <b>ЖДИТЕ СИГНАЛА «ОГОНЬ!»...</b>\n"
        f"<i>(Не нажимайте кнопку раньше времени — это фальстарт!)</i>",
        reply_markup=kb_standby
    )

    # Запускаем отложенный выстрел
    delay = random.uniform(3.0, 6.0)
    asyncio.create_task(_cowboy_signal_worker(bot, call.message.chat.id, call.message.message_id, gid, delay))


async def _cowboy_signal_worker(bot: Bot, chat_id: int, msg_id: int, gid: str, delay: float):
    await asyncio.sleep(delay)
    game = COWBOY_GAMES.get(gid)
    if not game or game["state"] != "standoff":
        return

    game["state"] = "fire"
    game["signal_time"] = time.time()

    kb_fire = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💥 ОГОНЬ! ВЫСТРЕЛ! 💥", callback_data=f"cb:shot:{gid}:fire")]
    ])

    try:
        await bot.edit_message_text(
            f"🔥 <b>ОГОНЬ! ВЫСТРЕЛ! СТРЕЛЯЙТЕ!</b> 🔥\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>ЖМИТЕ КНОПКУ ПРЯМО СЕЙЧАС!</b>",
            chat_id=chat_id,
            message_id=msg_id,
            reply_markup=kb_fire
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("cb:shot:"))
async def cb_cowboy_shot(call: CallbackQuery):
    parts = call.data.split(":")
    gid, action = parts[2], parts[3]
    game = COWBOY_GAMES.get(gid)
    if not game:
        return await call.answer("Дуэль уже завершена.", show_alert=True)

    uid = call.from_user.id
    if uid not in (game["p1_id"], game["p2_id"]):
        return await call.answer("Вы зритель в этой дуэли!", show_alert=True)

    bet = game["bet"]
    p1_id, p2_id = game["p1_id"], game["p2_id"]
    p1_name, p2_name = game["p1_name"], game["p2_name"]

    # ФАЛЬСТАРТ (нажатие раньше времени)
    if action == "false" or game["state"] == "standoff":
        COWBOY_GAMES.pop(gid, None)
        loser_id = uid
        loser_name = p1_name if uid == p1_id else p2_name
        winner_id = p2_id if uid == p1_id else p1_id
        winner_name = p2_name if uid == p1_id else p1_name

        pot_txt = ""
        if bet > 0:
            await db.add_balance(winner_id, bet, "cowboy_win")
            await db.add_balance(loser_id, -bet, "cowboy_lose")
            pot_txt = f"\n💰 <b>Банк:</b> +<code>{bet*2:,}</code> 🪙 достался {_mention_u(winner_id, winner_name)}!"

        return await call.message.edit_text(
            f"🚫 <b>ФАЛЬСТАРТ! РУКА ДРОГНУЛА!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤠 <b>{html.escape(loser_name)}</b> не сдержал нервы и выстрелил ДО сигнала!\n"
            f"🏆 Победитель дуэли: {_mention_u(winner_id, winner_name)}!{pot_txt}"
        )

    # ЧЕСТНЫЙ ВЫСТРЕЛ ПО СИГНАЛУ
    if game["state"] == "fire":
        COWBOY_GAMES.pop(gid, None)
        reaction_ms = int((time.time() - game["signal_time"]) * 1000)

        winner_id = uid
        winner_name = p1_name if uid == p1_id else p2_name
        loser_id = p2_id if uid == p1_id else p1_id
        loser_name = p2_name if uid == p1_id else p1_name

        pot_txt = ""
        if bet > 0:
            await db.add_balance(winner_id, bet, "cowboy_win")
            await db.add_balance(loser_id, -bet, "cowboy_lose")
            await db.add_game_xp(winner_id, 2, is_win=True)
            pot_txt = f"\n💰 <b>Банк дуэли:</b> +<code>{bet*2:,}</code> 🪙"

        return await call.message.edit_text(
            f"💥 <b>БАХ! МГНОВЕННЫЙ ВЫСТРЕЛ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 Самый быстрый стрелок: {_mention_u(winner_id, winner_name)}!\n"
            f"⚡ <b>Скорость реакции:</b> <code>{reaction_ms} мс</code>!\n"
            f"💀 {_mention_u(loser_id, loser_name)} не успел даже моргнуть!{pot_txt}"
        )


# ══════════════════════════════════════════════════════════════════
# 5. 🎲 КОСТИ PVP (DICE DUEL)
# ══════════════════════════════════════════════════════════════════

DICE_GAMES: dict[str, dict] = {}

@router.message(Cmd("кости дуэль", "кубики дуэль", "дуэль кости", section=S_GAMES,
                    usage="кости дуэль @юзер [ставка]", desc="🎲 Дуэль двух игроков на кубиках Telegram"))
async def cmd_dice_duel(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u = await db.get_user(uid)
    u_bal = int(u.get("balance", 0) or 0)

    target_id, target_name, rem_args = await resolve_target(message, args, bot)
    if not target_id or target_id == uid:
        return await message.reply("🎲 <b>Укажите соперника для костяной дуэли:</b> <code>кости дуэль @юзер [ставка]</code>")

    bet = _parse_bet_arg(rem_args, u_bal)
    if bet > 0 and u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет для ставки! Баланс: {money(u_bal)} 🪙")

    t_data = await db.get_user(target_id)
    t_bal = int(t_data.get("balance", 0) or 0)
    if bet > 0 and t_bal < bet:
        return await message.reply(f"❌ У соперника недостаточно монет ({money(t_bal)} 🪙).")

    gid = f"dd_{uid}_{target_id}_{int(time.time()*1000)%100000}"
    DICE_GAMES[gid] = {
        "p1_id": uid,
        "p1_name": uname,
        "p2_id": target_id,
        "p2_name": target_name,
        "bet": bet,
        "chat_id": message.chat.id,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Бросить кости!", callback_data=f"dd:accept:{gid}"),
            InlineKeyboardButton(text="❌ Отказ", callback_data=f"dd:decline:{gid}"),
        ]
    ])

    bet_txt = f"\n💰 <b>Банк игры:</b> <code>{bet*2:,}</code> 🪙" if bet > 0 else "\n🎮 <i>Дружеский бросок</i>"
    await message.reply(
        f"🎲 <b>БИТВА НА КУБИКАХ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {_mention_u(uid, uname)} вызывает {_mention_u(target_id, target_name)} на бросок костей!{bet_txt}\n\n"
        f"Каждый бросает нативный кубик 🎲. У кого больше очков — забирает банк!",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("dd:accept:"))
async def cb_dice_duel_accept(call: CallbackQuery, bot: Bot):
    gid = call.data.split(":")[2]
    game = DICE_GAMES.pop(gid, None)
    if not game:
        return await call.answer("Игра устарела.")
    if call.from_user.id != game["p2_id"]:
        return await call.answer("Только приглашённый игрок может бросить кости!", show_alert=True)

    p1_id, p1_name = game["p1_id"], game["p1_name"]
    p2_id, p2_name = game["p2_id"], game["p2_name"]
    bet = game["bet"]
    cid = game["chat_id"]

    await call.message.edit_text(f"🎲 <b>ДУЭЛЯНТЫ БРОСАЮТ КОСТИ!</b>\n━━━━━━━━━━━━━━━━━━━━\nБросок первого игрока...")

    # Бросок 1
    m1 = await bot.send_dice(cid, emoji="🎲")
    await asyncio.sleep(3.5)
    v1 = m1.dice.value if m1.dice else random.randint(1, 6)

    # Бросок 2
    await bot.send_message(cid, f"🎲 Бросок второго игрока...")
    m2 = await bot.send_dice(cid, emoji="🎲")
    await asyncio.sleep(3.5)
    v2 = m2.dice.value if m2.dice else random.randint(1, 6)

    if v1 > v2:
        winner_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p1_id, p1_name)} ({v1} против {v2})!</b>"
        if bet > 0:
            await db.add_balance(p1_id, bet, "dice_win")
            await db.add_balance(p2_id, -bet, "dice_lose")
            await db.add_game_xp(p1_id, 1, is_win=True)
            winner_txt += f"\n💰 Выигрыш: +<code>{bet*2:,}</code> 🪙"
    elif v2 > v1:
        winner_txt = f"🏆 <b>ПОБЕДИТЕЛЬ: {_mention_u(p2_id, p2_name)} ({v2} против {v1})!</b>"
        if bet > 0:
            await db.add_balance(p2_id, bet, "dice_win")
            await db.add_balance(p1_id, -bet, "dice_lose")
            await db.add_game_xp(p2_id, 1, is_win=True)
            winner_txt += f"\n💰 Выигрыш: +<code>{bet*2:,}</code> 🪙"
    else:
        winner_txt = f"🤝 <b>БОЕВАЯ НИЧЬЯ ({v1} : {v2})!</b>\nСтавки возвращены игрокам."

    await bot.send_message(
        cid,
        f"🎲 <b>ИТОГИ КОСТЯНОЙ ДУЭЛИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {_mention_u(p1_id, p1_name)}: <b>{v1}</b> 🎲\n"
        f"👤 {_mention_u(p2_id, p2_name)}: <b>{v2}</b> 🎲\n\n"
        f"{winner_txt}"
    )


# ══════════════════════════════════════════════════════════════════
# 6. 🧠 ВИКТОРИНА / КВИЗ ЧАТА (TRIVIA)
# ══════════════════════════════════════════════════════════════════

QUIZ_QUESTIONS = [
    {
        "q": "🎮 В какой игре главным героем является Геральт из Ривии?",
        "options": ["The Witcher", "Skyrim", "Dark Souls", "Dragon Age"],
        "answer": 0,
    },
    {
        "q": "🎬 Какой фильм получил больше всего статуэток Оскар в истории (11 наград)?",
        "options": ["Аватар", "Титаник", "Гладиатор", "Начало"],
        "answer": 1,
    },
    {
        "q": "🌍 Какой самый большой океан на планете Земля?",
        "options": ["Атлантический", "Индийский", "Тихий", "Северный Ледовитый"],
        "answer": 2,
    },
    {
        "q": "🚀 Какая планета Солнечной системы называется Красной планетой?",
        "options": ["Венера", "Марс", "Юпитер", "Меркурий"],
        "answer": 1,
    },
    {
        "q": "👾 В каком году вышла первая версия игры Minecraft?",
        "options": ["2007", "2009", "2011", "2013"],
        "answer": 1,
    },
    {
        "q": "⚡ Какая элементарная частица имеет отрицательный электрический заряд?",
        "options": ["Протон", "Нейтрон", "Электрон", "Фотон"],
        "answer": 2,
    },
    {
        "q": "🏛 В каком городе находится знаменитый Колизей?",
        "options": ["Афины", "Рим", "Париж", "Мадрид"],
        "answer": 1,
    },
    {
        "q": "🐍 Какой язык программирования назван в честь британского комедийного шоу?",
        "options": ["Python", "Java", "Ruby", "Kotlin"],
        "answer": 0,
    },
    {
        "q": "🐉 Кто был главным злодеем в первой части трилогии «Властелин Колец»?",
        "options": ["Саруман", "Саурон", "Голлум", "Смауг"],
        "answer": 1,
    },
    {
        "q": "🏎 Какая компания производит культовую модель спорткара 911?",
        "options": ["Ferrari", "Lamborghini", "Porsche", "BMW"],
        "answer": 2,
    },
]

ACTIVE_QUIZZES: dict[str, dict] = {}

@router.message(Cmd("квиз", "викторина", "вопрос", section=S_GAMES,
                    usage="квиз", desc="🧠 Запустить интеллектуальную викторину с призовыми монетами"))
async def cmd_quiz(message: Message, **kw):
    if not await _check_casino_allowed(message):
        return

    q_data = random.choice(QUIZ_QUESTIONS)
    qid = f"qz_{int(time.time()*1000)%100000}"
    prize = 2500

    ACTIVE_QUIZZES[qid] = {
        "answer": q_data["answer"],
        "prize": prize,
        "solved": False,
        "created_at": time.time(),
    }

    buttons = []
    for idx, opt in enumerate(q_data["options"]):
        buttons.append([InlineKeyboardButton(text=opt, callback_data=f"qz:ans:{qid}:{idx}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(
        f"🧠 <b>ИНТЕЛЛЕКТУАЛЬНЫЙ КВИЗ MOXXI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ <b>Вопрос:</b>\n{q_data['q']}\n\n"
        f"💰 <b>Награда первому ответившему:</b> <code>+{prize:,}</code> 🪙 и <code>+50 XP</code>\n"
        f"👇 <i>Выберите верный вариант:</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("qz:ans:"))
async def cb_quiz_answer(call: CallbackQuery):
    parts = call.data.split(":")
    qid, choice = parts[2], int(parts[3])
    quiz = ACTIVE_QUIZZES.get(qid)
    if not quiz:
        return await call.answer("Время викторины вышло или вопрос закрыт.", show_alert=True)

    if quiz["solved"]:
        return await call.answer("Кто-то уже дал правильный ответ на этот вопрос!", show_alert=True)

    uid = call.from_user.id
    uname = call.from_user.first_name

    if choice == quiz["answer"]:
        quiz["solved"] = True
        ACTIVE_QUIZZES.pop(qid, None)
        prize = quiz["prize"]

        bal = await db.add_balance(uid, prize, "quiz_reward")
        await db.add_xp(uid, 50)

        await call.message.edit_text(
            f"🎉 <b>ВИКТОРИНА ЗАВЕРШЕНА!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 Победитель: {_mention_u(uid, uname)}!\n"
            f"✅ <b>Правильный ответ дан первым!</b>\n\n"
            f"💰 <b>Награда:</b> +<code>{prize:,}</code> 🪙 (Баланс: {money(bal)})\n"
            f"⭐ Опыт: <b>+50 XP</b>!"
        )
    else:
        await call.answer("❌ Неверный ответ! Попробуйте другой вариант или дайте шанс другим.", show_alert=True)



# ══════════════════════════════════════════════════════════════════
# 7. 🏰 БАШНЯ / ЛЕСЕНКА (TOWER LADDER)
# ══════════════════════════════════════════════════════════════════

ACTIVE_TOWERS: dict[str, dict] = {}
TOWER_MULTS = {1: 1.40, 2: 2.00, 3: 3.00, 4: 4.50, 5: 7.00}


def _get_tower_kb(gid: str, floor: int, can_cashout: bool, cur_win: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🚪 Дверь #1", callback_data=f"tw:door:{gid}:0"),
            InlineKeyboardButton(text="🚪 Дверь #2", callback_data=f"tw:door:{gid}:1"),
            InlineKeyboardButton(text="🚪 Дверь #3", callback_data=f"tw:door:{gid}:2"),
        ]
    ]
    if can_cashout and cur_win > 0:
        buttons.append([
            InlineKeyboardButton(text=f"💰 ЗАБРАТЬ КУШ ({cur_win:,} 🪙)", callback_data=f"tw:cashout:{gid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Cmd("башня", "лесенка", "tower", "ladder", section=S_GAMES,
                    usage="башня {ставка}", desc="🏰 Подъём по этажам башни до x7.0 куша"))
async def cmd_tower(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "🏰 <b>Игра «Башня / Лесенка»:</b>\n"
            "Пройдите 5 этажей цитадели и заберите супер-куш <b>х7.00</b>!\n"
            "На каждом этаже 3 двери: 2 безопасных пути и 1 коварная ловушка.\n\n"
            f"👉 <b>Пример:</b> <code>башня 1000</code> (минимум {MIN_BET} 🪙)"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    gid = f"tw_{uid}_{int(time.time() * 1000)}"
    await db.add_balance(uid, -bet, "tower_bet")
    lock_game(uid, "tower", message.chat.id)

    trap = random.randint(0, 2)
    ACTIVE_TOWERS[gid] = {
        "uid": uid,
        "uname": uname,
        "bet": bet,
        "floor": 1,
        "cur_win": 0,
        "trap": trap,
        "created_at": time.time()
    }

    kb = _get_tower_kb(gid, floor=1, can_cashout=False, cur_win=0)
    text = (
        "🏰 <b>БАШНЯ MOXXI · ЭТАЖ 1 ИЗ 5</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, uname)}\n"
        f"💵 Ставка: <code>{bet:,}</code> 🪙\n"
        f"🎯 Множитель этажа: <b>x{TOWER_MULTS[1]}</b>\n\n"
        "⚠️ <i>На этаже 3 двери. За одной из них — смертельная ловушка!</i>\n"
        "👇 <b>Выберите дверь для входа:</b>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("tw:door:"))
async def cb_tower_door(call: CallbackQuery):
    parts = call.data.split(":")
    gid, chosen_door = parts[2], int(parts[3])
    st = ACTIVE_TOWERS.get(gid)
    if not st:
        return await call.answer("Игра завершена или время истекло.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваша башня!", show_alert=True)

    floor = st["floor"]
    trap = st["trap"]
    bet = st["bet"]
    uname = st["uname"]

    if chosen_door == trap:
        ACTIVE_TOWERS.pop(gid, None)
        unlock_game(uid)
        doors_view = ["🚪", "🚪", "🚪"]
        doors_view[trap] = "💥 ЛОВУШКА!"
        text = (
            "💥 <b>ОБВАЛ ЭТАЖА! ВЫ ПОГИБЛИ!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"💀 Дверь #{chosen_door + 1} оказалась ловушкой!\n"
            f"🚪 Раскладка: <code>{' | '.join(doors_view)}</code>\n\n"
            f"💸 <b>Потеряно:</b> <code>-{bet:,}</code> 🪙\n"
            f"🏰 Попробуйте подняться снова: <code>башня {bet}</code>"
        )
        return await call.message.edit_text(text)

    cur_win = int(bet * TOWER_MULTS[floor])
    st["cur_win"] = cur_win

    if floor >= 5:
        ACTIVE_TOWERS.pop(gid, None)
        unlock_game(uid)
        bal = await db.add_balance(uid, cur_win, "tower_jackpot")
        await db.add_game_xp(uid, 100)
        text = (
            "👑 <b>ВЕРШИНА БАШНИ ПОКОРЕНА! МЕГА-КУШ!</b> 👑\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 Герой: {_mention_u(uid, uname)}\n"
            "🏰 Все 5 этажей успешно пройдены!\n"
            f"🔥 Множитель: <b>x{TOWER_MULTS[5]}</b>\n\n"
            f"💰 <b>ВЫИГРЫШ:</b> +<code>{cur_win:,}</code> 🪙 (Баланс: {money(bal)})\n"
            "⭐ Опыт: <b>+100 XP</b>!"
        )
        return await call.message.edit_text(text)

    st["floor"] += 1
    st["trap"] = random.randint(0, 2)
    next_floor = st["floor"]
    next_mult = TOWER_MULTS[next_floor]

    kb = _get_tower_kb(gid, floor=next_floor, can_cashout=True, cur_win=cur_win)
    text = (
        f"🏰 <b>ЭТАЖ {floor} ПРОЙДЕН! ПОДЪЁМ НА ЭТАЖ {next_floor}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, uname)}\n"
        f"💰 Накопленный куш: <b>+{cur_win:,}</b> 🪙 (x{TOWER_MULTS[floor]})\n"
        f"🎯 Множитель этажа {next_floor}: <b>x{next_mult}</b>\n\n"
        f"👇 <i>Откройте дверь на этаже {next_floor} или заберите золото:</i>"
    )
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("tw:cashout:"))
async def cb_tower_cashout(call: CallbackQuery):
    parts = call.data.split(":")
    gid = parts[2]
    st = ACTIVE_TOWERS.pop(gid, None)
    if not st:
        return await call.answer("Игра уже завершена.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваша башня!", show_alert=True)

    unlock_game(uid)
    cur_win = st["cur_win"]
    bal = await db.add_balance(uid, cur_win, "tower_win")
    await db.add_game_xp(uid, 30)

    text = (
        "💰 <b>КУШ УСПЕШНО ЗАБРАН ИЗ БАШНИ!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, st['uname'])}\n"
        f"🏰 Завершено на этаже: <b>#{st['floor']}</b>\n"
        f"🎉 <b>Выигрыш:</b> +<code>{cur_win:,}</code> 🪙\n"
        f"💳 Текущий баланс: {money(bal)} 🪙"
    )
    await call.message.edit_text(text)


# ══════════════════════════════════════════════════════════════════
# 8. 📦 СУНДУКИ ФОРТУНЫ (CHESTS OF FORTUNE)
# ══════════════════════════════════════════════════════════════════

ACTIVE_CHESTS: dict[str, dict] = {}


@router.message(Cmd("сундуки", "сундук", "chests", "chest", section=S_GAMES,
                    usage="сундуки {ставка}", desc="📦 4 сундука удачи с множителем до x3.50"))
async def cmd_chests(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "📦 <b>Игра «Сундуки Фортуны»:</b>\n"
            "Перед вами 4 древних сундука. В одном из них спрятан <b>Бриллиантовый куш х3.50</b>!\n"
            "Призы: 💎 х3.50 | 💰 х2.00 | 🪙 х1.25 | 💀 0х (Мимик)\n\n"
            f"👉 <b>Пример:</b> <code>сундуки 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    gid = f"ch_{uid}_{int(time.time() * 1000)}"
    await db.add_balance(uid, -bet, "chests_bet")
    lock_game(uid, "chests", message.chat.id)

    pool = [3.50, 2.00, 1.25, 0.0]
    random.shuffle(pool)

    ACTIVE_CHESTS[gid] = {
        "uid": uid,
        "uname": uname,
        "bet": bet,
        "pool": pool,
        "created_at": time.time()
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Сундук #1", callback_data=f"ch:pick:{gid}:0"),
            InlineKeyboardButton(text="📦 Сундук #2", callback_data=f"ch:pick:{gid}:1"),
        ],
        [
            InlineKeyboardButton(text="📦 Сундук #3", callback_data=f"ch:pick:{gid}:2"),
            InlineKeyboardButton(text="📦 Сундук #4", callback_data=f"ch:pick:{gid}:3"),
        ]
    ])

    text = (
        "📦 <b>СУНДУКИ ФОРТУНЫ MOXXI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Искатель сокровищ: {_mention_u(uid, uname)}\n"
        f"💵 Ставка: <code>{bet:,}</code> 🪙\n\n"
        "👇 <i>Откройте один из 4 сундуков удачи:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("ch:pick:"))
async def cb_chests_pick(call: CallbackQuery):
    parts = call.data.split(":")
    gid, chosen = parts[2], int(parts[3])
    st = ACTIVE_CHESTS.pop(gid, None)
    if not st:
        return await call.answer("Игра завершена или время истекло.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваши сундуки!", show_alert=True)

    unlock_game(uid)
    bet = st["bet"]
    pool = st["pool"]
    uname = st["uname"]
    mult = pool[chosen]

    icons = {3.50: "💎 x3.50", 2.00: "💰 x2.00", 1.25: "🪙 x1.25", 0.0: "💀 0x (Мимик)"}
    revealed_lines = [f"{'👉 ' if i == chosen else '   '}Сундук #{i+1}: {icons[pool[i]]}" for i in range(4)]

    if mult > 0:
        win = int(bet * mult)
        bal = await db.add_balance(uid, win, "chests_win")
        await db.add_game_xp(uid, 25)
        text = (
            f"🎉 <b>СУНДУК ВЗЛОМАН! ВЫИГРЫШ: +{win:,} 🪙</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"✨ В выбранном сундуке: <b>{icons[mult]}</b>\n\n"
            "📋 <b>Содержимое всех сундуков:</b>\n"
            + "\n".join(revealed_lines) + "\n\n"
            f"💳 Баланс: {money(bal)} 🪙 | ⭐ Опыт: <b>+25 XP</b>"
        )
        await call.message.edit_text(text)
    else:
        text = (
            "💀 <b>ПУСТОЙ СУНДУК! ЛОВУШКА МИМИКА!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"❌ В сундуке #{chosen+1} не оказалось сокровищ!\n\n"
            "📋 <b>Где лежали сокровища:</b>\n"
            + "\n".join(revealed_lines) + "\n\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"📦 Попробовать ещё раз: <code>сундуки {bet}</code>"
        )
        await call.message.edit_text(text)


# ══════════════════════════════════════════════════════════════════
# 9. 🃏 ХАЙ-ЛОУ (БОЛЬШЕ ИЛИ МЕНЬШЕ)
# ══════════════════════════════════════════════════════════════════

ACTIVE_HIGHLOW: dict[str, dict] = {}
HL_MULTS = [1.40, 2.20, 3.50, 5.50, 10.00]
CARD_RANKS = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "Валет (J)", 12: "Дама (Q)", 13: "Король (K)", 14: "Туз (A)"}
CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]


def _format_card(rank: int, suit: str) -> str:
    return f"<b>[{CARD_RANKS[rank]} {suit}]</b>"


@router.message(Cmd("хайлоу", "больше меньше", "highlow", "карты", section=S_GAMES,
                    usage="хайлоу {ставка}", desc="🃏 Угадай карту: больше или меньше (до x10.0)"))
async def cmd_highlow(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "🃏 <b>Игра «Хай-Лоу (Больше / Меньше)»:</b>\n"
            "Угадайте, будет ли следующая карта колоды старше или младше текущей!\n"
            "Серия побед: 1x (х1.4) ➔ 2x (х2.2) ➔ 3x (х3.5) ➔ 4x (х5.5) ➔ 5x (х10.0)!\n\n"
            f"👉 <b>Пример:</b> <code>хайлоу 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    gid = f"hl_{uid}_{int(time.time() * 1000)}"
    await db.add_balance(uid, -bet, "highlow_bet")
    lock_game(uid, "highlow", message.chat.id)

    cur_rank = random.randint(3, 13)
    cur_suit = random.choice(CARD_SUITS)

    ACTIVE_HIGHLOW[gid] = {
        "uid": uid,
        "uname": uname,
        "bet": bet,
        "streak": 0,
        "cur_rank": cur_rank,
        "cur_suit": cur_suit,
        "history": [_format_card(cur_rank, cur_suit)],
        "created_at": time.time()
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔼 БОЛЬШЕ", callback_data=f"hl:g:{gid}:hi"),
            InlineKeyboardButton(text="🔽 МЕНЬШЕ", callback_data=f"hl:g:{gid}:lo"),
        ]
    ])

    text = (
        "🃏 <b>ХАЙ-ЛОУ MOXXI · РАУНД 1</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, uname)}\n"
        f"💵 Ставка: <code>{bet:,}</code> 🪙\n"
        f"🎴 Открытая карта: {_format_card(cur_rank, cur_suit)}\n"
        f"🎯 Множитель следующего шага: <b>x{HL_MULTS[0]}</b>\n\n"
        "👇 <i>Следующая карта будет выше или ниже?</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("hl:g:"))
async def cb_highlow_guess(call: CallbackQuery):
    parts = call.data.split(":")
    gid, guess = parts[2], parts[3]
    st = ACTIVE_HIGHLOW.get(gid)
    if not st:
        return await call.answer("Игра завершена или время вышло.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваша партия!", show_alert=True)

    cur_rank = st["cur_rank"]
    next_rank = random.randint(2, 14)
    while next_rank == cur_rank:
        next_rank = random.randint(2, 14)
    next_suit = random.choice(CARD_SUITS)
    st["history"].append(_format_card(next_rank, next_suit))

    is_higher = next_rank > cur_rank
    user_won = (guess == "hi" and is_higher) or (guess == "lo" and not is_higher)

    bet = st["bet"]
    uname = st["uname"]

    if not user_won:
        ACTIVE_HIGHLOW.pop(gid, None)
        unlock_game(uid)
        text = (
            "💀 <b>НЕ УГАДАЛИ! КАРТА НЕ СЫГРАЛА!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"Было: {_format_card(cur_rank, st['cur_suit'])}\n"
            f"Выпало: {_format_card(next_rank, next_suit)} ({'Выше' if is_higher else 'Ниже'})\n\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"🃏 Сыграть снова: <code>хайлоу {bet}</code>"
        )
        return await call.message.edit_text(text)

    st["streak"] += 1
    st["cur_rank"] = next_rank
    st["cur_suit"] = next_suit
    streak = st["streak"]
    mult = HL_MULTS[streak - 1]
    cur_win = int(bet * mult)

    if streak >= 5:
        ACTIVE_HIGHLOW.pop(gid, None)
        unlock_game(uid)
        bal = await db.add_balance(uid, cur_win, "highlow_jackpot")
        await db.add_game_xp(uid, 120)
        text = (
            "👑 <b>5 ИЗ 5 ПОБЕД В ХАЙ-ЛОУ! ДЖЕКПОТ х10.0!</b> 👑\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 Победитель: {_mention_u(uid, uname)}\n"
            f"Цепочка карт: {' ➔ '.join(st['history'])}\n\n"
            f"💰 <b>ВЫИГРЫШ:</b> +<code>{cur_win:,}</code> 🪙 (Баланс: {money(bal)})\n"
            "⭐ Опыт: <b>+120 XP</b>!"
        )
        return await call.message.edit_text(text)

    next_mult = HL_MULTS[streak]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔼 БОЛЬШЕ", callback_data=f"hl:g:{gid}:hi"),
            InlineKeyboardButton(text="🔽 МЕНЬШЕ", callback_data=f"hl:g:{gid}:lo"),
        ],
        [
            InlineKeyboardButton(text=f"💰 ЗАБРАТЬ {cur_win:,} 🪙 (x{mult})", callback_data=f"hl:cash:{gid}")
        ]
    ])

    text = (
        f"🎉 <b>УГАДАЛИ! СЕРИЯ: {streak} ПОДРЯД (x{mult})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, uname)}\n"
        f"🎴 Текущая карта: {_format_card(next_rank, next_suit)}\n"
        f"💰 Накопленный куш: <b>+{cur_win:,}</b> 🪙\n"
        f"🎯 Следующий множитель: <b>x{next_mult}</b>\n\n"
        "👇 <i>Следующая карта больше или меньше? Или заберёте куш:</i>"
    )
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("hl:cash:"))
async def cb_highlow_cashout(call: CallbackQuery):
    parts = call.data.split(":")
    gid = parts[2]
    st = ACTIVE_HIGHLOW.pop(gid, None)
    if not st:
        return await call.answer("Игра уже завершена.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваша партия!", show_alert=True)

    unlock_game(uid)
    streak = st["streak"]
    mult = HL_MULTS[streak - 1]
    cur_win = int(st["bet"] * mult)
    bal = await db.add_balance(uid, cur_win, "highlow_win")
    await db.add_game_xp(uid, 30)

    text = (
        "💰 <b>КУШ ХАЙ-ЛОУ ЗАФИКСИРОВАН!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {_mention_u(uid, st['uname'])}\n"
        f"🎯 Угадано подряд: <b>{streak} карт</b> (x{mult})\n"
        f"🎉 <b>Выигрыш:</b> +<code>{cur_win:,}</code> 🪙\n"
        f"💳 Баланс: {money(bal)} 🪙"
    )
    await call.message.edit_text(text)


# ══════════════════════════════════════════════════════════════════
# 10. 🎯 ТИР / СНАЙПЕР (SHOOTING RANGE)
# ══════════════════════════════════════════════════════════════════

ACTIVE_TARGETS: dict[str, dict] = {}


@router.message(Cmd("тир", "снайпер", "target", "мишень", section=S_GAMES,
                    usage="тир {ставка}", desc="🎯 Выстрел по 5 мишеням: множители до x5.0"))
async def cmd_target(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "🎯 <b>Стрелковый Тир Moxxi:</b>\n"
            "Перед вами 5 мишеней на стрельбище. Сделайте прицельный выстрел!\n"
            "Призы: 💥 Порох (х5.0) | 🎯 Яблочко (х3.0) | 🔘 Десятка (х1.75) | ⚪️ Касание (х0.8) | 💨 Мимо (0х)\n\n"
            f"👉 <b>Пример:</b> <code>тир 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    gid = f"tg_{uid}_{int(time.time() * 1000)}"
    await db.add_balance(uid, -bet, "target_bet")
    lock_game(uid, "target", message.chat.id)

    pool = [5.0, 3.0, 1.75, 0.8, 0.0]
    random.shuffle(pool)

    ACTIVE_TARGETS[gid] = {
        "uid": uid,
        "uname": uname,
        "bet": bet,
        "pool": pool,
        "created_at": time.time()
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Мишень #1", callback_data=f"tg:s:{gid}:0"),
            InlineKeyboardButton(text="🎯 Мишень #2", callback_data=f"tg:s:{gid}:1"),
            InlineKeyboardButton(text="🎯 Мишень #3", callback_data=f"tg:s:{gid}:2"),
        ],
        [
            InlineKeyboardButton(text="🎯 Мишень #4", callback_data=f"tg:s:{gid}:3"),
            InlineKeyboardButton(text="🎯 Мишень #5", callback_data=f"tg:s:{gid}:4"),
        ]
    ])

    text = (
        "🎯 <b>СТРЕЛЬБИЩЕ MOXXI · ОГОНЬ ПО ГОТОВНОСТИ!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Снайпер: {_mention_u(uid, uname)}\n"
        f"💵 Ставка: <code>{bet:,}</code> 🪙\n\n"
        "👇 <i>Выберите мишень для выстрела:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("tg:s:"))
async def cb_target_shoot(call: CallbackQuery):
    parts = call.data.split(":")
    gid, chosen = parts[2], int(parts[3])
    st = ACTIVE_TARGETS.pop(gid, None)
    if not st:
        return await call.answer("Выстрел уже сделан или время вышло.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваша винтовка!", show_alert=True)

    unlock_game(uid)
    bet = st["bet"]
    pool = st["pool"]
    uname = st["uname"]
    mult = pool[chosen]

    labels = {
        5.0: "💥 Бочка с порохом (x5.0)",
        3.0: "🎯 Точно в яблочко! (x3.0)",
        1.75: "🔘 В десятку! (x1.75)",
        0.8: "⚪️ По касательной (x0.8)",
        0.0: "💨 Рикошет / Мимо (0x)"
    }
    revealed_lines = [f"{'👉 ' if i == chosen else '   '}Мишень #{i+1}: {labels[pool[i]]}" for i in range(5)]

    if mult > 0:
        win = int(bet * mult)
        bal = await db.add_balance(uid, win, "target_win")
        await db.add_game_xp(uid, 30)
        text = (
            f"🎯 <b>ВЫСТРЕЛ В ЯБЛОЧКО! ВЫИГРЫШ: +{win:,} 🪙</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Стрелок: {_mention_u(uid, uname)}\n"
            f"💥 Результат попадания: <b>{labels[mult]}</b>\n\n"
            "📋 <b>Раскладка мишеней:</b>\n"
            + "\n".join(revealed_lines) + "\n\n"
            f"💳 Баланс: {money(bal)} 🪙 | ⭐ Опыт: <b>+30 XP</b>"
        )
        await call.message.edit_text(text)
    else:
        text = (
            "💨 <b>ПРОМАХ! ПУЛЯ УШЛА В МОЛОКО!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Стрелок: {_mention_u(uid, uname)}\n"
            f"❌ Мишень #{chosen+1} оказалась пустой мишенью!\n\n"
            "📋 <b>Где были призы:</b>\n"
            + "\n".join(revealed_lines) + "\n\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"🎯 Попробовать снова: <code>тир {bet}</code>"
        )
        await call.message.edit_text(text)


# ══════════════════════════════════════════════════════════════════
# 11. 🍾 БУТЫЛОЧКА В БЕСЕДЕ (SPIN THE BOTTLE)
# ══════════════════════════════════════════════════════════════════

BOTTLE_TASKS = [
    "Страстно поцеловать друг друга в щёчку при всей беседе 💋",
    "Обняться так крепко, чтобы захрустели рёбра 🤗",
    "Сказать самый безумный и романтичный комплимент в голосовом сообщении 🎙️",
    "Поставить парные аватарки в профиле на 24 часа 📸",
    "Перевести 2 500 монет на шоколадку («передать @юзер 2500») 🍫",
    "Признаться в тайной симпатии перед всей беседой 💖",
    "Придумать смешное милое прозвище и называть так целый день 🥰",
    "Отправить самый угарный стикер или кружочек с танцем в чат 💃",
    "Написать 3 факта, за что вы искренне уважаете этого человека ✨",
    "Сделать совместное предложение пожениться в боте («брак @юзер») 💍",
    "Подарить букет цветов или виртуальный подарок в боте 🌹",
    "Сыграть дружескую дуэль в кости на символические 500 монет 🎲",
    "Написать четверостишие про своего партнёра по бутылочке ✍️",
    "Включить режим личного телохранителя и защищать в спорах целый день 🛡️",
    "Сказать «Мяу» в голосовом сообщении для чата 🐱",
    "Рассказать самую неловкую и смешную историю из своей жизни 🙈",
]

LAST_BOTTLE_SPIN: dict[int, float] = {}


@router.message(Cmd("бутылочка", "бутылка", "spin", "крутить бутылочку", section=S_GAMES,
                    usage="бутылочка", desc="🍾 Крутить бутылочку для участников беседы с забавными заданиями"))
async def cmd_bottle(message: Message, bot: Bot, **kw):
    if message.chat.type == "private":
        return await message.reply("🍾 <b>Бутылочка создана только для бесед и групп!</b> Добавьте Мокси в чат с друзьями!")

    cid = message.chat.id
    now = time.time()
    if now - LAST_BOTTLE_SPIN.get(cid, 0) < 5:
        return await message.reply("⏳ Бутылочка ещё не успела остановиться! Подождите пару секунд.")
    LAST_BOTTLE_SPIN[cid] = now

    caller_id = message.from_user.id
    caller_name = message.from_user.first_name

    candidate_ids = []
    try:
        rows = await db.fetchall("SELECT user_id, first_name FROM users WHERE balance > 0 ORDER BY updated_at DESC LIMIT 30")
        candidate_ids = [r["user_id"] for r in rows if r["user_id"] != caller_id and r["user_id"] > 0]
    except Exception:
        pass

    if not candidate_ids:
        candidate_ids = [caller_id]

    partner_id = random.choice(candidate_ids) if candidate_ids else caller_id
    partner_name = "Соперник"
    try:
        p_user = await bot.get_chat_member(cid, partner_id)
        partner_name = p_user.user.first_name
    except Exception:
        pass

    task = random.choice(BOTTLE_TASKS)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Задание выполнено (+1 000 🪙 обоим)", callback_data=f"btl:done:{caller_id}:{partner_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Крутить бутылочку снова", callback_data="btl:spin")
        ]
    ])

    text = (
        "🍾 <b>БУТЫЛОЧКА КРУТИТСЯ... 🌀</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Горлышко бутылочки остановилось и указало на:\n"
        f"👉 {_mention_u(caller_id, caller_name)}  ❤️  {_mention_u(partner_id, partner_name)} 👈\n\n"
        "🎲 <b>ЗАДАНИЕ ОТ MOXXI:</b>\n"
        f"«<i>{task}</i>»\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>Выполните задание и подтвердите кнопкой:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("btl:done:"))
async def cb_bottle_done(call: CallbackQuery):
    parts = call.data.split(":")
    u1, u2 = int(parts[2]), int(parts[3])
    clicker = call.from_user.id

    if clicker not in (u1, u2):
        return await call.answer("Подтвердить выполнение могут только участники этой пары!", show_alert=True)

    await db.add_balance(u1, 1000, "bottle_reward")
    await db.add_balance(u2, 1000, "bottle_reward")
    await db.add_game_xp(u1, 20)
    await db.add_game_xp(u2, 20)

    text = (
        "🎉 <b>ЗАДАНИЕ БУТЫЛОЧКИ ВЫПОЛНЕНО!</b> 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Оба участника получили по <b>+1 000 🪙</b> и <b>+20 XP</b> за смелость и активность!\n\n"
        "🍾 Чтобы раскрутить снова, напишите <code>бутылочка</code>!"
    )
    await call.message.edit_text(text)


@router.callback_query(F.data == "btl:spin")
async def cb_bottle_spin(call: CallbackQuery, bot: Bot):
    await call.answer("Крутим бутылочку...")
    cid = call.message.chat.id
    caller_id = call.from_user.id
    caller_name = call.from_user.first_name

    candidate_ids = []
    try:
        rows = await db.fetchall("SELECT user_id, first_name FROM users WHERE balance > 0 ORDER BY updated_at DESC LIMIT 30")
        candidate_ids = [r["user_id"] for r in rows if r["user_id"] != caller_id and r["user_id"] > 0]
    except Exception:
        pass

    partner_id = random.choice(candidate_ids) if candidate_ids else caller_id
    partner_name = "Участник"
    try:
        p_user = await bot.get_chat_member(cid, partner_id)
        partner_name = p_user.user.first_name
    except Exception:
        pass

    task = random.choice(BOTTLE_TASKS)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Задание выполнено (+1 000 🪙 обоим)", callback_data=f"btl:done:{caller_id}:{partner_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Крутить бутылочку снова", callback_data="btl:spin")
        ]
    ])

    text = (
        "🍾 <b>БУТЫЛОЧКА СНОВА ВРАЩАЕТСЯ... 💫</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Новая судьбоносная пара беседы:\n"
        f"👉 {_mention_u(caller_id, caller_name)}  ❤️  {_mention_u(partner_id, partner_name)} 👈\n\n"
        "🎲 <b>НОВОЕ ЗАДАНИЕ:</b>\n"
        f"«<i>{task}</i>»\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>Действуйте!</i>"
    )
    await call.message.edit_text(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════
# 12. 🎳 БОУЛИНГ И ⚽️ ПЕНАЛЬТИ
# ══════════════════════════════════════════════════════════════════

@router.message(Cmd("боулинг", "bowling", section=S_GAMES,
                    usage="боулинг [ставка]", desc="🎳 Бросок шара по кеглям (Страйк = x3.0)"))
async def cmd_bowling_solo(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "🎳 <b>Боулинг Клуб Moxxi:</b>\n"
            "Бросьте шар и выбейте страйк!\n"
            "💥 Страйк (6 кеглей): <b>х3.00</b>\n"
            "🔘 4-5 кеглей: <b>х1.60</b>\n"
            "⚪️ 1-3 кегли: <b>0х</b>\n\n"
            f"👉 <b>Пример:</b> <code>боулинг 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    await db.add_balance(uid, -bet, "bowling_bet")
    lock_game(uid, "bowling", message.chat.id)

    dice_msg = await bot.send_dice(message.chat.id, emoji="🎳")
    await asyncio.sleep(3.5)
    unlock_game(uid)

    val = dice_msg.dice.value
    if val == 6:
        win = int(bet * 3.0)
        bal = await db.add_balance(uid, win, "bowling_strike")
        await db.add_game_xp(uid, 40)
        text = (
            "💥 <b>СТРАЙК! ВСЕ 6 КЕГЛЕЙ СБИТЫ!</b> 🎳\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"💰 <b>Выигрыш (х3.0):</b> +<code>{win:,}</code> 🪙 (Баланс: {money(bal)})"
        )
        await dice_msg.reply(text)
    elif val in (4, 5):
        win = int(bet * 1.6)
        bal = await db.add_balance(uid, win, "bowling_win")
        await db.add_game_xp(uid, 20)
        text = (
            f"🎳 <b>ОТЛИЧНЫЙ БРОСОК! СБИТО {val} КЕГЛЕЙ!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"💰 <b>Выигрыш (х1.6):</b> +<code>{win:,}</code> 🪙 (Баланс: {money(bal)})"
        )
        await dice_msg.reply(text)
    else:
        text = (
            f"💨 <b>ШАР УШЁЛ В ЖЕЛОБ! Сбито всего {val} кеглей.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"🎳 Реванш: <code>боулинг {bet}</code>"
        )
        await dice_msg.reply(text)


@router.message(Cmd("пенальти", "футбол", "penalty", section=S_GAMES,
                    usage="пенальти [ставка]", desc="⚽️ Пробитие 11-метрового пенальти по воротам (x1.95)"))
async def cmd_penalty_solo(message: Message, bot: Bot, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "⚽️ <b>Серия Пенальти Moxxi:</b>\n"
            "Пробейте точный 11-метровый удар в сетку ворот!\n"
            "⚽️ Гол в девятку/сетку: <b>х1.95</b>\n"
            "🧤 Сейф вратаря / Штанга: <b>0х</b>\n\n"
            f"👉 <b>Пример:</b> <code>пенальти 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    await db.add_balance(uid, -bet, "penalty_bet")
    lock_game(uid, "penalty", message.chat.id)

    dice_msg = await bot.send_dice(message.chat.id, emoji="⚽️")
    await asyncio.sleep(3.5)
    unlock_game(uid)

    val = dice_msg.dice.value
    if val in (3, 4, 5):
        win = int(bet * 1.95)
        bal = await db.add_balance(uid, win, "penalty_goal")
        await db.add_game_xp(uid, 25)
        text = (
            "⚽️🔥 <b>ГОООООЛ! ТОЧНО В ДЕВЯТКУ!</b> 🥅\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Форвард: {_mention_u(uid, uname)}\n"
            f"💰 <b>Выигрыш (х1.95):</b> +<code>{win:,}</code> 🪙 (Баланс: {money(bal)})"
        )
        await dice_msg.reply(text)
    else:
        text = (
            "🧤❌ <b>ВРАТАРЬ ПАРИРОВАЛ УДАР! МИМО ВОРОТ!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {_mention_u(uid, uname)}\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"⚽️ Повторить удар: <code>пенальти {bet}</code>"
        )
        await dice_msg.reply(text)


# ══════════════════════════════════════════════════════════════════
# 13. 🔐 ВЗЛОМ СЕЙФА (SAFE CRACKER)
# ══════════════════════════════════════════════════════════════════

ACTIVE_SAFES: dict[str, dict] = {}


@router.message(Cmd("сейф игра", "взлом сейфа", "сейф", "safe", section=S_GAMES,
                    usage="сейф {ставка}", desc="🔐 Подбор шифра от сейфа из 6 цифр (куш x5.0)"))
async def cmd_safe_crack(message: Message, args: str = "", **kw):
    if not await _check_casino_allowed(message):
        return

    uid = message.from_user.id
    uname = message.from_user.first_name
    u_data = await db.get_user(uid)
    u_bal = int(u_data.get("balance", 0) or 0)

    bet = _parse_bet_arg(args, u_bal)
    if bet < MIN_BET:
        text = (
            "🔐 <b>Взлом Сейфа Банка Moxxi:</b>\n"
            "Сейф защищён 6-значной кодовой панелью. Угадайте верную цифру шифра!\n"
            f"💰 За верный код вы сорвёте джекпот <b>х5.00</b> от ставки!\n\n"
            f"👉 <b>Пример:</b> <code>сейф 1000</code>"
        )
        return await message.reply(text)

    if u_bal < bet:
        return await message.reply(f"💰 Недостаточно монет! Баланс: {money(u_bal)} 🪙, ставка: {money(bet)} 🪙")

    gid = f"sf_{uid}_{int(time.time() * 1000)}"
    await db.add_balance(uid, -bet, "safe_bet")
    lock_game(uid, "safe", message.chat.id)

    code = random.randint(1, 6)
    ACTIVE_SAFES[gid] = {
        "uid": uid,
        "uname": uname,
        "bet": bet,
        "code": code,
        "created_at": time.time()
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔐 Цифра 1", callback_data=f"sf:d:{gid}:1"),
            InlineKeyboardButton(text="🔐 Цифра 2", callback_data=f"sf:d:{gid}:2"),
            InlineKeyboardButton(text="🔐 Цифра 3", callback_data=f"sf:d:{gid}:3"),
        ],
        [
            InlineKeyboardButton(text="🔐 Цифра 4", callback_data=f"sf:d:{gid}:4"),
            InlineKeyboardButton(text="🔐 Цифра 5", callback_data=f"sf:d:{gid}:5"),
            InlineKeyboardButton(text="🔐 Цифра 6", callback_data=f"sf:d:{gid}:6"),
        ]
    ])

    text = (
        "🔐 <b>ОГРАБЛЕНИЕ СЕЙФА MOXXI VAULT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Взломщик: {_mention_u(uid, uname)}\n"
        f"💵 Ставка: <code>{bet:,}</code> 🪙\n"
        f"🏆 Выигрыш при успехе: <b>+{bet * 5:,} 🪙 (х5.0)</b>\n\n"
        "👇 <i>Введите цифру шифра на кодовой панели:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("sf:d:"))
async def cb_safe_digit(call: CallbackQuery):
    parts = call.data.split(":")
    gid, chosen = parts[2], int(parts[3])
    st = ACTIVE_SAFES.pop(gid, None)
    if not st:
        return await call.answer("Код уже введён или время вышло.", show_alert=True)

    uid = call.from_user.id
    if uid != st["uid"]:
        return await call.answer("Это не ваш сейф!", show_alert=True)

    unlock_game(uid)
    bet = st["bet"]
    code = st["code"]
    uname = st["uname"]

    if chosen == code:
        win = int(bet * 5.0)
        bal = await db.add_balance(uid, win, "safe_heist")
        await db.add_game_xp(uid, 50)
        text = (
            "🔓💎 <b>СЕЙФ УСПЕШНО ВЗЛОМАН! ДЖЕКПОТ x5.0!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Взломщик: {_mention_u(uid, uname)}\n"
            f"✅ Код <b>#{chosen}</b> подошёл идеально!\n\n"
            f"💰 <b>КУШ:</b> +<code>{win:,}</code> 🪙 (Баланс: {money(bal)})\n"
            "⭐ Опыт: <b>+50 XP</b>!"
        )
        await call.message.edit_text(text)
    else:
        text = (
            "🚨 <b>ТРЕВОГА! КОД НЕВЕРНЫЙ! СИГНАЛИЗАЦИЯ!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Взломщик: {_mention_u(uid, uname)}\n"
            f"❌ Вы ввели цифру <b>#{chosen}</b>, а правильный код был <b>#{code}</b>!\n\n"
            f"💸 Потеряно: <code>-{bet:,}</code> 🪙\n"
            f"🔐 Попробовать новый шифр: <code>сейф {bet}</code>"
        )
        await call.message.edit_text(text)
