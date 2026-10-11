"""🎣 Рыбалка и Крафт редких предметов и снаряжения."""
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

router = Router(name="fishing_craft")
S = 37  # Раздел: Рыбалка и крафт

FISH_TYPES = [
    {"type": "boot", "name": "👢 Дырявый сапог", "min_p": 1, "max_p": 5, "weight": 5, "desc": "Кто-то утопил его много лет назад..."},
    {"type": "carp", "name": "🐟 Речной Карась", "min_p": 120, "max_p": 250, "weight": 35, "desc": "Свежая вкусная речная рыба."},
    {"type": "perch", "name": "🐠 Радужный Окунь", "min_p": 280, "max_p": 550, "weight": 25, "desc": "Красивый хищник с яркими плавниками."},
    {"type": "pike", "name": "🦈 Хищная Щука", "min_p": 600, "max_p": 1200, "weight": 16, "desc": "Зубастый речной монстр!"},
    {"type": "ray", "name": "🐡 Электрический Скат", "min_p": 1500, "max_p": 3000, "weight": 9, "desc": "Опасный скат, бьющий током!"},
    {"type": "gold", "name": "👑 Золотая Рыбка", "min_p": 5000, "max_p": 10000, "weight": 4, "desc": "Легендарная рыбка, исполняющая желания!"},
    {"type": "kraken", "name": "🐙 Древний Кракен", "min_p": 15000, "max_p": 30000, "weight": 2, "desc": "Мифическое морское чудовище с сокровищами!"},
    {"type": "chest", "name": "📦 Затонувший Сундук", "min_p": 0, "max_p": 0, "weight": 4, "desc": "Пиратский кованый сундук с артефактами!"}
]

CRAFT_RECIPES = {
    "rod_pro": {
        "id": "item_rod_pro",
        "name": "🎣 Профессиональный Спиннинг",
        "desc": "Ускоряет перезарядку рыбалки в 2 раза (КД 8 минут вместо 15)!",
        "reqs": {"craft_wood": 3, "craft_gear": 2}
    },
    "shield": {
        "id": "shield_warn",
        "name": "🛡️ Щит от варна",
        "desc": "Поглощает 1 полученное предупреждение (варн).",
        "reqs": {"craft_shard": 2, "craft_essence": 1}
    },
    "case_gold": {
        "id": "case_gold",
        "name": "🎁 Золотой кейс",
        "desc": "Кейс с ценными монетами и снаряжением.",
        "reqs": {"craft_shard": 3, "craft_gear": 2}
    },
    "case_moxxi": {
        "id": "case_moxxi",
        "name": "💎 Кейс Moxxi (Мифик)",
        "desc": "Элитный мифический кейс с бластерами и значками.",
        "reqs": {"craft_shard": 4, "craft_essence": 3}
    }
}

RESOURCE_NAMES = {
    "craft_wood": "🪵 Редкая древесина",
    "craft_gear": "⚙️ Шестеренка",
    "craft_shard": "💎 Осколок кристалла",
    "craft_essence": "🔮 Эссенция бездны"
}


# ══════════════════ 1. РЫБАЛКА ══════════════════

@router.message(Cmd("рыбалка", "рыбачить", "забросить удочку", "ловить рыбу", section=S, rank=0,
                    usage="рыбалка", desc="🎣 Забросить удочку и поймать рыбу"))
async def cmd_fishing(message: Message, bot: Bot, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    user = await db.get_user(uid)

    # Проверка профессионального спиннинга и VIP
    has_pro_rod = await db.fetchone(
        "SELECT count FROM user_inventory WHERE user_id=? AND item_id='item_rod_pro' AND count > 0",
        (uid,)
    )
    v_lvl, _, v_act = await db.get_vip_info(uid)

    cd_seconds = 8 * 60 if has_pro_rod else 15 * 60
    if v_act and v_lvl >= 2:
        cd_seconds = int(cd_seconds * 0.50)  # VIP+ Diamond: -50% времени рыбалки
    elif v_act and v_lvl == 1:
        cd_seconds = int(cd_seconds * 0.70)  # VIP: -30% времени рыбалки

    left = await db.cooldown_left(uid, "fishing", cd_seconds)
    if left > 0:
        if had_prefix or not in_group:
            return await message.reply(
                f"⏳ <b>Рыба ещё не клюёт!</b>\n"
                f"Следующий заброс удочки будет доступен через <b>{hms(left)}</b>."
            )
        return

    await db.set_cooldown(uid, "fishing")

    # Розыгрыш улова с весами (с учетом VIP)
    types = [f["type"] for f in FISH_TYPES]
    weights = []
    for f in FISH_TYPES:
        w = f["weight"]
        if f["type"] in {"gold", "kraken", "chest"}:
            if v_act and v_lvl >= 2:
                w = int(w * 2.5)  # VIP+: повышенный шанс на легендарную рыбу и сундуки
            elif v_act and v_lvl == 1:
                w = int(w * 1.5)  # VIP: +50% шанс на редкий улов
        weights.append(w)

    picked_type = random.choices(types, weights=weights, k=1)[0]
    fish_info = next(f for f in FISH_TYPES if f["type"] == picked_type)

    if picked_type == "chest":
        # Открытие затонувшего сундука
        base_chest_coins = random.randint(1500, 5000)
        if v_act and v_lvl >= 2:
            won_coins = int(base_chest_coins * 1.5)
        elif v_act and v_lvl == 1:
            won_coins = int(base_chest_coins * 1.2)
        else:
            won_coins = base_chest_coins

        res_key = random.choice(list(RESOURCE_NAMES.keys()))
        res_name = RESOURCE_NAMES[res_key]

        await db.add_balance(uid, won_coins)
        await db.execute(
            "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
            "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
            (uid, res_key, res_name, int(time.time()))
        )

        vip_badge = " 🌟 [VIP+]" if (v_act and v_lvl >= 2) else (" ⭐️ [VIP]" if (v_act and v_lvl == 1) else "")
        text = (
            f"📦 ✨ <b>ВЫ ВЫЛОВИЛИ ЗАТОНУВШИЙ СУНДУК!</b> ✨ 📦{vip_badge}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 Рыбак: {mention(message.from_user)}\n\n"
            f"🎁 <b>Содержимое сундука:</b>\n"
            f"  └─▸ 💰 <b>+{money(won_coins)}</b>\n"
            f"  └─▸ ✨ Ресурс: <b>{res_name} (1 шт.)</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🛠 <i>Создание предметов:</i> <code>крафт</code>"
        )
        return await message.reply(text)

    price = random.randint(fish_info["min_p"], fish_info["max_p"])
    if v_act and v_lvl >= 2:
        price = int(price * 1.4)  # +40% к стоимости рыбы для VIP+
    elif v_act and v_lvl == 1:
        price = int(price * 1.2)  # +20% к стоимости для VIP

    # Сохраняем рыбу в садок
    await db.execute(
        "INSERT INTO user_fish_catch (user_id, fish_type, fish_name, fish_price, caught_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, fish_info["type"], fish_info["name"], price, int(time.time()))
    )

    # Шанс выпадения ресурса при хорошем улове
    drop_res_text = ""
    res_chance = 0.50 if (v_act and v_lvl >= 2) else (0.40 if (v_act and v_lvl == 1) else 0.30)
    if random.random() < res_chance:
        res_key = random.choice(list(RESOURCE_NAMES.keys()))
        res_name = RESOURCE_NAMES[res_key]
        await db.execute(
            "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
            "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
            (uid, res_key, res_name, int(time.time()))
        )
        drop_res_text = f"\n✨ <i>Найдена деталь:</i> <b>{res_name} (1 шт.)</b>"

    xp_gain = 25 if picked_type not in {"gold", "kraken"} else 150
    if v_act and v_lvl >= 2:
        xp_gain = int(xp_gain * 1.5)

    await db.add_xp(message.chat.id, uid, xp_gain)

    rod_tag = " (🎣 Про-Спиннинг)" if has_pro_rod else ""
    vip_tag = " 🌟 [VIP+]" if (v_act and v_lvl >= 2) else (" ⭐️ [VIP]" if (v_act and v_lvl == 1) else "")

    text = (
        f"🎣 ✨ <b>УСПЕШНЫЙ УЛОВ!</b> ✨ 🎣{rod_tag}{vip_tag}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Рыбак: {mention(message.from_user)}\n"
        f"🐟 Вы поймали: <b>{fish_info['name']}</b>!\n"
        f"💵 Рыночная стоимость: <b>{money(price)}</b> · <b>+{xp_gain} XP</b>\n"
        f"📜 <i>{fish_info['desc']}</i>{drop_res_text}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🧺 <i>Посмотреть садок:</i> <code>садок</code>\n"
        f"💰 <i>Продать улов:</i> <code>продать рыбу</code>"
    )
    await message.reply(text)


@router.message(Cmd("садок", "моя рыба", "рыбы", section=S, rank=0,
                    usage="садок", desc="🧺 Посмотреть пойманную рыбу в садке"))
async def cmd_fish_basket(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    rows = await db.fetchall("SELECT * FROM user_fish_catch WHERE user_id=?", (uid,))

    if not rows:
        return await message.reply(
            "🧺 <b>Ваш садок пуст.</b>\n"
            "Забросьте удочку командой: <code>рыбалка</code>"
        )

    total_value = sum(r["fish_price"] for r in rows)
    text = [
        f"🧺 ✨ <b>САДОК РЫБАКА: {html.escape(message.from_user.first_name)}</b> ✨ 🧺",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Всего рыбы: <b>{len(rows)} шт.</b>",
        f"Общая стоимость: 💰 <b>{money(total_value)}</b>\n",
        "<b>Ваш улов:</b>"
    ]

    for r in rows[-10:]:
        text.append(f"• <b>{r['fish_name']}</b> — <code>{money(r['fish_price'])}</code>")

    if len(rows) > 10:
        text.append(f"<i>...и еще {len(rows) - 10} шт.</i>")

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💰 <i>Продать всю рыбу:</i> <code>продать рыбу</code>")
    await message.reply("\n".join(text))


@router.message(Cmd("продать рыбу", "продать улов", "сдать рыбу", section=S, rank=0,
                    usage="продать рыбу", desc="💰 Продать всю рыбу из садка за монеты"))
async def cmd_sell_fish(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    rows = await db.fetchall("SELECT * FROM user_fish_catch WHERE user_id=?", (uid,))

    if not rows:
        return await message.reply("🧺 В вашем садке нет рыбы для продажи! Наловите рыбу: <code>рыбалка</code>")

    total_coins = sum(r["fish_price"] for r in rows)
    count = len(rows)

    await db.execute("DELETE FROM user_fish_catch WHERE user_id=?", (uid,))
    await db.add_balance(uid, total_coins)
    await db.add_xp(message.chat.id, uid, int(total_coins / 50))

    await message.reply(
        f"💰 ✨ <b>УЛОВ УСПЕШНО ПРОДАН!</b> ✨ 💰\n\n"
        f"👤 Продавец: {mention(message.from_user)}\n"
        f"🐟 Продано рыбы: <b>{count} шт.</b>\n"
        f"💵 Получено монет: <b>+{money(total_coins)}</b>!"
    )


# ══════════════════ 2. КРАФТ ══════════════════

@router.message(Cmd("крафт", "рецепты", "скрафтить", section=S, rank=0,
                    usage="крафт [номер/название]", desc="🛠 Создание редких предметов из ресурсов"))
async def cmd_craft(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    a = (args or "").strip().lower()

    # Получаем ресурсы игрока
    inv_rows = await db.fetchall(
        "SELECT item_id, count FROM user_inventory WHERE user_id=? AND count > 0", (uid,)
    )
    user_inv = {r["item_id"]: r["count"] for r in inv_rows}

    if a:
        target_recipe = None
        if a in CRAFT_RECIPES:
            target_recipe = CRAFT_RECIPES[a]
        elif a.isdigit():
            idx = int(a)
            keys = list(CRAFT_RECIPES.keys())
            if 1 <= idx <= len(keys):
                target_recipe = CRAFT_RECIPES[keys[idx - 1]]
        elif "спиннинг" in a or "удочк" in a:
            target_recipe = CRAFT_RECIPES["rod_pro"]
        elif "щит" in a:
            target_recipe = CRAFT_RECIPES["shield"]
        elif "золот" in a:
            target_recipe = CRAFT_RECIPES["case_gold"]
        elif "мифик" in a or "мокси" in a or "moxxi" in a:
            target_recipe = CRAFT_RECIPES["case_moxxi"]

        if target_recipe:
            # Проверяем хватает ли ресурсов
            missing = []
            for res_id, req_count in target_recipe["reqs"].items():
                have = user_inv.get(res_id, 0)
                if have < req_count:
                    rname = RESOURCE_NAMES.get(res_id, res_id)
                    missing.append(f"{rname} (нужно {req_count}, у вас {have})")

            if missing:
                return await message.reply(
                    f"❌ <b>Недостаточно ресурсов для крафта {target_recipe['name']}!</b>\n\n"
                    f"Не хватает:\n" + "\n".join(f"• {m}" for m in missing)
                )

            # Списываем ресурсы
            for res_id, req_count in target_recipe["reqs"].items():
                new_cnt = user_inv[res_id] - req_count
                if new_cnt > 0:
                    await db.execute("UPDATE user_inventory SET count=? WHERE user_id=? AND item_id=?", (new_cnt, uid, res_id))
                else:
                    await db.execute("DELETE FROM user_inventory WHERE user_id=? AND item_id=?", (uid, res_id))

            # Выдаем предмет
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                (uid, target_recipe["id"], target_recipe["name"], int(time.time()))
            )
            await db.add_xp(message.chat.id, uid, 100)

            return await message.reply(
                f"🎉 🛠 <b>КРАФТ УСПЕШНО ЗАВЕРШЕН!</b> 🛠 🎉\n\n"
                f"Вы создали: <b>{target_recipe['name']}</b>!\n"
                f"Эффект: <i>{target_recipe['desc']}</i>\n"
                f"🎒 Проверить инвентарь: <code>инвентарь</code>"
            )

    text = [
        "🛠 ✨ <b>ВЕРСТАК КРАФТА MOXXI</b> ✨ 🛠",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        "<b>Ваши ресурсы для крафта:</b>"
    ]

    has_any_res = False
    for r_key, r_name in RESOURCE_NAMES.items():
        cnt = user_inv.get(r_key, 0)
        if cnt > 0:
            has_any_res = True
            text.append(f"• {r_name}: <b>{cnt} шт.</b>")
    if not has_any_res:
        text.append("<i>У вас пока нет ресурсов (добываются на рыбалке и в сундуках).</i>")

    text.append("\n<b>Доступные рецепты:</b>\n")
    for i, (k, r) in enumerate(CRAFT_RECIPES.items(), 1):
        req_list = ", ".join(f"{RESOURCE_NAMES[rk]}: {rc} шт." for rk, rc in r["reqs"].items())
        text.append(
            f"<b>{i}. {r['name']}</b>\n"
            f"   └─▸ Требуется: <code>{req_list}</code>\n"
            f"   └─▸ <i>{r['desc']}</i>\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Скрафтить:</i> <code>крафт 1</code> или <code>крафт спиннинг</code>")
    await message.reply("\n".join(text))
