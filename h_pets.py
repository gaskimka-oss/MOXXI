"""🐾 Модуль РПГ-Питомцев (Moxxi Pets System).

Включает:
- 5 видов уникальных питомцев с игровыми бонусами;
- Прокачку уровня и шкалу сытости;
- Экспедиции за сокровищами, ресурсами и монетами;
- Интерактивное меню с инлайн-управлением.
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
from utils import hms, mention, money

router = Router(name="pets")
S = 39  # Раздел: Инвентарь, предметы и питомцы

PET_CATALOG = {
    "cat": {
        "name": "🐱 Кот-Баюн",
        "price": 15000,
        "desc": "Мягкий и хитрый кот. Даёт +15% к удаче в казино и +25% к шансу редкой рыбы.",
        "icon": "🐱",
        "bonus_type": "luck"
    },
    "dog": {
        "name": "🐕 Боевой Пёс",
        "price": 20000,
        "desc": "Верный защитник. Даёт +20% к урону на Рейдовых Боссах и в PvP-Дуэлях.",
        "icon": "🐕",
        "bonus_type": "combat"
    },
    "dragon": {
        "name": "🐉 Маленький Дракончик",
        "price": 50000,
        "desc": "Легендарный спутник. Даёт +50% к наградам за экспедиции и пассивному опыту.",
        "icon": "🐉",
        "bonus_type": "dragon"
    },
    "falcon": {
        "name": "🦅 Зоркий Сокол",
        "price": 25000,
        "desc": "Быстрокрылый охотник. Сокращает время любых экспедиций в 2 раза!",
        "icon": "🦅",
        "bonus_type": "speed"
    },
    "drone": {
        "name": "🤖 Кибер-Дрон",
        "price": 35000,
        "desc": "Высокотехнологичный сканер. Шанс 35% принести удвоенный лут из экспедиций!",
        "icon": "🤖",
        "bonus_type": "tech"
    }
}

EXPEDITIONS = {
    "1": {"name": "🌲 Прогулка по лесу", "dur": 3600, "min_gold": 800, "max_gold": 1800, "xp": 40},
    "2": {"name": "⛰ Вылазка в горы", "dur": 7200, "min_gold": 2000, "max_gold": 4200, "xp": 100},
    "4": {"name": "🌋 Экспедиция в Пустоши", "dur": 14400, "min_gold": 5000, "max_gold": 10000, "xp": 250},
}

RESOURCE_POOL = ["craft_wood", "craft_gear", "craft_shard", "craft_essence"]
RESOURCE_NAMES = {
    "craft_wood": "🪵 Редкая древесина",
    "craft_gear": "⚙️ Шестеренка",
    "craft_shard": "💎 Осколок кристалла",
    "craft_essence": "🔮 Эссенция бездны"
}


def _hunger_bar(hunger: int) -> str:
    filled = int(max(0, min(100, hunger)) / 10)
    empty = 10 - filled
    return f"[{'🍗' * filled}{'░' * empty}] {hunger}%"


def _exp_bar(xp: int, next_xp: int) -> str:
    pct = max(0.0, min(1.0, xp / max(1, next_xp)))
    filled = int(round(pct * 10))
    empty = 10 - filled
    return f"[{'⭐️' * filled}{'░' * empty}] {int(pct * 100)}% ({xp}/{next_xp} XP)"


def _get_pet_card(pet: dict, user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    now = int(time.time())
    p_info = PET_CATALOG.get(pet["pet_type"], PET_CATALOG["cat"])
    lvl = pet["level"]
    next_xp = lvl * 100
    
    # Расчет сытости с течением времени
    hours_passed = int((now - pet["last_feed"]) / 3600)
    current_hunger = max(0, pet["hunger"] - (hours_passed * 4))

    exp_status = "💤 Отдыхает дома"
    is_exp_done = False
    exp_until = pet.get("expedition_until", 0)

    if exp_until > now:
        left = exp_until - now
        exp_status = f"🧭 В экспедиции (вернётся через <b>{hms(left)}</b>)"
    elif exp_until > 0 and exp_until <= now:
        exp_status = "🎉 <b>Вернулся из экспедиции! Награда готова!</b>"
        is_exp_done = True

    status_tag = "💚 Сыт и готов к подвигам" if current_hunger >= 30 else "⚠️ <b>Очень голоден! (Бонусы временно не действуют)</b>"

    text = (
        f"🐾 ✨ <b>ПИТОМЕЦ: {html.escape(pet['pet_name'])}</b> ✨ 🐾\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Хозяин: <b>{html.escape(user_name)}</b>\n"
        f"🏷 Порода: <b>{p_info['name']}</b>\n"
        f"🎖 Уровень: <b>{lvl} ур.</b>\n"
        f"📊 Опыт: {_exp_bar(pet['xp'], next_xp)}\n"
        f"🍖 Сытость: {_hunger_bar(current_hunger)}\n"
        f"💖 Статус: {status_tag}\n\n"
        f"🧭 <b>Экспедиция:</b> {exp_status}\n\n"
        f"🌟 <b>Суперсила породы:</b>\n"
        f"<i>{p_info['desc']}</i>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Переименовать:</i> <code>назвать питомца [новое имя]</code>"
    )

    kb_rows = []
    if is_exp_done:
        kb_rows.append([InlineKeyboardButton(text="🎁 Забрать добычу экспедиции!", callback_data="pet:claim_exp")])
    elif exp_until <= now:
        kb_rows.append([
            InlineKeyboardButton(text="🌲 В лес (1ч)", callback_data="pet:start_exp:1"),
            InlineKeyboardButton(text="⛰ В горы (2ч)", callback_data="pet:start_exp:2"),
        ])
        kb_rows.append([
            InlineKeyboardButton(text="🌋 В Пустоши (4ч)", callback_data="pet:start_exp:4")
        ])

    kb_rows.append([
        InlineKeyboardButton(text="🍖 Покормить (200 🪙)", callback_data="pet:feed"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="pet:refresh")
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


# ================== КОМАНДЫ ==================

@router.message(Cmd("питомец", "мой питомец", "пет", "питомцы", section=S, rank=0,
                    usage="питомец", desc="🐾 Меню вашего боевого питомца"))
async def cmd_pet_menu(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    pet = await db.get_user_pet(uid)

    if not pet:
        # Предлагаем магазин питомцев
        lines = [
            "🐾 ✨ <b>ПИТОМНИК МОКСИ: ВЫБЕРИТЕ СПУТНИКА!</b> ✨ 🐾",
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
            "У вас пока нет боевого питомца. Заведите верного друга, чтобы он помогал в рейдах, приносил сокровища из экспедиций и радовал в чате!\n"
        ]
        for key, p in PET_CATALOG.items():
            lines.append(f"{p['name']} — <b>{money(p['price'])}</b>\n<i>└─▸ {p['desc']}</i>\n")

        lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n💡 <b>Как купить:</b> <code>купить питомца [кот/пёс/дракон/сокол/дрон]</code>")

        kb_rows = [
            [InlineKeyboardButton(text="🐱 Купить Кота (15 000 🪙)", callback_data="pet:buy:cat")],
            [InlineKeyboardButton(text="🐕 Купить Пса (20 000 🪙)", callback_data="pet:buy:dog")],
            [InlineKeyboardButton(text="🦅 Купить Сокола (25 000 🪙)", callback_data="pet:buy:falcon")],
            [InlineKeyboardButton(text="🤖 Купить Дрона (35 000 🪙)", callback_data="pet:buy:drone")],
            [InlineKeyboardButton(text="🐉 Купить Дракончика (50 000 🪙)", callback_data="pet:buy:dragon")],
        ]
        return await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

    user_name = message.from_user.first_name or "Хозяин"
    text, kb = _get_pet_card(pet, user_name)
    await message.reply(text, reply_markup=kb)


@router.message(Cmd("купить питомца", "завести питомца", section=S, rank=0,
                    usage="купить питомца [кот/пес/дракон/сокол/дрон]", desc="🐾 Купить боевого питомца"))
async def cmd_buy_pet(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    arg = (args or "").strip().lower()

    key_map = {
        "кот": "cat", "кота": "cat", "кошка": "cat", "cat": "cat",
        "пес": "dog", "пёс": "dog", "собака": "dog", "пса": "dog", "dog": "dog",
        "дракон": "dragon", "дракончик": "dragon", "dragon": "dragon",
        "сокол": "falcon", "птица": "falcon", "falcon": "falcon",
        "дрон": "drone", "кибердрон": "drone", "робот": "drone", "drone": "drone"
    }

    pet_key = key_map.get(arg)
    if not pet_key or pet_key not in PET_CATALOG:
        if had_prefix or not in_group:
            return await message.reply("⚠️ Укажите породу: <code>купить питомца кот / пес / дракон / сокол / дрон</code>")
        return

    p_info = PET_CATALOG[pet_key]
    user = await db.get_user(uid)
    if user["balance"] < p_info["price"]:
        return await message.reply(f"❌ Недостаточно монет! {p_info['name']} стоит <b>{money(p_info['price'])}</b>.")

    await db.add_balance(uid, -p_info["price"])
    await db.create_user_pet(uid, pet_key, p_info["name"])

    await message.reply(
        f"🎉 ✨ <b>ПОЗДРАВЛЯЕМ С ПРИОБРЕТЕНИЕМ ПИТОМЦА!</b> ✨ 🎉\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Хозяин: {mention(message.from_user)}\n"
        f"🐾 Ваш новый спутник: <b>{p_info['name']}</b>!\n\n"
        f"🌟 <i>{p_info['desc']}</i>\n\n"
        f"🍖 Покормите питомца и отправьте его на первую охоту: <code>питомец</code>"
    )


@router.message(Cmd("назвать питомца", "имя питомца", "переименовать питомца", section=S, rank=0,
                    usage="назвать питомца [новое имя]", desc="🐾 Дать кличку питомцу"))
async def cmd_rename_pet(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    pet = await db.get_user_pet(uid)
    if not pet:
        if had_prefix or not in_group:
            return await message.reply("❌ У вас ещё нет питомца. Купить: <code>питомец</code>")
        return

    new_name = (args or "").strip()
    if not new_name or len(new_name) > 30:
        if had_prefix or not in_group:
            return await message.reply("⚠️ Введите имя питомца длиной от 1 до 30 символов:\n👉 <code>назвать питомца Барсик</code>")
        return

    await db.update_user_pet(uid, pet_name=new_name)
    await message.reply(f"💖 Вашего питомца теперь зовут <b>{html.escape(new_name)}</b>!")


@router.message(Cmd("покормить питомца", "кормить питомца", "корм питомцу", section=S, rank=0,
                    usage="покормить питомца", desc="🍖 Покормить питомца (200 монет)"))
async def cmd_feed_pet(message: Message, bot: Bot, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    pet = await db.get_user_pet(uid)
    if not pet:
        if had_prefix or not in_group:
            return await message.reply("❌ У вас ещё нет питомца. Купить: <code>питомец</code>")
        return

    user = await db.get_user(uid)
    if user["balance"] < 200:
        return await message.reply("❌ Порция премиум-корма стоит <b>200 монет</b>.")

    await db.add_balance(uid, -200)
    now = int(time.time())
    new_hunger = min(100, pet["hunger"] + 50)
    new_xp = pet["xp"] + 20
    new_lvl = pet["level"]

    next_req = new_lvl * 100
    lvl_up_text = ""
    if new_xp >= next_req:
        new_lvl += 1
        new_xp -= next_req
        lvl_up_text = f"\n🎉 ✨ <b>УРОВЕНЬ ПИТОМЦА ПОВЫШЕН ДО {new_lvl}!</b> ✨"

    await db.update_user_pet(uid, hunger=new_hunger, last_feed=now, xp=new_xp, level=new_lvl)

    await message.reply(
        f"🍖 {mention(message.from_user)} вкусно покормил питомца <b>{html.escape(pet['pet_name'])}</b>!\n"
        f"🍗 Сытость: <b>{new_hunger}%</b> · ⭐️ <b>+20 XP</b> питомцу!{lvl_up_text}"
    )


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("pet:"))
async def cb_pet_actions(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    action = parts[1]
    uid = call.from_user.id

    if action == "buy":
        pet_key = parts[2]
        p_info = PET_CATALOG.get(pet_key)
        if not p_info:
            return await call.answer("Порода не найдена", show_alert=True)

        user = await db.get_user(uid)
        if user["balance"] < p_info["price"]:
            return await call.answer(f"Недостаточно монет! Нужно {money(p_info['price'])}.", show_alert=True)

        await db.add_balance(uid, -p_info["price"])
        await db.create_user_pet(uid, pet_key, p_info["name"])
        await call.answer("🎉 Питомец успешно куплен!", show_alert=True)

        pet = await db.get_user_pet(uid)
        text, kb = _get_pet_card(pet, call.from_user.first_name or "Хозяин")
        return await call.message.edit_text(text, reply_markup=kb)

    pet = await db.get_user_pet(uid)
    if not pet:
        return await call.answer("У вас нет питомца!", show_alert=True)

    now = int(time.time())

    if action == "feed":
        user = await db.get_user(uid)
        if user["balance"] < 200:
            return await call.answer("Недостаточно монет на корм (нужно 200 🪙)", show_alert=True)

        await db.add_balance(uid, -200)
        new_hunger = min(100, pet["hunger"] + 50)
        new_xp = pet["xp"] + 20
        new_lvl = pet["level"]
        next_req = new_lvl * 100
        if new_xp >= next_req:
            new_lvl += 1
            new_xp -= next_req

        await db.update_user_pet(uid, hunger=new_hunger, last_feed=now, xp=new_xp, level=new_lvl)
        await call.answer(f"🍖 Питомец сыт на {new_hunger}%! (+20 XP)")
        pet = await db.get_user_pet(uid)
        text, kb = _get_pet_card(pet, call.from_user.first_name or "Хозяин")
        return await call.message.edit_text(text, reply_markup=kb)

    if action == "start_exp":
        exp_key = parts[2]
        exp_info = EXPEDITIONS.get(exp_key)
        if not exp_info:
            return await call.answer("Экспедиция не найдена", show_alert=True)

        # Проверяем сокола (скорость x2)
        dur = exp_info["dur"]
        if pet["pet_type"] == "falcon":
            dur = int(dur / 2)

        until = now + dur
        await db.update_user_pet(uid, expedition_until=until, expedition_type=exp_key)
        await call.answer(f"🧭 {pet['pet_name']} отправился в поход: {exp_info['name']}!")
        pet = await db.get_user_pet(uid)
        text, kb = _get_pet_card(pet, call.from_user.first_name or "Хозяин")
        return await call.message.edit_text(text, reply_markup=kb)

    if action == "claim_exp":
        exp_until = pet.get("expedition_until", 0)
        if exp_until > now:
            return await call.answer(f"Питомец ещё не вернулся! Ждите {hms(exp_until - now)}.", show_alert=True)

        exp_key = pet.get("expedition_type", "1")
        exp_info = EXPEDITIONS.get(exp_key, EXPEDITIONS["1"])

        # Награды
        min_g, max_g = exp_info["min_gold"], exp_info["max_gold"]
        gold = random.randint(min_g, max_g)
        xp_gain = exp_info["xp"]

        # Бонусы дракона (+50%)
        if pet["pet_type"] == "dragon":
            gold = int(gold * 1.5)
            xp_gain = int(xp_gain * 1.5)

        # Бонус дрона (35% двойной лут)
        is_double = (pet["pet_type"] == "drone") and (random.random() < 0.35)
        if is_double:
            gold *= 2
            xp_gain *= 2

        # Шанс редкого ресурса
        res_text = ""
        if random.random() < 0.65:
            res_key = random.choice(RESOURCE_POOL)
            res_name = RESOURCE_NAMES[res_key]
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                (uid, res_key, res_name, now)
            )
            res_text = f"\n📦 Найдена деталь: <b>{res_name} (1 шт.)</b>"

        await db.add_balance(uid, gold)
        await db.add_xp(call.message.chat.id, uid, int(xp_gain / 2))

        # Опыт питомцу
        p_xp = pet["xp"] + xp_gain
        p_lvl = pet["level"]
        if p_xp >= p_lvl * 100:
            p_lvl += 1
            p_xp -= (p_lvl - 1) * 100

        await db.update_user_pet(uid, expedition_until=0, expedition_type="", xp=p_xp, level=p_lvl)

        double_tag = " ⚡️ <b>[ДВОЙНОЙ КИБЕР-ЛУТ ДРОНА!]</b>" if is_double else ""
        await call.answer(f"🎉 Добыча получена: +{gold} монет!", show_alert=True)

        res_msg = (
            f"🎉 ✨ <b>ПИТОМЕЦ ВЕРНУЛСЯ ИЗ ЭКСПЕДИЦИИ!</b> ✨ 🎉{double_tag}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🐾 <b>{html.escape(pet['pet_name'])}</b> успешно завершил вылазку «{exp_info['name']}»!\n\n"
            f"🎁 <b>Добыча питомца:</b>\n"
            f"  └─▸ 💰 <b>+{money(gold)}</b>\n"
            f"  └─▸ ⭐️ <b>+{xp_gain} XP</b> питомцу{res_text}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🍖 Не забудьте покормить героя: <code>питомец</code>"
        )
        try:
            await call.message.reply(res_msg)
        except Exception:
            pass

        pet = await db.get_user_pet(uid)
        text, kb = _get_pet_card(pet, call.from_user.first_name or "Хозяин")
        return await call.message.edit_text(text, reply_markup=kb)

    if action == "refresh":
        pet = await db.get_user_pet(uid)
        text, kb = _get_pet_card(pet, call.from_user.first_name or "Хозяин")
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer("🔄 Обновлено!")
