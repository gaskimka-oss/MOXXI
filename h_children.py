"""👶 Модуль Детей в Отношениях и Система Воспитания (как в Iris).

Включает:
1. Заведение ребёнка с явным выбором пола (мальчик / девочка) текстом или инлайн-кнопками;
2. Профиль малыша со стадиями взросления (Младенец -> Малыш -> Дошкольник -> Школьник -> Подросток -> Взрослый);
3. Динамические шкалы сытости, настроения, здоровья и уровня развития;
4. Детский магазин за валюту бота (🌑):
   • 🍼 Питание: молочная смесь, фруктовая каша, семейный обед;
   • 🧸 Игрушки: погремушка, плюшевый мишка, конструктор LEGO, игровая консоль;
   • 👕 Гардероб: мягкий бодик, стильный костюмчик, брендовая тёплая куртка;
   • 💊 Здоровье: полезные витаминки, вызов семейного врача;
   • 📚 Обучение: азбука и сказки, творческие кружки, элитная академия.
5. Интерактивные инлайн-карточки и быстрые команды ухода.
"""
from __future__ import annotations

import html
import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
from core_registry import Cmd
from utils import mention, mention_id

log = logging.getLogger("moxxibot.children")
router = Router(name="children")
S_REL = 20  # Раздел браков и отношений

GROWTH_STAGES = [
    (1, "🍼 Младенец", 0, 0),
    (2, "🧸 Малыш", 2, 50),
    (3, "🎒 Дошкольник", 5, 150),
    (4, "📚 Школьник", 10, 350),
    (5, "🎮 Подросток", 20, 800),
    (6, "🎓 Взрослый", 35, 1800),
]

CHILD_CARE_ITEMS = {
    # 🍼 ЕДА (Покормить)
    "feed_1": {
        "cat": "feed", "name": "Детская смесь / Молоко", "emoji": "🥛",
        "price": 500, "sat": 25, "hap": 10, "hp": 5, "xp": 10, "rel_xp": 5,
        "desc": "Свежее тёплое молочко для малыша"
    },
    "feed_2": {
        "cat": "feed", "name": "Фруктовая овсяная каша", "emoji": "🥣",
        "price": 1500, "sat": 50, "hap": 20, "hp": 10, "xp": 25, "rel_xp": 15,
        "desc": "Сытная вкусная каша с лесными ягодами"
    },
    "feed_3": {
        "cat": "feed", "name": "Царский семейный обед", "emoji": "🍲",
        "price": 3500, "sat": 100, "hap": 40, "hp": 20, "xp": 60, "rel_xp": 35,
        "desc": "Суп, пюре с котлеткой и десерт"
    },

    # 🧸 ИГРУШКИ (Поиграть / Порадовать)
    "toy_1": {
        "cat": "toy", "name": "Звенящая погремушка", "emoji": "🪇",
        "price": 1000, "sat": 0, "hap": 25, "hp": 0, "xp": 15, "rel_xp": 10,
        "desc": "Яркая звонкая погремушка"
    },
    "toy_2": {
        "cat": "toy", "name": "Плюшевый мишка", "emoji": "🧸",
        "price": 3000, "sat": 0, "hap": 50, "hp": 0, "xp": 40, "rel_xp": 25,
        "desc": "Мягкий и пушистый верный друг"
    },
    "toy_3": {
        "cat": "toy", "name": "Большой набор LEGO", "emoji": "🧱",
        "price": 8000, "sat": 0, "hap": 80, "hp": 0, "xp": 90, "rel_xp": 60,
        "desc": "Развивающий конструктор для постройки замка"
    },
    "toy_4": {
        "cat": "toy", "name": "Игровая приставка / Планшет", "emoji": "🎮",
        "price": 20000, "sat": 0, "hap": 100, "hp": 0, "xp": 200, "rel_xp": 150,
        "desc": "Топовый интерактивный гаджет для видеоигр"
    },

    # 👕 ОДЕЖДА (Одеть)
    "cloth_1": {
        "cat": "cloth", "name": "Уютный хлопковый бодик", "emoji": "👶",
        "price": 2500, "sat": 0, "hap": 20, "hp": 10, "xp": 25, "rel_xp": 20,
        "desc": "Мягкий и нежный наряд для дома"
    },
    "cloth_2": {
        "cat": "cloth", "name": "Стильный костюм и кроссы", "emoji": "👟",
        "price": 7500, "sat": 0, "hap": 45, "hp": 15, "xp": 70, "rel_xp": 50,
        "desc": "Модный наряд для прогулок по парку"
    },
    "cloth_3": {
        "cat": "cloth", "name": "Брендовая тёплая куртка", "emoji": "🧥",
        "price": 18000, "sat": 0, "hap": 90, "hp": 30, "xp": 160, "rel_xp": 120,
        "desc": "Шикарная непродуваемая зимняя куртка"
    },

    # 💊 ЗДОРОВЬЕ (Полечить)
    "med_1": {
        "cat": "med", "name": "Вкусные детские витамины", "emoji": "🍊",
        "price": 2000, "sat": 10, "hap": 15, "hp": 40, "xp": 20, "rel_xp": 15,
        "desc": "Крепкий иммунитет и защита от вирусов"
    },
    "med_2": {
        "cat": "med", "name": "Осмотр у семейного врача", "emoji": "🩺",
        "price": 5000, "sat": 0, "hap": 25, "hp": 100, "xp": 50, "rel_xp": 40,
        "desc": "Полное восстановление детского здоровья"
    },

    # 📚 ОБРАЗОВАНИЕ (Учить)
    "edu_1": {
        "cat": "edu", "name": "Яркая азбука и сказки", "emoji": "📖",
        "price": 3000, "sat": 0, "hap": 20, "hp": 0, "xp": 60, "rel_xp": 25,
        "desc": "Чтение добрых сказок на ночь"
    },
    "edu_2": {
        "cat": "edu", "name": "Секция творчества и музыки", "emoji": "🎨",
        "price": 10000, "sat": 0, "hap": 50, "hp": 0, "xp": 150, "rel_xp": 80,
        "desc": "Уроки рисования, гитары и вокала"
    },
    "edu_3": {
        "cat": "edu", "name": "Элитная академия развития", "emoji": "🏫",
        "price": 35000, "sat": 0, "hap": 80, "hp": 0, "xp": 450, "rel_xp": 250,
        "desc": "Лучшие репетиторы и олимпийская подготовка"
    },
}


def stat_bar(val: int, max_val: int = 100, length: int = 8) -> str:
    filled = int(round((val / max_val) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def get_child_current_stats(child: dict) -> dict:
    now = int(time.time())
    care_ts = child.get("care_last_ts") or child.get("born_at") or now
    hours_passed = max(0, (now - care_ts) // 3600)

    raw_satiety = child.get("satiety", 80)
    decay_sat = min(65, (hours_passed // 2) * 3)
    cur_satiety = max(15, raw_satiety - decay_sat)

    raw_happy = child.get("happiness", 80)
    decay_happy = min(65, (hours_passed // 3) * 3)
    cur_happy = max(15, raw_happy - decay_happy)

    raw_health = child.get("health", 100)
    decay_health = 0
    if cur_satiety < 30 or cur_happy < 30:
        decay_health = min(50, (hours_passed // 4) * 4)
    cur_health = max(20, raw_health - decay_health)

    days = max(1, int((now - child["born_at"]) // 86400))
    xp = child.get("xp", 0)
    current_stage = 1
    stage_name = "🍼 Младенец"
    for s_idx, s_title, req_days, req_xp in GROWTH_STAGES:
        if days >= req_days or xp >= req_xp:
            current_stage = s_idx
            stage_name = s_title

    return {
        "satiety": cur_satiety,
        "happiness": cur_happy,
        "health": cur_health,
        "days": days,
        "stage_num": current_stage,
        "stage_title": stage_name,
        "xp": xp
    }


def format_child_card(child: dict, parent_names: str) -> str:
    stats = get_child_current_stats(child)
    c_name = html.escape(child["name"])
    c_gender = child["gender"]

    toys = child.get("toys_count", 0)
    clothes = child.get("clothes_count", 0)
    food = child.get("food_count", 0)

    return (
        f"👶 ✨ <b>ПРОФИЛЬ РЕБЁНКА: {c_name}</b> ✨\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>Пол:</b> {c_gender}\n"
        f"🎂 <b>Возраст:</b> {stats['days']} дн. (Стадия: <b>{stats['stage_title']}</b>)\n"
        f"💖 <b>Родители:</b> {parent_names}\n"
        f"🎓 <b>Развитие / Опыт:</b> <b>{stats['xp']} XP</b>\n\n"
        f"📊 <b>Состояние малыша:</b>\n"
        f"🍼 Сытость:    <code>[{stat_bar(stats['satiety'])}]</code> <b>{stats['satiety']}%</b>\n"
        f"😊 Настроение: <code>[{stat_bar(stats['happiness'])}]</code> <b>{stats['happiness']}%</b>\n"
        f"❤️ Здоровье:   <code>[{stat_bar(stats['health'])}]</code> <b>{stats['health']}%</b>\n\n"
        f"📦 <b>Детские вещи:</b>\n"
        f"🧸 Игрушек: <b>{toys} шт.</b> | 👕 Нарядов: <b>{clothes} шт.</b> | 🥣 Кормлений: <b>{food}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Заботьтесь о малыше: покупайте игрушки, кормите и развивайте его за валюту 🌑!</i>"
    )


def child_main_keyboard(child_id: int, rel_id: int, current_idx: int = 0, total_children: int = 1) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🍼 Покормить", callback_data=f"kid_cat:feed:{child_id}:{rel_id}:{current_idx}"),
            InlineKeyboardButton(text="🧸 Купить игрушку", callback_data=f"kid_cat:toy:{child_id}:{rel_id}:{current_idx}")
        ],
        [
            InlineKeyboardButton(text="👕 Одеть", callback_data=f"kid_cat:cloth:{child_id}:{rel_id}:{current_idx}"),
            InlineKeyboardButton(text="💊 Витамины / Врач", callback_data=f"kid_cat:med:{child_id}:{rel_id}:{current_idx}")
        ],
        [
            InlineKeyboardButton(text="📚 Обучение", callback_data=f"kid_cat:edu:{child_id}:{rel_id}:{current_idx}"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"kid_view:{child_id}:{rel_id}:{current_idx}")
        ],
        [
            InlineKeyboardButton(text="👦/👧 Сменить пол малыша", callback_data=f"kid_ch_gender:{child_id}:{rel_id}:{current_idx}")
        ]
    ]
    if total_children > 1:
        prev_idx = (current_idx - 1) % total_children
        next_idx = (current_idx + 1) % total_children
        rows.append([
            InlineKeyboardButton(text="◀️ Пред. ребёнок", callback_data=f"kid_nav:{prev_idx}:{rel_id}"),
            InlineKeyboardButton(text=f"👶 #{current_idx + 1} из {total_children}", callback_data="noop"),
            InlineKeyboardButton(text="След. ребёнок ▶️", callback_data=f"kid_nav:{next_idx}:{rel_id}"),
        ])
    rows.append([
        InlineKeyboardButton(text="💖 Меню пары", callback_data=f"rel_ui:main:{rel_id}"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="rel_ui:close")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def child_cat_keyboard(category: str, child_id: int, rel_id: int, current_idx: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for k, item in CHILD_CARE_ITEMS.items():
        if item["cat"] == category:
            btn_txt = f"{item['emoji']} {item['name']} ({item['price']:,} 🌑)"
            rows.append([InlineKeyboardButton(text=btn_txt, callback_data=f"kid_buy:{k}:{child_id}:{rel_id}:{current_idx}")])
    rows.append([
        InlineKeyboardButton(text="🔙 Назад к ребёнку", callback_data=f"kid_view:{child_id}:{rel_id}:{current_idx}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_child_name_and_gender(args: str, cmd_name: str = "") -> tuple[str | None, str]:
    text = (args or "").strip()
    full = f"{cmd_name} {text}".strip().lower()

    gender = None
    if any(k in full for k in ["девочк", "дочь", "дочк", "дочурк", "девчонк", "удочерить"]):
        gender = "👧 Девочка"
    elif any(k in full for k in ["мальчик", "сын", "сынок", "сыночек", "парен", "усыновить"]):
        gender = "👦 Мальчик"

    words = text.split()
    name_words = []
    for w in words:
        wl = w.lower()
        if any(g in wl for g in ["мальчик", "девочк", "сын", "сынок", "сыночек", "дочь", "дочк", "дочурк", "девчонк", "ребенок", "ребёнок", "усыновить", "удочерить", "малыш"]):
            continue
        name_words.append(w)

    child_name = " ".join(name_words).strip()
    return gender, child_name


def _get_other_partner(rel: dict, me_id: int) -> int:
    return rel["user2_id"] if rel["user1_id"] == me_id else rel["user1_id"]


@router.message(Cmd("отн ребенок", "завести ребенка", "родить ребенка", "родить мальчика",
                    "родить девочку", "завести мальчика", "завести девочку", "родить",
                    "родить сына", "родить дочь", "завести сына", "завести дочь",
                    "усыновить", "удочерить", "отн родить", "новый ребенок", "создать ребенка",
                    section=S_REL, usage="родить [мальчик/девочка] [имя]",
                    desc="Завести совместного ребёнка в паре с выбором пола"))
async def cmd_have_child(message: Message, bot: Bot, args: str = "", cmd_name: str = "родить", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")

    if rel["level"] < 3:
        return await message.reply("🔒 Завести ребёнка можно только с <b>3 уровня отношений</b>!")

    gender, child_name = parse_child_name_and_gender(args, cmd_name)

    if not child_name:
        return await message.reply(
            "👶 <b>Как завести ребёнка в отношениях:</b>\n\n"
            "• <code>родить мальчика [Имя]</code> (или: <code>усыновить [Имя]</code>)\n"
            "• <code>родить девочку [Имя]</code> (или: <code>удочерить [Имя]</code>)\n"
            "• Или просто: <code>родить [Имя]</code> — и выберите пол кнопками!\n\n"
            "💖 <i>За рождение малыша даётся +150 любви к отношениям пары!</i>"
        )

    # Если пол не указан текстом — предлагаем выбрать интерактивными кнопками (без рандома!)
    if not gender:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👦 Мальчик", callback_data=f"rel_kid_gender:{rel['id']}:boy:{child_name[:24]}"),
                InlineKeyboardButton(text="👧 Девочка", callback_data=f"rel_kid_gender:{rel['id']}:girl:{child_name[:24]}")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="rel_ui:close")
            ]
        ])
        return await message.reply(
            f"🍼 <b>В семье пополнение! Выберите пол для вашего малыша:</b>\n\n"
            f"👶 Имя ребёнка: <b>{html.escape(child_name)}</b>\n\n"
            f"👇 <i>Кто у вас родится? Нажмите нужную кнопку:</i>",
            reply_markup=kb
        )

    await db.add_rel_child(rel["id"], child_name[:32], gender)
    await db.add_rel_xp(rel["id"], 150)

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)

    await message.reply(
        f"🍼 🎉 <b>В семье пополнение!</b> 🎉 🍼\n\n"
        f"У {mention(message.from_user)} и {mention_id(other_id, pname)} родился {gender} "
        f"по имени <b>{html.escape(child_name)}</b>!\n"
        f"💖 <b>+150 очков любви</b> к отношениям пары!\n\n"
        f"👶 <i>Чтобы посмотреть профиль и заботиться о ребёнке, напишите: <code>ребенок</code></i>"
    )


@router.callback_query(F.data.startswith("rel_kid_gender:"))
async def cb_rel_kid_gender(call: CallbackQuery, bot: Bot):
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split(":", 3)
    rel_id = int(parts[1])
    g_code = parts[2]
    child_name = parts[3] if len(parts) > 3 else "Малыш"

    rel = await db.get_rel_by_id(rel_id)
    if not rel:
        return await call.answer("Отношения не найдены.", show_alert=True)

    if call.from_user.id not in (rel["user1_id"], rel["user2_id"]):
        return await call.answer("Это выбор для родителей пары! 🔒", show_alert=True)

    gender = "👦 Мальчик" if g_code == "boy" else "👧 Девочка"
    await db.add_rel_child(rel_id, child_name[:32], gender)
    await db.add_rel_xp(rel_id, 150)

    other_id = _get_other_partner(rel, call.from_user.id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)

    try:
        await call.message.edit_text(
            f"🍼 🎉 <b>В семье пополнение!</b> 🎉 🍼\n\n"
            f"У {mention(call.from_user)} и {mention_id(other_id, pname)} родился {gender} "
            f"по имени <b>{html.escape(child_name)}</b>!\n"
            f"💖 <b>+150 очков любви</b> к отношениям пары!\n\n"
            f"👶 <i>Чтобы посмотреть профиль и заботиться о ребёнке, напишите: <code>ребенок</code></i>"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("kid_ch_gender:"))
async def cb_kid_change_gender_menu(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split(":")
    child_id = int(parts[1])
    rel_id = int(parts[2])
    idx = int(parts[3]) if len(parts) > 3 else 0

    rel = await db.get_rel_by_id(rel_id)
    if not rel or call.from_user.id not in (rel["user1_id"], rel["user2_id"]):
        return await call.answer("🔒 Меню доступно только родителям малыша!", show_alert=True)

    child = await db.get_child_by_id(child_id)
    if not child:
        return await call.answer("Ребёнок не найден.", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👦 Сделать мальчиком", callback_data=f"kid_set_g:boy:{child_id}:{rel_id}:{idx}"),
            InlineKeyboardButton(text="👧 Сделать девочкой", callback_data=f"kid_set_g:girl:{child_id}:{rel_id}:{idx}")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад в профиль", callback_data=f"kid_view:{child_id}:{rel_id}:{idx}")
        ]
    ])

    try:
        await call.message.edit_text(
            f"👶 <b>СМЕНА ПОЛА РЕБЁНКА: {html.escape(child['name'])}</b>\n\n"
            f"🏷 Текущий пол: <b>{child['gender']}</b>\n\n"
            f"👇 <i>Выберите нужный пол для вашего малыша:</i>",
            reply_markup=kb
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("kid_set_g:"))
async def cb_kid_set_gender(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    g_code = parts[1]
    child_id = int(parts[2])
    rel_id = int(parts[3])
    idx = int(parts[4]) if len(parts) > 4 else 0

    rel = await db.get_rel_by_id(rel_id)
    if not rel or call.from_user.id not in (rel["user1_id"], rel["user2_id"]):
        return await call.answer("🔒 Сменить пол могут только родители!", show_alert=True)

    child = await db.get_child_by_id(child_id)
    if not child:
        return await call.answer("Ребёнок не найден.", show_alert=True)

    new_gender = "👦 Мальчик" if g_code == "boy" else "👧 Девочка"
    await db.execute("UPDATE relationship_children SET gender=? WHERE id=?", (new_gender, child_id))
    await call.answer(f"✅ Пол малыша изменён на {new_gender}!", show_alert=True)

    kids = await db.get_rel_children(rel_id)
    u1 = await db.get_user(rel["user1_id"])
    u2 = await db.get_user(rel["user2_id"])
    n1 = u1["first_name"] or str(rel["user1_id"])
    n2 = u2["first_name"] or str(rel["user2_id"])
    parent_names = f"{mention_id(rel['user1_id'], n1)} & {mention_id(rel['user2_id'], n2)}"

    updated_child = await db.get_child_by_id(child_id)
    text = format_child_card(updated_child, parent_names)
    kb = child_main_keyboard(child_id, rel_id, idx, len(kids))
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.message(Cmd("сменить пол ребенка", "пол ребенка", "изменить пол ребенка", "отн пол ребенка",
                    section=S_REL, usage="пол ребенка [мальчик/девочка]", desc="Сменить пол ребёнка пары"))
async def cmd_change_child_gender(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")

    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    arg_low = (args or "").strip().lower()
    if not arg_low or not any(k in arg_low for k in ["мал", "дев", "сын", "доч"]):
        return await message.reply(
            "👶 <b>Как изменить пол ребёнка:</b>\n\n"
            "• <code>пол ребенка мальчик</code>\n"
            "• <code>пол ребенка девочка</code>\n"
            "• Если несколько детей: <code>пол ребенка 1 мальчик</code> (или укажите имя)"
        )

    new_gender = "👦 Мальчик" if any(k in arg_low for k in ["мал", "сын", "парен"]) else "👧 Девочка"

    target_child = kids[0]
    parts = arg_low.split()
    for p in parts:
        if p.isdigit():
            c_idx = int(p) - 1
            if 0 <= c_idx < len(kids):
                target_child = kids[c_idx]
                break
        else:
            for c in kids:
                if c["name"].lower() in p or p in c["name"].lower():
                    target_child = c
                    break

    await db.execute("UPDATE relationship_children SET gender=? WHERE id=?", (new_gender, target_child["id"]))
    await message.reply(f"✅ 👶 Пол ребёнка <b>{html.escape(target_child['name'])}</b> успешно изменён на <b>{new_gender}</b>!")


@router.callback_query(F.data == "noop")
async def cb_noop_children(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass


@router.message(Cmd("ребенок", "ребёнок", "мой ребенок", "мой ребёнок", "дети", "отн дети", "отн ребенок инфо",
                    section=S_REL, usage="ребенок", desc="Профиль ребёнка и забота о нём"))
async def cmd_my_child(message: Message, bot: Bot, **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")

    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply(
            "🍼 <b>У вашей пары пока нет детей!</b>\n\n"
            "Завести ребёнка можно с <b>3 уровня отношений</b>:\n"
            "• <code>отн ребенок мальчик Максим</code>\n"
            "• <code>отн ребенок девочка Алиса</code>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"

    child = kids[0]
    text = format_child_card(child, parent_names)
    kb = child_main_keyboard(child["id"], rel["id"], 0, len(kids))
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("kid_view:"))
async def cb_kid_view(call: CallbackQuery, bot: Bot):
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split(":")
    child_id = int(parts[1])
    rel_id = int(parts[2])
    idx = int(parts[3]) if len(parts) > 3 else 0

    child = await db.get_child_by_id(child_id)
    rel = await db.get_rel_by_id(rel_id)
    if not child or not rel:
        return await call.answer("Данные не найдены.", show_alert=True)

    kids = await db.get_rel_children(rel_id)
    u1 = await db.get_user(rel["user1_id"])
    u2 = await db.get_user(rel["user2_id"])
    n1 = u1["first_name"] or str(rel["user1_id"])
    n2 = u2["first_name"] or str(rel["user2_id"])
    parent_names = f"{mention_id(rel['user1_id'], n1)} & {mention_id(rel['user2_id'], n2)}"

    text = format_child_card(child, parent_names)
    kb = child_main_keyboard(child_id, rel_id, idx, len(kids))
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("kid_nav:"))
async def cb_kid_nav(call: CallbackQuery, bot: Bot):
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split(":")
    target_idx = int(parts[1])
    rel_id = int(parts[2])

    rel = await db.get_rel_by_id(rel_id)
    if not rel:
        return await call.answer("Отношения не найдены.", show_alert=True)

    kids = await db.get_rel_children(rel_id)
    if not kids:
        return await call.answer("У пары нет детей.", show_alert=True)

    target_idx = target_idx % len(kids)
    child = kids[target_idx]

    u1 = await db.get_user(rel["user1_id"])
    u2 = await db.get_user(rel["user2_id"])
    n1 = u1["first_name"] or str(rel["user1_id"])
    n2 = u2["first_name"] or str(rel["user2_id"])
    parent_names = f"{mention_id(rel['user1_id'], n1)} & {mention_id(rel['user2_id'], n2)}"

    text = format_child_card(child, parent_names)
    kb = child_main_keyboard(child["id"], rel_id, target_idx, len(kids))
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("kid_cat:"))
async def cb_kid_cat(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    category = parts[1]
    child_id = int(parts[2])
    rel_id = int(parts[3])
    idx = int(parts[4]) if len(parts) > 4 else 0

    child = await db.get_child_by_id(child_id)
    if not child:
        return await call.answer("Ребёнок не найден.", show_alert=True)

    cat_titles = {
        "feed": "🍼 ПИТАНИЕ ДЛЯ МАЛЫША",
        "toy": "🧸 МАГАЗИН ИГРУШЕК",
        "cloth": "👕 ДЕТСКИЙ ГАРДЕРОБ",
        "med": "💊 ЗДОРОВЬЕ И ВИТАМИНЫ",
        "edu": "📚 ОБУЧЕНИЕ И РАЗВИТИЕ"
    }
    title = cat_titles.get(category, "🛍 МАГАЗИН УХОДА ЗА РЕБЁНКОМ")
    lines = [f"<b>{title}</b> (для: {html.escape(child['name'])})\n"]

    for k, item in CHILD_CARE_ITEMS.items():
        if item["cat"] == category:
            lines.append(
                f"• {item['emoji']} <b>{item['name']}</b> — <b>{item['price']:,} 🌑</b>\n"
                f"  <i>{item['desc']}</i> (+{item['rel_xp']} любви к паре)"
            )

    lines.append("\n💡 <i>Оплата списывается с личного баланса или семейного банка пары!</i>")
    kb = child_cat_keyboard(category, child_id, rel_id, idx)
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("kid_buy:"))
async def cb_kid_buy(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    item_key = parts[1]
    child_id = int(parts[2])
    rel_id = int(parts[3])
    idx = int(parts[4]) if len(parts) > 4 else 0

    item = CHILD_CARE_ITEMS.get(item_key)
    if not item:
        return await call.answer("Товар не найден.", show_alert=True)

    rel = await db.get_rel_by_id(rel_id)
    if not rel:
        return await call.answer("Отношения не найдены.", show_alert=True)

    caller_id = call.from_user.id
    if caller_id not in (rel["user1_id"], rel["user2_id"]):
        return await call.answer("Заботиться о ребёнке могут только его родители! 🔒", show_alert=True)

    price = item["price"]
    user_bal = await db.get_balance(caller_id)
    bank_bal = await db.get_rel_bank(rel_id)

    paid_from = "баланса"
    if user_bal >= price:
        await db.add_balance(caller_id, -price, "child_care", item_key)
    elif bank_bal >= price:
        await db.add_rel_bank(rel_id, -price)
        paid_from = "семейного банка"
    else:
        needed = price - user_bal
        return await call.answer(
            f"❌ Недостаточно средств! Нужно {price:,} 🌑 (не хватает {needed:,} 🌑).\n"
            f"Пополните баланс или семейный банк пары!",
            show_alert=True
        )

    child = await db.get_child_by_id(child_id)
    if not child:
        return await call.answer("Ребёнок не найден.", show_alert=True)

    cur_stats = get_child_current_stats(child)
    new_sat = min(100, cur_stats["satiety"] + item["sat"])
    new_hap = min(100, cur_stats["happiness"] + item["hap"])
    new_hp = min(100, cur_stats["health"] + item["hp"])
    new_xp = cur_stats["xp"] + item["xp"]

    new_food = int(child.get("food_count") or 0) + (1 if item["cat"] == "feed" else 0)
    new_toys = int(child.get("toys_count") or 0) + (1 if item["cat"] == "toy" else 0)
    new_cloth = int(child.get("clothes_count") or 0) + (1 if item["cat"] == "cloth" else 0)

    # Пересчёт стадии
    days = max(1, int((time.time() - child["born_at"]) // 86400))
    current_stage = 1
    for s_idx, _, req_days, req_xp in GROWTH_STAGES:
        if days >= req_days or new_xp >= req_xp:
            current_stage = s_idx

    await db.update_child_stats(
        child_id, new_sat, new_hap, new_hp, current_stage, new_xp,
        new_toys, new_cloth, new_food
    )
    await db.add_rel_xp(rel_id, item["rel_xp"])

    alert_txt = f"🎉 Приобретено: {item['emoji']} {item['name']} за {price:,} 🌑 (с {paid_from})!\n💖 +{item['rel_xp']} любви к паре!"
    await call.answer(alert_txt, show_alert=True)

    # Возвращаемся в профиль ребёнка
    kids = await db.get_rel_children(rel_id)
    u1 = await db.get_user(rel["user1_id"])
    u2 = await db.get_user(rel["user2_id"])
    n1 = u1["first_name"] or str(rel["user1_id"])
    n2 = u2["first_name"] or str(rel["user2_id"])
    parent_names = f"{mention_id(rel['user1_id'], n1)} & {mention_id(rel['user2_id'], n2)}"

    updated_child = await db.get_child_by_id(child_id)
    text = format_child_card(updated_child, parent_names)
    kb = child_main_keyboard(child_id, rel_id, idx, len(kids))
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


# Быстрые текстовые команды заботы о ребёнке
@router.message(Cmd("покормить ребенка", "покормить ребёнка", "кормить ребенка", "кормить ребёнка",
                    section=S_REL, usage="покормить ребенка [1-3]", desc="Покормить ребёнка"))
async def cmd_quick_feed_child(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")
    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    child = kids[0]
    num = (args or "").strip()
    key_map = {"1": "feed_1", "2": "feed_2", "3": "feed_3"}
    if num in key_map:
        item = CHILD_CARE_ITEMS[key_map[num]]
        price = item["price"]
        bal = await db.get_balance(me_id)
        bank_bal = await db.get_rel_bank(rel["id"])
        if bal >= price:
            await db.add_balance(me_id, -price, "child_care", key_map[num])
        elif bank_bal >= price:
            await db.add_rel_bank(rel["id"], -price)
        else:
            return await message.reply(f"❌ Недостаточно средств: нужно {price:,} 🌑.")

        cur = get_child_current_stats(child)
        new_sat = min(100, cur["satiety"] + item["sat"])
        new_hap = min(100, cur["happiness"] + item["hap"])
        new_hp = min(100, cur["health"] + item["hp"])
        new_xp = cur["xp"] + item["xp"]
        new_food = int(child.get("food_count") or 0) + 1
        await db.update_child_stats(child["id"], new_sat, new_hap, new_hp, cur["stage_num"], new_xp,
                                    child.get("toys_count", 0), child.get("clothes_count", 0), new_food)
        await db.add_rel_xp(rel["id"], item["rel_xp"])
        return await message.reply(
            f"🍼 {mention(message.from_user)} покормил(а) <b>{html.escape(child['name'])}</b>: {item['emoji']} <b>{item['name']}</b>!\n"
            f"Сытость: <b>{new_sat}%</b> | 💖 <b>+{item['rel_xp']} любви</b>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"
    text = format_child_card(child, parent_names)
    kb = child_cat_keyboard("feed", child["id"], rel["id"], 0)
    await message.reply(f"🍼 <b>Выберите еду для малыша:</b>\n\n" + text, reply_markup=kb)


@router.message(Cmd("купить игрушку", "купить игрушки", "поиграть с ребенком", "поиграть с ребёнком",
                    section=S_REL, usage="купить игрушку [1-4]", desc="Купить игрушку для ребёнка"))
async def cmd_quick_toy_child(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")
    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    child = kids[0]
    num = (args or "").strip()
    key_map = {"1": "toy_1", "2": "toy_2", "3": "toy_3", "4": "toy_4"}
    if num in key_map:
        item = CHILD_CARE_ITEMS[key_map[num]]
        price = item["price"]
        bal = await db.get_balance(me_id)
        bank_bal = await db.get_rel_bank(rel["id"])
        if bal >= price:
            await db.add_balance(me_id, -price, "child_care", key_map[num])
        elif bank_bal >= price:
            await db.add_rel_bank(rel["id"], -price)
        else:
            return await message.reply(f"❌ Недостаточно средств: нужно {price:,} 🌑.")

        cur = get_child_current_stats(child)
        new_sat = min(100, cur["satiety"] + item["sat"])
        new_hap = min(100, cur["happiness"] + item["hap"])
        new_hp = min(100, cur["health"] + item["hp"])
        new_xp = cur["xp"] + item["xp"]
        new_toys = int(child.get("toys_count") or 0) + 1
        await db.update_child_stats(child["id"], new_sat, new_hap, new_hp, cur["stage_num"], new_xp,
                                    new_toys, child.get("clothes_count", 0), child.get("food_count", 0))
        await db.add_rel_xp(rel["id"], item["rel_xp"])
        return await message.reply(
            f"🧸 {mention(message.from_user)} купил(а) для <b>{html.escape(child['name'])}</b>: {item['emoji']} <b>{item['name']}</b>!\n"
            f"Настроение: <b>{new_hap}%</b> | Опыт: <b>{new_xp} XP</b> | 💖 <b>+{item['rel_xp']} любви</b>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"
    text = format_child_card(child, parent_names)
    kb = child_cat_keyboard("toy", child["id"], rel["id"], 0)
    await message.reply(f"🧸 <b>Выберите игрушку для малыша:</b>\n\n" + text, reply_markup=kb)


@router.message(Cmd("одеть ребенка", "одеть ребёнка", "купить одежду ребенку",
                    section=S_REL, usage="одеть ребенка [1-3]", desc="Купить одежду для ребёнка"))
async def cmd_quick_cloth_child(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")
    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    child = kids[0]
    num = (args or "").strip()
    key_map = {"1": "cloth_1", "2": "cloth_2", "3": "cloth_3"}
    if num in key_map:
        item = CHILD_CARE_ITEMS[key_map[num]]
        price = item["price"]
        bal = await db.get_balance(me_id)
        bank_bal = await db.get_rel_bank(rel["id"])
        if bal >= price:
            await db.add_balance(me_id, -price, "child_care", key_map[num])
        elif bank_bal >= price:
            await db.add_rel_bank(rel["id"], -price)
        else:
            return await message.reply(f"❌ Недостаточно средств: нужно {price:,} 🌑.")

        cur = get_child_current_stats(child)
        new_sat = min(100, cur["satiety"] + item["sat"])
        new_hap = min(100, cur["happiness"] + item["hap"])
        new_hp = min(100, cur["health"] + item["hp"])
        new_xp = cur["xp"] + item["xp"]
        new_cloth = int(child.get("clothes_count") or 0) + 1
        await db.update_child_stats(child["id"], new_sat, new_hap, new_hp, cur["stage_num"], new_xp,
                                    child.get("toys_count", 0), new_cloth, child.get("food_count", 0))
        await db.add_rel_xp(rel["id"], item["rel_xp"])
        return await message.reply(
            f"👕 {mention(message.from_user)} одел(а) <b>{html.escape(child['name'])}</b>: {item['emoji']} <b>{item['name']}</b>!\n"
            f"Настроение: <b>{new_hap}%</b> | Нарядов: <b>{new_cloth}</b> | 💖 <b>+{item['rel_xp']} любви</b>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"
    text = format_child_card(child, parent_names)
    kb = child_cat_keyboard("cloth", child["id"], rel["id"], 0)
    await message.reply(f"👕 <b>Выберите одежду для малыша:</b>\n\n" + text, reply_markup=kb)


@router.message(Cmd("полечить ребенка", "полечить ребёнка", "витамины ребенку", "витамины ребёнку",
                    section=S_REL, usage="полечить ребенка [1-2]", desc="Полечить ребёнка или дать витамины"))
async def cmd_quick_med_child(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")
    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    child = kids[0]
    num = (args or "").strip()
    key_map = {"1": "med_1", "2": "med_2"}
    if num in key_map:
        item = CHILD_CARE_ITEMS[key_map[num]]
        price = item["price"]
        bal = await db.get_balance(me_id)
        bank_bal = await db.get_rel_bank(rel["id"])
        if bal >= price:
            await db.add_balance(me_id, -price, "child_care", key_map[num])
        elif bank_bal >= price:
            await db.add_rel_bank(rel["id"], -price)
        else:
            return await message.reply(f"❌ Недостаточно средств: нужно {price:,} 🌑.")

        cur = get_child_current_stats(child)
        new_sat = min(100, cur["satiety"] + item["sat"])
        new_hap = min(100, cur["happiness"] + item["hap"])
        new_hp = min(100, cur["health"] + item["hp"])
        new_xp = cur["xp"] + item["xp"]
        await db.update_child_stats(child["id"], new_sat, new_hap, new_hp, cur["stage_num"], new_xp,
                                    child.get("toys_count", 0), child.get("clothes_count", 0), child.get("food_count", 0))
        await db.add_rel_xp(rel["id"], item["rel_xp"])
        return await message.reply(
            f"💊 {mention(message.from_user)} позаботился(ась) о здоровье <b>{html.escape(child['name'])}</b>: {item['emoji']} <b>{item['name']}</b>!\n"
            f"Здоровье: <b>{new_hp}%</b> | 💖 <b>+{item['rel_xp']} любви</b>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"
    text = format_child_card(child, parent_names)
    kb = child_cat_keyboard("med", child["id"], rel["id"], 0)
    await message.reply(f"💊 <b>Забота о здоровье малыша:</b>\n\n" + text, reply_markup=kb)


@router.message(Cmd("учить ребенка", "учить ребёнка", "развивать ребенка", "развивать ребёнка",
                    section=S_REL, usage="учить ребенка [1-3]", desc="Развивать интеллект и обучать ребёнка"))
async def cmd_quick_edu_child(message: Message, bot: Bot, args: str = "", **kw):
    me_id = message.from_user.id
    rel = await db.get_relationship(me_id)
    if not rel:
        return await message.reply("❌ У вас нет отношений.")
    kids = await db.get_rel_children(rel["id"])
    if not kids:
        return await message.reply("🍼 У вашей пары пока нет детей.")

    child = kids[0]
    num = (args or "").strip()
    key_map = {"1": "edu_1", "2": "edu_2", "3": "edu_3"}
    if num in key_map:
        item = CHILD_CARE_ITEMS[key_map[num]]
        price = item["price"]
        bal = await db.get_balance(me_id)
        bank_bal = await db.get_rel_bank(rel["id"])
        if bal >= price:
            await db.add_balance(me_id, -price, "child_care", key_map[num])
        elif bank_bal >= price:
            await db.add_rel_bank(rel["id"], -price)
        else:
            return await message.reply(f"❌ Недостаточно средств: нужно {price:,} 🌑.")

        cur = get_child_current_stats(child)
        new_sat = min(100, cur["satiety"] + item["sat"])
        new_hap = min(100, cur["happiness"] + item["hap"])
        new_hp = min(100, cur["health"] + item["hp"])
        new_xp = cur["xp"] + item["xp"]
        days = max(1, int((time.time() - child["born_at"]) // 86400))
        current_stage = 1
        for s_idx, _, req_days, req_xp in GROWTH_STAGES:
            if days >= req_days or new_xp >= req_xp:
                current_stage = s_idx
        await db.update_child_stats(child["id"], new_sat, new_hap, new_hp, current_stage, new_xp,
                                    child.get("toys_count", 0), child.get("clothes_count", 0), child.get("food_count", 0))
        await db.add_rel_xp(rel["id"], item["rel_xp"])
        return await message.reply(
            f"📚 {mention(message.from_user)} вложился(ась) в обучение <b>{html.escape(child['name'])}</b>: {item['emoji']} <b>{item['name']}</b>!\n"
            f"Опыт развития: <b>{new_xp} XP</b> | 💖 <b>+{item['rel_xp']} любви</b>"
        )

    other_id = _get_other_partner(rel, me_id)
    partner = await db.get_user(other_id)
    pname = partner["first_name"] or str(other_id)
    parent_names = f"{mention(message.from_user)} & {mention_id(other_id, pname)}"
    text = format_child_card(child, parent_names)
    kb = child_cat_keyboard("edu", child["id"], rel["id"], 0)
    await message.reply(f"📚 <b>Обучение и развитие малыша:</b>\n\n" + text, reply_markup=kb)
