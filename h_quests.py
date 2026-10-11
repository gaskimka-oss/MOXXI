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
