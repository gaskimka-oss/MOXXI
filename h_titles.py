"""👑 Модуль Кастомных Титулов и Значков Профиля (Moxxi Titles & Badges).

Позволяет игрокам покупать, коллекционировать и надевать уникальные звания,
которые отображаются в анкете, профиле и игровых карточках.
"""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, money

router = Router(name="titles")
S = 39  # Раздел: Инвентарь, предметы и титулы

TITLES_CATALOG = {
    "boss_slayer": {
        "id": "boss_slayer",
        "title": "⚡️ Гроза Боссов",
        "price": 15000,
        "desc": "Для бесстрашных охотников на рейдовых боссов!"
    },
    "billionaire": {
        "id": "billionaire",
        "title": "👑 Миллиардер",
        "price": 50000,
        "desc": "Символ безграничного богатства и влияния."
    },
    "bounty_hunter": {
        "id": "bounty_hunter",
        "title": "🩸 Охотник за головами",
        "price": 20000,
        "desc": "Для непобедимых мастеров смертельных PvP-дуэлей."
    },
    "cutie": {
        "id": "cutie",
        "title": "🌸 Няшка Чата",
        "price": 10000,
        "desc": "Милый и всеми любимый участник беседы."
    },
    "dragon_knight": {
        "id": "dragon_knight",
        "title": "🐉 Рыцарь Дракона",
        "price": 30000,
        "desc": "Благородный воин с чешуйчатым спутником."
    },
    "casino_king": {
        "id": "casino_king",
        "title": "🎰 Король Азарта",
        "price": 25000,
        "desc": "Любимец фортуны и завсегдатай казино Мокси."
    },
    "legend": {
        "id": "legend",
        "title": "💎 Живая Легенда",
        "price": 100000,
        "desc": "Высшее признание авторитета во всем Telegram."
    },
    "vip_lord": {
        "id": "vip_lord",
        "title": "🌟 VIP Авторитет",
        "price": 0,
        "vip_only": True,
        "desc": "Эксклюзивный титул для обладателей статуса VIP+ Diamond!"
    }
}


def _titles_kb(user_titles: list[str], active_title: str, is_vip_plus: bool) -> InlineKeyboardMarkup:
    rows = []
    for tid, tinfo in TITLES_CATALOG.items():
        is_owned = (tid in user_titles) or (tinfo.get("vip_only") and is_vip_plus)
        is_active = (active_title == tid)

        if is_active:
            btn_text = f"✅ {tinfo['title']} (Надет)"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"ttl:unequip:{tid}")])
        elif is_owned:
            btn_text = f"✨ {tinfo['title']} (Надеть)"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"ttl:equip:{tid}")])
        else:
            cost_str = f"{money(tinfo['price'])}" if tinfo['price'] > 0 else "VIP+"
            btn_text = f"🛒 {tinfo['title']} — {cost_str}"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"ttl:buy:{tid}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("титулы", "магазин титулов", "мои титулы", "звания", section=S, rank=0,
                    usage="титулы", desc="👑 Магазин кастомных титулов и званий для профиля"))
async def cmd_titles_menu(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    user_titles = await db.get_user_titles(uid)
    active_title = await db.get_active_title(uid) or ""
    v_lvl, _, v_act = await db.get_vip_info(uid)
    is_vip_plus = v_act and v_lvl >= 2

    cur_title_name = "Не выбран"
    if active_title and active_title in TITLES_CATALOG:
        cur_title_name = TITLES_CATALOG[active_title]["title"]

    text = (
        f"👑 ✨ <b>ГАРДЕРОБ ТИТУЛОВ И ЗВАНИЙ</b> ✨ 👑\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Владелец: {mention(message.from_user)}\n"
        f"🏷 <b>Текущий титул:</b> <b>{cur_title_name}</b>\n\n"
        f"Титулы отображаются в вашем профиле (<code>профиль</code>) и карточках побед.\n"
        f"<i>Нажмите кнопку для покупки или надевания титула:</i>"
    )
    await message.reply(text, reply_markup=_titles_kb(user_titles, active_title, is_vip_plus))


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("ttl:"))
async def cb_titles_action(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    action = parts[1]
    tid = parts[2]
    uid = call.from_user.id

    tinfo = TITLES_CATALOG.get(tid)
    if not tinfo:
        return await call.answer("Титул не найден", show_alert=True)

    v_lvl, _, v_act = await db.get_vip_info(uid)
    is_vip_plus = v_act and v_lvl >= 2

    if action == "buy":
        if tinfo.get("vip_only") and not is_vip_plus:
            return await call.answer("🌟 Этот титул эксклюзивно доступен для ранга VIP+ Diamond!", show_alert=True)

        user = await db.get_user(uid)
        price = tinfo["price"]
        if user["balance"] < price:
            return await call.answer(f"❌ Недостаточно монет! Требуется {money(price)}.", show_alert=True)

        await db.add_balance(uid, -price)
        await db.unlock_user_title(uid, tid)
        await db.set_active_title(uid, tid)

        await call.answer(f"🎉 Титул «{tinfo['title']}» успешно куплен и надет!", show_alert=True)

    elif action == "equip":
        user_titles = await db.get_user_titles(uid)
        is_owned = (tid in user_titles) or (tinfo.get("vip_only") and is_vip_plus)
        if not is_owned:
            return await call.answer("У вас нет этого титула!", show_alert=True)

        await db.set_active_title(uid, tid)
        await call.answer(f"✅ Надет титул: {tinfo['title']}")

    elif action == "unequip":
        await db.set_active_title(uid, "")
        await call.answer("Снят активный титул.")

    user_titles = await db.get_user_titles(uid)
    active_title = await db.get_active_title(uid) or ""
    cur_title_name = TITLES_CATALOG[active_title]["title"] if active_title in TITLES_CATALOG else "Не выбран"

    text = (
        f"👑 ✨ <b>ГАРДЕРОБ ТИТУЛОВ И ЗВАНИЙ</b> ✨ 👑\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Владелец: {mention(call.from_user)}\n"
        f"🏷 <b>Текущий титул:</b> <b>{cur_title_name}</b>\n\n"
        f"Титулы отображаются в вашем профиле (<code>профиль</code>) и карточках побед.\n"
        f"<i>Нажмите кнопку для покупки или надевания титула:</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=_titles_kb(user_titles, active_title, is_vip_plus))
    except Exception:
        pass


# ================== КАСТОМНЫЕ ПРЕФИКСЫ И ТИТУЛЫ В ЧАТЕ ==================

RANK_PREFIXES = {
    10: "[👑 Владелец]",
    9: "[⚜️ Зам]",
    8: "[💻 Техадмин]",
    7: "[🏛 Гл. Админ]",
    6: "[🛡 Ст. Админ]",
    5: "[⚔️ Мл. Админ]",
    4: "[🔮 Гл. Модер]",
    3: "[🎖 Ст. Модер]",
    2: "[🔰 Мл. Модер]",
    1: "[🍃 Стажёр]",
}


async def get_display_prefix(chat_id: int, user_id: int) -> str:
    """Возвращает отображаемый префикс пользователя: кастомный или по рангу должности."""
    cust = await db.get_setting(chat_id, f"prefix_{user_id}", "")
    if cust:
        return cust
    from core_ranks import get_rank
    r = await get_rank(chat_id, user_id)
    return RANK_PREFIXES.get(r, "")


@router.message(Cmd("+префикс", "префикс", "установить префикс", section=S, rank=0,
                    usage="+префикс [текст]", desc="Установить личный префикс в чате"))
async def cmd_set_prefix(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    text = (args or "").strip()
    if not text:
        cur = await get_display_prefix(message.chat.id, uid)
        cur_str = f"<b>{html.escape(cur)}</b>" if cur else "<i>не установлен (действует по рангу)</i>"
        return await message.reply(
            f"🏷 <b>Ваш текущий префикс в чате:</b> {cur_str}\n\n"
            f"💡 Чтобы установить: <code>+префикс [Лидер]</code> или <code>+префикс [Босс]</code>\n"
            f"🗑 Чтобы снять: <code>-префикс</code>"
        )
    if len(text) > 30:
        return await message.reply("⛔️ Префикс слишком длинный (максимум 30 символов).")

    if not (text.startswith("[") and text.endswith("]")):
        text = f"[{text}]"

    await db.set_setting(message.chat.id, f"prefix_{uid}", text)
    await message.reply(f"✅ Установлен личный префикс в чате: <b>{html.escape(text)}</b>")


@router.message(Cmd("-префикс", "снять префикс", "удалить префикс", section=S, rank=0,
                    usage="-префикс", desc="Снять кастомный префикс"))
async def cmd_remove_prefix(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    await db.set_setting(message.chat.id, f"prefix_{uid}", "")
    def_prefix = await get_display_prefix(message.chat.id, uid)
    def_str = f" (теперь действует по должности: <b>{html.escape(def_prefix)}</b>)" if def_prefix else ""
    await message.reply(f"🧹 Личный префикс снят{def_str}.")
