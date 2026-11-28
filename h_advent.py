"""Новогодний Адвент-Календарь (1-31 декабря 2026): ежедневные подарки, кейсы, снежинки и мешок Деда Мороза."""
from __future__ import annotations

import datetime
import html
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
from core_registry import Cmd
from h_winter_event import is_winter_active, time_until_str, WINTER_START_TS
from utils import mention, money

router = Router(name="advent")

# Награды за каждый день декабря (1-31)
ADVENT_REWARDS = {
    1: {"desc": "3,000 монет + 20 ❄️", "coins": 3000, "flakes": 20, "case_id": 0},
    2: {"desc": "5,000 монет + 25 ❄️", "coins": 5000, "flakes": 25, "case_id": 0},
    3: {"desc": "7,000 монет + 25 ❄️", "coins": 7000, "flakes": 25, "case_id": 0},
    4: {"desc": "10,000 монет + 30 ❄️", "coins": 10000, "flakes": 30, "case_id": 0},
    5: {"desc": "📦 Бронзовый кейс + 35 ❄️", "coins": 5000, "flakes": 35, "case_id": 1},
    6: {"desc": "12,000 монет + 35 ❄️", "coins": 12000, "flakes": 35, "case_id": 0},
    7: {"desc": "15,000 монет + 40 ❄️", "coins": 15000, "flakes": 40, "case_id": 0},
    8: {"desc": "18,000 монет + 40 ❄️", "coins": 18000, "flakes": 40, "case_id": 0},
    9: {"desc": "20,000 монет + 45 ❄️", "coins": 20000, "flakes": 45, "case_id": 0},
    10: {"desc": "🧰 Серебряный кейс + 50 ❄️", "coins": 10000, "flakes": 50, "case_id": 2},
    11: {"desc": "22,000 монет + 50 ❄️", "coins": 22000, "flakes": 50, "case_id": 0},
    12: {"desc": "25,000 монет + 55 ❄️", "coins": 25000, "flakes": 55, "case_id": 0},
    13: {"desc": "28,000 монет + 55 ❄️", "coins": 28000, "flakes": 55, "case_id": 0},
    14: {"desc": "30,000 монет + 60 ❄️", "coins": 30000, "flakes": 60, "case_id": 0},
    15: {"desc": "🎁 Золотой кейс + 70 ❄️", "coins": 15000, "flakes": 70, "case_id": 3},
    16: {"desc": "32,000 монет + 70 ❄️", "coins": 32000, "flakes": 70, "case_id": 0},
    17: {"desc": "35,000 монет + 75 ❄️", "coins": 35000, "flakes": 75, "case_id": 0},
    18: {"desc": "38,000 монет + 75 ❄️", "coins": 38000, "flakes": 75, "case_id": 0},
    19: {"desc": "40,000 монет + 80 ❄️", "coins": 40000, "flakes": 80, "case_id": 0},
    20: {"desc": "❄️ Ледяной Кейс 2026-2027 + 85 ❄️", "coins": 20000, "flakes": 85, "case_id": 5},
    21: {"desc": "42,000 монет + 85 ❄️", "coins": 42000, "flakes": 85, "case_id": 0},
    22: {"desc": "45,000 монет + 90 ❄️", "coins": 45000, "flakes": 90, "case_id": 0},
    23: {"desc": "48,000 монет + 90 ❄️", "coins": 48000, "flakes": 90, "case_id": 0},
    24: {"desc": "50,000 монет + 95 ❄️", "coins": 50000, "flakes": 95, "case_id": 0},
    25: {"desc": "💎 Кейс Moxxi (Мифик) + 100 ❄️", "coins": 25000, "flakes": 100, "case_id": 4},
    26: {"desc": "55,000 монет + 100 ❄️", "coins": 55000, "flakes": 100, "case_id": 0},
    27: {"desc": "60,000 монет + 110 ❄️", "coins": 60000, "flakes": 110, "case_id": 0},
    28: {"desc": "70,000 монет + 120 ❄️", "coins": 70000, "flakes": 120, "case_id": 0},
    29: {"desc": "80,000 монет + 130 ❄️", "coins": 80000, "flakes": 130, "case_id": 0},
    30: {"desc": "90,000 монет + 140 ❄️", "coins": 90000, "flakes": 140, "case_id": 0},
    31: {"desc": "🎆 МЕШОК ДЕДА МОРОЗА: 100,000 монет + 150 ❄️ + Титул «Встретил 2027»!", "coins": 100000, "flakes": 150, "case_id": 5, "title": "🎆 Встретил 2027"},
}


def _get_current_december_day() -> int:
    """Возвращает текущий день декабря (по МСК). Если еще ноябрь — возвращает 0 или 1 при овнер-тесте."""
    tz_msk = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz_msk)
    if now.month == 12:
        return now.day
    # Если включен тестовый режим овнера до 1 декабря:
    from h_winter_event import _winter_test_mode
    if _winter_test_mode:
        return 1
    return 0


async def render_advent_card(user_obj) -> tuple[str, InlineKeyboardMarkup]:
    uid = user_obj.id
    claimed = await db.get_advent_claimed_days(uid)
    today = _get_current_december_day()

    grid = []
    for d in range(1, 32):
        if d in claimed:
            icon = f"[{d:02d}:✅]"
        elif d == today:
            icon = f"[{d:02d}:🎁]"
        elif d < today:
            icon = f"[{d:02d}:❌]"
        else:
            icon = f"[{d:02d}:🔒]"
        grid.append(icon)

    # Разбиваем на строки по 4 дня
    grid_rows = []
    for i in range(0, len(grid), 4):
        grid_rows.append(" ".join(grid[i:i+4]))

    today_claimed = (today in claimed)
    reward_today = ADVENT_REWARDS.get(today, ADVENT_REWARDS[1])

    text = (
        f"🎅 🎄 <b>НОВОГОДНИЙ АДВЕНТ-КАЛЕНДАРЬ</b> 🎄 🎅\n"
        f"✦ ══════════════════════════════════ ✦\n\n"
        f"👋 Игрок: {mention(user_obj)}\n"
        f"📅 <b>Сегодня:</b> <b>{today if today > 0 else 1} декабря</b>\n"
        f"🎁 <b>Подарок на сегодня:</b> <b>{reward_today['desc']}</b>\n\n"
        f"<b>СЕТКА ДНЕЙ ДЕКАБРЯ:</b>\n"
        f"<pre>" + "\n".join(grid_rows) + "</pre>\n\n"
        f"<i>Легенда: ✅ Получено · 🎁 Доступно · 🔒 Закрыто · ❌ Пропущено</i>\n"
        f"✦ ══════════════════════════════════ ✦\n"
        f"<i>Заходите каждый день и не пропускайте ни одной награды!</i>"
    )

    buttons = []
    if today > 0 and not today_claimed:
        buttons.append([InlineKeyboardButton(text=f"🎁 Забрать подарок за {today} декабря", callback_data=f"advent_claim:{today}")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить календарь", callback_data="advent_refresh")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Cmd("календарь", "адвент", "подарок дня", "нг календарь", "advent", section=32,
                    usage="календарь", desc="🎅 Новогодний Адвент-календарь с подарками на каждый день"))
async def cmd_advent(message: Message, **kw):
    if not is_winter_active():
        time_left = time_until_str(WINTER_START_TS)
        return await message.reply(
            f"❄️ <b>НОВОГОДНИЙ АДВЕНТ-КАЛЕНДАРЬ</b> ❄️\n"
            f"✦ ══════════════════════════════════ ✦\n"
            f"Календарь ежедневных подарков откроется <b>1 декабря в 00:00 по МСК</b>!\n\n"
            f"⏳ <b>До открытия первого подарка:</b> <b>{time_left}</b>\n\n"
            f"🎁 <i>Каждый день с 1 по 31 декабря вас будут ждать монеты, снежинки, кейсы и финальный Мешок Деда Мороза!</i>"
        )

    text, kb = await render_advent_card(message.from_user)
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("advent_claim:"))
async def cb_advent_claim(call: CallbackQuery):
    if not is_winter_active():
        return await call.answer("❄️ Сезон стартует 1 декабря!", show_alert=True)

    day = int(call.data.split(":")[1])
    today = _get_current_december_day()
    if day != today:
        return await call.answer("❌ Можно забрать только подарок за сегодняшний день!", show_alert=True)

    uid = call.from_user.id
    ok = await db.claim_advent_day(uid, day)
    if not ok:
        return await call.answer("Вы уже забрали подарок за сегодня!", show_alert=True)

    rw = ADVENT_REWARDS.get(day, ADVENT_REWARDS[1])
    if rw.get("coins"):
        await db.add_balance(uid, rw["coins"], "advent_gift")
    if rw.get("flakes"):
        await db.add_user_snowflakes(uid, rw["flakes"])
    if rw.get("case_id"):
        await db.add_user_case(uid, rw["case_id"], 1)
    if rw.get("title"):
        try:
            await db.unlock_user_title(uid, rw["title"])
        except Exception:
            pass

    text, kb = await render_advent_card(call.from_user)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer(f"🎉 Вы успешно забрали: {rw['desc']}!", show_alert=True)


@router.callback_query(F.data == "advent_refresh")
async def cb_advent_refresh(call: CallbackQuery):
    if not is_winter_active():
        return await call.answer("❄️ Сезон стартует 1 декабря!", show_alert=True)
    text, kb = await render_advent_card(call.from_user)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer("Календарь обновлен!")
