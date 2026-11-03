"""Старт в личке: капча -> Роскошное Главное Меню VIP Moxxi с разделами игр, экономики и рейдов."""
from __future__ import annotations

import asyncio
import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message,
                           PreCheckoutQuery, WebAppInfo)

import db
import config
from config import START_BALANCE
import core_keyboard as kb
from core_registry import Cmd
from h_webapp import DEFAULT_WEBAPP_URL
from utils import mention, mention_id, money

router = Router(name="start")
router.message.filter(F.chat.type == "private")

# --- Капча и Состояния ----------------------------------------------------
EMOJI = ["🍎", "🍌", "🍇", "🍓", "🍒", "🥝", "🍑", "🍍", "🥥", "🍋"]
_captcha: dict[int, dict] = {}
_pending_support_ticket: dict[int, float] = {}


def _captcha_kb(right: str, options: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=o, callback_data=f"cap:{o}") for o in options]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


async def send_captcha(message: Message) -> None:
    right = random.choice(EMOJI)
    others = random.sample([e for e in EMOJI if e != right], 5)
    options = others + [right]
    random.shuffle(options)
    _captcha[message.from_user.id] = {"right": right, "tries": 0, "ts": time.time()}
    await message.answer("🛡 Проверка, что вы человек…", reply_markup=kb.hide())
    await message.answer(
        f"🛡 <b>Проверка, что вы человек</b>\n\n"
        f"Нажмите на этот символ: <b>{right}</b>\n\n"
        f"<i>Это займёт секунду и делается один раз.</i>",
        reply_markup=_captcha_kb(right, options))


@router.callback_query(F.data.startswith("cap:"))
async def cb_captcha(call: CallbackQuery, bot: Bot):
    data = _captcha.get(call.from_user.id)
    if not data:
        await call.message.edit_text("Капча устарела. Отправьте /start ещё раз.")
        return await call.answer()
    choice = call.data.split(":", 1)[1]
    if choice != data["right"]:
        data["tries"] += 1
        if data["tries"] >= 3:
            _captcha.pop(call.from_user.id, None)
            await call.message.edit_text(
                "❌ Слишком много ошибок.\nОтправьте /start, чтобы попробовать снова.")
            return await call.answer("Не угадали", show_alert=True)
        return await call.answer(f"❌ Не то. Попыток осталось: {3 - data['tries']}",
                                 show_alert=True)
    _captcha.pop(call.from_user.id, None)
    await db.get_user(call.from_user.id)
    await db.execute("UPDATE users SET verified=1 WHERE user_id=?", (call.from_user.id,))
    u = await db.get_user(call.from_user.id)
    me = await bot.me()
    await call.message.edit_text(await main_text(call.from_user.first_name, u),
                                 reply_markup=await main_kb(call.from_user.id, me.username))
    await call.answer("✅ Проверка пройдена!")


async def _delayed_delete(msg: Message, delay: float = 1.5) -> None:
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# --- Главное меню ---------------------------------------------------------
async def main_text(name: str | None, u: dict) -> str:
    uid = u["user_id"]
    u_dict = dict(u)
    from h_modules import _rep_title
    rep_val = u_dict.get("rep", 0) or 0
    xp_val = u_dict.get("xp", 0) or 0
    rep_title = _rep_title(rep_val)

    inv_rows = await db.fetchall("SELECT count FROM user_inventory WHERE user_id=? AND count > 0", (uid,))
    inv_count = sum(r["count"] for r in inv_rows)

    is_owner = config.is_bot_owner(uid)
    staff_rank = 4 if is_owner else (await db.get_bot_staff_rank(uid))
    v_lvl, _, v_act = await db.get_vip_info(uid)

    if staff_rank >= 4:
        status_str = "👑 Владелец проекта"
    elif staff_rank == 3:
        status_str = "🥇 Администратор"
    elif staff_rank == 2:
        status_str = "🥈 Модератор"
    elif staff_rank == 1:
        status_str = "🥉 Хелпер"
    elif v_act:
        status_str = "🌟 VIP+ Diamond" if v_lvl >= 2 else "⭐️ VIP"
    else:
        status_str = "🔹 Участник"

    return (
        f"🍸 ✨ <b>MOXXI 2.1 — ГЛАВНОЕ МЕНЮ</b> ✨ 🍸\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🏢 ⚔️ 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👋 Рады видеть, <b>{html.escape(name or 'Боец')}</b>!\n"
        f"🔥 <i>Игровой мир азарта, экономики, рейдов и умного ИИ!</i>\n\n"
        f"┌ 💎 <b>Ваш статус:</b> {status_str}\n"
        f"├ 💰 <b>Баланс:</b> <code>{money(u_dict.get('balance', 0))}</code>\n"
        f"├ ⚡️ <b>Опыт:</b> <code>{xp_val} XP</code>\n"
        f"├ ⭐️ <b>Репутация:</b> <code>{rep_val}</code> <i>({rep_title})</i>\n"
        f"└ 🎒 <b>Инвентарь:</b> <code>{inv_count} предм.</code>\n\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"🚀 <b>Выберите интересующий раздел:</b>"
    )


async def main_kb(uid: int = 0, bot_username: str = "moxxichat_bot") -> InlineKeyboardMarkup:
    rights = ("change_info+delete_messages+restrict_members+invite_users"
              "+pin_messages+manage_chat")
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin={rights}"

    rows = [
        [
            InlineKeyboardButton(text="➕ Добавить бота в беседу", url=add_url)
        ],
        [
            InlineKeyboardButton(text="🎰 Казино и Игры", callback_data="mm:grams"),
            InlineKeyboardButton(text="🏢 Бизнесы и Рынок", callback_data="mm:biz"),
        ],
        [
            InlineKeyboardButton(text="🐉 Рейдовые Боссы", callback_data="mm:boss"),
            InlineKeyboardButton(text="⚔️ PvP-Дуэли", callback_data="mm:duels"),
        ],
        [
            InlineKeyboardButton(text="🛍 Магазин и Кейсы", callback_data="mm:shop_menu"),
            InlineKeyboardButton(text="🎣 Рыбалка и Крафт", callback_data="mm:fish"),
        ],
        [
            InlineKeyboardButton(text="📜 Квесты и Ачивки", callback_data="mm:quests"),
            InlineKeyboardButton(text="🏆 Топ Рейтинги", callback_data="mm:tops"),
        ],
        [
            InlineKeyboardButton(text="🎁 Бонусы", callback_data="mm:bonus"),
            InlineKeyboardButton(text="📖 Все Команды", callback_data="mm:cmds"),
        ],
        [
            InlineKeyboardButton(text="🆘 Написать в техподдержку", callback_data="mm:support")
        ]
    ]

    is_owner = config.is_bot_owner(uid)
    staff_rank = 4 if is_owner else (await db.get_bot_staff_rank(uid))
    if staff_rank >= 1:
        rows.insert(0, [
            InlineKeyboardButton(text="👑 Админ-Панель (Управление)", callback_data="mm:admin_panel")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(extra: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
@router.message(Cmd("старт", section=32, usage="старт", desc="Запуск и главное меню"))
async def cmd_start(message: Message, bot: Bot, **kw):
    try:
        await db.track_daily_activity(message.from_user.id, is_start=True)
    except Exception:
        pass
    u = await db.get_user(message.from_user.id)
    if not u["verified"]:
        return await send_captcha(message)
    me = await bot.me()

    if message.chat.type != "private":
        kb_group = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Справочник всех команд", callback_data="h:p:0")],
            [InlineKeyboardButton(text="🚀 Открыть бота в ЛС", url=f"https://t.me/{me.username}?start=group")]
        ])
        text_msg = (
            f"👋 Привет, {html.escape(message.from_user.first_name or '')}!\n"
            f"Я бот <b>MOXXI</b>.\n\n"
            f"• В беседах я отвечаю на команды: <code>/help</code>, <code>казик</code>, <code>игры</code>, <code>брак</code>, <code>дуэли</code> и сотни других.\n"
            f"• Личный кабинет и персональные настройки открываются в личке с ботом 👇"
        )
        return await message.reply(text_msg, reply_markup=kb_group)

    
