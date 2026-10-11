"""🛡️ Магазин предметов, Боевое снаряжение, Кейсы, Инвентарь и Щиты от наказаний."""
from __future__ import annotations

import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, money

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
    1: {"name": "📦 Бронзовый кейс", "price": 500, "min_c": 300, "max_c": 1500, "xp": 50},
    2: {"name": "🧰 Серебряный кейс", "price": 1500, "min_c": 1000, "max_c": 4500, "xp": 150},
    3: {"name": "🎁 Золотой кейс", "price": 4000, "min_c": 3000, "max_c": 12000, "xp": 400},
    4: {"name": "💎 Кейс Moxxi (Мифик)", "price": 10000, "min_c": 8000, "max_c": 35000, "xp": 1200}
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


# ══════════════════ 2. КЕЙСЫ ══════════════════

@router.message(Cmd("кейсы", "открыть кейс", "кейсы мокси", section=S, rank=0,
                    usage="кейс [1-4]", desc="🎁 Открытие кейсов с ценными призами"))
async def cmd_cases(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    a = (args or "").strip()
    uid = message.from_user.id
    user = await db.get_user(uid)

    if a and not (a.isdigit() and int(a) in CASES):
        if not had_prefix and in_group:
            return

    if a.isdigit() and int(a) in CASES:
        case_id = int(a)
        c = CASES[case_id]
        if user["balance"] < c["price"]:
            return await message.reply(
                f"❌ Недостаточно средств для открытия {c['name']}! Нужно <b>{money(c['price'])}</b>."
            )

        await db.add_balance(uid, -c["price"])

        # Розыгрыш призов
        won_coins = random.randint(c["min_c"], c["max_c"])
        won_xp = c["xp"]
        won_items: list[str] = []

        # Дроп аптечки (бронзовый/серебряный)
        if case_id == 1 and random.random() < 0.20:
            won_items.append("🧪 Аптечка первой помощи")
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                "VALUES (?, 'item_medkit', '🧪 Аптечка первой помощи', 1, ?) "
                "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                (uid, int(time.time()))
            )

        if case_id == 2:
            if random.random() < 0.22:
                won_items.append("🛡️ Щит от варна")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'shield_warn', '🛡️ Щит от варна', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.12:
                won_items.append("🗡️ Меч Драконоборца")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'weapon_sword', '🗡️ Меч Драконоборца', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )

        if case_id == 3:
            if random.random() < 0.25:
                won_items.append("🛡️ Щит от варна")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'shield_warn', '🛡️ Щит от варна', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.15:
                won_items.append("🦺 Титановый Бронежилет")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'armor_titan', '🦺 Титановый Бронежилет', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.15:
                won_items.append("💊 Набор медика")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'item_doc_kit', '💊 Набор медика', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.10:
                won_items.append("💎 Кристальный значок")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'badge_diamond', '💎 Кристальный значок', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )

        if case_id == 4:
            if random.random() < 0.18:
                won_items.append("🔫 Плазменный Бластер (СУПЕР ДРОП!)")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'weapon_blaster', '🔫 Плазменный Бластер', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.20:
                won_items.append("🦺 Титановый Бронежилет")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'armor_titan', '🦺 Титановый Бронежилет', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )
            if random.random() < 0.15:
                won_items.append("🌌 Космический значок (МИФИК!)")
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, 'badge_void', '🌌 Космический значок', 1, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, int(time.time()))
                )

        await db.add_balance(uid, won_coins)
        await db.add_xp(message.chat.id, uid, won_xp)

        drops = [f"💰 <b>+{money(won_coins)}</b>", f"⚡️ <b>+{won_xp} XP</b>"]
        for it in won_items:
            drops.append(f"✨ <b>{it}</b>")

        res = (
            f"🎉 ✨ <b>ОТКРЫТИЕ {c['name'].upper()}!</b> ✨ 🎉\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
            f"👤 Открыл: {mention(message.from_user)}\n\n"
            f"🎁 <b>ВАШ ВЫИГРЫШ:</b>\n" +
            "\n".join(f"  └─▸ {d}" for d in drops) +
            "\n\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"<i>Открыть еще:</i> <code>кейс {case_id}</code>"
        )
        return await message.reply(res)

    text = [
        "🎁 ✨ <b>КЕЙСЫ И БОКСЫ MOXXI</b> ✨ 🎁",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Ваш баланс: <b>{money(user['balance'])}</b>\n"
    ]

    for cid, c in CASES.items():
        text.append(
            f"<b>{cid}. {c['name']}</b> — <b>{money(c['price'])}</b>\n"
            f"   └─▸ Призы: <code>{c['min_c']}–{c['max_c']} монет</code>, <code>+{c['xp']} XP</code>, шанс на оружие, броню и значки!\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Открыть кейс:</i> <code>кейс 1</code>, <code>кейс 2</code>, <code>кейс 3</code>, <code>кейс 4</code>")
    await message.reply("\n".join(text))


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
