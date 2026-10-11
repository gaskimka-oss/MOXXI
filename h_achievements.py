"""🏆 Система Достижений, Ачивок и Титулов игрока."""
from __future__ import annotations

import html
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, mention_id, money

router = Router(name="achievements")
S = 38  # Раздел: Квесты и достижения

ACHIEVEMENTS = {
    "ach_boss_first": {
        "id": "ach_boss_first",
        "icon": "🩸",
        "name": "Первая кровь",
        "desc": "Нанести свой первый удар по Рейдовому Боссу",
        "reward_c": 1000,
        "reward_xp": 100
    },
    "ach_boss_slayer": {
        "id": "ach_boss_slayer",
        "icon": "👑",
        "name": "Истребитель Боссов",
        "desc": "Нанести суммарно более 25 000 урона по боссам",
        "reward_c": 6000,
        "reward_xp": 500
    },
    "ach_angel": {
        "id": "ach_angel",
        "icon": "🚑",
        "name": "Ангел-Спаситель",
        "desc": "Воскресить союзников из нокаута во время рейда",
        "reward_c": 2500,
        "reward_xp": 250
    },
    "ach_millionaire": {
        "id": "ach_millionaire",
        "icon": "💰",
        "name": "Олигарх Moxxi",
        "desc": "Накопить баланс свыше 50 000 монет",
        "reward_c": 5000,
        "reward_xp": 400
    },
    "ach_duel_master": {
        "id": "ach_duel_master",
        "icon": "🤠",
        "name": "Гроза Дуэлянтов",
        "desc": "Победить хотя бы в 3 PvP-дуэлях",
        "reward_c": 2500,
        "reward_xp": 250
    },
    "ach_fisherman": {
        "id": "ach_fisherman",
        "icon": "🎣",
        "name": "Старый Мореход",
        "desc": "Поймать более 10 рыб на рыбалке",
        "reward_c": 2000,
        "reward_xp": 200
    },
    "ach_kraken": {
        "id": "ach_kraken",
        "icon": "🐙",
        "name": "Покоритель Глубин",
        "desc": "Выловить легендарного Кракена или Золотую рыбку",
        "reward_c": 8000,
        "reward_xp": 700
    },
    "ach_rep_star": {
        "id": "ach_rep_star",
        "icon": "🌟",
        "name": "Человек Чести",
        "desc": "Заработать 25+ очков репутации от участников",
        "reward_c": 3000,
        "reward_xp": 300
    },
    "ach_chatter": {
        "id": "ach_chatter",
        "icon": "💬",
        "name": "Душа Компании",
        "desc": "Отправить более 300 сообщений в чат",
        "reward_c": 2000,
        "reward_xp": 200
    },
    "ach_gear_full": {
        "id": "ach_gear_full",
        "icon": "🛡️",
        "name": "Тяжеловооружен",
        "desc": "Иметь в инвентаре Меч/Бластер и Бронежилет",
        "reward_c": 4000,
        "reward_xp": 400
    },
    "ach_crafter": {
        "id": "ach_crafter",
        "icon": "🛠",
        "name": "Мастер-Кузнец",
        "desc": "Скрафтить хотя бы один предмет на верстаке",
        "reward_c": 2500,
        "reward_xp": 250
    }
}


async def award_achievement(chat_id: int, user_id: int, ach_id: str, bot: Bot | None = None) -> bool:
    """Выдает достижение игроку, если оно еще не получено."""
    if ach_id not in ACHIEVEMENTS:
        return False

    already = await db.fetchone(
        "SELECT 1 FROM user_achievements WHERE user_id=? AND ach_id=?",
        (user_id, ach_id)
    )
    if already:
        return False

    ach = ACHIEVEMENTS[ach_id]
    await db.execute(
        "INSERT INTO user_achievements (user_id, ach_id, unlocked_at) VALUES (?, ?, ?)",
        (user_id, ach_id, int(time.time()))
    )

    await db.add_balance(user_id, ach["reward_c"])
    await db.add_xp(chat_id, user_id, ach["reward_xp"])

    if bot and chat_id:
        u = await db.get_user(user_id)
        name = u.get("first_name") or "Боец"
        text = (
            f"🏆 ✨ <b>НОВОЕ ДОСТИЖЕНИЕ РАЗБЛОКИРОВАНО!</b> ✨ 🏆\n\n"
            f"👤 {mention_id(user_id, name)} получил достижение:\n"
            f"<b>{ach['icon']} {ach['name']}</b>\n"
            f"📜 <i>{ach['desc']}</i>\n"
            f"🎁 Награда: 💰 <b>+{money(ach['reward_c'])}</b> · ⚡️ <b>+{ach['reward_xp']} XP</b>"
        )
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            pass
    return True


@router.message(Cmd("достижения", "ачивки", "мои ачивки", "титулы", section=S, rank=0,
                    usage="достижения", desc="🏆 Список ваших открытых и заблокированных достижений"))
async def cmd_achievements(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    unlocked_rows = await db.fetchall(
        "SELECT ach_id FROM user_achievements WHERE user_id=?", (uid,)
    )
    unlocked_set = {r["ach_id"] for r in unlocked_rows}
    total_count = len(ACHIEVEMENTS)
    unlocked_count = len(unlocked_set)
    pct = int((unlocked_count / total_count) * 100)

    text = [
        f"🏆 ✨ <b>ДОСТИЖЕНИЯ: {html.escape(message.from_user.first_name)}</b> ✨ 🏆",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"Прогресс: <b>{unlocked_count}/{total_count}</b> (<b>{pct}%</b>)\n"
    ]

    for k, a in ACHIEVEMENTS.items():
        if k in unlocked_set:
            text.append(f"✅ <b>{a['icon']} {a['name']}</b> — <i>{a['desc']}</i>")
        else:
            text.append(f"🔒 <b>{a['icon']} {a['name']}</b> — <i>{a['desc']}</i> (+{money(a['reward_c'])})")

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Рейтинг лидеров:</i> <code>топ ачивок</code>")
    await message.reply("\n".join(text))


@router.message(Cmd("топ ачивок", "топ достижений", section=S, rank=0,
                    usage="топ ачивок", desc="🏆 Рейтинг игроков по количеству достижений"))
async def cmd_top_achievements(message: Message, bot: Bot, **kw):
    rows = await db.fetchall(
        "SELECT a.user_id, COUNT(a.ach_id) as count, u.first_name FROM user_achievements a "
        "LEFT JOIN users u ON u.user_id=a.user_id "
        "GROUP BY a.user_id ORDER BY count DESC LIMIT 10"
    )
    if not rows:
        return await message.reply("🏆 Достижения пока никто не разблокировал. Будьте первыми!")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = [
        "🏆 ✨ <b>ТОП ПО ДОСТИЖЕНИЯМ</b> ✨ 🏆",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    for i, r in enumerate(rows):
        icon = medals[i] if i < len(medals) else "▫️"
        name = html.escape(r["first_name"] or str(r["user_id"]))
        text.append(f"{icon} <b>{name}</b> — 🏆 <b>{r['count']}/{len(ACHIEVEMENTS)} ачивок</b>")

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Ваши ачивки:</i> <code>достижения</code>")
    await message.reply("\n".join(text))
