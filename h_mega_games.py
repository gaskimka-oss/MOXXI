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
