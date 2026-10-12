"""Модуль 11: Звания за выслугу лет (Ветеранские титулы беседы).

Автоматически отслеживает стаж каждого участника в текущем чате (по first_seen),
присваивает престижные титулы, шкалу прогресса и ежедневный ветеранский бонус.
"""
from __future__ import annotations

import html
import time
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_registry import Cmd
from core_resolve import human_period, resolve_target
from utils import mention_id

router = Router(name="veteran")

# Уровни стажа: (min_days, max_days, title, daily_bonus)
SENIORITY_TIERS = [
    (730, 99999, "⚡️ Вечный Хранитель", 2500),
    (365, 729, "🏛 Основатель эпохи", 1200),
    (180, 364, "👑 Легенда чата", 600),
    (90, 179, "🎖 Ветеран беседы", 300),
    (30, 89, "💬 Старожил беседы", 150),
    (7, 29, "🌱 Новичок беседы", 50),
    (0, 6, "🐣 Гость беседы", 0),
]


async def get_user_seniority(chat_id: int, user_id: int) -> dict:
    """Возвращает информацию о стаже пользователя в конкретном чате."""
    fs = await db.fetchone("SELECT ts FROM first_seen WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    now = int(time.time())
    if fs and fs["ts"]:
        first_ts = fs["ts"]
    else:
        u = await db.get_user(user_id)
        first_ts = u["created_at"] if u and u["created_at"] else now

    days = max(0, int((now - first_ts) // 86400))

    # Определяем текущий ранг
    cur_tier = SENIORITY_TIERS[-1]
    next_tier = None
    for i, t in enumerate(SENIORITY_TIERS):
        if days >= t[0]:
            cur_tier = t
            if i > 0:
                next_tier = SENIORITY_TIERS[i - 1]
            break

    # Вычисляем прогресс
    if next_tier:
        need_days = next_tier[0] - cur_tier[0]
        cur_progress = days - cur_tier[0]
        pct = min(100, max(0, int((cur_progress / need_days) * 100))) if need_days > 0 else 100
        bars = int(pct // 10)
        progress_bar = "🟩" * bars + "⬜️" * (10 - bars)
    else:
        progress_bar = "🟩" * 10
        pct = 100

    return {
        "days": days,
        "first_ts": first_ts,
        "title": cur_tier[2],
        "daily_bonus": cur_tier[3],
        "next_title": next_tier[2] if next_tier else None,
        "days_left": (next_tier[0] - days) if next_tier else 0,
        "progress_bar": progress_bar,
        "pct": pct,
    }


# ---------------- КАРТОЧКА СТАЖА ----------------
@router.message(Cmd("стаж", "выслуга", "моё звание", "мой стаж", usage="стаж {ссылка}",
                    desc="🏛 Ветеранское звание и стаж в беседе"))
async def cmd_seniority(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    uid = uid or message.from_user.id
    name = name or message.from_user.first_name

    info = await get_user_seniority(message.chat.id, uid)
    dt_str = time.strftime("%d.%m.%Y", time.localtime(info["first_ts"]))

    next_info = ""
    if info["next_title"]:
        next_info = (
            f"\n📊 <b>Прогресс до звания {info['next_title']}:</b>\n"
            f"[ {info['progress_bar']} ] {info['pct']}%\n"
            f"⏳ Осталось: <b>{info['days_left']} дн.</b> общения в чате\n"
        )
    else:
        next_info = "\n🌟 <i>Вы достигли наивысшего звания ветерана! Легенда чата!</i>\n"

    # Проверка доступности бонуса
    bonus_row = await db.fetchone(
        "SELECT last_claimed FROM veteran_bonus_claims WHERE chat_id=? AND user_id=?",
        (message.chat.id, uid)
    )
    now = int(time.time())
    can_claim = False
    if uid == message.from_user.id and info["daily_bonus"] > 0:
        if not bonus_row or (now - bonus_row["last_claimed"] >= 86400):
            can_claim = True

    bonus_status = "🎁 <b>Доступен к получению!</b> (<code>бонус стажа</code>)" if can_claim else f"💰 +{info['daily_bonus']:,} монет/день"

    kb = None
    if can_claim:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎁 Забрать бонус за стаж", callback_data="claim_veteran_bonus")
        ]])

    text = (
        f"🏛 <b>ВЕТЕРАНСКАЯ ВЫСЛУГА ЛЕТ</b>\n\n"
        f"👤 Участник: {mention_id(uid, name)}\n"
        f"📅 В беседе с: <b>{dt_str}</b> (стаж: <b>{info['days']} дн.</b>)\n"
        f"🎖 Почётное звание: <b>{info['title']}</b>\n"
        f"💵 Ежедневный бонус: {bonus_status}\n"
        f"{next_info}\n"
        f"<i>Смотреть всех ветеранов:</i> <code>топ стаж</code> · <code>звания стажа</code>"
    )

    await message.reply(text, reply_markup=kb)


# ---------------- ТОП СТАРОЖИЛОВ БЕСЕДЫ ----------------
@router.message(Cmd("топ стаж", "топ старожилы", "ветераны", "старожилы", usage="топ стаж",
                    desc="Показать рейтинг самых давних участников беседы"))
async def cmd_top_seniority(message: Message, bot: Bot, **kw):
    rows = await db.fetchall(
        "SELECT user_id, ts FROM first_seen WHERE chat_id=? ORDER BY ts ASC LIMIT 10",
        (message.chat.id,)
    )
    if not rows:
        return await message.reply("В базе пока нет записей о стаже участников этого чата.")

    now = int(time.time())
    lines = [f"🏛 <b>ТОП-10 СТАРОЖИЛОВ ЧАТА «{html.escape(message.chat.title or '')}»:</b>\n"]
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    for idx, r in enumerate(rows):
        uid = r["user_id"]
        days = max(0, int((now - r["ts"]) // 86400))
        u = await db.get_user(uid)
        u_name = u["first_name"] if u else f"ID {uid}"

        # Титул
        tier_title = "🐣 Гость"
        for t in SENIORITY_TIERS:
            if days >= t[0]:
                tier_title = t[2]
                break

        lines.append(f"{medals[idx]} {mention_id(uid, u_name)} — <b>{days} дн.</b> [{tier_title}]")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- ПАМЯТКА ВСЕХ ЗВАНИЙ СТАЖА ----------------
@router.message(Cmd("звания стажа", "ранги стажа", usage="звания стажа",
                    desc="Иерархия ветеранских званий и требования"))
async def cmd_veteran_ranks_info(message: Message, bot: Bot, **kw):
    lines = [
        "🏛 <b>ИЕРАРХИЯ ВЕТЕРАНСКИХ ЗВАНИЙ БЕСЕДЫ</b>\n",
        "Стаж рассчитывается автоматически по времени нахождения в этом чате:\n"
    ]
    for t in reversed(SENIORITY_TIERS):
        req_str = f"от {t[0]} дн." if t[0] > 0 else "0–6 дн."
        bonus_str = f"+{t[3]:,} монет/день" if t[3] > 0 else "—"
        lines.append(
            f"┌ <b>{t[2]}</b> ({req_str})\n"
            f"└─▸ Бонус за верность: <b>{bonus_str}</b>\n"
        )
    lines.append("<i>Проверить свой стаж:</i> <code>стаж</code>")
    await message.reply("\n".join(lines))


# ---------------- ЗАБРАТЬ ВЕТЕРАНСКИЙ БОНУС ----------------
@router.message(Cmd("бонус стажа", "ветеранский бонус", usage="бонус стажа",
                    desc="Забрать ежедневный денежный бонус за свой стаж"))
async def cmd_claim_veteran_bonus(message: Message, bot: Bot, **kw):
    chat_id = message.chat.id
    uid = message.from_user.id
    info = await get_user_seniority(chat_id, uid)
    bonus = info["daily_bonus"]

    if bonus <= 0:
        return await message.reply(
            f"🐣 Ваше текущее звание — <b>{info['title']}</b> (стаж: {info['days']} дн.).\n"
            f"Первый ежедневный бонус (<b>+50 монет</b>) открывается со звания <b>🌱 Новичок беседы</b> (от 7 дней в чате)!"
        )

    now = int(time.time())
    row = await db.fetchone(
        "SELECT last_claimed FROM veteran_bonus_claims WHERE chat_id=? AND user_id=?",
        (chat_id, uid)
    )
    if row and (now - row["last_claimed"] < 86400):
        rem = 86400 - (now - row["last_claimed"])
        return await message.reply(
            f"⏳ Вы уже забирали бонус за стаж сегодня!\n"
            f"Следующий бонус будет доступен через: <b>{human_period(rem)}</b>."
        )

    await db.execute(
        "INSERT INTO veteran_bonus_claims (chat_id, user_id, last_claimed) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET last_claimed=excluded.last_claimed",
        (chat_id, uid, now)
    )
    await db.add_coins(uid, bonus, "veteran_bonus")

    await message.reply(
        f"🎁 <b>ВЕТЕРАНСКИЙ БОНУС ПОЛУЧЕН!</b>\n\n"
        f"🎖 Звание: <b>{info['title']}</b> (стаж: {info['days']} дн.)\n"
        f"💰 Начислено: <b>+{bonus:,} монет</b> на ваш баланс!\n"
        f"Возвращайтесь завтра за новой наградой!"
    )


@router.callback_query(F.data == "claim_veteran_bonus")
async def cb_claim_veteran_bonus(call: CallbackQuery, bot: Bot):
    chat_id = call.message.chat.id
    uid = call.from_user.id
    info = await get_user_seniority(chat_id, uid)
    bonus = info["daily_bonus"]
    now = int(time.time())

    row = await db.fetchone(
        "SELECT last_claimed FROM veteran_bonus_claims WHERE chat_id=? AND user_id=?",
        (chat_id, uid)
    )
    if row and (now - row["last_claimed"] < 86400):
        rem = 86400 - (now - row["last_claimed"])
        return await call.answer(f"⏳ Бонус уже забран! Ждите {human_period(rem)}.", show_alert=True)

    await db.execute(
        "INSERT INTO veteran_bonus_claims (chat_id, user_id, last_claimed) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET last_claimed=excluded.last_claimed",
        (chat_id, uid, now)
    )
    await db.add_coins(uid, bonus, "veteran_bonus")
    await call.answer(f"🎉 Получено +{bonus:,} монет за стаж!", show_alert=True)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
