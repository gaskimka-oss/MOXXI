"""🏰 Модуль Подземелий и Данжей (Moxxi Dungeon Crawler).

Пошаговые интерактивные исследования лабиринтов, ловушки, монстры, сундуки
и сокровища с механикой риска и эвакуации добычи.
"""
from __future__ import annotations

import html
import json
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from h_items import get_user_combat_gear
from utils import hms, mention, money

router = Router(name="dungeon")
S = 39  # Раздел: Подземелья и рейды

DUNGEON_CD = 20 * 60  # 20 минут

MONSTERS = [
    {"name": "💀 Скелет-Копейщик", "hp": 120, "min_dmg": 15, "max_dmg": 30, "gold": 400, "xp": 35},
    {"name": "👺 Гоблин-Вор", "hp": 150, "min_dmg": 20, "max_dmg": 40, "gold": 650, "xp": 50},
    {"name": "🦇 Пещерный Нетопырь", "hp": 90, "min_dmg": 10, "max_dmg": 25, "gold": 300, "xp": 25},
    {"name": "🧟 Чумной Зомби", "hp": 220, "min_dmg": 25, "max_dmg": 50, "gold": 900, "xp": 75},
    {"name": "🕷 Гигантский Тарантул", "hp": 180, "min_dmg": 20, "max_dmg": 45, "gold": 750, "xp": 60},
    {"name": "🔥 Огненный Элементаль", "hp": 280, "min_dmg": 35, "max_dmg": 65, "gold": 1400, "xp": 110},
    {"name": "👑 Теневой Лорд (Мини-Босс)", "hp": 450, "min_dmg": 45, "max_dmg": 85, "gold": 3000, "xp": 250},
]

RESOURCE_POOL = ["craft_wood", "craft_gear", "craft_shard", "craft_essence"]
RESOURCE_NAMES = {
    "craft_wood": "🪵 Редкая древесина",
    "craft_gear": "⚙️ Шестеренка",
    "craft_shard": "💎 Осколок кристалла",
    "craft_essence": "🔮 Эссенция бездны"
}


def _hp_bar(hp: int, max_hp: int) -> str:
    pct = max(0.0, min(1.0, hp / max(1, max_hp)))
    filled = int(round(pct * 10))
    empty = 10 - filled
    return f"[{'❤️' * filled}{'░' * empty}] {hp}/{max_hp} HP"


def _dungeon_room_kb(event_type: str, floor: int, room: int) -> InlineKeyboardMarkup:
    rows = []
    if event_type == "monster":
        rows.append([
            InlineKeyboardButton(text="⚔️ Атаковать врага!", callback_data="dung:hit"),
            InlineKeyboardButton(text="🏃‍♂️ Попытаться сбежать", callback_data="dung:flee")
        ])
    elif event_type == "chest":
        rows.append([
            InlineKeyboardButton(text="🗝 Открыть сундук", callback_data="dung:open_chest"),
            InlineKeyboardButton(text="🚪 Пройти мимо", callback_data="dung:next_room")
        ])
    elif event_type == "fountain":
        rows.append([
            InlineKeyboardButton(text="🧪 Выпить из источника", callback_data="dung:drink"),
            InlineKeyboardButton(text="🚪 Идти дальше", callback_data="dung:next_room")
        ])
    elif event_type == "stairs":
        rows.append([
            InlineKeyboardButton(text=f"🪜 Спуститься на этаж {floor + 1} ⬇️", callback_data="dung:down_floor"),
            InlineKeyboardButton(text="🏆 Эвакуироваться с добычей", callback_data="dung:leave")
        ])
    elif event_type == "cleared":
        rows.append([
            InlineKeyboardButton(text="🚪 Следующая комната ➡️", callback_data="dung:next_room"),
            InlineKeyboardButton(text="🏃‍♂️ Выйти с добычей", callback_data="dung:leave")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("данж", "подземелье", "поход в данж", "пещера", section=S, rank=0,
                    usage="данж", desc="🏰 Спуститься в интерактивное подземелье"))
async def cmd_start_dungeon(message: Message, bot: Bot, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    v_lvl, _, v_act = await db.get_vip_info(uid)

    cd = DUNGEON_CD
    if v_act and v_lvl >= 2:
        cd = int(cd * 0.35)  # VIP+: КД 7 минут
    elif v_act and v_lvl == 1:
        cd = int(cd * 0.60)  # VIP: КД 12 минут

    left = await db.cooldown_left(uid, "dungeon_cd", cd)
    if left > 0:
        if had_prefix or not in_group:
            return await message.reply(
                f"⏳ <b>Ваш отряд отдыхает после прошлого похода!</b>\n"
                f"Вход в подземелье откроется через <b>{hms(left)}</b>."
            )
        return

    # Проверяем, есть ли незавершенная сессия
    cur = await db.get_dungeon_progress(uid)
    if cur and cur.get("active", 0) == 1:
        # Продолжаем текущее подземелье
        state = json.loads(cur.get("state_data", "{}"))
        text = _format_dungeon_screen(cur, state, message.from_user.first_name)
        kb = _dungeon_room_kb(state.get("type", "cleared"), cur["floor"], cur["room"])
        return await message.reply(text, reply_markup=kb)

    # Начинаем новое подземелье
    await db.set_cooldown(uid, "dungeon_cd")

    floor = 1
    room = 1
    hp = 100
    max_hp = 100
    gold_found = 0
    xp_found = 0

    # Генерируем первое событие
    first_event = random.choice(["monster", "chest", "fountain"])
    state = _generate_room_event(first_event, floor)

    await db.save_dungeon_progress(
        uid, floor, room, hp, max_hp, gold_found, xp_found, 1, json.dumps(state, ensure_ascii=False)
    )

    cur_dict = {
        "floor": floor, "room": room, "hp": hp, "max_hp": max_hp,
        "gold_found": gold_found, "xp_found": xp_found
    }
    text = _format_dungeon_screen(cur_dict, state, message.from_user.first_name)
    kb = _dungeon_room_kb(state["type"], floor, room)
    await message.reply(text, reply_markup=kb)


def _generate_room_event(event_type: str, floor: int) -> dict:
    if event_type == "monster":
        m_tmpl = random.choice(MONSTERS[:min(len(MONSTERS), 3 + floor)])
        m_hp = int(m_tmpl["hp"] * (1 + (floor - 1) * 0.25))
        return {
            "type": "monster",
            "name": m_tmpl["name"],
            "hp": m_hp,
            "max_hp": m_hp,
            "min_dmg": m_tmpl["min_dmg"],
            "max_dmg": m_tmpl["max_dmg"],
            "gold": int(m_tmpl["gold"] * (1 + (floor - 1) * 0.3)),
            "xp": int(m_tmpl["xp"] * (1 + (floor - 1) * 0.3)),
            "desc": f"Перед вами появился опасный <b>{m_tmpl['name']}</b>!"
        }
    elif event_type == "chest":
        return {
            "type": "chest",
            "desc": "📦 В углу комнаты стоит старинный кованый сундук сокровищ! Открыть его или пройти мимо?"
        }
    elif event_type == "fountain":
        return {
            "type": "fountain",
            "desc": "🧪 Вы нашли алтарь с целебным источником! Вода восстановит часть вашего здоровья."
        }
    elif event_type == "stairs":
        return {
            "type": "stairs",
            "desc": f"🪜 Вы нашли каменную лестницу, ведущую глубже на <b>Этаж {floor + 1}</b>! Враги там сильнее, но и сокровища богаче!"
        }
    return {"type": "cleared", "desc": "Комната пуста и безопасна."}


def _format_dungeon_screen(cur: dict, state: dict, user_name: str) -> str:
    floor = cur["floor"]
    room = cur["room"]
    hp = cur["hp"]
    max_hp = cur["max_hp"]
    gold = cur["gold_found"]
    xp = cur["xp_found"]

    m_info = ""
    if state.get("type") == "monster":
        m_info = f"\n👾 <b>Враг:</b> {state['name']}\n❤️ HP врага: {_hp_bar(state['hp'], state['max_hp'])}\n"

    return (
        f"🏰 ✨ <b>ПОДЗЕМЕЛЬЕ МОКСИ (ЭТАЖ {floor} · КОМНАТА {room})</b> ✨ 🏰\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Герой: <b>{html.escape(user_name)}</b>\n"
        f"❤️ Ваше здоровье: {_hp_bar(hp, max_hp)}\n"
        f"💰 Накопленная добыча: <b>+{money(gold)}</b> · <b>+{xp} XP</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{state.get('desc', '')}{m_info}"
    )


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("dung:"))
async def cb_dungeon_action(call: CallbackQuery, bot: Bot):
    action = call.data.split(":")[1]
    uid = call.from_user.id

    cur = await db.get_dungeon_progress(uid)
    if not cur or cur.get("active", 0) == 0:
        return await call.answer("Вы сейчас не в подземелье! Напишите «данж».", show_alert=True)

    state = json.loads(cur.get("state_data", "{}"))
    gear = await get_user_combat_gear(uid)
    now = int(time.time())

    user_name = call.from_user.first_name or "Герой"

    if action == "hit":
        if state.get("type") != "monster":
            return await call.answer("Здесь нет монстра!", show_alert=True)

        # Урон игрока
        dmg = int(random.randint(40, 75) * gear["dmg_mult"])
        is_crit = random.random() < 0.20
        if is_crit:
            dmg = int(dmg * 2.0)

        state["hp"] = max(0, state["hp"] - dmg)

        if state["hp"] <= 0:
            # Монстр побежден!
            gold = state["gold"]
            xp = state["xp"]
            new_gold = cur["gold_found"] + gold
            new_xp = cur["xp_found"] + xp

            # Шанс ресурса крафта
            res_text = ""
            if random.random() < 0.40:
                res_key = random.choice(RESOURCE_POOL)
                res_name = RESOURCE_NAMES[res_key]
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
                    (uid, res_key, res_name, now)
                )
                res_text = f" Найдена деталь: <b>{res_name}</b>!"

            state = {
                "type": "cleared",
                "desc": f"⚔️ Вы повергли монстра <b>{state['name']}</b>! Найдено <b>+{money(gold)}</b> и <b>+{xp} XP</b>!{res_text}"
            }
            await db.save_dungeon_progress(
                uid, cur["floor"], cur["room"], cur["hp"], cur["max_hp"], new_gold, new_xp, 1, json.dumps(state, ensure_ascii=False)
            )
            cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": cur["hp"], "max_hp": cur["max_hp"], "gold_found": new_gold, "xp_found": new_xp}
            await call.answer(f"💥 Вы нанесли -{dmg} HP! Враг повержен!")
            text = _format_dungeon_screen(cur_dict, state, user_name)
            return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("cleared", cur["floor"], cur["room"]))

        # Ответный урон монстра
        m_dmg = random.randint(state["min_dmg"], state["max_dmg"])
        if gear["has_armor"]:
            m_dmg = int(m_dmg * 0.6)  # Броня снижает урон на 40%

        new_hp = max(0, cur["hp"] - m_dmg)

        if new_hp <= 0:
            # Игрок погиб! Теряет 50% золота
            lost_gold = int(cur["gold_found"] * 0.5)
            saved_gold = cur["gold_found"] - lost_gold
            await db.add_balance(uid, saved_gold)
            await db.add_xp(call.message.chat.id, uid, cur["xp_found"])
            await db.save_dungeon_progress(uid, 1, 1, 0, 100, 0, 0, 0, "{}")

            await call.answer("💀 ВЫ ПОГИБЛИ В ПОДЗЕМЕЛЬЕ!", show_alert=True)
            death_text = (
                f"💀 ✨ <b>ВАШ ГЕРОЙ ПАЛ В БОЮ!</b> ✨ 💀\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"Враг <b>{state['name']}</b> нанёс смертельный удар (-{m_dmg} HP)!\n"
                f"Вы потеряли часть золота, но спасли: <b>+{money(saved_gold)}</b> и <b>+{cur['xp_found']} XP</b>.\n\n"
                f"🧪 <i>Купите броню и оружие в магазине перед следующим походом!</i>"
            )
            return await call.message.edit_text(death_text)

        await db.save_dungeon_progress(
            uid, cur["floor"], cur["room"], new_hp, cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": new_hp, "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
        await call.answer(f"⚔️ Удар на -{dmg} HP! (Ответный урон -{m_dmg} HP)")
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("monster", cur["floor"], cur["room"]))

    if action == "flee":
        # Побег с шансом получить урон
        flee_dmg = random.randint(15, 30)
        new_hp = max(1, cur["hp"] - flee_dmg)
        state = {"type": "cleared", "desc": f"🏃‍♂️ Вы чудом увернулись от ударов и сбежали из боя (-{flee_dmg} HP)!"}
        await db.save_dungeon_progress(
            uid, cur["floor"], cur["room"], new_hp, cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": new_hp, "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
        await call.answer(f"🏃‍♂️ Вы сбежали! (-{flee_dmg} HP)")
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("cleared", cur["floor"], cur["room"]))

    if action == "open_chest":
        is_trap = random.random() < 0.20
        if is_trap:
            trap_dmg = random.randint(20, 35)
            new_hp = max(1, cur["hp"] - trap_dmg)
            state = {"type": "cleared", "desc": f"⚠️ <b>ЛОВУШКА!</b> Из сундука вылетели ядовитые иглы! (-{trap_dmg} HP)"}
            await db.save_dungeon_progress(
                uid, cur["floor"], cur["room"], new_hp, cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
            )
            cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": new_hp, "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
            await call.answer(f"⚠️ Ловушка! -{trap_dmg} HP", show_alert=True)
            text = _format_dungeon_screen(cur_dict, state, user_name)
            return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("cleared", cur["floor"], cur["room"]))

        chest_gold = random.randint(800, 2500) * cur["floor"]
        new_gold = cur["gold_found"] + chest_gold
        state = {"type": "cleared", "desc": f"🎉 <b>УСПЕХ!</b> В сундуке лежало <b>+{money(chest_gold)}</b> монет!"}
        await db.save_dungeon_progress(
            uid, cur["floor"], cur["room"], cur["hp"], cur["max_hp"], new_gold, cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": cur["hp"], "max_hp": cur["max_hp"], "gold_found": new_gold, "xp_found": cur["xp_found"]}
        await call.answer(f"💰 Найдено +{chest_gold} монет!", show_alert=True)
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("cleared", cur["floor"], cur["room"]))

    if action == "drink":
        heal = random.randint(30, 50)
        new_hp = min(cur["max_hp"], cur["hp"] + heal)
        state = {"type": "cleared", "desc": f"✨ Целебная вода восстановила вам <b>+{heal} HP</b>!"}
        await db.save_dungeon_progress(
            uid, cur["floor"], cur["room"], new_hp, cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": cur["floor"], "room": cur["room"], "hp": new_hp, "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
        await call.answer(f"💚 +{heal} HP восстановлено!")
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb("cleared", cur["floor"], cur["room"]))

    if action == "next_room":
        new_room = cur["room"] + 1
        floor = cur["floor"]

        # На 5-й комнате появляются ступени на следующий этаж
        if new_room >= 5:
            state = _generate_room_event("stairs", floor)
        else:
            next_ev = random.choice(["monster", "monster", "chest", "fountain"])
            state = _generate_room_event(next_ev, floor)

        await db.save_dungeon_progress(
            uid, floor, new_room, cur["hp"], cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": floor, "room": new_room, "hp": cur["hp"], "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
        await call.answer(f"🚪 Входим в комнату {new_room}...")
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb(state["type"], floor, new_room))

    if action == "down_floor":
        new_floor = cur["floor"] + 1
        new_room = 1
        state = _generate_room_event("monster", new_floor)

        await db.save_dungeon_progress(
            uid, new_floor, new_room, cur["hp"], cur["max_hp"], cur["gold_found"], cur["xp_found"], 1, json.dumps(state, ensure_ascii=False)
        )
        cur_dict = {"floor": new_floor, "room": new_room, "hp": cur["hp"], "max_hp": cur["max_hp"], "gold_found": cur["gold_found"], "xp_found": cur["xp_found"]}
        await call.answer(f"🪜 Спускаемся на Этаж {new_floor}!", show_alert=True)
        text = _format_dungeon_screen(cur_dict, state, user_name)
        return await call.message.edit_text(text, reply_markup=_dungeon_room_kb(state["type"], new_floor, new_room))

    if action == "leave":
        # Успешный выход с сохранением 100% добычи
        gold = cur["gold_found"]
        xp = cur["xp_found"]

        await db.add_balance(uid, gold)
        await db.add_xp(call.message.chat.id, uid, xp)
        await db.save_dungeon_progress(uid, 1, 1, 100, 100, 0, 0, 0, "{}")

        await call.answer("🏆 Вы успешно вынесли всю добычу!", show_alert=True)

        win_text = (
            f"🏆 ✨ <b>ЭКСПЕДИЦИЯ В ПОДЗЕМЕЛЬЕ ЗАВЕРШЕНА!</b> ✨ 🏆\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 Герой: {mention(call.from_user)}\n"
            f"🏰 Пройдено: <b>Этаж {cur['floor']} (Комната {cur['room']})</b>\n\n"
            f"💰 <b>Заработано монет:</b> <b>+{money(gold)}</b>\n"
            f"⭐️ <b>Получено опыта:</b> <b>+{xp} XP</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"⚔️ <i>Следующий поход: напишите <code>данж</code></i>"
        )
        return await call.message.edit_text(win_text)
