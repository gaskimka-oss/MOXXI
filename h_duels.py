"""⚔️ PvP-Дуэли между участниками чата на монеты и снаряжение."""
from __future__ import annotations

import asyncio
import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from h_items import get_user_combat_gear
from utils import mention, mention_id, money, parse_amount

router = Router(name="duels")
S = 15  # Раздел 15: Модуль «PvP-Дуэли»

# Временное хранилище активных вызовов на дуэль:
# key: (chat_id, target_id) -> dict
PENDING_DUELS: dict[tuple[int, int], dict] = {}


def _duel_kb(chat_id: int, challenger_id: int, target_id: int, bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"duel:accept:{chat_id}:{challenger_id}:{target_id}:{bet}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"duel:decline:{chat_id}:{challenger_id}:{target_id}")
        ]
    ])


@router.message(Cmd("дуэль", "вызов", "стреляться", "дуель", section=S, rank=0,
                    usage="дуэль [@юзер/реплай] [ставка]", desc="⚔️ Вызвать игрока на PvP-дуэль"))
async def cmd_duel_create(message: Message, bot: Bot, args: str = "", **kw):
    if message.chat.type == "private":
        return await message.reply("⚔️ PvP-Дуэли доступны только в групповых беседах!")

    cid = message.chat.id
    challenger_id = message.from_user.id
    target_id = None
    target_name = ""
    bet = 0

    # 1. Извлекаем ставку и цель
    rep = real_reply(message)
    if rep and rep.from_user and not rep.from_user.is_bot:
        target_id = rep.from_user.id
        target_name = rep.from_user.first_name or "Боец"
        if args:
            bet = parse_amount(args.strip())
    else:
        # Парсим аргументы: @username [bet] или [bet]
        parts = (args or "").strip().split()
        if parts:
            # Ищем число в конце или начале
            target_str = ""
            for p in parts:
                amt = parse_amount(p)
                if amt > 0 and bet == 0:
                    bet = amt
                else:
                    target_str += (" " + p)
            target_str = target_str.strip()
            if target_str:
                uid, name, _ = await resolve_target(message, target_str, bot)
                if uid:
                    target_id = uid
                    target_name = name

    if not target_id:
        return await message.reply(
            "⚔️ <b>Формат дуэли:</b>\n"
            "• Реплаем: <code>дуэль 500</code>\n"
            "• С юзернеймом: <code>дуэль @username 1000</code>\n"
            "• Статистика: <code>топ дуэлей</code> или <code>мои дуэли</code>"
        )

    if target_id == challenger_id:
        return await message.reply("🙂 Стреляться с самим собой нельзя!")

    # Проверка баланса вызывающего
    ch_user = await db.get_user(challenger_id)
    if bet > 0 and ch_user["balance"] < bet:
        return await message.reply(
            f"❌ У вас недостаточно монет для такой ставки! Ваш баланс: <b>{money(ch_user['balance'])}</b>."
        )

    # Проверка баланса цели
    tg_user = await db.get_user(target_id)
    if bet > 0 and tg_user["balance"] < bet:
        return await message.reply(
            f"❌ У {mention_id(target_id, target_name)} недостаточно монет! (Нужно {money(bet)})."
        )

    # Сохраняем вызов (таймаут 120 сек)
    PENDING_DUELS[(cid, target_id)] = {
        "challenger_id": challenger_id,
        "challenger_name": message.from_user.first_name or "Боец",
        "target_id": target_id,
        "target_name": target_name,
        "bet": bet,
        "ts": time.time()
    }

    bet_text = f"💰 Ставка дуэли: <b>{money(bet)}</b> (Банк: <b>{money(bet * 2)}</b>)\n" if bet > 0 else "🤝 Дружеская дуэль (без ставки)\n"

    text = (
        f"⚔️ 💥 <b>ВЫЗОВ НА PvP-ДУЭЛЬ!</b> 💥 ⚔️\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>Вызывающий:</b> {mention(message.from_user)}\n"
        f"🎯 <b>Оппонент:</b> {mention_id(target_id, target_name)}\n"
        f"{bet_text}"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👉 {mention_id(target_id, target_name)}, у вас есть <b>2 минуты</b>, чтобы принять вызов!"
    )

    await message.reply(
        text,
        reply_markup=_duel_kb(cid, challenger_id, target_id, bet)
    )


@router.callback_query(F.data.startswith("duel:accept:"))
async def cb_duel_accept(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[2])
    ch_id = int(parts[3])
    tg_id = int(parts[4])
    bet = int(parts[5])

    if call.from_user.id != tg_id:
        return await call.answer("❌ Этот вызов брошен не вам!", show_alert=True)

    duel_key = (cid, tg_id)
    duel_data = PENDING_DUELS.get(duel_key)
    if not duel_data or (time.time() - duel_data["ts"]) > 120:
        PENDING_DUELS.pop(duel_key, None)
        return await call.answer("⏳ Время вызова на дуэль истекло!", show_alert=True)

    # Снова проверяем балансы
    ch_user = await db.get_user(ch_id)
    tg_user = await db.get_user(tg_id)
    if bet > 0:
        if ch_user["balance"] < bet or tg_user["balance"] < bet:
            PENDING_DUELS.pop(duel_key, None)
            return await call.answer("❌ У одного из участников недостаточно средств!", show_alert=True)
        # Списываем ставки
        await db.add_balance(ch_id, -bet)
        await db.add_balance(tg_id, -bet)

    PENDING_DUELS.pop(duel_key, None)
    await call.answer("⚔️ Дуэль принята! К бою!", show_alert=False)

    # Проводим расчет боя
    await _resolve_duel(call.message, bot, cid, ch_id, ch_user, tg_id, tg_user, bet)


@router.callback_query(F.data.startswith("duel:decline:"))
async def cb_duel_decline(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[2])
    ch_id = int(parts[3])
    tg_id = int(parts[4])

    if call.from_user.id not in {tg_id, ch_id}:
        return await call.answer("❌ Вы не участвуете в этой дуэли!", show_alert=True)

    PENDING_DUELS.pop((cid, tg_id), None)
    await call.message.edit_text(
        f"❌ <b>Дуэль отклонена.</b> {mention(call.from_user)} отказался от поединка."
    )


async def _resolve_duel(message: Message, bot: Bot, cid: int,
                        u1_id: int, u1_row: dict,
                        u2_id: int, u2_row: dict, bet: int):
    """Красиво разыгрывает PvP-дуэль в 3 раунда."""
    gear1 = await get_user_combat_gear(u1_id)
    gear2 = await get_user_combat_gear(u2_id)

    name1 = html.escape(u1_row.get("first_name") or "Боец 1")
    name2 = html.escape(u2_row.get("first_name") or "Боец 2")

    # Базовые очки силы + бонусы экипировки
    score1 = random.randint(30, 90) * gear1["dmg_mult"]
    score2 = random.randint(30, 90) * gear2["dmg_mult"]

    if gear1["has_armor"] and random.random() < 0.25:
        score1 += 30  # Броня парировала удар
    if gear2["has_armor"] and random.random() < 0.25:
        score2 += 30

    # Определяем победителя
    winner_id = u1_id if score1 >= score2 else u2_id
    loser_id = u2_id if score1 >= score2 else u1_id
    winner_name = name1 if score1 >= score2 else name2
    loser_name = name2 if score1 >= score2 else name1

    # Запись в статистику
    await db.execute(
        "INSERT INTO duels_stats (user_id, wins, losses, total_earned) VALUES (?, 1, 0, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET wins = wins + 1, total_earned = total_earned + ?",
        (winner_id, bet * 2 if bet > 0 else 0, bet if bet > 0 else 0)
    )
    await db.execute(
        "INSERT INTO duels_stats (user_id, wins, losses, total_earned) VALUES (?, 0, 1, 0) "
        "ON CONFLICT(user_id) DO UPDATE SET losses = losses + 1",
        (loser_id,)
    )

    if bet > 0:
        win_pot = bet * 2
        await db.add_balance(winner_id, win_pot)
        await db.add_xp(cid, winner_id, 80)
        await db.add_xp(cid, loser_id, 20)
        win_text = f"💰 Выигрыш: <b>+{money(win_pot)}</b> · <b>+80 XP</b>!"
    else:
        await db.add_xp(cid, winner_id, 40)
        win_text = "✨ Награда: <b>+40 XP</b> за победу!"

    w_gear = gear1 if winner_id == u1_id else gear2
    weapon_used = f" (Оружие: {w_gear['weapon_name']})" if w_gear.get("weapon_name") else ""

    result_text = (
        f"💥 💥 <b>ИТОГИ СМЕРТЕЛЬНОЙ PvP-ДУЭЛИ!</b> 💥 💥\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🔫 {name1}  <b>VS</b>  {name2} 🔫\n\n"
        f"💨 <i>Раунд 1:</i> Бойцы сошлись на дистанции выстрела...\n"
        f"⚡️ <i>Раунд 2:</i> Прогремели залпы, пули просвистели у виска!\n"
        f"🔥 <i>Раунд 3:</i> Решающий точный выстрел на поражение!\n\n"
        f"👑 <b>ПОБЕДИТЕЛЬ ДУЭЛИ:</b> {mention_id(winner_id, winner_name)}!{weapon_used}\n"
        f"💀 <b>Повержен:</b> {mention_id(loser_id, loser_name)}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{win_text}"
    )

    try:
        await message.edit_text(result_text)
    except Exception:
        await message.answer(result_text)


@router.message(Cmd("топ дуэлей", "топ дуэлянтов", "топ стрелков", section=S, rank=0,
                    usage="топ дуэлей", desc="🏆 Рейтинг лучших дуэлянтов"))
async def cmd_duels_top(message: Message, bot: Bot, **kw):
    rows = await db.fetchall(
        "SELECT d.user_id, d.wins, d.losses, d.total_earned, u.first_name FROM duels_stats d "
        "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.wins > 0 ORDER BY d.wins DESC, d.total_earned DESC LIMIT 10"
    )
    if not rows:
        return await message.reply("⚔️ В чате пока никто не побеждал в PvP-дуэлях. Вызовите кого-нибудь: <code>дуэль @юзер</code>")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = [
        "🏆 ✨ <b>ТОП ЛУЧШИХ PvP-ДУЭЛЯНТОВ</b> ✨ 🏆",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    for i, r in enumerate(rows):
        icon = medals[i] if i < len(medals) else "▫️"
        name = html.escape(r["first_name"] or str(r["user_id"]))
        total_m = money(r["total_earned"]) if r["total_earned"] > 0 else "0 🪙"
        text.append(f"{icon} <b>{name}</b> — <b>{r['wins']} побед</b> ({r['losses']} пор.) · 💰 {total_m}")

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Бросить вызов:</i> <code>дуэль @юзер 1000</code>")
    await message.reply("\n".join(text))


@router.message(Cmd("мои дуэли", "дуэль стата", section=S, rank=0,
                    usage="мои дуэли", desc="📊 Личная статистика дуэлей"))
async def cmd_my_duels(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT * FROM duels_stats WHERE user_id=?", (uid,))
    wins = row["wins"] if row else 0
    losses = row["losses"] if row else 0
    earned = row["total_earned"] if row else 0
    total = wins + losses
    winrate = int((wins / total * 100)) if total > 0 else 0

    text = (
        f"📊 ✨ <b>СТАТИСТИКА ДУЭЛЕЙ: {html.escape(message.from_user.first_name)}</b> ✨ 📊\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🏆 Побед: <b>{wins}</b>\n"
        f"💀 Поражений: <b>{losses}</b>\n"
        f"📈 Винрейт: <b>{winrate}%</b>\n"
        f"💰 Всего выиграно: <b>{money(earned)}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Бросить вызов:</i> <code>дуэль @юзер 500</code>"
    )
    await message.reply(text)
