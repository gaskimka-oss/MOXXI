"""
🧭 МОДУЛЬ «ИССЛЕДОВАТЕЛЬ КОМАНД И ЧАТ-ЧЕЛЛЕНДЖИ» (Command Explorer Engine)
Решает проблему неиспользуемых команд:
1. Коллекция открытых команд игрока (из 822 команд MOXXI).
2. Награды и титулы за достижение порогов (10, 25, 50, 100, 200, 300 команд).
3. Внезапные вызовы чата (Chat Challenges): бот дропает задание применить редкие команды
   с мгновенной денежной и снежной наградой тому, кто введёт первым.
4. Случайная команда дня и рекомендации неизученных механик.
"""
from __future__ import annotations

import html
import json
import random
import time
from typing import Any

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
from core_ranks import require
from core_registry import Cmd, REGISTRY
from utils import mention, mention_id

router = Router(name="command_discovery")
S = 38  # Раздел: Квесты, достижения и ивенты

# Пороги наград за открытие команд
THRESHOLDS = [
    (10, 5000, 10, "🥉 Искатель"),
    (25, 20000, 25, "🥈 Странник"),
    (50, 50000, 50, "🥇 Следопыт"),
    (100, 150000, 100, "👑 Знаток MOXXI"),
    (200, 350000, 200, "🔮 Магистр Вселенной"),
    (300, 750000, 500, "⚡️ Легендарный Первооткрыватель")
]

# Исключаем сугубо служебные/админские команды из пула случайных челленджей
EXCLUDED_FROM_CHALLENGE = {
    "бан", "кик", "мут", "варн", "пред", "разбан", "размут", "снять", "повысить",
    "понизить", "старт", "help", "меню", "дк", "чек", "ограничить", "амнистия"
}


async def init_discovery_db() -> None:
    """Инициализация таблиц базы данных для системы открытий и челленджей."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_discovered_commands (
            user_id INTEGER NOT NULL,
            cmd_key TEXT NOT NULL,
            discovered_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, cmd_key)
        );
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_disc_user ON user_discovered_commands(user_id);"
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_active_challenges (
            chat_id INTEGER PRIMARY KEY,
            target_cmds TEXT NOT NULL,
            reward_coins INTEGER NOT NULL,
            reward_flakes INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            winner_id INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_discovery_rewards (
            user_id INTEGER NOT NULL,
            threshold INTEGER NOT NULL,
            claimed_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, threshold)
        );
        """
    )


async def record_command_use(user_id: int, cmd_key: str, chat_id: int, bot: Bot | None = None) -> None:
    """Фиксация использования команды, проверка челленджа чата и выдача наград за вехи."""
    if not user_id or not cmd_key:
        return

    now_ts = int(time.time())
    try:
        await init_discovery_db()

        # 1. Запись открытия команды
        await db.execute(
            "INSERT OR IGNORE INTO user_discovered_commands (user_id, cmd_key, discovered_at) VALUES (?,?,?)",
            (user_id, cmd_key.lower(), now_ts)
        )

        # 2. Проверка активного челленджа в этом чате
        if chat_id < 0:
            chal = await db.fetchone(
                "SELECT * FROM chat_active_challenges WHERE chat_id=? AND completed=0",
                (chat_id,)
            )
            if chal:
                exp = chal["expires_at"]
                if now_ts <= exp:
                    try:
                        targets = json.loads(chal["target_cmds"])
                    except Exception:
                        targets = []
                    if cmd_key.lower() in [t.lower() for t in targets]:
                        # Завершение челленджа победителем
                        await db.execute(
                            "UPDATE chat_active_challenges SET completed=1, winner_id=? WHERE chat_id=?",
                            (user_id, chat_id)
                        )
                        r_coins = chal["reward_coins"]
                        r_flakes = chal["reward_flakes"]
                        await db.add_balance(user_id, r_coins)
                        if r_flakes > 0:
                            await db.add_user_snowflakes(user_id, r_flakes)

                        if bot is not None:
                            u_info = await db.get_user(user_id)
                            u_name = u_info["first_name"] or u_info["username"] or f"Игрок {user_id}"
                            u_link = mention_id(user_id, u_name)

                            win_text = (
                                "⚡️ ══ 🏆 ══ 🎯 <b>ЧЕЛЛЕНДЖ ЧАТА ЗАВЕРШЁН!</b> 🎯 ══ 🏆 ══ ⚡️\n\n"
                                f"👤 <b>{u_link}</b> первым активировал целевую команду <code>{cmd_key}</code>!\n\n"
                                "🎁 <b>Праздничная награда победителя:</b>\n"
                                f"• <b>+{r_coins:,} 🌑 Граммов</b> на баланс\n"
                                f"• <b>+{r_flakes:,} ❄️ Снежинок</b> в зимний мешок\n\n"
                                "✨ <i>Продолжайте исследовать команды MOXXI! Новый вызов скоро появится в чате!</i>"
                            )
                            try:
                                await bot.send_message(chat_id, win_text)
                            except Exception:
                                pass
                else:
                    # Челлендж просрочен
                    await db.execute(
                        "UPDATE chat_active_challenges SET completed=1, winner_id=0 WHERE chat_id=?",
                        (chat_id,)
                    )

        # 3. Проверка достижения вех наград
        row_cnt = await db.fetchone(
            "SELECT COUNT(*) as c FROM user_discovered_commands WHERE user_id=?",
            (user_id,)
        )
        total_disc = row_cnt["c"] if row_cnt else 0

        for thresh, rew_c, rew_f, title in THRESHOLDS:
            if total_disc >= thresh:
                already = await db.fetchone(
                    "SELECT 1 FROM user_discovery_rewards WHERE user_id=? AND threshold=?",
                    (user_id, thresh)
                )
                if not already:
                    await db.execute(
                        "INSERT INTO user_discovery_rewards (user_id, threshold, claimed_at) VALUES (?,?,?)",
                        (user_id, thresh, now_ts)
                    )
                    await db.add_balance(user_id, rew_c)
                    if rew_f > 0:
                        await db.add_user_snowflakes(user_id, rew_f)

                    if bot is not None and chat_id:
                        u_info = await db.get_user(user_id)
                        u_name = u_info["first_name"] or u_info["username"] or f"Игрок {user_id}"
                        u_link = mention_id(user_id, u_name)
                        reward_msg = (
                            f"🧭 <b>ДОСТИЖЕНИЕ ИССЛЕДОВАТЕЛЯ!</b>\n\n"
                            f"🎉 {u_link} открыл <b>{thresh} уникальных команд</b> бота!\n"
                            f"🎖 Ранг: <b>{title}</b>\n"
                            f"🎁 Награда: <b>+{rew_c:,} 🌑 Грамм</b> и <b>+{rew_f:,} ❄️ Снежинок</b>!"
                        )
                        try:
                            await bot.send_message(chat_id, reward_msg)
                        except Exception:
                            pass
    except Exception:
        pass


@router.message(Cmd("исследователь", "мои команды", "коллекция", "открыто", "прогресс команд", section=S,
                    usage="исследователь", desc="🧭 Прогресс изучения 822 команд бота и награды"))
async def cmd_explorer(message: Message, bot: Bot, **kw):
    await init_discovery_db()
    uid = message.from_user.id
    row_cnt = await db.fetchone(
        "SELECT COUNT(*) as c FROM user_discovered_commands WHERE user_id=?",
        (uid,)
    )
    user_count = row_cnt["c"] if row_cnt else 0
    total_all = len(REGISTRY) or 822
    pct = round((user_count / total_all) * 100, 1)

    # Определяем текущий ранг
    cur_rank = "🌱 Новичок"
    next_thresh = THRESHOLDS[0]
    for thresh, coins, flakes, title in THRESHOLDS:
        if user_count >= thresh:
            cur_rank = title
        else:
            next_thresh = (thresh, coins, flakes, title)
            break

    # Ищем 3 случайные команды, которые игрок ещё не открыл
    user_cmds_rows = await db.fetchall(
        "SELECT cmd_key FROM user_discovered_commands WHERE user_id=?",
        (uid,)
    )
    known = {r["cmd_key"].lower() for r in user_cmds_rows}
    all_unopened = [c for c in REGISTRY if c.key.lower() not in known and c.key.lower() not in EXCLUDED_FROM_CHALLENGE]
    sample_cmds = random.sample(all_unopened, min(3, len(all_unopened))) if all_unopened else []

    tips = []
    for c in sample_cmds:
        desc = c.desc or "Интересная механика"
        tips.append(f"• <code>{c.usage or c.key}</code> — <i>{desc}</i>")
    tips_str = "\n".join(tips) if tips else "🎉 <i>Вы открыли все доступные команды бота!</i>"

    text = (
        "🧭 ══ 📜 ══ 🌟 <b>ИССЛЕДОВАТЕЛЬ ВСЕЛЕННОЙ MOXXI</b> 🌟 ══ 📜 ══ 🧭\n\n"
        f"👤 <b>Игрок:</b> {mention(message.from_user)}\n"
        f"📊 <b>Открыто команд:</b> <b>{user_count}</b> из <b>{total_all}</b> (<b>{pct}%</b>)\n"
        f"🎖 <b>Ваш статус:</b> <b>{cur_rank}</b>\n\n"
        f"🎯 <b>Следующая награда на {next_thresh[0]} команд:</b>\n"
        f"• +{next_thresh[1]:,} 🌑 Граммов\n"
        f"• +{next_thresh[2]:,} ❄️ Снежинок\n\n"
        "💡 <b>Команды, которые вы ещё не пробовали:</b>\n"
        f"{tips_str}\n\n"
        "✨ <i>Используйте новые команды в чате и забирайте крутые бонусы!</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Случайная команда", callback_data="disc:random_cmd"),
            InlineKeyboardButton(text="🎯 Челлендж чата", callback_data="disc:show_chal")
        ]
    ])
    await message.reply(text, reply_markup=kb)


@router.message(Cmd("челлендж", "вызов", "ивент чата", "задание чата", section=S, group_only=True,
                    usage="челлендж", desc="🎯 Просмотр текущего испытания чата"))
async def cmd_challenge(message: Message, bot: Bot, **kw):
    await init_discovery_db()
    cid = message.chat.id
    now_ts = int(time.time())

    chal = await db.fetchone(
        "SELECT * FROM chat_active_challenges WHERE chat_id=? AND completed=0",
        (cid,)
    )

    if not chal or now_ts > chal["expires_at"]:
        # Если нет или истек — создаем новый сочный челлендж!
        new_chal = await _create_chat_challenge(cid)
        chal = new_chal

    left_sec = max(0, chal["expires_at"] - now_ts)
    mins = left_sec // 60
    secs = left_sec % 60

    try:
        targets = json.loads(chal["target_cmds"])
    except Exception:
        targets = ["рыбалка", "крафт", "гороскоп"]

    targets_fmt = "  ·  ".join([f"<code>{t}</code>" for t in targets])

    text = (
        "⚡️ ══ 🎯 ══ 🎁 <b>ВНЕЗАПНЫЙ ЧЕЛЛЕНДЖ ЧАТА!</b> 🎁 ══ 🎯 ══ ⚡️\n\n"
        "Дедушка Мороз и MOXXI бросают вызов всей беседке!\n"
        "Кто первым применит в этом чате одну из команд:\n\n"
        f"👉  {targets_fmt}  👈\n\n"
        "💰 <b>Награда первому, кто введёт:</b>\n"
        f"• <b>+{chal['reward_coins']:,} 🌑 Граммов</b>\n"
        f"• <b>+{chal['reward_flakes']:,} ❄️ Снежинок</b>\n\n"
        f"⏳ <i>Времени осталось: <b>{mins} мин. {secs} сек.</b></i>\n"
        "🏃‍♂️ <i>Быстрее пишите команду в чат, пока её не забрали другие!</i>"
    )
    await message.reply(text)


async def _create_chat_challenge(chat_id: int) -> dict[str, Any]:
    """Генерирует свежий случайный челлендж для чата."""
    candidates = [
        c.key for c in REGISTRY
        if c.key not in EXCLUDED_FROM_CHALLENGE and len(c.key) >= 3 and not c.group_only
    ]
    if len(candidates) < 4:
        candidates = ["рыбалка", "крафт", "гороскоп", "анекдот", "амулет", "подземелье", "кубик", "шаблон", "профиль"]

    chosen = random.sample(candidates, 3)
    r_coins = random.choice([10000, 15000, 20000, 25000])
    r_flakes = random.choice([10, 15, 20, 25])
    expires_at = int(time.time()) + 1800  # 30 минут на выполнение

    await db.execute(
        """
        INSERT INTO chat_active_challenges (chat_id, target_cmds, reward_coins, reward_flakes, expires_at, winner_id, completed, created_at)
        VALUES (?,?,?,?,?,0,0,?)
        ON CONFLICT(chat_id) DO UPDATE SET
            target_cmds=excluded.target_cmds,
            reward_coins=excluded.reward_coins,
            reward_flakes=excluded.reward_flakes,
            expires_at=excluded.expires_at,
            winner_id=0,
            completed=0,
            created_at=excluded.created_at
        """,
        (chat_id, json.dumps(chosen, ensure_ascii=False), r_coins, r_flakes, expires_at, int(time.time()))
    )
    return {
        "chat_id": chat_id,
        "target_cmds": json.dumps(chosen, ensure_ascii=False),
        "reward_coins": r_coins,
        "reward_flakes": r_flakes,
        "expires_at": expires_at,
        "completed": 0
    }


@router.message(Cmd("+челлендж", "новый челлендж", "запустить челлендж", section=S, rank=2, group_only=True,
                    usage="+челлендж", desc="Запустить внезапное состязание команд в чате (для админов)"))
async def cmd_start_challenge_admin(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return
    await init_discovery_db()
    chal = await _create_chat_challenge(message.chat.id)
    targets = json.loads(chal["target_cmds"])
    targets_fmt = "  ·  ".join([f"<code>{t}</code>" for t in targets])
    await message.reply(
        "⚡️ <b>НОВЫЙ ЧЕЛЛЕНДЖ УСПЕШНО ЗАПУЩЕН АДМИНИСТРАТОРОМ!</b>\n\n"
        f"Целевые команды: {targets_fmt}\n"
        f"🎁 Награда: <b>+{chal['reward_coins']:,} грамм</b> и <b>+{chal['reward_flakes']:,} ❄️ Снежинок</b>!\n"
        "⏳ Испытание активно 30 минут!"
    )


@router.message(Cmd("рандом команда", "случайная команда", "что попробовать", "рандомная команда", section=S,
                    usage="рандом команда", desc="🎲 Показать случайную интересную команду"))
async def cmd_random_command(message: Message, **kw):
    valid = [c for c in REGISTRY if c.key not in EXCLUDED_FROM_CHALLENGE and not c.group_only]
    if not valid:
        valid = REGISTRY
    c = random.choice(valid)
    synonyms = ", ".join([f"<code>{n}</code>" for n in c.names[:4]])
    desc = c.desc or "Интересная механика бота"

    text = (
        "🎲 <b>СЛУЧАЙНАЯ КОМАНДА ДНЯ</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"📌 <b>Команда:</b> <code>{c.usage or c.key}</code>\n"
        f"📖 <b>Описание:</b> <i>{desc}</i>\n"
        f"🏷 <b>Синонимы:</b> {synonyms}\n\n"
        f"👉 <i>Попробуйте ввести её прямо сейчас:</i> <code>{c.usage or c.key}</code>"
    )
    await message.reply(text)


@router.callback_query(F.data == "disc:random_cmd")
async def cb_random_cmd(call: CallbackQuery):
    valid = [c for c in REGISTRY if c.key not in EXCLUDED_FROM_CHALLENGE and not c.group_only]
    if not valid:
        valid = REGISTRY
    c = random.choice(valid)
    desc = c.desc or "Интересная механика бота"
    await call.answer()
    await call.message.reply(
        f"🎲 <b>Попробуйте команду:</b> <code>{c.usage or c.key}</code>\n"
        f"📖 <i>{desc}</i>"
    )


@router.callback_query(F.data == "disc:show_chal")
async def cb_show_chal(call: CallbackQuery, bot: Bot):
    await call.answer()
    if call.message.chat.type == "private":
        return await call.message.reply("🎯 Челленджи проводятся в группах и беседах!")
    chal = await db.fetchone(
        "SELECT * FROM chat_active_challenges WHERE chat_id=? AND completed=0",
        (call.message.chat.id,)
    )
    if not chal:
        chal = await _create_chat_challenge(call.message.chat.id)
    targets = json.loads(chal["target_cmds"])
    targets_fmt = "  ·  ".join([f"<code>{t}</code>" for t in targets])
    await call.message.reply(
        "⚡️ <b>АКТИВНЫЙ ЧЕЛЛЕНДЖ ЧАТА:</b>\n\n"
        f"🎯 Введите первым: {targets_fmt}\n"
        f"🎁 Награда: <b>+{chal['reward_coins']:,} грамм</b> и <b>+{chal['reward_flakes']:,} ❄️ Снежинок</b>!"
    )
