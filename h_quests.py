"""📜 Ежедневные Квесты и Боевой Пропуск (Battle Pass)."""
from __future__ import annotations

import html
import random
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, money

router = Router(name="quests")
S = 38  # Раздел: Квесты и достижения

ALL_QUEST_POOL = [
    {
        "id": "quest_boss",
        "title": "🐉 Нанести 800 урона Рейдовому Боссу",
        "target": 800,
        "reward_c": 600,
        "reward_xp": 120
    },
    {
        "id": "quest_duel",
        "title": "⚔️ Победить в 1 PvP-дуэли",
        "target": 1,
        "reward_c": 500,
        "reward_xp": 100
    },
    {
        "id": "quest_fish",
        "title": "🎣 Поймать 3 рыбы на рыбалке",
        "target": 3,
        "reward_c": 500,
        "reward_xp": 100
    },
    {
        "id": "quest_chat",
        "title": "💬 Написать 25 сообщений в чат",
        "target": 25,
        "reward_c": 400,
        "reward_xp": 80
    },
    {
        "id": "quest_rep",
        "title": "⭐️ Поблагодарить союзника (+реп)",
        "target": 1,
        "reward_c": 400,
        "reward_xp": 80
    },
    {
        "id": "quest_game",
        "title": "🎲 Сыграть 3 раза в любые игры/казино",
        "target": 3,
        "reward_c": 500,
        "reward_xp": 100
    }
]


def _today_key(tz_offset: int = 3) -> str:
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    return now.strftime("%Y-%m-%d")


async def get_or_create_daily_quests(user_id: int) -> list[dict]:
    day = _today_key()
    rows = await db.fetchall(
        "SELECT * FROM user_daily_quests WHERE user_id=? AND day=?", (user_id, day)
    )
    if rows:
        return [dict(r) for r in rows]

    # Выбираем 3 случайных квеста из пула
    selected = random.sample(ALL_QUEST_POOL, 3)
    for q in selected:
        await db.execute(
            "INSERT INTO user_daily_quests (user_id, day, quest_id, quest_title, target_count, current_count, reward_coins, reward_xp, completed, claimed) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, 0)",
            (user_id, day, q["id"], q["title"], q["target"], q["reward_c"], q["reward_xp"])
        )

    rows = await db.fetchall(
        "SELECT * FROM user_daily_quests WHERE user_id=? AND day=?", (user_id, day)
    )
    return [dict(r) for r in rows]


async def advance_quest(user_id: int, quest_id: str, amount: int = 1, bot: Bot | None = None, chat_id: int = 0):
    """Продвигает прогресс квеста игрока."""
    day = _today_key()
    row = await db.fetchone(
        "SELECT * FROM user_daily_quests WHERE user_id=? AND day=? AND quest_id=? AND completed=0",
        (user_id, day, quest_id)
    )
    if not row:
        return

    new_count = row["current_count"] + amount
    target = row["target_count"]

    if new_count >= target:
        await db.execute(
            "UPDATE user_daily_quests SET current_count=?, completed=1 WHERE user_id=? AND day=? AND quest_id=?",
            (target, user_id, day, quest_id)
        )
        # Уведомление о выполнении
        if bot and chat_id:
            try:
                await bot.send_message(
                    chat_id,
                    f"🎯 <b>КВЕСТ ВЫПОЛНЕН!</b>\n"
                    f"Задание: <i>{row['quest_title']}</i>\n"
                    f"Заберите награду командой: <code>квесты</code>!"
                )
            except Exception:
                pass
    else:
        await db.execute(
            "UPDATE user_daily_quests SET current_count=? WHERE user_id=? AND day=? AND quest_id=?",
            (new_count, user_id, day, quest_id)
        )


@router.message(Cmd("квесты", "задания дня", "дейлики", "боевой пропуск", "квесты дня", section=S, rank=0,
                    usage="квесты", desc="📜 Ежедневные задания и награды"))
async def cmd_quests(message: Message, bot: Bot, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if kw.get("args") and not had_prefix and in_group:
        return
    uid = message.from_user.id
    quests = await get_or_create_daily_quests(uid)

    text = [
        f"📜 ✨ <b>ЕЖЕДНЕВНЫЕ КВЕСТЫ: {html.escape(message.from_user.first_name)}</b> ✨ 📜",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Дата: <b>{_today_key()}</b>\n"
    ]

    all_done = True
    has_unclaimed = False

    for i, q in enumerate(quests, 1):
        cur = q["current_count"]
        tgt = q["target_count"]
        pct = min(1.0, cur / max(1, tgt))
        filled = int(round(pct * 6))
        bar = "█" * filled + "░" * (6 - filled)

        status = "✅ <b>ГОТОВО!</b>" if q["completed"] else f"[{bar}] {cur}/{tgt}"
        if q["claimed"]:
            status = "🎁 <i>Получено</i>"
        elif q["completed"]:
            has_unclaimed = True

        if not q["completed"]:
            all_done = False

        text.append(
            f"<b>{i}. {q['quest_title']}</b>\n"
            f"   └─▸ Прогресс: {status}\n"
            f"   └─▸ Награда: 💰 <b>+{money(q['reward_coins'])}</b> · ⚡️ <b>+{q['reward_xp']} XP</b>\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    if all_done:
        text.append("🎉 <b>ВСЕ КВЕСТЫ ВЫПОЛНЕНЫ!</b> Супер-награда дня разблокирована!")
    else:
        text.append("🎁 <b>Супер-бонус за все 3 квеста:</b> 📦 <b>Золотой кейс</b> + <b>2 000 монет</b>!")

    if has_unclaimed:
        text.append("\n👉 <i>Забрать награду:</i> <code>забрать квесты</code>")

    await message.reply("\n".join(text))


@router.message(Cmd("забрать квесты", "забрать награду", "квест забрать", section=S, rank=0,
                    usage="забрать квесты", desc="🎁 Получить награды за выполненные квесты"))
async def cmd_claim_quests(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    day = _today_key()
    rows = await db.fetchall(
        "SELECT * FROM user_daily_quests WHERE user_id=? AND day=? AND completed=1 AND claimed=0",
        (uid, day)
    )
    if not rows:
        return await message.reply("⚠️ У вас нет выполненных, но ещё не забранных квестов на сегодня.")

    total_coins = 0
    total_xp = 0
    for r in rows:
        total_coins += r["reward_coins"]
        total_xp += r["reward_xp"]
        await db.execute(
            "UPDATE user_daily_quests SET claimed=1 WHERE user_id=? AND day=? AND quest_id=?",
            (uid, day, r["quest_id"])
        )

    await db.add_balance(uid, total_coins)
    await db.add_xp(message.chat.id, uid, total_xp)

    # Проверяем, забраны ли ВСЕ 3 квеста
    all_q = await db.fetchall(
        "SELECT * FROM user_daily_quests WHERE user_id=? AND day=?", (uid, day)
    )
    super_bonus_text = ""
    if len(all_q) >= 3 and all(q["claimed"] for q in all_q):
        # Выдаем Золотой Кейс + 2 000 монет
        await db.add_balance(uid, 2000)
        await db.execute(
            "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
            "VALUES (?, 'case_gold', '🎁 Золотой кейс', 1, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1",
            (uid, int(time.time()))
        )
        super_bonus_text = (
            "\n\n👑 🌟 <b>СУПЕР-БОНУС ДНЯ ПОЛУЧЕН!</b> 🌟 👑\n"
            "Вы закрыли ВСЕ 3 ежедневных квеста!\n"
            "🎁 Награда: <b>🎁 Золотой кейс (1 шт.)</b> + 💰 <b>+2 000 монет</b>!"
        )

    await message.reply(
        f"🎉 ✨ <b>НАГРАДА ЗА КВЕСТЫ ПОЛУЧЕНА!</b> ✨ 🎉\n\n"
        f"👤 Игрок: {mention(message.from_user)}\n"
        f"💰 Монеты: <b>+{money(total_coins)}</b>\n"
        f"⚡️ Опыт: <b>+{total_xp} XP</b>{super_bonus_text}"
    )


# ══════════════════ 2. СЕЗОННЫЙ БОЕВОЙ ПРОПУСК (MOXXI CYBER PASS) ══════════════════

BP_TIER_REWARDS: dict[int, dict] = {
    1: {"coins": 5_000, "xp": 50, "desc": "💰 5 000 монет + 50 XP"},
    2: {"coins": 10_000, "xp": 100, "desc": "💰 10 000 монет + 100 XP"},
    3: {"case": "case_bronze", "case_name": "📦 Бронзовый кейс", "desc": "📦 Бронзовый кейс"},
    4: {"coins": 20_000, "desc": "💰 20 000 монет"},
    5: {"title": "⚡ Неоновый Новичок", "coins": 25_000, "desc": "👑 Титул «⚡ Неоновый Новичок» + 25k 🪙"},
    6: {"coins": 35_000, "desc": "💰 35 000 монет"},
    7: {"case": "case_silver", "case_name": "📦 Серебряный кейс", "desc": "📦 Серебряный кейс"},
    8: {"coins": 50_000, "desc": "💰 50 000 монет"},
    9: {"coins": 75_000, "desc": "💰 75 000 монет"},
    10: {"vip_days": 3, "coins": 100_000, "desc": "💎 VIP-статус на 3 дня + 100 000 🪙"},
    11: {"coins": 120_000, "desc": "💰 120 000 монет"},
    12: {"case": "case_gold", "case_name": "🎁 Золотой кейс", "desc": "🎁 Золотой кейс"},
    13: {"coins": 160_000, "desc": "💰 160 000 монет"},
    14: {"coins": 200_000, "desc": "💰 200 000 монет"},
    15: {"title": "🌆 Киберпанк", "coins": 250_000, "desc": "👑 Титул «🌆 Киберпанк» + 250k 🪙"},
    16: {"coins": 300_000, "desc": "💰 300 000 монет"},
    17: {"case": "case_gold", "case_name": "🎁 Золотой кейс", "count": 2, "desc": "🎁 Золотой кейс (2 шт.)"},
    18: {"coins": 400_000, "desc": "💰 400 000 монет"},
    19: {"coins": 500_000, "desc": "💰 500 000 монет"},
    20: {"vip_days": 7, "coins": 600_000, "desc": "💎 VIP-статус на 7 дней + 600 000 🪙"},
    21: {"coins": 750_000, "desc": "💰 750 000 монет"},
    22: {"case": "case_neon", "case_name": "🌌 Неоновый кейс", "desc": "🌌 Неоновый кейс"},
    23: {"coins": 900_000, "desc": "💰 900 000 монет"},
    24: {"coins": 1_100_000, "desc": "💰 1 100 000 монет"},
    25: {"title": "🔥 Доминатор", "coins": 1_300_000, "desc": "👑 Титул «🔥 Доминатор» + 1.3M 🪙"},
    26: {"coins": 1_600_000, "desc": "💰 1 600 000 монет"},
    27: {"coins": 2_000_000, "desc": "💰 2 000 000 монет"},
    28: {"case": "case_mythic", "case_name": "👑 Мифический кейс", "desc": "👑 Мифический кейс"},
    29: {"coins": 3_000_000, "desc": "💰 3 000 000 монет"},
    30: {"title": "👑 Легенда Сезона", "coins": 5_000_000, "desc": "🌌 5 000 000 🪙 + Титул «👑 Легенда Сезона»!"},
}


def _render_battlepass_text(user_name: str, bp: dict) -> tuple[str, InlineKeyboardMarkup]:
    lvl = bp["level"]
    xp = bp["xp"]
    XP_MAX = 500
    claimed = set(bp["claimed_levels"].split(",")) if bp["claimed_levels"] else set()

    bar_len = 10
    pct = min(1.0, xp / XP_MAX)
    filled = int(round(pct * bar_len))
    bar = "█" * filled + "░" * (bar_len - filled)

    unclaimed_count = sum(1 for i in range(1, lvl + 1) if str(i) not in claimed and i in BP_TIER_REWARDS)

    lines = [
        "🌟 ══════ • 🏆 <b>MOXXI BATTLE PASS</b> 🏆 • ══════ 🌟",
        "👑 <b>Сезон 1: «Неоновый Киберпанк»</b> 🌆",
        f"👤 Игрок: <b>{html.escape(user_name)}</b>\n",
        f"🎖 Уровень Пропуска: ⭐ <b>{lvl} LVL</b> / 30 LVL",
        f"⚡️ Опыт: [<code>{bar}</code>] <b>{xp} / {XP_MAX} XP</b> ({int(pct * 100)}%)\n",
    ]

    if unclaimed_count > 0:
        lines.append(f"🎁 <b>Готово к получению наград:</b> <b>{unclaimed_count} шт.</b>!\n")

    lines.append("✨ <b>НАГРАДЫ УРОВНЕЙ:</b>")
    # Показываем текущие и ближайшие 4 уровня
    start_show = max(1, lvl - 1)
    end_show = min(30, start_show + 4)
    for i in range(start_show, end_show + 1):
        r = BP_TIER_REWARDS.get(i, {"desc": "Награда"})
        if str(i) in claimed:
            tag = "✅ [Получено]"
        elif i <= lvl:
            tag = "🔓 <b>[ГОТОВО К СБОРУ!]</b>"
        else:
            need_xp = (i - lvl - 1) * XP_MAX + (XP_MAX - xp)
            tag = f"🔒 [{need_xp} XP]"
        lines.append(f"• <b>{i} LVL:</b> {r['desc']} — {tag}")

    lines.append("\n✦ ════════════════════════════════════ ✦")
    lines.append("💡 <i>Опыт даётся за задания, общение в чате, дуэли и бизнесы!</i>")

    buttons = []
    if unclaimed_count > 0:
        buttons.append([InlineKeyboardButton(text=f"🎁 Забрать награды ({unclaimed_count})", callback_data="bp:claim")])
    buttons.append([
        InlineKeyboardButton(text="📜 Задания дня", callback_data="bp:quests"),
        InlineKeyboardButton(text="🏆 Топ Сезона", callback_data="bp:top"),
    ])
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="bp:close")])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Cmd("пропуск", "бп", "pass", "сезон", "боевой пропуск", section=S, rank=0,
                    usage="пропуск", desc="🏆 Сезонный Боевой Пропуск (Battle Pass)"))
async def cmd_battlepass(message: Message, bot: Bot, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if kw.get("args") and not had_prefix and in_group:
        return
    uid = message.from_user.id
    bp = await db.get_battlepass(uid)
    text, kb = _render_battlepass_text(message.from_user.first_name, bp)
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(Cmd("забрать пропуск", "забрать бп", "бп забрать", section=S, rank=0,
                    usage="забрать пропуск", desc="🎁 Забрать разблокированные награды Пропуска"))
async def cmd_claim_battlepass(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    bp = await db.get_battlepass(uid)
    lvl = bp["level"]
    claimed = set(bp["claimed_levels"].split(",")) if bp["claimed_levels"] else set()

    to_claim = [i for i in range(1, lvl + 1) if str(i) not in claimed and i in BP_TIER_REWARDS]
    if not to_claim:
        return await message.reply("⚠️ У вас нет готовых к получению наград Пропуска. Повышайте уровень заданиями!")

    total_coins = 0
    items_given = []
    titles_given = []

    for l in to_claim:
        r = BP_TIER_REWARDS[l]
        if "coins" in r:
            total_coins += r["coins"]
        if "case" in r:
            c_cnt = r.get("count", 1)
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + ?",
                (uid, r["case"], r["case_name"], c_cnt, int(time.time()), c_cnt)
            )
            items_given.append(f"{r['case_name']} x{c_cnt}")
        if "title" in r:
            titles_given.append(r["title"])
            try:
                await db.unlock_user_title(uid, r["title"])
            except Exception:
                pass
        await db.claim_battlepass_level(uid, l)

    if total_coins > 0:
        await db.add_coins(uid, total_coins, "battlepass_reward")

    res = [
        "🎉 ✨ <b>НАГРАДЫ БОЕВОГО ПРОПУСКА ПОЛУЧЕНЫ!</b> ✨ 🎉",
        "✦ ══ • ⊰ 🏆 🎁 ⚡️ ⊱ • ══ ✦\n",
        f"👤 Игрок: {mention(message.from_user)}",
        f"🎖 Разблокировано уровней: <b>+{len(to_claim)} ур.</b>",
    ]
    if total_coins > 0:
        res.append(f"💰 Монеты: <b>+{money(total_coins)} 🪙</b>")
    if items_given:
        res.append(f"📦 Предметы: <b>{', '.join(items_given)}</b>")
    if titles_given:
        res.append(f"👑 Новый титул: <b>{', '.join(titles_given)}</b>")

    res.append("\n🔥 <i>Продолжайте выполнять задания и поднимайтесь в топ сезона!</i>")
    await message.reply("\n".join(res))


@router.message(Cmd("топ пропуск", "топ бп", "пропуск топ", section=S, rank=0,
                    usage="топ пропуск", desc="🏆 Топ игроков Сезонного Пропуска"))
async def cmd_top_battlepass(message: Message, bot: Bot, **kw):
    rows = await db.get_top_battlepass(10)
    if not rows:
        return await message.reply("🏆 Список лидеров Сезона пока пуст. Будьте первым!")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [
        "🏆 ══════ • <b>ТОП ЛИДЕРОВ СЕЗОНА</b> • ══════ 🏆",
        "👑 <b>Сезон 1: «Неоновый Киберпанк»</b>\n"
    ]
    for idx, r in enumerate(rows):
        m = medals[idx] if idx < len(medals) else f"{idx+1}."
        name = r.get("first_name") or f"Игрок {r['user_id']}"
        lines.append(f"{m} <b>{html.escape(name)}</b> — ⭐ <b>{r['level']} LVL</b> (<code>{r['xp']} XP</code>)")

    lines.append("\n✦ ════════════════════════════════════ ✦")
    lines.append("👉 <i>Открыть свой пропуск:</i> <code>пропуск</code>")
    await message.reply("\n".join(lines))


@router.callback_query(F.data.startswith("bp:"))
async def on_battlepass_callback(call: CallbackQuery, bot: Bot):
    action = call.data.split(":")[1]
    uid = call.from_user.id
    if action == "close":
        try:
            await call.message.delete()
        except Exception:
            pass
        return await call.answer()

    if action == "claim":
        bp = await db.get_battlepass(uid)
        lvl = bp["level"]
        claimed = set(bp["claimed_levels"].split(",")) if bp["claimed_levels"] else set()
        to_claim = [i for i in range(1, lvl + 1) if str(i) not in claimed and i in BP_TIER_REWARDS]
        if not to_claim:
            return await call.answer("⚠️ Все доступные награды уже получены!", show_alert=True)

        total_coins = 0
        for l in to_claim:
            r = BP_TIER_REWARDS[l]
            if "coins" in r:
                total_coins += r["coins"]
            if "case" in r:
                c_cnt = r.get("count", 1)
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + ?",
                    (uid, r["case"], r["case_name"], c_cnt, int(time.time()), c_cnt)
                )
            await db.claim_battlepass_level(uid, l)

        if total_coins > 0:
            await db.add_coins(uid, total_coins, "battlepass_reward")

        await call.answer(f"🎉 Забрано {len(to_claim)} наград! (+{money(total_coins)} монет)", show_alert=True)
        # Перерисовываем карточку
        bp_new = await db.get_battlepass(uid)
        text, kb = _render_battlepass_text(call.from_user.first_name, bp_new)
        try:
            await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        return

    if action == "quests":
        quests = await get_or_create_daily_quests(uid)
        q_lines = [f"📜 <b>Задания дня ({_today_key()}):</b>\n"]
        for i, q in enumerate(quests, 1):
            st = "✅" if q["completed"] else f"{q['current_count']}/{q['target_count']}"
            q_lines.append(f"{i}. {q['quest_title']} — [{st}]")
        await call.answer("\n".join(q_lines), show_alert=True)
        return

    if action == "top":
        rows = await db.get_top_battlepass(5)
        top_str = "🏆 Топ Сезона:\n" + "\n".join(f"{i+1}. {r.get('first_name','Игрок')}: {r['level']} LVL" for i, r in enumerate(rows))
        await call.answer(top_str, show_alert=True)
        return


# ══════════════════ 3. ИНТЕРАКТИВНЫЙ ЧАТ-ДРОП (СЕЙФ С МОНЕТАМИ) ══════════════════

_active_drops: dict[str, dict] = {}

@router.message(Cmd("дроп", "раздача", "drop", section=S, rank=0,
                    usage="дроп [сумма]", desc="💸 Бросить интерактивный сейф с монетами в чат"))
async def cmd_chat_drop(message: Message, bot: Bot, args: str = "", **kw):
    if message.chat.type == "private":
        return await message.reply("⚠️ Раздавать дропы можно только в групповых беседах!")

    parts = (args or "").strip().split()
    if not parts or not parts[0].isdigit():
        return await message.reply(
            "💸 <b>Интерактивный Чат-Дроп Мокси:</b>\n\n"
            "Вы бросаете сейф с монетами в чат, а участники соревнуются на скорость реакции, кто первый нажмёт кнопку!\n\n"
            "👉 Формат: <code>дроп [сумма]</code>\n"
            "👉 Пример: <code>дроп 50000</code> · <code>дроп 100000</code>"
        )

    amount = int(parts[0])
    if amount < 500:
        return await message.reply("⚠️ Минимальная сумма дропа: <b>500 монет</b>.")
    if amount > 100_000_000:
        return await message.reply("⚠️ Максимальная сумма одного дропа: <b>100 000 000 монет</b>.")

    uid = message.from_user.id
    bal = await db.get_coins(uid)
    if bal < amount:
        return await message.reply(
            f"❌ <b>Недостаточно монет!</b>\n\n"
            f"Ваш баланс: <b>{money(bal)} 🪙</b>\n"
            f"Требуется: <b>{money(amount)} 🪙</b>"
        )

    # Списываем сумму с отправителя
    await db.add_coins(uid, -amount, "chat_drop_create")

    drop_id = f"{message.chat.id}_{int(time.time()*1000)}_{random.randint(100, 999)}"
    _active_drops[drop_id] = {
        "chat_id": message.chat.id,
        "sender_id": uid,
        "sender_name": message.from_user.first_name,
        "amount": amount,
        "created_at": time.time(),
        "claimed": False,
        "winner_id": None,
        "winner_name": None,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔓 Взломать сейф (+{money(amount)} 🪙)!", callback_data=f"drop:claim:{drop_id}")]
    ])

    text = (
        "💸 ✨ <b>ИНТЕРАКТИВНЫЙ ДРОП МОКСИ!</b> ✨ 💸\n"
        "✦ ══ • ⊰ 💰 🎁 ⚡️ ⊱ • ══ ✦\n\n"
        f"👤 Щедрый спонсор: <b>{html.escape(message.from_user.first_name)}</b>\n"
        f"💰 В сейфе: <b>{money(amount)} 🪙</b>\n"
        "🎲 <i>Кто успеет первым нажать кнопку и взломать замок?!</i>\n\n"
        "👇 <b>Жмите кнопку ниже быстрее всех:</b>"
    )

    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("drop:claim:"))
async def on_drop_claim_callback(call: CallbackQuery, bot: Bot):
    drop_id = call.data.split(":", 2)[2]
    drop = _active_drops.get(drop_id)
    if not drop:
        return await call.answer("❌ Этот сейф уже давно взломан или истёк!", show_alert=True)

    if drop["claimed"]:
        return await call.answer("❌ Сейф уже успел забрать другой игрок!", show_alert=False)

    winner_id = call.from_user.id
    # Защита от самосбора в первые 5 секунд (чтобы создатель дал шанс другим)
    if winner_id == drop["sender_id"] and (time.time() - drop["created_at"]) < 5:
        return await call.answer("⏳ Создатель дропа может забрать его назад только через 5 секунд!", show_alert=True)

    # Атомарный захват дропа
    drop["claimed"] = True
    drop["winner_id"] = winner_id
    winner_name = call.from_user.first_name
    drop["winner_name"] = winner_name
    reaction_time = time.time() - drop["created_at"]
    amount = drop["amount"]

    # Начисляем монеты и сезонный опыт за победу в дропе
    await db.add_coins(winner_id, amount, "chat_drop_win")
    try:
        await db.add_battlepass_xp(winner_id, 30)
    except Exception:
        pass

    await call.answer(f"🎉 ПОЗДРАВЛЯЕМ! Вы успели первым и забрали {money(amount)} 🪙!", show_alert=True)

    win_text = (
        "🎉 ✨ <b>СЕЙФ УСПЕШНО ВЗЛОМАН!</b> ✨ 🎉\n"
        "✦ ══ • ⊰ 🏆 💰 ⚡️ ⊱ • ══ ✦\n\n"
        f"🏆 Победитель: <b>{html.escape(winner_name)}</b>!\n"
        f"💰 Выигрыш: <b>+{money(amount)} 🪙</b> зачислен на баланс!\n"
        f"⚡️ Скорость реакции: <b>{reaction_time:.2f} сек.</b>\n"
        f"👤 Спонсор: <i>{html.escape(drop['sender_name'])}</i>"
    )

    try:
        await call.message.edit_text(win_text, reply_markup=None)
    except Exception:
        pass

    # Очищаем память
    _active_drops.pop(drop_id, None)
