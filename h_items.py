"""🛡️ Магазин предметов, Боевое снаряжение, Кейсы, Инвентарь и Щиты от наказаний."""
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
from utils import mention, money
from h_winter_event import is_winter_active

router = Router(name="items")
S = 39  # Раздел: Инвентарь, предметы и снаряжение

SHOP_ITEMS = {
    "shield_warn": {
        "id": "shield_warn",
        "name": "🛡️ Щит от варна",
        "price": 2500,
        "type": "shield",
        "desc": "Автоматически поглощает и отменяет 1 полученное предупреждение (варн)."
    },
    "weapon_sword": {
        "id": "weapon_sword",
        "name": "🗡️ Меч Драконоборца",
        "price": 6000,
        "type": "weapon",
        "desc": "Увеличивает ваш урон по рейдовым боссам на +50% (постоянный)."
    },
    "weapon_blaster": {
        "id": "weapon_blaster",
        "name": "🔫 Плазменный Бластер",
        "price": 18000,
        "type": "weapon",
        "desc": "Увеличивает ваш урон по рейдовым боссам на +120% (постоянный)."
    },
    "armor_titan": {
        "id": "armor_titan",
        "name": "🦺 Титановый Бронежилет",
        "price": 8000,
        "type": "armor",
        "desc": "Снижает шанс получить нокаут от контратаки босса на 65% (постоянный)."
    },
    "item_medkit": {
        "id": "item_medkit",
        "name": "🧪 Аптечка первой помощи",
        "price": 1500,
        "type": "medkit",
        "desc": "Мгновенно возрождает вас при нокауте от босса (одноразовая)."
    },
    "item_doc_kit": {
        "id": "item_doc_kit",
        "name": "💊 Набор медика",
        "price": 3500,
        "type": "doc_kit",
        "desc": "Позволяет лечить союзников и получать +350 монет и +60 XP за спасение."
    },
    "badge_diamond": {
        "id": "badge_diamond",
        "name": "💎 Кристальный значок",
        "price": 5000,
        "type": "badge",
        "desc": "Устанавливает статус 💎 Кристальный VIP в карточке «кто я»."
    },
    "badge_fire": {
        "id": "badge_fire",
        "name": "🔥 Пламенный значок",
        "price": 5000,
        "type": "badge",
        "desc": "Устанавливает статус 🔥 Огненный боец в карточке «кто я»."
    },
    "badge_crown": {
        "id": "badge_crown",
        "name": "👑 Королевский значок",
        "price": 10000,
        "type": "badge",
        "desc": "Устанавливает статус 👑 Королевская элита в карточке «кто я»."
    },
    "badge_void": {
        "id": "badge_void",
        "name": "🌌 Космический значок",
        "price": 15000,
        "type": "badge",
        "desc": "Устанавливает статус 🌌 Владыка Бездны в карточке «кто я»."
    }
}

CASES = {
    1: {"name": "📦 Бронзовый кейс", "price": 500, "currency": "coins", "min_c": 300, "max_c": 1500, "xp": 50, "icon": "📦"},
    2: {"name": "🧰 Серебряный кейс", "price": 1500, "currency": "coins", "min_c": 1000, "max_c": 4500, "xp": 150, "icon": "🧰"},
    3: {"name": "🎁 Золотой кейс", "price": 4000, "currency": "coins", "min_c": 3000, "max_c": 12000, "xp": 400, "icon": "🎁"},
    4: {"name": "💎 Кейс Moxxi (Мифик)", "price": 10000, "currency": "coins", "min_c": 8000, "max_c": 35000, "xp": 1200, "icon": "💎"},
    5: {"name": "❄️ Ледяной Кейс 2026-2027", "price": 30, "currency": "snowflakes", "min_c": 15000, "max_c": 80000, "xp": 2500, "icon": "❄️", "winter_only": True}
}


# ══════════════════ 1. МАГАЗИН ══════════════════

@router.message(Cmd("магазин предметов", "шоп", "магазин", "shop", section=S, rank=0,
                    usage="магазин [номер/название]", desc="🛍️ Магазин предметов, снаряжения и щитов"))
async def cmd_shop(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    a = (args or "").strip().lower()
    uid = message.from_user.id

    if a:
        # Покупка по ключу или номеру
        item = None
        if a in SHOP_ITEMS:
            item = SHOP_ITEMS[a]
        elif a.isdigit():
            idx = int(a)
            keys = list(SHOP_ITEMS.keys())
            if 1 <= idx <= len(keys):
                item = SHOP_ITEMS[keys[idx - 1]]
        elif "щит" in a or "варн" in a:
            item = SHOP_ITEMS["shield_warn"]
        elif "бластер" in a or "плазм" in a:
            item = SHOP_ITEMS["weapon_blaster"]
        elif "меч" in a or "дракон" in a:
            item = SHOP_ITEMS["weapon_sword"]
        elif "брон" in a or "титан" in a or "жилет" in a:
            item = SHOP_ITEMS["armor_titan"]
        elif "аптечк" in a or "медпак" in a or "хилка" in a:
            item = SHOP_ITEMS["item_medkit"]
        elif "медик" in a or "набор" in a or "доктор" in a:
            item = SHOP_ITEMS["item_doc_kit"]
        elif "кристалл" in a or "алмаз" in a:
            item = SHOP_ITEMS["badge_diamond"]
        elif "пламя" in a or "огонь" in a:
            item = SHOP_ITEMS["badge_fire"]
        elif "корон" in a:
            item = SHOP_ITEMS["badge_crown"]
        elif "космос" in a or "бездн" in a:
            item = SHOP_ITEMS["badge_void"]

        if item:
            user = await db.get_user(uid)
            if user["balance"] < item["price"]:
                return await message.reply(
                    f"❌ Недостаточно средств! У вас <b>{money(user['balance'])}</b>, а предмет стоит <b>{money(item['price'])}</b>."
                )

            # Проверка на постоянное снаряжение (оружие, броня, набор медика)
            if item["type"] in {"weapon", "armor", "doc_kit"}:
                already = await db.fetchone(
                    "SELECT count FROM user_inventory WHERE user_id=? AND item_id=? AND count > 0",
                    (uid, item["id"])
                )
                if already:
                    return await message.reply(f"⚠️ У вас уже есть <b>{item['name']}</b>! Это постоянное снаряжение.")

            await db.add_balance(uid, -item["price"])
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                (uid, item["id"], item["name"], int(time.time()))
            )
            return await message.reply(
                f"🎉 Вы успешно приобрели <b>{item['name']}</b> за <b>{money(item['price'])}</b>!\n"
                f"🎒 Проверить инвентарь: <code>инвентарь</code>"
            )
        elif not had_prefix and in_group:
            return

    user = await db.get_user(uid)
    text = [
        "🛍 ✨ <b>МАГАЗИН ПРЕДМЕТОВ И СНАРЯЖЕНИЯ MOXXI</b> ✨ 🛍",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Ваш баланс: <b>{money(user['balance'])}</b>\n",
        "<b>Доступные товары:</b>\n"
    ]

    for i, (k, item) in enumerate(SHOP_ITEMS.items(), 1):
        text.append(
            f"<b>{i}. {item['name']}</b> — <b>{money(item['price'])}</b>\n"
            f"   └─▸ <i>{item['desc']}</i>\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Купить:</i> <code>магазин 1</code> или <code>магазин меч</code>")
    text.append("🎁 <i>Кейсы с призами:</i> <code>кейсы</code>")

    await message.reply("\n".join(text))


# ══════════════════ 2. КЕЙСЫ И АНИМИРОВАННАЯ РУЛЕТКА ══════════════════

async def open_case_animated(bot: Bot, chat_id: int, user_obj, case_id: int, edit_msg=None, reply_to_msg=None) -> None:
    uid = user_obj.id
    user = await db.get_user(uid)
    c = CASES.get(case_id)
    if not c:
        return

    # Проверка зимнего кейса
    if c.get("winter_only") and not is_winter_active():
        err_txt = "❄️ Ледяной Кейс 2026-2027 откроется 1 декабря вместе со стартом новогоднего сезона!"
        if edit_msg:
            return await edit_msg.edit_text(err_txt)
        elif reply_to_msg:
            return await reply_to_msg.reply(err_txt)
        return

    # Проверка наличия кейса в инвентаре
    user_cases = await db.get_user_cases(uid)
    has_stored = user_cases.get(case_id, 0) > 0

    if has_stored:
        await db.add_user_case(uid, case_id, -1)
    else:
        if c["currency"] == "snowflakes":
            flakes = user.get("snowflakes", 0) or 0
            if flakes < c["price"]:
                err_txt = f"❌ Недостаточно ❄️ Снежинок! Нужно <b>{c['price']} ❄️</b> (у вас: {flakes} ❄️)."
                if edit_msg:
                    return await edit_msg.edit_text(err_txt)
                elif reply_to_msg:
                    return await reply_to_msg.reply(err_txt)
                return
            await db.add_user_snowflakes(uid, -c["price"])
        else:
            if user["balance"] < c["price"]:
                err_txt = f"❌ Недостаточно средств для открытия {c['name']}! Нужно <b>{money(c['price'])}</b>."
                if edit_msg:
                    return await edit_msg.edit_text(err_txt)
                elif reply_to_msg:
                    return await reply_to_msg.reply(err_txt)
                return
            await db.add_balance(uid, -c["price"])

    # Розыгрыш призов
    won_coins = random.randint(c["min_c"], c["max_c"])
    won_xp = c["xp"]
    won_items = []
    main_drop_icon = "💰"
    now_ts = int(time.time())

    if case_id == 1 and random.random() < 0.20:
        won_items.append("🧪 Аптечка первой помощи")
        main_drop_icon = "🧪"
        await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'item_medkit', '🧪 Аптечка первой помощи', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
    elif case_id == 2:
        if random.random() < 0.22:
            won_items.append("🛡️ Щит от варна")
            main_drop_icon = "🛡️"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'shield_warn', '🛡️ Щит от варна', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.12:
            won_items.append("🗡️ Меч Драконоборца")
            main_drop_icon = "🗡️"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'weapon_sword', '🗡️ Меч Драконоборца', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
    elif case_id == 3:
        if random.random() < 0.25:
            won_items.append("🛡️ Щит от варна")
            main_drop_icon = "🛡️"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'shield_warn', '🛡️ Щит от варна', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.15:
            won_items.append("🦺 Титановый Бронежилет")
            main_drop_icon = "🦺"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'armor_titan', '🦺 Титановый Бронежилет', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.15:
            won_items.append("💊 Набор медика")
            main_drop_icon = "💊"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'item_doc_kit', '💊 Набор медика', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.10:
            won_items.append("💎 Кристальный значок")
            main_drop_icon = "💎"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'badge_diamond', '💎 Кристальный значок', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
    elif case_id == 4:
        if random.random() < 0.18:
            won_items.append("🔫 Плазменный Бластер (СУПЕР ДРОП!)")
            main_drop_icon = "🔫"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'weapon_blaster', '🔫 Плазменный Бластер', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.20:
            won_items.append("🦺 Титановый Бронежилет")
            main_drop_icon = "🦺"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'armor_titan', '🦺 Титановый Бронежилет', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.15:
            won_items.append("🌌 Космический значок (МИФИК!)")
            main_drop_icon = "🌌"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'badge_void', '🌌 Космический значок', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
    elif case_id == 5:
        if random.random() < 0.25:
            won_items.append("❄️ Ледяной Клинок Вьюги (Эксклюзив!)")
            main_drop_icon = "❄️"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'weapon_ice_blade', '❄️ Ледяной Клинок Вьюги', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.20:
            won_items.append("🛷 Ледяные Сани Санты (Транспорт!)")
            main_drop_icon = "🛷"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'car_ice_sleigh', '🛷 Ледяные Сани Санты', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))
        if random.random() < 0.30:
            won_items.append("🎄 Новогодний значок Деда Мороза")
            main_drop_icon = "🎄"
            await db.execute("INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) VALUES (?, 'badge_santa', '🎄 Новогодний значок Деда Мороза', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1", (uid, now_ts))

    await db.add_balance(uid, won_coins)
    await db.add_xp(chat_id, uid, won_xp)

    # 🎬 КАДР 1: Запуск рулетки
    frame1 = (
        f"🎰 <b>ОТКРЫВАЕМ: {c['name']}...</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"░░░░░ [ 📦 | 💰 | 🧪 | 💎 | 🔫 ] ░░░░░\n\n"
        f"<i>Запуск барабана рулетки...</i>"
    )
    if edit_msg:
        active_msg = edit_msg
        await active_msg.edit_text(frame1)
    elif reply_to_msg:
        active_msg = await reply_to_msg.reply(frame1)
    else:
        active_msg = await bot.send_message(chat_id, frame1)

    await asyncio.sleep(0.7)

    # 🎬 КАДР 2: Быстрое вращение
    frame2 = (
        f"🎰 <b>ВРАЩЕНИЕ БАРАБАНА: {c['name']}...</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"⚡️ 🌀 [ 💰 | 🦺 | ⚡️ | 🧪 | 🗡️ ] 🌀 ⚡️\n\n"
        f"<i>Барабан крутится на полной скорости... 💨</i>"
    )
    try:
        await active_msg.edit_text(frame2)
    except Exception:
        pass

    await asyncio.sleep(0.7)

    # 🎬 КАДР 3: Замедление стрелки
    slot_pool = ["💰", "🦺", "🧪", "💎", "🔫", "🗡️", "⚡️", "🎁", "❄️"]
    p_left = random.choice([x for x in slot_pool if x != main_drop_icon])
    p_right = random.choice([x for x in slot_pool if x != main_drop_icon and x != p_left])
    frame3 = (
        f"🎰 <b>ЗАМЕДЛЕНИЕ СТРЕЛКИ...</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"▶️ 🎯 [ {p_left} | ✨ <b>{main_drop_icon}</b> ✨ | {p_right} ] 🎯 ◀️\n\n"
        f"<i>Стрелка останавливается... ⏳</i>"
    )
    try:
        await active_msg.edit_text(frame3)
    except Exception:
        pass

    await asyncio.sleep(0.8)

    # 🎬 КАДР 4: Финальный показ
    drops = [f"💰 <b>+{money(won_coins)}</b>", f"⚡️ <b>+{won_xp} XP</b>"]
    for it in won_items:
        drops.append(f"✨ <b>{it}</b>")

    final_card = (
        f"🎉 💥 <b>УСПЕШНО ОТКРЫТ {c['name'].upper()}!</b> 💥 🎉\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"👤 <b>Игрок:</b> {mention(user_obj)}\n\n"
        f"🎁 <b>ВАШ ВЫИГРЫШ:</b>\n" +
        "\n".join(f"  └─▸ {d}" for d in drops) +
        f"\n\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"<i>Открыть еще раз:</i> <code>кейс {case_id}</code>"
    )
    kb_res = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Открыть ещё", callback_data=f"open_case:{case_id}"),
            InlineKeyboardButton(text="🎁 Все кейсы", callback_data="cases_list")
        ]
    ])
    try:
        await active_msg.edit_text(final_card, reply_markup=kb_res)
    except Exception:
        pass


async def render_cases_menu(user_obj) -> tuple[str, InlineKeyboardMarkup]:
    uid = user_obj.id
    user = await db.get_user(uid)
    stored_cases = await db.get_user_cases(uid)
    flakes = user.get("snowflakes", 0) or 0
    winter_on = is_winter_active()

    stored_lines = []
    for cid, cnt in stored_cases.items():
        if cnt > 0 and cid in CASES:
            stored_lines.append(f"  └─▸ {CASES[cid]['name']}: <b>{cnt} шт.</b>")

    stored_block = ""
    if stored_lines:
        stored_block = "🎒 <b>Ваши кейсы в инвентаре:</b>\n" + "\n".join(stored_lines) + "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

    winter_line = f" · ❄️ <b>{flakes:,} Снежинок</b>" if winter_on else ""

    text = [
        "🎁 ✨ <b>КЕЙСЫ И БОКСЫ MOXXI</b> ✨ 🎁",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"💰 Баланс: <b>{money(user['balance'])}</b>{winter_line}\n",
        stored_block,
        "<b>ДОСТУПНЫЕ КЕЙСЫ:</b>"
    ]

    buttons = []
    for cid, c in CASES.items():
        if c.get("winter_only") and not winter_on:
            continue
        curr_str = f"{c['price']} ❄️" if c["currency"] == "snowflakes" else money(c['price'])
        text.append(
            f"<b>{cid}. {c['name']}</b> — <b>{curr_str}</b>\n"
            f"   └─▸ Призы: <code>{c['min_c']}–{c['max_c']} монет</code>, <code>+{c['xp']} XP</code>, оружие, броня и значки!\n"
        )
        buttons.append([InlineKeyboardButton(text=f"{c['name']} ({curr_str})", callback_data=f"open_case:{cid}")])

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Открыть кейс:</i> <code>кейс 1</code>, <code>кейс 2</code>, <code>кейс 3</code>, <code>кейс 4</code>, <code>кейс 5</code>")
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return "\n".join(text), kb


@router.message(Cmd("кейсы", "открыть кейс", "кейсы мокси", "кейси", "кейс", section=S, rank=0,
                    usage="кейс [1-5]", desc="🎁 Открытие кейсов с живой анимацией рулетки"))
async def cmd_cases(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    a = (args or "").strip().lower()

    if a in ("нг", "зима", "зимний", "лед", "ледяной"):
        a = "5"

    if a and not (a.isdigit() and int(a) in CASES):
        if not had_prefix and in_group:
            return

    if a.isdigit() and int(a) in CASES:
        case_id = int(a)
        await open_case_animated(bot, message.chat.id, message.from_user, case_id, reply_to_msg=message)
        return

    text, kb = await render_cases_menu(message.from_user)
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("open_case:"))
async def cb_open_case(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[1])
    await open_case_animated(bot, call.message.chat.id, call.from_user, cid, edit_msg=call.message)
    await call.answer()


@router.callback_query(F.data == "cases_list")
async def cb_cases_list(call: CallbackQuery, bot: Bot):
    text, kb = await render_cases_menu(call.from_user)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


# ══════════════════ 3. ИНВЕНТАРЬ ══════════════════

@router.message(Cmd("инвентарь", "мои вещи", "рюкзак", "предметы", section=S, rank=0,
                    usage="инвентарь", desc="🎒 Просмотр ваших предметов, оружия и щитов"))
async def cmd_inventory(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    items = await db.fetchall("SELECT * FROM user_inventory WHERE user_id=? AND count > 0", (uid,))
    user = await db.get_user(uid)

    text = [
        f"🎒 ✨ <b>ИНВЕНТАРЬ: {html.escape(message.from_user.first_name)}</b> ✨ 🎒",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"💰 Баланс: <b>{money(user['balance'])}</b> · <b>{user['xp']} XP</b>\n"
    ]

    if not items:
        text.append("<i>Ваш инвентарь пока пуст.</i>\n")
        text.append("🛍 Купить снаряжение и щиты: <code>магазин</code>")
        text.append("🎁 Испытать удачу в кейсах: <code>кейсы</code>")
    else:
        text.append("<b>Ваши предметы и снаряжение:</b>")
        for it in items:
            text.append(f"• <b>{it['item_name']}</b> — <b>{it['count']} шт.</b>")
        text.append("\n💡 <i>Боевое снаряжение (оружие/броня) работает автоматически в рейдах боссов.</i>")
        text.append("🧪 <i>Использовать аптечку:</i> <code>аптечка</code>")

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    await message.reply("\n".join(text))


# ══════════════════ 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ══════════════════

async def check_and_consume_warn_shield(user_id: int) -> bool:
    """Если у пользователя есть щит от варна, поглощает 1 щит и возвращает True."""
    row = await db.fetchone(
        "SELECT count FROM user_inventory WHERE user_id=? AND item_id='shield_warn' AND count > 0",
        (user_id,)
    )
    if row and row["count"] > 0:
        new_count = row["count"] - 1
        if new_count > 0:
            await db.execute("UPDATE user_inventory SET count=? WHERE user_id=? AND item_id='shield_warn'", (new_count, user_id))
        else:
            await db.execute("DELETE FROM user_inventory WHERE user_id=? AND item_id='shield_warn'", (user_id,))
        return True
    return False


async def get_user_combat_gear(user_id: int) -> dict:
    """Возвращает множитель урона от оружия, наличие брони, аптечек и набора медика."""
    rows = await db.fetchall(
        "SELECT item_id, count FROM user_inventory WHERE user_id=? AND count > 0",
        (user_id,)
    )
    items = {r["item_id"]: r["count"] for r in rows}

    dmg_mult = 1.0
    weapon_name = ""
    if items.get("weapon_blaster", 0) > 0:
        dmg_mult = 2.2  # +120%
        weapon_name = "🔫 Плазменный Бластер"
    elif items.get("weapon_sword", 0) > 0:
        dmg_mult = 1.5  # +50%
        weapon_name = "🗡️ Меч Драконоборца"

    has_armor = items.get("armor_titan", 0) > 0
    medkits = items.get("item_medkit", 0)
    has_doc_kit = items.get("item_doc_kit", 0) > 0

    return {
        "dmg_mult": dmg_mult,
        "weapon_name": weapon_name,
        "has_armor": has_armor,
        "medkits": medkits,
        "has_doc_kit": has_doc_kit
    }


async def consume_medkit(user_id: int) -> bool:
    """Использует одну аптечку из инвентаря пользователя."""
    row = await db.fetchone(
        "SELECT count FROM user_inventory WHERE user_id=? AND item_id='item_medkit' AND count > 0",
        (user_id,)
    )
    if row and row["count"] > 0:
        new_c = row["count"] - 1
        if new_c > 0:
            await db.execute("UPDATE user_inventory SET count=? WHERE user_id=? AND item_id='item_medkit'", (new_c, user_id))
        else:
            await db.execute("DELETE FROM user_inventory WHERE user_id=? AND item_id='item_medkit'", (user_id,))
        return True
    return False


# ═══════════════ АВТОСАЛОН, ГАРАЖ И УЛИЧНЫЕ ГОНКИ ═══════════════
CARS = {
    "vaz2107": {
        "id": "vaz2107",
        "name": "🚙 ВАЗ 2107 «Боевая классика»",
        "price": 25_000,
        "hp": 75,
        "speed": 150,
        "win_rate": 0.45,
        "desc": "Легендарный заднеприводный жигуль для дрифта вокруг столбов."
    },
    "camry": {
        "id": "camry",
        "name": "🚗 Toyota Camry 3.5 «Держать руль»",
        "price": 120_000,
        "hp": 249,
        "speed": 220,
        "win_rate": 0.52,
        "desc": "Уважаемый японский седан для уверенных обгонов по шашкам."
    },
    "m5": {
        "id": "m5",
        "name": "🏎 BMW M5 CS «Гроза автобанов»",
        "price": 650_000,
        "hp": 635,
        "speed": 305,
        "win_rate": 0.60,
        "desc": "Битурбо V8 зверь с лаунч-контролем и выхлопом с отстрелами."
    },
    "porsche": {
        "id": "porsche",
        "name": "🏁 Porsche 911 Turbo S",
        "price": 2_500_000,
        "hp": 650,
        "speed": 330,
        "win_rate": 0.68,
        "desc": "Немецкая инженерная магия: 2.7 секунды до первой сотни."
    },
    "ferrari": {
        "id": "ferrari",
        "name": "🔥 Ferrari SF90 Stradale",
        "price": 9_000_000,
        "hp": 1000,
        "speed": 340,
        "win_rate": 0.75,
        "desc": "Итальянский гибридный монстр мощностью 1000 лошадиных сил."
    },
    "chiron": {
        "id": "chiron",
        "name": "⚡ Bugatti Chiron Super Sport",
        "price": 35_000_000,
        "hp": 1600,
        "speed": 440,
        "win_rate": 0.83,
        "desc": "W16 квадро-турбо. Разрывает законы физики на максимальной скорости."
    },
    "rolls": {
        "id": "rolls",
        "name": "👑 Золотой Rolls-Royce Mansory",
        "price": 120_000_000,
        "hp": 600,
        "speed": 250,
        "win_rate": 0.72,
        "desc": "Сверхроскошный дворец на колёсах с золотым напылением и звёздным небом."
    },
    "cybercar": {
        "id": "cybercar",
        "name": "🚀 Гиперкар Moxxi Void-Speeder",
        "price": 500_000_000,
        "hp": 5000,
        "speed": 1000,
        "win_rate": 0.92,
        "desc": "Космический антигравитационный болид с плазменным ускорителем."
    },
}


def _car_showroom_kb() -> InlineKeyboardMarkup:
    rows = []
    for k, car in CARS.items():
        rows.append([InlineKeyboardButton(text=f"{car['name']} ({car['price']:,} 🪙)", callback_data=f"car_buy:{k}")])
    rows.append([InlineKeyboardButton(text="🚪 В гараж", callback_data="car_to_garage")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("автосалон", "машины", "салон авто", "купить авто", "купить машину",
                    section=S, usage="автосалон", desc="Автосалон суперкаров и автомобилей"))
async def cmd_car_showroom(message: Message, bot: Bot, args: str = "", **kw):
    lines = [
        "🏎 ✨ <b>ЭЛИТНЫЙ АВТОСАЛОН МОКСИ</b> ✨ 🏁\n",
        "Покупайте автомобили, собирайте гараж мечты и побеждайте в уличных гонках!\n",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>Каталог автомобилей в наличии:</b>\n"
    ]
    for k, car in CARS.items():
        lines.append(
            f"{car['name']}\n"
            f"   💰 Цена: <b>{car['price']:,} 🪙</b> · 🐎 Мощность: <b>{car['hp']} л.с.</b>\n"
            f"   ⚡️ Скорость: <b>до {car['speed']} км/ч</b> · Шанс в гонках: <b>{int(car['win_rate']*100)}%</b>\n"
            f"   <i>{car['desc']}</i>\n"
        )
    lines.append("💡 <i>Купить машину можно кнопкой ниже или командой: <code>купить авто [название]</code></i>\n"
                 "🚪 <i>Ваш личный транспорт: <code>гараж</code></i>")

    await message.reply("\n".join(lines), reply_markup=_car_showroom_kb())


@router.callback_query(F.data.startswith("car_buy:"))
async def cb_car_buy(call: CallbackQuery):
    car_key = call.data.split(":")[1]
    car = CARS.get(car_key)
    if not car:
        return await call.answer("Автомобиль не найден.", show_alert=True)

    uid = call.from_user.id
    bal = await db.get_balance(uid)
    if bal < car["price"]:
        return await call.answer(f"Недостаточно монет! Нужно {car['price']:,} 🪙, у вас {bal:,} 🪙.", show_alert=True)

    user_cars = await db.get_user_cars(uid)
    if any(c["car_key"] == car_key for c in user_cars):
        return await call.answer("Этот автомобиль уже есть в вашем гараже!", show_alert=True)

    await db.add_balance(uid, -car["price"], "buy_car", car_key)
    await db.add_user_car(uid, car_key)

    res = (
        f"🎉 🍾 <b>ПОЗДРАВЛЯЕМ С ПРИОБРЕТЕНИЕМ АВТОМОБИЛЯ!</b> 🍾 🎉\n"
        f"✦ ══ • ⊰ 🏎 🔑 ✨ ⊱ • ══ ✦\n\n"
        f"👤 Владелец: {mention(call.from_user)}\n"
        f"🚘 Приобретено: <b>{car['name']}</b>\n"
        f"🐎 Мощность: <b>{car['hp']} л.с.</b> · Скорость: <b>{car['speed']} км/ч</b>\n"
        f"💰 Списано: <b>{car['price']:,} 🪙</b>\n\n"
        f"🔑 Автомобиль доставлен в ваш <code>гараж</code> и установлен как активный!\n"
        f"🏁 Проверьте его в деле на уличных гонках: <code>гонка 1000</code>!"
    )
    try:
        await call.message.edit_text(res)
    except Exception:
        await call.message.reply(res)
    await call.answer(f"Поздравляем с покупкой {car['name']}!")


@router.message(Cmd("гараж", "мои авто", "мои машины", "автопарк", section=S,
                    usage="гараж", desc="Личный гараж и автопарк"))
async def cmd_garage(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    user_cars = await db.get_user_cars(uid)

    if not user_cars:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏎 Посетить Автосалон", callback_data="car_to_showroom")
        ]])
        return await message.reply(
            "🚪 <b>ВАШ ГАРАЖ ПУСТ!</b> 🕸\n\n"
            "У вас пока нет купленных автомобилей.\n"
            "Загляните в <code>автосалон</code> и приобретите свой первый транспорт!",
            reply_markup=kb
        )

    lines = [
        "🚪 🏎 <b>ВАШ ЛИЧНЫЙ ГАРАЖ</b> 🏁 🚪\n",
        f"👤 Владелец: {mention(message.from_user)}\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    rows = []
    for c_entry in user_cars:
        car = CARS.get(c_entry["car_key"])
        if not car:
            continue
        status = "⭐️ <b>[АКТИВНОЕ АВТО]</b>" if c_entry["is_active"] else "💤 В гараже"
        lines.append(
            f"{car['name']} — {status}\n"
            f"   🐎 {car['hp']} л.с. · ⚡️ до {car['speed']} км/ч · Шанс победы: {int(car['win_rate']*100)}%\n"
        )
        if not c_entry["is_active"]:
            rows.append([InlineKeyboardButton(text=f"🔑 Выбрать {car['name']}", callback_data=f"car_equip:{c_entry['id']}")])

    rows.append([InlineKeyboardButton(text="🏎 Посетить Автосалон", callback_data="car_to_showroom")])
    lines.append("💡 <i>Активный автомобиль используется в заездах: <code>гонка 1000</code>!</i>")

    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "car_to_showroom")
async def cb_car_to_showroom(call: CallbackQuery):
    await call.answer()
    lines = [
        "🏎 ✨ <b>ЭЛИТНЫЙ АВТОСАЛОН МОКСИ</b> ✨ 🏁\n",
        "Покупайте автомобили, собирайте гараж мечты и побеждайте в уличных гонках!\n",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>Каталог автомобилей:</b>\n"
    ]
    for k, car in CARS.items():
        lines.append(f"{car['name']} — <b>{car['price']:,} 🪙</b> (🐎 {car['hp']} л.с.)\n")
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=_car_showroom_kb())
    except Exception:
        pass


@router.callback_query(F.data == "car_to_garage")
async def cb_car_to_garage(call: CallbackQuery):
    await call.answer()
    uid = call.from_user.id
    user_cars = await db.get_user_cars(uid)
    if not user_cars:
        return await call.answer("Ваш гараж пуст!", show_alert=True)

    lines = ["🚪 🏎 <b>ВАШ ЛИЧНЫЙ ГАРАЖ</b> 🏁 🚪\n"]
    rows = []
    for c_entry in user_cars:
        car = CARS.get(c_entry["car_key"])
        if not car:
            continue
        status = "⭐️ [АКТИВНО]" if c_entry["is_active"] else "💤 В гараже"
        lines.append(f"{car['name']} — {status} (🐎 {car['hp']} л.с.)\n")
        if not c_entry["is_active"]:
            rows.append([InlineKeyboardButton(text=f"🔑 Выбрать {car['name']}", callback_data=f"car_equip:{c_entry['id']}")])

    rows.append([InlineKeyboardButton(text="🏎 В автосалон", callback_data="car_to_showroom")])
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass


@router.callback_query(F.data.startswith("car_equip:"))
async def cb_car_equip(call: CallbackQuery):
    car_id = int(call.data.split(":")[1])
    uid = call.from_user.id
    ok = await db.set_active_car(uid, car_id)
    if not ok:
        return await call.answer("Машина не найдена в гараже.", show_alert=True)

    await call.answer("Автомобиль успешно выбран активным для гонок! 🏎")
    user_cars = await db.get_user_cars(uid)
    lines = ["🚪 🏎 <b>ВАШ ЛИЧНЫЙ ГАРАЖ</b> 🏁 🚪\n"]
    rows = []
    for c_entry in user_cars:
        car = CARS.get(c_entry["car_key"])
        if not car:
            continue
        status = "⭐️ <b>[АКТИВНОЕ АВТО]</b>" if c_entry["is_active"] else "💤 В гараже"
        lines.append(f"{car['name']} — {status}\n")
        if not c_entry["is_active"]:
            rows.append([InlineKeyboardButton(text=f"🔑 Выбрать {car['name']}", callback_data=f"car_equip:{c_entry['id']}")])
    rows.append([InlineKeyboardButton(text="🏎 Посетить Автосалон", callback_data="car_to_showroom")])
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass


# ═══════════════ УЛИЧНЫЙ ДРАГ-РЕЙСИНГ (ГОНКИ) ═══════════════
@router.message(Cmd("гонка", "гонки", "драг", "заезд", "drag", section=S,
                    usage="гонка [ставка]", desc="Уличный драг-рейсинг на машинах (x2)"))
async def cmd_street_race(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    active_car_data = await db.get_user_active_car(uid)
    if not active_car_data or active_car_data.get("car_key") not in CARS:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏎 Посетить Автосалон", callback_data="car_to_showroom")
        ]])
        return await message.reply(
            "🚦 <b>Вам не на чем участвовать в уличных гонках!</b> 🛑\n\n"
            "Чтобы соревноваться на трассе, у вас должен быть автомобиль в гараже.\n"
            "Загляните в <code>автосалон</code> и приобретите хотя бы 🚙 <b>ВАЗ 2107</b> или 🚗 <b>Toyota Camry</b>!",
            reply_markup=kb
        )

    my_car = CARS[active_car_data["car_key"]]

    bal = await db.get_balance(uid)
    raw_bet = (args or "").strip()
    bet = parse_amount(raw_bet, bal, 500) if raw_bet else 500

    if not bet or bet < 500:
        return await message.reply(f"Минимальная ставка в гонке: <b>500 🪙</b>.\nВаш баланс: <b>{bal:,} 🪙</b>.")
    if bet > bal:
        return await message.reply(f"Недостаточно монет! Требуется: <b>{bet:,} 🪙</b>, у вас: <b>{bal:,} 🪙</b>.")

    await db.add_balance(uid, -bet, "race_bet", my_car["id"])

    rival_key = random.choice(list(CARS.keys()))
    rival_car = CARS[rival_key]
    user_name = message.from_user.first_name or "Гонщик"

    race_msg = await message.reply(
        f"🚦 <b>УЛИЧНЫЙ ДРАГ-РЕЙСИНГ МОКСИ!</b> 🏁\n"
        f"✦ ══ • ⊰ 🏎 💨 🔥 ⊱ • ══ ✦\n\n"
        f"👤 Пилот: <b>{html.escape(user_name)}</b> на <b>{my_car['name']}</b>\n"
        f"🚘 Соперник: уличный гонщик на <b>{rival_car['name']}</b>\n"
        f"💰 Ставка: <b>{bet:,} 🪙</b>\n\n"
        f"🔴 🔴 🔴 <i>Двигатели ревут на холостых... Прогрев резины!</i>"
    )

    await asyncio.sleep(1.2)

    try:
        await race_msg.edit_text(
            f"🚦 🟡 🟡 🟡 <b>ЗЕЛЁНЫЙ СВЕТ! СТАРТ!</b> 🔥\n"
            f"✦ ══ • ⊰ 🏎 💨 🔥 ⊱ • ══ ✦\n\n"
            f"👤 {html.escape(user_name)}:   ▓▓▓▓▓▓▓▓───────── 🏁\n"
            f"🚘 Соперник:        ▓▓▓▓▓▓─────────── 🏁\n\n"
            f"💨 <i>{my_car['name']} срывается с места на пределе сцепления!</i>"
        )
    except Exception:
        pass

    await asyncio.sleep(1.2)

    hp_diff = my_car["hp"] - rival_car["hp"]
    adjusted_chance = my_car["win_rate"] + (hp_diff / 5000.0)
    adjusted_chance = max(0.20, min(0.92, adjusted_chance))

    is_win = (random.random() < adjusted_chance)

    if is_win:
        win_amt = bet * 2
        new_bal = await db.add_balance(uid, win_amt, "race_win", my_car["id"])
        await db.add_xp(message.chat.id, uid, 50)
        final_text = (
            f"🏆 🏁 <b>ФИНИШ! ПОБЕДА НА ТРАССЕ!</b> 🏁 🏆\n"
            f"✦ ══ • ⊰ 🥇 🏎 🔥 ⊱ • ══ ✦\n\n"
            f"👤 {html.escape(user_name)}:   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓🏁 <b>ПОБЕДА!</b>\n"
            f"🚘 Соперник:        ▓▓▓▓▓▓▓▓▓▓▓▓────🏁\n\n"
            f"🎉 <b>Ваш {my_car['name']} вырвал победу перед финишной чертой!</b>\n"
            f"💰 Выигрыш: <b>+{win_amt:,} 🪙</b> <i>(чистая прибыль: +{bet:,} 🪙)</i>\n"
            f"🪙 Ваш баланс: <b>{new_bal:,} 🪙</b>\n"
            f"⚡️ Опыт: <b>+50 XP</b>"
        )
    else:
        new_bal = await db.get_balance(uid)
        final_text = (
            f"💔 🏁 <b>ФИНИШ! ПОРАЖЕНИЕ НА ТРАССЕ!</b> 🏁 🥀\n"
            f"✦ ══ • ⊰ 🏁 💨 🥀 ⊱ • ══ ✦\n\n"
            f"🚘 Соперник:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓🏁 <b>ПОБЕДИТЕЛЬ!</b>\n"
            f"👤 {html.escape(user_name)}:   ▓▓▓▓▓▓▓▓▓▓▓▓────🏁\n\n"
            f"🥀 Соперник обошёл вас на полкорпуса перед финишем...\n"
            f"Потери: <b>−{bet:,} 🪙</b>\n"
            f"🪙 Ваш баланс: <b>{new_bal:,} 🪙</b>"
        )

    try:
        await race_msg.edit_text(final_text)
    except Exception:
        await message.reply(final_text)
