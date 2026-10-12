"""🐉 Рейдовый Босс чата: битвы в спец-темах, нокауты, лечение союзников, снаряжение и раздел куша.

Особенности:
  1. Автоматический спавн до 4 боссов в день (08:00, 12:00, 16:00, 20:00).
  2. Строгий лимит: МАКСИМУМ 4 босса в сутки на чат (для всех, включая владельцев).
  3. Привязка темы: «+тема босс» / «-тема босс» — бои проходят строго в отдельной ветке.
  4. Механика нокаута: босс может контратаковать и оглушить бойца!
  5. Лечение и воскрешение: «хил @юзер», «возродить», кнопка «💊 Возродить» или «аптечка».
  6. Снаряжение: оружие (+50% / +120% к урону), броня (-65% шанс нокаута), набор медика (+награда).
  7. Раздел куша и опыта пропорционально нанесенному урону между всеми бойцами + бонусы ТОП-3!
"""
from __future__ import annotations

import asyncio
import html
import random
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from h_items import consume_medkit, get_user_combat_gear
from utils import mention, mention_id, money

router = Router(name="boss")
S = 36  # Раздел: Рейдовые боссы

# Максимальное число боссов в сутки на один чат
MAX_DAILY_BOSSES = 4

# Базовые шаблоны боссов
BOSS_TEMPLATES = [
    {
        "name": "Гоблин-Грабитель",
        "icon": "👹",
        "level": 1,
        "hp": 3500,
        "pool": 7000,
        "xp": 600,
        "counter_chance": 0.20,
        "desc": "Хитрый карлик с мешком украденных монет!"
    },
    {
        "name": "Огненный Дракон Мокси",
        "icon": "🐉",
        "level": 2,
        "hp": 7500,
        "pool": 16000,
        "xp": 1400,
        "counter_chance": 0.25,
        "desc": "Изрыгает пламя и сжигает врагов на арене!"
    },
    {
        "name": "Каменный Титан Разлома",
        "icon": "🗿",
        "level": 3,
        "hp": 12000,
        "pool": 28000,
        "xp": 2500,
        "counter_chance": 0.30,
        "desc": "Древний исполин с непробиваемой гранитной броней!"
    },
    {
        "name": "Владыка Тьмы и Бездны",
        "icon": "🌌",
        "level": 4,
        "hp": 20000,
        "pool": 60000,
        "xp": 6000,
        "counter_chance": 0.35,
        "desc": "Мифический властелин хаоса с колоссальной наградой!"
    }
]


def _today_key(tz_offset: int = 3) -> str:
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    return now.strftime("%Y-%m-%d")


def _topic_id(message: Message) -> int:
    return int(getattr(message, "message_thread_id", None) or 0)


def _topic_link(chat_id: int, tid: int) -> str:
    cid = str(chat_id)
    short = cid[4:] if cid.startswith("-100") else cid.lstrip("-")
    return f"https://t.me/c/{short}/{tid}"


async def get_boss_topic(chat_id: int) -> int:
    """ID темы, где проходят битвы с боссами. 0 — тема не задана."""
    v = await db.get_setting(chat_id, "boss_topic", "0")
    try:
        return int(v)
    except Exception:
        return 0


def _hp_bar(current: int, max_hp: int, length: int = 10) -> str:
    """Генерирует графический бар здоровья: [██████░░░░] 60%."""
    pct = max(0.0, min(1.0, current / max(1, max_hp)))
    filled = int(round(pct * length))
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {int(pct * 100)}% ({current}/{max_hp} HP)"


async def _get_daily_spawns(chat_id: int) -> int:
    day = _today_key()
    row = await db.fetchone("SELECT count FROM boss_daily_count WHERE chat_id=? AND day=?", (chat_id, day))
    return int(row["count"]) if row else 0


async def _inc_daily_spawns(chat_id: int) -> int:
    day = _today_key()
    await db.execute(
        "INSERT INTO boss_daily_count (chat_id, day, count) VALUES (?, ?, 1) "
        "ON CONFLICT(chat_id, day) DO UPDATE SET count = count + 1",
        (chat_id, day)
    )
    return await _get_daily_spawns(chat_id)


async def is_player_knocked_out(chat_id: int, user_id: int) -> bool:
    """Проверяет, находится ли боец в нокауте."""
    row = await db.fetchone(
        "SELECT knocked_out_ts FROM boss_knockouts WHERE chat_id=? AND user_id=?",
        (chat_id, user_id)
    )
    return bool(row)


async def revive_player(chat_id: int, user_id: int) -> bool:
    """Воскрешает бойца из нокаута."""
    res = await db.execute(
        "DELETE FROM boss_knockouts WHERE chat_id=? AND user_id=?",
        (chat_id, user_id)
    )
    return res > 0


def _boss_card(row: dict) -> str:
    hp_str = _hp_bar(row["current_hp"], row["max_hp"])
    text = (
        f"{row['boss_icon']} ✨ <b>РЕЙДОВЫЙ БОСС: {html.escape(row['boss_name']).upper()}</b> ✨ {row['boss_icon']}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Уровень угрозы: <b>⭐ {row['boss_level']}</b>\n"
        f"Здоровье: <b>{hp_str}</b>\n"
        f"💰 Призовой куш: <b>{money(row['reward_pool'])}</b> · <b>+{row['reward_xp']} XP</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"⚔️ <i>Атакуйте:</i> <code>ударить</code>, <code>выстрел</code>, <code>атака</code>\n"
        f"🚑 <i>Помощь упавшим союзникам:</i> <code>хил @юзер</code> или <code>возродить</code>\n"
        f"🧪 <i>Самолечение аптечкой:</i> <code>аптечка</code>"
    )
    return text


def _attack_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ НАНЕСТИ УДАР!", callback_data=f"boss:hit:{chat_id}")],
        [
            InlineKeyboardButton(text="🚑 Поднять союзника", callback_data=f"boss:revive_menu:{chat_id}"),
            InlineKeyboardButton(text="📊 Топ дамага", callback_data=f"boss:top:{chat_id}")
        ]
    ])


# ══════════════════ 1. НАСТРОЙКА ТЕМЫ БОССОВ ══════════════════

@router.message(Cmd("+тема босс", "+тема боссы", "тема босс", "тема боссы", "тема боссов", "тема босса",
                    section=S, rank=3, usage="+тема босс", desc="🎯 Привязать тему для рейдовых боссов"))
async def cmd_set_boss_topic(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return

    cid = message.chat.id
    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем боссы появляются прямо в основном чате.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    a = (args or "").strip().lower()

    if a in {"выкл", "off", "откл", "удалить", "0", "disable"}:
        await db.set_setting(cid, "boss_topic", "0")
        return await message.reply("🛑 <b>Привязка темы боссов отключена!</b>")

    here = _topic_id(message)
    if not here:
        cur = await get_boss_topic(cid)
        cur_txt = f"\nТекущая тема: {_topic_link(cid, cur)}" if cur else "\nТекущая тема: <i>не привязана</i>"
        return await message.reply(
            f"⚠️ <b>Команду нужно писать внутри нужной темы (ветки)!</b>{cur_txt}\n\n"
            f"👉 Зайдите в созданную ветку (напр. «🐉 Рейдовые Боссы») и напишите: <code>+тема босс</code>\n"
            f"Отключить: <code>-тема босс</code>",
            disable_web_page_preview=True
        )

    await db.set_setting(cid, "boss_topic", str(here))
    await message.reply(
        f"🐉 ✅ <b>Тема рейдовых боссов успешно привязана!</b>\n\n"
        f"👉 ID темы: <code>{here}</code>\n"
        f"🔗 Ссылка: {_topic_link(cid, here)}\n\n"
        f"Все рейдовые боссы (автоматические и ручные спавны) будут появляться исключительно в этой ветке, не засоряя чат!",
        disable_web_page_preview=True
    )


@router.message(Cmd("-тема босс", "-тема боссы", "выкл тема босс", section=S, rank=3,
                    usage="-тема босс", desc="Отвязать тему рейдовых боссов"))
async def cmd_del_boss_topic(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return
    await db.set_setting(message.chat.id, "boss_topic", "0")
    await message.reply("🛑 <b>Привязка темы для боссов снята.</b>")


# ══════════════════ 2. ИНФОРМАЦИЯ И СПАВН ══════════════════

@router.message(Cmd("босс", "рейд", "босс инфо", section=S, rank=0,
                    usage="босс", desc="🐉 Информация о текущем рейдовом боссе"))
async def cmd_boss_info(message: Message, bot: Bot, **kw):
    if message.chat.type == "private":
        return await message.reply("🐉 Рейдовые боссы доступны только в беседах!")

    cid = message.chat.id
    btopic = await get_boss_topic(cid)
    here = _topic_id(message)

    # Если тема привязана, а пользователь пишет вне темы — направляем туда
    if btopic and here != btopic:
        return await message.reply(
            f"🐉 <b>Рейды боссов проходят в специальной теме:</b>\n"
            f"👉 {_topic_link(cid, btopic)}",
            disable_web_page_preview=True
        )

    row = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=? AND active=1", (cid,))
    if not row or row["current_hp"] <= 0:
        spawns = await _get_daily_spawns(cid)
        return await message.reply(
            f"🐉 <b>Сейчас в чате нет активного босса.</b>\n\n"
            f"📊 Побеждено боссов сегодня: <b>{spawns}/{MAX_DAILY_BOSSES}</b>\n"
            f"⏰ Стандартное расписание: <b>08:00, 12:00, 16:00, 20:00</b> (МСК)\n"
            f"👑 Админы могут вызвать босса: <code>заспавнить босса</code>"
        )

    await message.reply(_boss_card(row), reply_markup=_attack_kb(cid))


@router.message(Cmd("заспавнить босса", "призвать босса", "спавн босс", "спавн босса",
                    "спавнить босса", "вызвать босса", "призыв босса", "заспавни босса",
                    "призови босса", "босс спавн", "босс призыв", section=S, rank=3,
                    usage="заспавнить босса", desc="👑 Принудительно призвать рейдового босса"))
async def cmd_spawn_boss(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return

    cid = message.chat.id
    btopic = await get_boss_topic(cid)
    here = _topic_id(message)

    active = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=? AND active=1", (cid,))
    if active and active["current_hp"] > 0:
        return await message.reply("⚠️ В чате уже есть живой босс! Добейте его перед призывом нового.")

    spawns = await _get_daily_spawns(cid)
    if spawns >= MAX_DAILY_BOSSES:
        return await message.reply(
            f"⛔️ <b>Достигнут строгий лимит дня!</b>\n\n"
            f"В этом чате уже было призвано <b>{spawns}/{MAX_DAILY_BOSSES}</b> боссов за сегодня.\n"
            f"Следующий босс будет доступен только завтра!"
        )

    tmpl = BOSS_TEMPLATES[spawns % len(BOSS_TEMPLATES)]
    await _inc_daily_spawns(cid)

    # Очищаем урон прошлого рейда и нокауты
    await db.execute("DELETE FROM boss_damage WHERE chat_id=?", (cid,))
    await db.execute("DELETE FROM boss_knockouts WHERE chat_id=?", (cid,))

    await db.execute(
        "INSERT INTO chat_boss (chat_id, boss_name, boss_icon, boss_level, max_hp, current_hp, reward_pool, reward_xp, spawn_time, active, last_msg_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0) ON CONFLICT(chat_id) DO UPDATE SET "
        "boss_name=excluded.boss_name, boss_icon=excluded.boss_icon, boss_level=excluded.boss_level, "
        "max_hp=excluded.max_hp, current_hp=excluded.current_hp, reward_pool=excluded.reward_pool, "
        "reward_xp=excluded.reward_xp, spawn_time=excluded.spawn_time, active=1",
        (cid, tmpl["name"], tmpl["icon"], tmpl["level"], tmpl["hp"], tmpl["hp"],
         tmpl["pool"], tmpl["xp"], int(time.time()))
    )

    row = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=?", (cid,))
    card = (
        f"🚨 🚨 <b>ВНИМАНИЕ! ПОЯВИЛСЯ РЕЙДОВЫЙ БОСС!</b> 🚨 🚨\n\n"
        + _boss_card(row)
    )

    if btopic and btopic > 0:
        target_thread = btopic
    elif here > 0:
        target_thread = here
    else:
        target_thread = None

    try:
        sent = await bot.send_message(
            cid, card,
            message_thread_id=target_thread,
            reply_markup=_attack_kb(cid)
        )
        await db.execute("UPDATE chat_boss SET last_msg_id=? WHERE chat_id=?", (sent.message_id, cid))
    except Exception:
        sent = await message.answer(card, reply_markup=_attack_kb(cid))
        await db.execute("UPDATE chat_boss SET last_msg_id=? WHERE chat_id=?", (sent.message_id, cid))


# ══════════════════ 3. АТАКА БОССА ══════════════════

@router.message(Cmd("ударить босса", "атака босса", "бить босса", "атаковать босса",
                    "выстрел в босса", "удар по боссу", "удар босс", "удар босса",
                    "босс удар", "атаковать", "ударить", "атака", "выстрел", "бить",
                    section=S, rank=0, usage="ударить босса", desc="⚔️ Нанести удар по активному боссу"))
async def cmd_attack_boss(message: Message, bot: Bot, **kw):
    if message.chat.type == "private":
        return

    cid = message.chat.id
    btopic = await get_boss_topic(cid)
    here = _topic_id(message)

    # Изоляция темы: если тема боссов назначена, а игрок бьет в другой теме
    if btopic and here != btopic and here > 0:
        return await message.reply(
            f"🐉 <b>Битва с боссом проходит в спец-теме:</b>\n"
            f"👉 {_topic_link(cid, btopic)}",
            disable_web_page_preview=True
        )

    uid = message.from_user.id
    user_name = message.from_user.first_name or "Боец"

    res = await _perform_attack(cid, uid, user_name, bot)
    if res.get("error"):
        return await message.reply(res["error"])

    if res.get("defeated"):
        await message.reply(res["text"])
    else:
        crit_mult = res.get("crit_mult", 2.5)
        if res["is_crit"]:
            if crit_mult >= 3.5:
                crit_tag = " 🌟 🔥 <b>МЕГА-КРИТ x3.5! (VIP+)</b>"
            elif crit_mult >= 3.0:
                crit_tag = " ⭐️ 🔥 <b>КРИТИЧЕСКИЙ УРОН x3.0! (VIP)</b>"
            else:
                crit_tag = " 🔥 <b>КРИТИЧЕСКИЙ УРОН x2.5!</b>"
        else:
            crit_tag = ""

        weapon_tag = f" ({res['weapon_name']})" if res.get("weapon_name") else ""
        ko_tag = ""
        if res.get("knocked_out"):
            ko_tag = (
                "\n\n💀 <b>БОСС НАНЁС ОТВЕТНЫЙ УДАР И ОТПРАВИЛ ВАС В НОКАУТ!</b>\n"
                "Вы потеряли сознание и не можете атаковать, пока вас не поднимут союзники!\n"
                "🚑 <i>Союзники могут написать:</i> <code>хил @юзер</code> или <code>возродить</code>\n"
                "🧪 <i>Использовать свою аптечку:</i> <code>аптечка</code>"
            )

        await message.reply(
            f"⚔️ {mention(message.from_user)} нанёс <b>-{res['dmg']} HP</b>!{crit_tag}{weapon_tag}\n"
            f"❤️ У босса осталось: <b>{res['left_hp']}/{res['max_hp']} HP</b>{ko_tag}"
        )


@router.callback_query(F.data.startswith("boss:hit:"))
async def cb_boss_hit(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[2])
    uid = call.from_user.id
    user_name = call.from_user.first_name or "Боец"

    res = await _perform_attack(cid, uid, user_name, bot)
    if res.get("error"):
        return await call.answer(res["error"], show_alert=True)

    if res.get("defeated"):
        try:
            await call.message.edit_text(res["text"])
        except Exception:
            pass
        return await call.answer("🏆 БОСС УНИЧТОЖЕН!", show_alert=True)

    if res.get("knocked_out"):
        return await call.answer(
            f"💀 БОСС ОТПРАВИЛ ВАС В НОКАУТ! (Урон -{res['dmg']})\nПопросите союзников написать 'хил' или используйте аптечку!",
            show_alert=True
        )

    crit_mult = res.get("crit_mult", 2.5)
    crit_tag = f" 🔥 КРИТ x{crit_mult:.1f}!" if res["is_crit"] else ""
    await call.answer(f"⚔️ Удар на -{res['dmg']} HP!{crit_tag} (Осталось {res['left_hp']} HP)")


# ══════════════════ 4. ЛЕЧЕНИЕ И ВОСКРЕШЕНИЕ СОЮЗНИКОВ ══════════════════

@router.message(Cmd("хил", "возродить бойца", "хил бойца", "поднять бойца", "рес бойца", "revive", "воскресить бойца", section=S, rank=0,
                    usage="хил [@юзер/реплай]", desc="🚑 Поднять союзника из нокаута"))
async def cmd_heal_user(message: Message, bot: Bot, args: str = "", **kw):
    if message.chat.type == "private":
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    cid = message.chat.id
    healer_id = message.from_user.id
    target_id = None
    target_name = ""

    # 1. Проверяем реплай
    rep = real_reply(message)
    if rep and rep.from_user and not rep.from_user.is_bot:
        target_id = rep.from_user.id
        target_name = rep.from_user.first_name or "Боец"
    elif args:
        uid, name, _ = await resolve_target(message, args, bot)
        if uid:
            target_id = uid
            target_name = name

    if not target_id:
        # Если цель не указана — проверяем список упавших бойцов
        ko_rows = await db.fetchall("SELECT user_id FROM boss_knockouts WHERE chat_id=?", (cid,))
        if not ko_rows:
            if had_prefix or not in_group:
                return await message.reply("🚑 Сейчас в чате нет бойцов в нокауте. Все готовы к сражению!")
            return
        # Поднимаем первого упавшего
        target_id = ko_rows[0]["user_id"]
        t_user = await db.get_user(target_id)
        target_name = t_user.get("first_name") or "Боец"

    if target_id == healer_id:
        return await message.reply(
            "⚠️ Вы не можете воскресить себя обычной командой! Используйте: <code>аптечка</code>"
        )

    is_ko = await is_player_knocked_out(cid, target_id)
    if not is_ko:
        return await message.reply(f"💚 {mention_id(target_id, target_name)} в полном порядке и готов крушить босса!")

    await revive_player(cid, target_id)

    # Проверяем экипировку лечащего
    gear = await get_user_combat_gear(healer_id)
    bonus_text = ""
    if gear["has_doc_kit"]:
        # Бонус за профессиональное лечение
        await db.add_balance(healer_id, 350)
        await db.add_xp(cid, healer_id, 60)
        bonus_text = "\n💊 <b>Набор медика:</b> лечащий получил <b>+350 монет</b> · <b>+60 XP</b> за спасение союзника!"

    await message.reply(
        f"💖 ✨ <b>БОЕЦ ВОЗВРАЩЕН В СТРОЙ!</b> ✨ 💖\n\n"
        f"🚑 {mention(message.from_user)} оказал первую помощь {mention_id(target_id, target_name)}!\n"
        f"⚔️ {mention_id(target_id, target_name)} поднялся из нокаута и готов снова атаковать босса!{bonus_text}"
    )


@router.message(Cmd("аптечка", "исп аптечку", "самохил", "использовать аптечку", section=S, rank=0,
                    usage="аптечка", desc="🧪 Использовать аптечку для выхода из нокаута"))
async def cmd_use_medkit(message: Message, bot: Bot, **kw):
    cid = message.chat.id
    uid = message.from_user.id

    is_ko = await is_player_knocked_out(cid, uid)
    if not is_ko:
        return await message.reply("💚 Вы в полном порядке и не находитесь в нокауте!")

    consumed = await consume_medkit(uid)
    if not consumed:
        return await message.reply(
            "❌ <b>У вас нет аптечки в инвентаре!</b>\n\n"
            "• Купить аптечку: <code>купить аптечку</code> (1 500 монет)\n"
            "• Либо попросите союзника в чате написать: <code>хил</code>"
        )

    await revive_player(cid, uid)
    await message.reply(
        f"🧪 ✨ <b>АПТЕЧКА ИСПОЛЬЗОВАНА!</b> ✨ 🧪\n\n"
        f"👤 {mention(message.from_user)} мгновенно поднялся на ноги и готов наносить урон!"
    )


@router.callback_query(F.data.startswith("boss:revive_menu:"))
async def cb_boss_revive_menu(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[2])
    uid = call.from_user.id

    ko_rows = await db.fetchall(
        "SELECT k.user_id, u.first_name FROM boss_knockouts k "
        "LEFT JOIN users u ON u.user_id=k.user_id WHERE k.chat_id=?",
        (cid,)
    )
    if not ko_rows:
        return await call.answer("🚑 В нокауте никого нет! Все бойцы на ногах.", show_alert=True)

    # Если сам кликающий в нокауте
    is_ko = any(r["user_id"] == uid for r in ko_rows)
    if is_ko:
        consumed = await consume_medkit(uid)
        if consumed:
            await revive_player(cid, uid)
            return await call.answer("🧪 Вы использовали аптечку и поднялись из нокаута!", show_alert=True)
        return await call.answer("💀 Вы в нокауте! Попросите союзников написать 'хил' или купите аптечку в магазине.", show_alert=True)

    # Лечим первого упавшего союзника
    target = ko_rows[0]
    target_id = target["user_id"]
    target_name = target["first_name"] or "Боец"
    await revive_player(cid, target_id)

    gear = await get_user_combat_gear(uid)
    bonus_str = ""
    if gear["has_doc_kit"]:
        await db.add_balance(uid, 350)
        await db.add_xp(cid, uid, 60)
        bonus_str = " (+350 🪙 за Набор медика!)"

    await call.answer(f"💖 Вы успешно подняли {target_name} из нокаута!{bonus_str}", show_alert=True)
    try:
        await bot.send_message(
            cid,
            f"💖 {mention(call.from_user)} поднял бойца {mention_id(target_id, target_name)} из нокаута! Снова в бой! ⚔️"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("boss:top:"))
async def cb_boss_top(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[2])
    rows = await db.fetchall(
        "SELECT d.user_id, d.damage, d.attacks_count, u.first_name FROM boss_damage d "
        "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.chat_id=? ORDER BY d.damage DESC LIMIT 10",
        (cid,)
    )
    if not rows:
        return await call.answer("Пока никто не наносил урон этому боссу.", show_alert=True)

    lines = ["🏆 ТОП ДАМАГЕРОВ ТЕКУЩЕГО РЕЙДА:\n"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {r['first_name'] or str(r['user_id'])} — {r['damage']} урона ({r['attacks_count']} уд.)")

    await call.answer("\n".join(lines), show_alert=True)


# ══════════════════ 5. РАСЧЕТ БОЯ И КОНТРАТАКИ ══════════════════

async def _perform_attack(chat_id: int, user_id: int, user_name: str, bot: Bot) -> dict:
    """Выполняет расчет атаки по боссу, проверяет экипировку и контратаку босса."""
    row = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=? AND active=1", (chat_id,))
    if not row or row["current_hp"] <= 0:
        return {"error": "🐉 Сейчас в чате нет активного босса. Ждите следующего рейда!"}

    # 1. Проверка на нокаут
    if await is_player_knocked_out(chat_id, user_id):
        return {
            "error": "💀 Вы находитесь в нокауте!\nПопросите союзников написать «хил» или используйте «аптечка»."
        }

    now = time.time()
    dmg_row = await db.fetchone(
        "SELECT * FROM boss_damage WHERE chat_id=? AND user_id=?", (chat_id, user_id)
    )
    last_attack = dmg_row["last_attack_ts"] if dmg_row else 0
    cooldown = 8  # 8 секунд кулдаун между ударами

    if (now - last_attack) < cooldown:
        left = int(cooldown - (now - last_attack)) + 1
        return {"error": f"⏳ Перезарядка оружия! Подождите {left} сек."}

    # 2. Получаем экипировку игрока и VIP-статус
    gear = await get_user_combat_gear(user_id)
    user_row = await db.get_user(user_id)
    level_bonus = min(int(user_row.get("messages", 0) / 100), 60)

    # Проверка VIP-статуса
    v_lvl, _, v_act = await db.get_vip_info(user_id)

    base_dmg = random.randint(100, 200) + level_bonus
    dmg_mult = gear["dmg_mult"]
    is_crit = random.random() < 0.22  # 22% шанс крита

    if is_crit:
        if v_act and v_lvl >= 2:
            crit_mult = 3.5  # VIP+ Diamond МЕГА-крит x3.5
        elif v_act and v_lvl == 1:
            crit_mult = 3.0  # VIP крит x3.0
        else:
            crit_mult = 2.5  # Обычный крит x2.5
    else:
        crit_mult = 1.0

    final_dmg = int(base_dmg * dmg_mult * crit_mult)
    new_hp = max(0, row["current_hp"] - final_dmg)

    # 3. Сохраняем урон
    await db.execute(
        "INSERT INTO boss_damage (chat_id, user_id, damage, attacks_count, last_attack_ts) "
        "VALUES (?, ?, ?, 1, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET "
        "damage = damage + excluded.damage, attacks_count = attacks_count + 1, last_attack_ts = excluded.last_attack_ts",
        (chat_id, user_id, final_dmg, int(now))
    )

    # 4. Если босс повержен
    if new_hp <= 0:
        await db.execute("UPDATE chat_boss SET current_hp=0, active=0 WHERE chat_id=?", (chat_id,))
        defeat_text = await _distribute_boss_rewards(chat_id, row)
        return {
            "defeated": True,
            "text": defeat_text,
            "dmg": final_dmg,
            "is_crit": is_crit,
            "crit_mult": crit_mult,
            "vip_lvl": v_lvl if v_act else 0,
            "weapon_name": gear["weapon_name"],
            "left_hp": 0,
            "max_hp": row["max_hp"],
            "knocked_out": False
        }

    await db.execute("UPDATE chat_boss SET current_hp=? WHERE chat_id=?", (new_hp, chat_id))

    # 5. Расчет контратаки босса (нокаут игрока)
    base_counter_chance = 0.25 + (row["boss_level"] * 0.03)  # 28-37%
    if gear["has_armor"]:
        base_counter_chance *= 0.35  # Титановый бронежилет снижает шанс нокаута на 65%
    if v_act and v_lvl >= 2:
        base_counter_chance *= 0.40  # VIP+ снижает шанс нокаута на 60%
    elif v_act and v_lvl == 1:
        base_counter_chance *= 0.70  # VIP снижает шанс нокаута на 30%

    got_knocked_out = random.random() < base_counter_chance
    if got_knocked_out:
        await db.execute(
            "INSERT INTO boss_knockouts (chat_id, user_id, knocked_out_ts) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET knocked_out_ts=excluded.knocked_out_ts",
            (chat_id, user_id, int(now))
        )

    return {
        "defeated": False,
        "dmg": final_dmg,
        "is_crit": is_crit,
        "crit_mult": crit_mult,
        "vip_lvl": v_lvl if v_act else 0,
        "weapon_name": gear["weapon_name"],
        "left_hp": new_hp,
        "max_hp": row["max_hp"],
        "knocked_out": got_knocked_out
    }


async def _distribute_boss_rewards(chat_id: int, boss_row: dict) -> str:
    """Разделяет призовой куш между всеми участниками пропорционально урону."""
    damagers = await db.fetchall(
        "SELECT d.user_id, d.damage, d.attacks_count, u.first_name, u.username FROM boss_damage d "
        "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.chat_id=? ORDER BY d.damage DESC",
        (chat_id,)
    )

    # Очищаем нокауты рейда
    await db.execute("DELETE FROM boss_knockouts WHERE chat_id=?", (chat_id,))

    total_damage = sum(d["damage"] for d in damagers) or 1
    total_pool = boss_row["reward_pool"]
    total_xp = boss_row["reward_xp"]

    out = [
        f"🎉 ✨ <b>РЕЙДОВЫЙ БОСС {boss_row['boss_icon']} {boss_row['boss_name'].upper()} ПОВЕРЖЕН!</b> ✨ 🎉",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"💰 Общий призовой куш: <b>{money(total_pool)}</b> · <b>+{total_xp} XP</b>\n",
        "🏆 <b>ГЕРОИ БИТВЫ И НАГРАДЫ:</b>"
    ]

    medals = ["🥇", "🥈", "🥉"]

    for i, d in enumerate(damagers[:8], 1):
        uid = d["user_id"]
        dmg = d["damage"]
        share_pct = dmg / total_damage
        user_coins = max(60, int(total_pool * share_pct))
        user_xp = max(15, int(total_xp * share_pct))

        # Бонус топ-3
        if i == 1:
            user_coins += int(total_pool * 0.15)  # +15% победителю
        elif i == 2:
            user_coins += int(total_pool * 0.08)
        elif i == 3:
            user_coins += int(total_pool * 0.04)

        # Бонус VIP и VIP+
        v_lvl, _, v_act = await db.get_vip_info(uid)
        vip_tag = ""
        if v_act and v_lvl >= 2:
            user_coins = int(user_coins * 1.30)
            user_xp = int(user_xp * 1.30)
            vip_tag = " 🌟 <i>(VIP+ +30%)</i>"
        elif v_act and v_lvl == 1:
            vip_tag = " ⭐️"

        await db.add_balance(uid, user_coins)
        await db.add_xp(chat_id, uid, user_xp)

        icon = medals[i - 1] if i <= 3 else "🎖"
        name = html.escape(d["first_name"] or str(uid))
        out.append(f"{icon} <b>{name}</b>{vip_tag} — <code>{dmg} урона</code> ({int(share_pct * 100)}%)\n"
                   f"   └─▸ 💰 <b>+{money(user_coins)}</b> · <b>+{user_xp} XP</b>")

    out.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    spawns = await _get_daily_spawns(chat_id)
    out.append(f"📊 Боссов побеждено сегодня: <b>{spawns}/{MAX_DAILY_BOSSES}</b>")
    return "\n".join(out)


# ══════════════════ 6. АВТО-СПАВН ПО РАСПИСАНИЮ ══════════════════

async def boss_schedule_worker(bot: Bot):
    """Фоновый воркер: спавнит боссов по времени (08:00, 12:00, 16:00, 20:00)."""
    spawn_hours = {8, 12, 16, 20}
    last_spawned_hour = -1

    while True:
        try:
            await asyncio.sleep(40)
            now = datetime.now(timezone(timedelta(hours=3)))  # МСК
            if now.hour in spawn_hours and now.minute <= 2 and now.hour != last_spawned_hour:
                last_spawned_hour = now.hour
                chats = await db.fetchall("SELECT chat_id FROM chats WHERE silent=0")
                for c in chats:
                    cid = c["chat_id"]
                    btopic = await get_boss_topic(cid)

                    # Проверяем лимит
                    spawns = await _get_daily_spawns(cid)
                    if spawns < MAX_DAILY_BOSSES:
                        # Если тема не привязана — отправляем напоминание привязать тему
                        if not btopic:
                            try:
                                await bot.send_message(
                                    cid,
                                    f"⚠️ <b>[Рейды Боссов] Настало время появления Босса ({now.hour:02d}:00 МСК)!</b>\n\n"
                                    f"Чтобы боссы появлялись в чате по расписанию (08:00, 12:00, 16:00, 20:00), пожалуйста, привяжите тему для битв:\n"
                                    f"👉 Перейдите в нужную ветку и напишите: <code>+тема босс</code>"
                                )
                            except Exception:
                                pass
                            continue

                        # Проверяем, нет ли уже активного
                        act = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=? AND active=1", (cid,))
                        if not act or act["current_hp"] <= 0:
                            tmpl = BOSS_TEMPLATES[spawns % len(BOSS_TEMPLATES)]
                            await _inc_daily_spawns(cid)
                            await db.execute("DELETE FROM boss_damage WHERE chat_id=?", (cid,))
                            await db.execute("DELETE FROM boss_knockouts WHERE chat_id=?", (cid,))
                            await db.execute(
                                "INSERT INTO chat_boss (chat_id, boss_name, boss_icon, boss_level, max_hp, current_hp, reward_pool, reward_xp, spawn_time, active, last_msg_id) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0) ON CONFLICT(chat_id) DO UPDATE SET "
                                "boss_name=excluded.boss_name, boss_icon=excluded.boss_icon, boss_level=excluded.boss_level, "
                                "max_hp=excluded.max_hp, current_hp=excluded.current_hp, reward_pool=excluded.reward_pool, "
                                "reward_xp=excluded.reward_xp, spawn_time=excluded.spawn_time, active=1",
                                (cid, tmpl["name"], tmpl["icon"], tmpl["level"], tmpl["hp"], tmpl["hp"],
                                 tmpl["pool"], tmpl["xp"], int(time.time()))
                            )
                            row = await db.fetchone("SELECT * FROM chat_boss WHERE chat_id=?", (cid,))
                            card = f"🚨 <b>ВРЕМЯ РЕЙДА! ПОЯВИЛСЯ БОСС!</b> 🚨\n\n" + _boss_card(row)
                            try:
                                sent = await bot.send_message(
                                    cid, card,
                                    message_thread_id=btopic,
                                    reply_markup=_attack_kb(cid)
                                )
                                await db.execute("UPDATE chat_boss SET last_msg_id=? WHERE chat_id=?", (sent.message_id, cid))
                            except Exception:
                                pass
        except asyncio.CancelledError:
            break
        except Exception:
            pass
