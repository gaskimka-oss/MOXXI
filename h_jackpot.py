"""🎰 Модуль Накопительного Джекпота Чата (Moxxi Progressive Jackpot).

Каждая игра в казино и покупка билетов отчисляет процент в общий призовой банк.
Джекпот может быть сорван счастливчиком в казино или в ежедневном розыгрыше.
"""
from __future__ import annotations

import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, mention_id, money

router = Router(name="jackpot")
S = 16  # Раздел 16: Казино и мини-игры

TICKET_PRICE = 250


def _jackpot_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎟 Купить 1 билет (250 🪙)", callback_data=f"jp:buy:1:{chat_id}"),
            InlineKeyboardButton(text="🎟 Купить 5 билетов (1 250 🪙)", callback_data=f"jp:buy:5:{chat_id}")
        ],
        [
            InlineKeyboardButton(text="🎰 Крутить Слоты (шанс куша)", callback_data=f"jp:play_slots"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"jp:refresh:{chat_id}")
        ]
    ])


@router.message(Cmd("джекпот", "банк джекпота", "куш", "прогрессивный джекпот", section=S, rank=0,
                    usage="джекпот", desc="🎰 Посмотреть банк Накопительного Джекпота чата"))
async def cmd_jackpot_show(message: Message, bot: Bot, **kw):
    cid = message.chat.id
    if message.chat.type == "private":
        return await message.reply("🎰 Джекпот накапливается и разыгрывается в беседах!")

    jp = await db.get_chat_jackpot(cid)
    pool = jp.get("pool", 5000)

    last_win_str = "Пока никто не срывал"
    if jp.get("last_winner_name") and jp.get("last_winner_amount"):
        last_win_str = f"<b>{html.escape(jp['last_winner_name'])}</b> (+{money(jp['last_winner_amount'])})"

    text = (
        f"🎰 ✨ <b>НАКОПИТЕЛЬНЫЙ ДЖЕКПОТ ЧАТА</b> ✨ 🎰\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💎 <b>ТЕКУЩИЙ ПРИЗОВОЙ КУШ:</b>\n"
        f"🔥 <b>{money(pool)}</b> 🔥\n\n"
        f"👑 <b>Последний победитель:</b> {last_win_str}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🎲 <b>Как сорвать Джекпот:</b>\n"
        f"1. 🎰 Играйте в казино (<code>казик</code>, <code>мины</code>, <code>рулетка</code>, <code>краш</code>) — 2% ставок летят в куш, а комбинация <b>777</b> срывает весь банк!\n"
        f"2. 🎟 Покупайте лотерейные билеты кнопками ниже — каждый билет повышает ваш шанс сорвать куш!\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"<i>Цена 1 лотерейного билета: 250 монет</i>"
    )
    await message.reply(text, reply_markup=_jackpot_kb(cid))


@router.message(Cmd("купить билеты", "купить билет", "лотерея", section=S, rank=0,
                    usage="купить билеты [кол-во]", desc="🎟 Купить билеты розыгрыша Джекпота"))
async def cmd_buy_tickets(message: Message, bot: Bot, args: str = "", **kw):
    cid = message.chat.id
    uid = message.from_user.id
    if message.chat.type == "private":
        return await message.reply("🎟 Лотерея Джекпота доступна только в группах!")

    count = 1
    if args and args.strip().isdigit():
        count = max(1, min(100, int(args.strip())))

    cost = count * TICKET_PRICE
    user = await db.get_user(uid)
    if user["balance"] < cost:
        return await message.reply(f"❌ Недостаточно монет! {count} билетов стоят <b>{money(cost)}</b>.")

    await db.add_balance(uid, -cost)
    # 80% от цены билетов добавляем в джекпот
    new_pool = await db.add_to_chat_jackpot(cid, int(cost * 0.8))

    # Шанс сорвать куш прямо при покупке билета!
    win_chance = min(0.15, count * 0.005)  # 0.5% за билет, макс 15%
    won = random.random() < win_chance

    if won:
        winner_name = message.from_user.first_name or "Счастливчик"
        won_pool = await db.claim_chat_jackpot(cid, uid, winner_name)
        await db.add_balance(uid, won_pool)
        await db.add_xp(cid, uid, 500)

        jackpot_msg = (
            f"🎉 🚨 🚨 <b>ДЖЕКПОТ ЧАТА СОРВАН!</b> 🚨 🚨 🎉\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👑 <b>СЧАСТЛИВЧИК:</b> {mention(message.from_user)}!\n"
            f"💰 <b>ВЫИГРЫШ:</b> <b>+{money(won_pool)}</b> прямо на баланс!\n"
            f"⭐️ <b>Опыт:</b> +500 XP!\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🔥 <i>Новый банк Джекпота перезапущен с 5 000 монет!</i>"
        )
        return await message.reply(jackpot_msg)

    await message.reply(
        f"🎟 {mention(message.from_user)} приобрёл <b>{count} шт.</b> лотерейных билетов за <b>{money(cost)}</b>!\n"
        f"💎 Банк Джекпота пополнился до: <b>{money(new_pool)}</b>!"
    )


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("jp:"))
async def cb_jackpot(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    action = parts[1]
    uid = call.from_user.id

    if action == "refresh":
        cid = int(parts[2])
        jp = await db.get_chat_jackpot(cid)
        pool = jp.get("pool", 5000)

        last_win_str = "Пока никто не срывал"
        if jp.get("last_winner_name") and jp.get("last_winner_amount"):
            last_win_str = f"<b>{html.escape(jp['last_winner_name'])}</b> (+{money(jp['last_winner_amount'])})"

        text = (
            f"🎰 ✨ <b>НАКОПИТЕЛЬНЫЙ ДЖЕКПОТ ЧАТА</b> ✨ 🎰\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"💎 <b>ТЕКУЩИЙ ПРИЗОВОЙ КУШ:</b>\n"
            f"🔥 <b>{money(pool)}</b> 🔥\n\n"
            f"👑 <b>Последний победитель:</b> {last_win_str}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🎲 <b>Как сорвать Джекпот:</b>\n"
            f"1. 🎰 Играйте в казино (<code>казик</code>, <code>мины</code>, <code>рулетка</code>, <code>краш</code>) — 2% ставок летят в куш, а комбинация <b>777</b> срывает весь банк!\n"
            f"2. 🎟 Покупайте лотерейные билеты кнопками ниже — каждый билет повышает ваш шанс сорвать куш!\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"<i>Цена 1 лотерейного билета: 250 монет</i>"
        )
        try:
            await call.message.edit_text(text, reply_markup=_jackpot_kb(cid))
        except Exception:
            pass
        return await call.answer("🔄 Джекпот обновлен!")

    if action == "buy":
        count = int(parts[2])
        cid = int(parts[3])
        cost = count * TICKET_PRICE
        user = await db.get_user(uid)

        if user["balance"] < cost:
            return await call.answer(f"❌ Недостаточно монет! Нужно {money(cost)}.", show_alert=True)

        await db.add_balance(uid, -cost)
        new_pool = await db.add_to_chat_jackpot(cid, int(cost * 0.8))

        win_chance = min(0.15, count * 0.005)
        won = random.random() < win_chance

        if won:
            winner_name = call.from_user.first_name or "Счастливчик"
            won_pool = await db.claim_chat_jackpot(cid, uid, winner_name)
            await db.add_balance(uid, won_pool)
            await db.add_xp(cid, uid, 500)

            await call.answer(f"🎉 🚨 ВЫ СОРВАЛИ ДЖЕКПОТ: +{money(won_pool)}! 🚨", show_alert=True)
            jackpot_msg = (
                f"🎉 🚨 🚨 <b>ДЖЕКПОТ ЧАТА СОРВАН!</b> 🚨 🚨 🎉\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"👑 <b>СЧАСТЛИВЧИК:</b> {mention(call.from_user)}!\n"
                f"💰 <b>ВЫИГРЫШ:</b> <b>+{money(won_pool)}</b> прямо на баланс!\n"
                f"⭐️ <b>Опыт:</b> +500 XP!\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"🔥 <i>Новый банк Джекпота перезапущен с 5 000 монет!</i>"
            )
            return await call.message.reply(jackpot_msg)

        await call.answer(f"🎟 Куплено {count} билетов! Банк Джекпота: {money(new_pool)}")

    if action == "play_slots":
        await call.answer("Напишите в чат: казик 1000", show_alert=True)
