"""Мировой Новогодний Рейд-Босс «Злой Крампус» и праздничная социальная система «Тайный Санта»."""
from __future__ import annotations

import asyncio
import html
import random
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
from core_ranks import require
from core_registry import Cmd
from h_winter_event import is_winter_active, time_until_str, WINTER_START_TS
from utils import mention, mention_id, money, parse_amount

router = Router(name="winter_boss_santa")

# Кулдауны на атаку босса (user_id -> timestamp)
_boss_attack_cooldowns: dict[int, float] = {}


def _render_boss_hp_bar(cur: int, total: int, length: int = 10) -> str:
    filled = int(round(length * max(0, min(cur, total)) / total)) if total > 0 else 0
    return "█" * filled + "░" * (length - filled)


# ═══════════════════════════════════════════════════════════════════════════
# 1. МИРОВОЙ РЕЙД-БОСС: ЗЛОЙ КРАМПУС
# ═══════════════════════════════════════════════════════════════════════════

async def render_krampus_card() -> tuple[str, InlineKeyboardMarkup]:
    boss = await db.get_or_spawn_world_boss()
    top_hitters = await db.get_world_boss_top_hitters(limit=5)

    cur_hp = boss.get("current_hp", 0)
    max_hp = boss.get("max_hp", 1_500_000)
    bar = _render_boss_hp_bar(cur_hp, max_hp, length=10)

    rows = []
    if not top_hitters:
        rows.append("<i>Пока никто не атаковал Крампуса. Нанесите первый удар!</i>")
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, h in enumerate(top_hitters):
            m = medals[idx] if idx < len(medals) else f"#{idx+1}"
            name = html.escape(h.get("first_name") or "Боец")
            dmg = h.get("damage", 0)
            rows.append(f"{m} <b>{name}</b> — нанёс <code>{dmg:,} урона</code>")

    status_tag = "⚔️ <b>В БОЮ</b>" if boss.get("status") == "alive" else "💀 <b>ПОВЕРЖЕН (Возродится через 2 часа)</b>"

    text = (
        f"👹 🎄 <b>МИРОВОЙ РЕЙД-БОСС: ЗЛОЙ КРАМПУС</b> 🎄 👹\n"
        f"✦ ══════════════════════════════════════ ✦\n\n"
        f"❄️ <i>Древний ледяной демон пришел украсть Новый Год!</i>\n"
        f"Объединяйтесь всеми беседами бота и победите чудовище!\n\n"
        f"📊 <b>Состояние босса:</b> {status_tag}\n"
        f"❤️ <b>Здоровье:</b> <code>{cur_hp:,} / {max_hp:,} HP</code>\n"
        f"[{bar}]\n\n"
        f"🎁 <b>Награда победителям:</b>\n"
        f"├ ❄️ +500 Снежинок всем участникам боя\n"
        f"└ 💰 +500,000 монет разделят топ дамагеры!\n\n"
        f"🏆 <b>ТОП-5 ОХОТНИКОВ НА КРАМПУСА:</b>\n"
        + "\n".join(rows) + "\n"
        f"✦ ══════════════════════════════════════ ✦\n"
        f"👉 <i>Атаковать: кнопка ниже или команда <code>ударить крампуса</code>!</i>"
    )

    buttons = []
    if boss.get("status") == "alive":
        buttons.append([InlineKeyboardButton(text="⚔️ НАНЕСТИ УДАР ПО КРАМПУСУ!", callback_data="krampus_hit")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить статус", callback_data="krampus_refresh")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Cmd("крампус", "нг босс", "босс нг", "злой крампус", "krampus", section=32,
                    usage="крампус", desc="👹 Мировой Новогодний Рейд-Босс Злой Крампус"))
async def cmd_krampus(message: Message, **kw):
    if not is_winter_active():
        time_left = time_until_str(WINTER_START_TS)
        return await message.reply(
            f"❄️ <b>МИРОВОЙ БОСС: ЗЛОЙ КРАМПУС</b> ❄️\n"
            f"✦ ══════════════════════════════════════ ✦\n\n"
            f"Крампус выйдет из вечной мерзлоты <b>1 декабря в 00:00 по МСК</b>!\n\n"
            f"⏳ <b>До пробуждения босса:</b> <b>{time_left}</b>\n\n"
            f"⚔️ <i>Готовьте оружие и снежки — бой будет легендарным!</i>"
        )
    text, kb = await render_krampus_card()
    await message.reply(text, reply_markup=kb)


@router.message(Cmd("ударить крампуса", "атака крампуса", "бить крампуса", "атаковать крампуса", section=32,
                    usage="ударить крампуса", desc="⚔️ Атаковать мирового босса Крампуса"))
async def cmd_hit_krampus(message: Message, bot: Bot, **kw):
    if not is_winter_active():
        return await message.reply("❄️ Босс появится 1 декабря в 00:00 по МСК!")

    uid = message.from_user.id
    now = time.time()
    last = _boss_attack_cooldowns.get(uid, 0.0)
    if now - last < 25:
        left = int(25 - (now - last))
        return await message.reply(f"⏳ Перезарядка оружия! Вы сможете атаковать через <b>{left} сек.</b> ❄️")

    _boss_attack_cooldowns[uid] = now

    base_dmg = random.randint(8000, 25000)
    res = await db.hit_world_boss(uid, base_dmg)
    dmg = res["damage_dealt"]
    boss = res["boss"]

    # Продвигаем квесты чата
    try:
        await db.advance_chat_quest(message.chat.id, "games", 1)
    except Exception:
        pass

    if res["defeated"]:
        # Босс повержен! Выдаем награды топ дамагерам
        top_h = await db.get_world_boss_top_hitters(limit=3)
        for h in top_h:
            await db.add_balance(h["user_id"], 150_000, "krampus_defeat")
            await db.add_user_snowflakes(h["user_id"], 100)
        return await message.reply(
            f"🎉 💥 <b>НЕВЕРОЯТНО! ЗЛОЙ КРАМПУС ПОВЕРЖЕН!</b> 💥 🎉\n\n"
            f"Финишный сокрушительный удар нанёс {mention(message.from_user)} (<b>{dmg:,} урона</b>)!\n\n"
            f"🏆 Новый Год спасён! Топ-дамагеры получили по <b>150,000 монет и 100 ❄️ Снежинок</b>!"
        )

    left_hp = boss.get("current_hp", 0)
    await message.reply(
        f"⚔️ 💥 <b>АТАКА ПО КРАМПУСУ!</b>\n\n"
        f"{mention(message.from_user)} нанёс <b>{dmg:,} урона</b> по ледяной броне чудовища!\n"
        f"❤️ Осталось HP у Крампуса: <b>{left_hp:,}</b>"
    )


@router.callback_query(F.data == "krampus_hit")
async def cb_krampus_hit(call: CallbackQuery, bot: Bot):
    if not is_winter_active():
        return await call.answer("❄️ Босс появится 1 декабря!", show_alert=True)

    uid = call.from_user.id
    now = time.time()
    last = _boss_attack_cooldowns.get(uid, 0.0)
    if now - last < 25:
        left = int(25 - (now - last))
        return await call.answer(f"⏳ Перезарядка! Подождите {left} сек.", show_alert=True)

    _boss_attack_cooldowns[uid] = now
    base_dmg = random.randint(8000, 25000)
    res = await db.hit_world_boss(uid, base_dmg)
    dmg = res["damage_dealt"]

    await call.answer(f"💥 Вы нанесли {dmg:,} урона!", show_alert=True)
    text, kb = await render_krampus_card()
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "krampus_refresh")
async def cb_krampus_refresh(call: CallbackQuery):
    text, kb = await render_krampus_card()
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer("Статус босса обновлен!")


# ═══════════════════════════════════════════════════════════════════════════
# 2. ТАЙНЫЙ САНТА (ПОДАРОК @ЮЗЕР)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Cmd("подарок", "тайный санта", "санта", "подарить", section=32,
                    usage="подарок [@юзер] [сумма] [пожелание]", desc="🎁 Отправить подарок Тайного Санты"))
async def cmd_santa_gift(message: Message, bot: Bot, args: str = "", **kw):
    if message.chat.type == "private":
        return await message.reply("🎁 Отправлять подарки Тайного Санты можно только в беседах!")

    if not is_winter_active():
        return await message.reply("❄️ Тайный Санта начнет дарить подарки 1 декабря вместе со стартом сезона!")

    uid = message.from_user.id
    u_sender = await db.get_user(uid)

    # Ищем цель (реплай или юзер)
    target_id: Optional[int] = None
    target_name: str = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or "Друг"
    elif message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name
                break

    if not target_id:
        return await message.reply(
            "🎁 <b>Как отправить подарок Тайного Санты:</b>\n\n"
            "Ответьте на сообщение человека командой:\n"
            "<code>подарок 5000 С Новым Годом, бро!</code>"
        )

    if target_id == uid:
        return await message.reply("😅 Нельзя отправить подарок Тайного Санты самому себе!")

    # Разбираем сумму и текст
    parts = (args or "").strip().split(maxsplit=1)
    raw_amount = parts[0] if parts else ""
    note = parts[1] if len(parts) > 1 else "С наступающим Новым Годом! 🎄"

    amount = parse_amount(raw_amount) or 1000
    if amount < 100:
        return await message.reply("❌ Минимальная сумма подарка: <b>100 монет</b>.")

    if u_sender["balance"] < amount:
        return await message.reply(f"❌ Недостаточно средств! Нужно: <b>{money(amount)}</b>.")

    await db.add_balance(uid, -amount)

    gift_id = await db.create_santa_gift(
        chat_id=message.chat.id,
        from_id=uid,
        to_id=target_id,
        amount=amount,
        flakes=10,
        note=note,
        is_anon=False
    )

    t_mention = f'<a href="tg://user?id={target_id}">{html.escape(target_name)}</a>'
    box_text = (
        f"🎁 ✨ <b>ТАЙНЫЙ САНТА ПРИНЁС ПОДАРОК!</b> ✨ 🎁\n"
        f"✦ ══════════════════════════════════ ✦\n\n"
        f"Для: {t_mention}\n"
        f"От: {mention(message.from_user)} 🎅\n\n"
        f"📦 Внутри коробки спрятаны монеты и снежинки!\n"
        f"✦ ══════════════════════════════════ ✦\n"
        f"👇 <i>Нажмите кнопку ниже, чтобы распаковать подарок:</i>"
    )
    kb_box = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎀 РАСПАКОВАТЬ ПОДАРОК 🎀", callback_data=f"open_gift:{gift_id}")]
    ])
    await message.reply(box_text, reply_markup=kb_box)


@router.callback_query(F.data.startswith("open_gift:"))
async def cb_open_gift(call: CallbackQuery):
    gift_id = int(call.data.split(":")[1])
    gift = await db.get_santa_gift(gift_id)
    if not gift:
        return await call.answer("Подарок не найден", show_alert=True)

    if call.from_user.id != gift["to_id"]:
        return await call.answer("❌ Этот подарок приготовлен не для вас!", show_alert=True)

    if gift["opened"]:
        return await call.answer("Подарок уже распакован!", show_alert=True)

    opened = await db.open_santa_gift(gift_id, call.from_user.id)
    if not opened:
        return await call.answer("Ошибка распаковки", show_alert=True)

    note_clean = html.escape(gift.get("note") or "С Новым Годом!")
    amt = gift["amount"]
    flakes = gift["flakes"]

    res_text = (
        f"🎉 💥 <b>ХЛОП! ПОДАРОК РАСПАКОВАН!</b> 💥 🎉\n"
        f"✦ ══════════════════════════════════ ✦\n\n"
        f"👤 Получатель: {mention(call.from_user)}\n\n"
        f"🎁 <b>ВНУТРИ ОКАЗАЛОСЬ:</b>\n"
        f"├ 💰 <b>+{money(amt)}</b> зачислено на баланс!\n"
        f"└ ❄️ <b>+{flakes} Снежинок</b>\n\n"
        f"💌 <b>Записка с пожеланием:</b>\n"
        f"<i>«{note_clean}»</i>\n"
        f"✦ ══════════════════════════════════ ✦\n"
        f"🎅 <i>Тайный Санта желает отличных праздников!</i>"
    )
    try:
        await call.message.edit_text(res_text)
    except Exception:
        pass
    await call.answer("🎁 Подарок успешно распакован!")
