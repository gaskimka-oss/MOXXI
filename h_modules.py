"""Разделы 17–27, 30–31: кланы, кружки, отношения, браки, репутация,
награды, закладки, заметки, таймеры, каталог, биржа, репорты, розыгрыши."""
from __future__ import annotations

import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
import core_members as members
from config import REP_COOLDOWN
from core_ranks import require
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from utils import hms, mention, mention_id, money, parse_amount

router = Router(name="modules")
(S_CLAN, S_CIRCLE, S_REL, S_MARRY, S_REP, S_AWARD, S_BOOK,
 S_NOTE, S_TIMER, S_CAT, S_MARKET, S_REPORT, S_GIVE) = (
    17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 30, 31)


# ================= 17. КЛАНЫ =================
@router.message(Cmd("создать клан", "клан создать", section=S_CLAN,
                    usage="создать клан {название}", desc="Создать клан"))
async def clan_create(message: Message, args: str = "", **kw):
    name = (args or "").strip()
    if not name:
        return await message.reply("Формат: <code>создать клан Драконы</code>")
    if await db.fetchone("SELECT 1 FROM clan_members WHERE user_id=?", (message.from_user.id,)):
        return await message.reply("Вы уже состоите в клане. Сначала <code>выйти из клана</code>.")
    if await db.fetchone("SELECT 1 FROM clans WHERE lower(name)=lower(?)", (name,)):
        return await message.reply("Клан с таким названием уже есть.")
    u = await db.get_user(message.from_user.id)
    if u["balance"] < 5000:
        return await message.reply(f"Создание клана стоит {money(5000)}. У вас {money(u['balance'])}.")
    await db.add_balance(message.from_user.id, -5000, "clan_create")
    await db.execute("INSERT INTO clans (name, owner_id, ts) VALUES (?,?,?)",
                     (name, message.from_user.id, int(time.time())))
    row = await db.fetchone("SELECT id FROM clans WHERE name=?", (name,))
    await db.execute("INSERT INTO clan_members (clan_id, user_id, ts) VALUES (?,?,?)",
                     (row["id"], message.from_user.id, int(time.time())))
    await message.reply(f"🏰 Клан <b>{html.escape(name)}</b> создан! Вы его глава.")


@router.message(Cmd("клан", "мой клан", section=S_CLAN, usage="клан", desc="Информация о клане"))
async def clan_info(message: Message, args: str = "", **kw):
    name = (args or "").strip()
    if name:
        clan = await db.fetchone("SELECT * FROM clans WHERE lower(name)=lower(?)", (name,))
    else:
        cm = await db.fetchone("SELECT clan_id FROM clan_members WHERE user_id=?",
                               (message.from_user.id,))
        clan = await db.fetchone("SELECT * FROM clans WHERE id=?", (cm["clan_id"],)) if cm else None
    if not clan:
        return await message.reply("Клан не найден. Создать: <code>создать клан Название</code>")
    members = await db.fetchall(
        "SELECT m.user_id, u.first_name FROM clan_members m LEFT JOIN users u "
        "ON u.user_id=m.user_id WHERE m.clan_id=?", (clan["id"],))
    owner = await db.get_user(clan["owner_id"])
    lst = "\n".join(f"  • {mention_id(m['user_id'], m['first_name'])}" for m in members[:20])
    await message.reply(
        f"🏰 <b>{html.escape(clan['name'])}</b>\n"
        f"👑 Глава: {mention_id(clan['owner_id'], owner['first_name'])}\n"
        f"💰 Казна: {money(clan['balance'])}\n"
        f"👥 Участников: {len(members)}\n{lst}")


@router.message(Cmd("вступить в клан", "клан вступить", section=S_CLAN,
                    usage="вступить в клан {название}", desc="Вступить в клан"))
async def clan_join(message: Message, args: str = "", **kw):
    name = (args or "").strip()
    clan = await db.fetchone("SELECT * FROM clans WHERE lower(name)=lower(?)", (name,))
    if not clan:
        return await message.reply("Клан не найден.")
    if await db.fetchone("SELECT 1 FROM clan_members WHERE user_id=?", (message.from_user.id,)):
        return await message.reply("Вы уже в клане.")
    await db.execute("INSERT INTO clan_members (clan_id, user_id, ts) VALUES (?,?,?)",
                     (clan["id"], message.from_user.id, int(time.time())))
    await message.reply(f"✅ Вы вступили в клан <b>{html.escape(clan['name'])}</b>")


@router.message(Cmd("выйти из клана", "покинуть клан", section=S_CLAN,
                    usage="выйти из клана", desc="Покинуть клан"))
async def clan_leave(message: Message, **kw):
    cm = await db.fetchone("SELECT clan_id FROM clan_members WHERE user_id=?",
                           (message.from_user.id,))
    if not cm:
        return await message.reply("Вы не состоите в клане.")
    clan = await db.fetchone("SELECT * FROM clans WHERE id=?", (cm["clan_id"],))
    await db.execute("DELETE FROM clan_members WHERE user_id=?", (message.from_user.id,))
    if clan and clan["owner_id"] == message.from_user.id:
        await db.execute("DELETE FROM clans WHERE id=?", (clan["id"],))
        await db.execute("DELETE FROM clan_members WHERE clan_id=?", (clan["id"],))
        return await message.reply("🏰 Вы были главой — клан расформирован.")
    await message.reply("👋 Вы покинули клан.")


@router.message(Cmd("топ кланов", "кланы", section=S_CLAN, usage="топ кланов",
                    desc="Рейтинг кланов"))
async def clan_top(message: Message, **kw):
    rows = await db.fetchall(
        "SELECT c.name, c.balance, COUNT(m.user_id) cnt FROM clans c "
        "LEFT JOIN clan_members m ON m.clan_id=c.id GROUP BY c.id "
        "ORDER BY cnt DESC, c.balance DESC LIMIT 10")
    if not rows:
        return await message.reply("Кланов пока нет.")
    lines = [f"{i+1}. <b>{html.escape(r['name'])}</b> — {r['cnt']} чел., {money(r['balance'])}"
             for i, r in enumerate(rows)]
    await message.reply("🏰 <b>Топ кланов</b>\n" + "\n".join(lines))


# ================= 18. КРУЖКИ =================
@router.message(Cmd("кружок", "круг", section=S_CIRCLE, usage="кружок",
                    desc="Случайный видеокружок-ответ"))
async def circle(message: Message, **kw):
    await message.reply("⭕️ Модуль кружков: пришлите видеокружок реплаем с командой "
                        "<code>сохранить кружок</code>, и бот будет присылать его случайно.")


@router.message(Cmd("сохранить кружок", section=S_CIRCLE, usage="сохранить кружок (реплаем)",
                    desc="Сохранить кружок"))
async def circle_save(message: Message, **kw):
    r = message.reply_to_message
    if not r or not r.video_note:
        return await message.reply("Ответьте командой на видеокружок.")
    await db.execute("INSERT INTO notes (chat_id,user_id,name,text,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, message.from_user.id, "__circle__",
                      r.video_note.file_id, int(time.time())))
    await message.reply("⭕️ Кружок сохранён.")


@router.message(Cmd("случайный кружок", section=S_CIRCLE, usage="случайный кружок",
                    desc="Прислать случайный кружок"))
async def circle_rand(message: Message, **kw):
    row = await db.fetchone("SELECT text FROM notes WHERE name='__circle__' "
                            "AND chat_id=? ORDER BY RANDOM() LIMIT 1", (message.chat.id,))
    if not row:
        return await message.reply("Кружков нет. Сохраните: <code>сохранить кружок</code>")
    await message.answer_video_note(row["text"])


# ================= 20. БРАКИ И ОТНОШЕНИЯ =================
@router.message(Cmd("браки", "топ браков", "свадьбы", "топ отн", section=S_MARRY, usage="браки",
                    desc="Список браков и отношений"))
async def marry_list(message: Message, **kw):
    rows = await db.fetchall(
        "SELECT r.*, u1.first_name as n1, u2.first_name as n2 "
        "FROM relationships r "
        "LEFT JOIN users u1 ON u1.user_id = r.user1_id "
        "LEFT JOIN users u2 ON u2.user_id = r.user2_id "
        "ORDER BY r.xp DESC LIMIT 20")
    if not rows:
        return await message.reply("💒 <b>Браки и отношения</b>\n\nПока никто не состоит в отношениях.")
    lines = []
    for i, r in enumerate(rows, 1):
        days = max(1, int((time.time() - r["created_at"]) // 86400))
        lines.append(f"{i}. 💍 {mention_id(r['user1_id'], r['n1'] or str(r['user1_id']))} + "
                     f"{mention_id(r['user2_id'], r['n2'] or str(r['user2_id']))} — "
                     f"Ур. {r['level']} (✨ {r['xp']} любви, {days} дн.)")
    await message.reply("💒 <b>Топ отношений</b>\n\n" + "\n".join(lines))



# ================= 21. РЕПУТАЦИЯ И КАРМА =================
MAX_DAILY_REPUTATION = 3

def _rep_today_key(tz_offset: int = 3) -> str:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    return now.strftime("%Y-%m-%d")

async def _get_daily_rep_count(user_id: int) -> int:
    day = _rep_today_key()
    row = await db.fetchone("SELECT count FROM rep_daily_count WHERE user_id=? AND day=?", (user_id, day))
    return int(row["count"]) if row else 0

async def _inc_daily_rep_count(user_id: int) -> int:
    day = _rep_today_key()
    await db.execute(
        "INSERT INTO rep_daily_count (user_id, day, count) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, day) DO UPDATE SET count = count + 1",
        (user_id, day)
    )
    return await _get_daily_rep_count(user_id)

def _rep_title(rep: int) -> str:
    if rep >= 500:
        return "🌌 Владыка уважения"
    if rep >= 250:
        return "👑 Легенда чата"
    if rep >= 100:
        return "⚜️ Авторитет"
    if rep >= 50:
        return "🌟 Уважаемый"
    if rep >= 20:
        return "⭐️ Известный"
    if rep >= 5:
        return "🌱 Знакомый"
    if rep <= -50:
        return "💀 Изгой"
    if rep <= -15:
        return "⚠️ Подозрительный"
    return "🔹 Участник"


@router.message(Cmd("моя репутация", "моя карма", "реп инфо", "карма", section=S_REP,
                    usage="репутация", desc="🌟 Посмотреть свой уровень репутации и кармы"))
async def rep_info(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    u = await db.get_user(uid)
    used = await _get_daily_rep_count(uid)
    title = _rep_title(u.get("rep", 0))

    text = (
        f"🌟 ✨ <b>ВАША РЕПУТАЦИЯ И КАРМА</b> ✨ 🌟\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 Пользователь: {mention(message.from_user)}\n"
        f"⭐️ Очков репутации: <b>{u.get('rep', 0)}</b>\n"
        f"🎖 Текущий статус: <b>{title}</b>\n"
        f"📊 Использовано сегодня: <b>{used}/{MAX_DAILY_REPUTATION}</b> благодарностей\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Поблагодарить участника:</i> <code>+реп</code> (или реплаем <code>спасибо</code>)\n"
        f"🏆 <i>Рейтинг лидеров уважения:</i> <code>топ реп</code>"
    )
    await message.reply(text)


@router.message(Cmd("реп", "+реп", "+rep", "плюс реп", "плюсреп", "спасибо", "сяб", "благодарю", "респект", "+",
                    section=S_REP, usage="+реп {@юзер/реплай}", desc="⭐️ Повысить репутацию участнику"))
async def rep_plus(message: Message, bot: Bot, args: str = "", **kw):
    from core_resolve import real_reply
    uid, name, _ = await resolve_target(message, args, bot)
    
    # Если аргументов нет и не реплай на человека — смотрим команду "реп" как инфо
    if not uid and not real_reply(message):
        return await rep_info(message, bot, **kw)

    if not uid:
        return await message.reply("Укажите пользователя или ответьте на его сообщение.")

    from_uid = message.from_user.id
    if uid == from_uid:
        return await message.reply("🙂 Себе репутацию повышать нельзя!")

    # Проверка суточного лимита (макс 3 в день)
    used = await _get_daily_rep_count(from_uid)
    if used >= MAX_DAILY_REPUTATION:
        return await message.reply(
            f"⛔️ <b>Достигнут лимит на сегодня!</b>\n\n"
            f"Вы уже использовали все <b>{MAX_DAILY_REPUTATION}/{MAX_DAILY_REPUTATION}</b> благодарностей за сутки.\n"
            f"Новые плюсики будут доступны завтра!"
        )

    await _inc_daily_rep_count(from_uid)
    await db.execute("UPDATE users SET rep = rep + 1 WHERE user_id=?", (uid,))
    
    # Небольшая награда за дружелюбие
    await db.add_balance(uid, 50)
    await db.add_xp(message.chat.id, uid, 15)
    await db.add_balance(from_uid, 20)

    target_user = await db.get_user(uid)
    new_rep = target_user.get("rep", 0)
    title = _rep_title(new_rep)
    used_now = used + 1

    await message.reply(
        f"⭐️ ✨ <b>РЕПУТАЦИЯ ПОВЫШЕНА!</b> ✨ ⭐️\n\n"
        f"👤 {mention(message.from_user)} поблагодарил {mention_id(uid, name)}!\n"
        f"📈 Новая репутация: <b>{new_rep}</b> ({title})\n"
        f"💰 Награда за взаимность: <b>+{money(50)}</b> · <b>+15 XP</b>\n"
        f"⏳ Осталось благодарностей на сегодня: <b>{MAX_DAILY_REPUTATION - used_now}/{MAX_DAILY_REPUTATION}</b>"
    )


@router.message(Cmd("-реп", "-rep", "минус реп", "минусреп", "дизреспект", "-", section=S_REP,
                    usage="-реп {@юзер/реплай}", desc="📉 Понизить репутацию участнику"))
async def rep_minus(message: Message, bot: Bot, args: str = "", **kw):
    from core_resolve import real_reply
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя или ответьте на его сообщение.")

    from_uid = message.from_user.id
    if uid == from_uid:
        return await message.reply("🙂 Себе репутацию понижать нельзя!")

    # Проверка суточного лимита
    used = await _get_daily_rep_count(from_uid)
    if used >= MAX_DAILY_REPUTATION:
        return await message.reply(
            f"⛔️ <b>Достигнут суточный лимит!</b> ({MAX_DAILY_REPUTATION}/{MAX_DAILY_REPUTATION})"
        )

    await _inc_daily_rep_count(from_uid)
    await db.execute("UPDATE users SET rep = rep - 1 WHERE user_id=?", (uid,))
    target_user = await db.get_user(uid)
    new_rep = target_user.get("rep", 0)
    title = _rep_title(new_rep)
    used_now = used + 1

    await message.reply(
        f"📉 <b>РЕПУТАЦИЯ ПОНИЖЕНА</b>\n\n"
        f"👤 {mention(message.from_user)} выразил дизреспект {mention_id(uid, name)}.\n"
        f"📊 Новая репутация: <b>{new_rep}</b> ({title})\n"
        f"⏳ Осталось действий на сегодня: <b>{MAX_DAILY_REPUTATION - used_now}/{MAX_DAILY_REPUTATION}</b>"
    )


@router.message(Cmd("топ репутации", "топ репы", "топ кармы", "авторитеты", "топ реп", section=S_REP,
                    usage="топ реп", desc="🏆 Рейтинг лидеров по репутации"))
async def rep_top(message: Message, **kw):
    rows = await db.fetchall(
        "SELECT user_id, first_name, rep FROM users "
        "WHERE rep <> 0 ORDER BY rep DESC LIMIT 10"
    )
    if not rows:
        return await message.reply("🌟 В чате пока никто не заработал очков репутации.")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [
        "🌟 ✨ <b>ТОП АВТОРИТЕТОВ И ЛИДЕРОВ УВАЖЕНИЯ</b> ✨ 🌟",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    for i, r in enumerate(rows):
        icon = medals[i] if i < len(medals) else "▫️"
        title = _rep_title(r["rep"])
        name = html.escape(r["first_name"] or str(r["user_id"]))
        lines.append(f"{icon} <b>{name}</b> — ⭐️ <b>{r['rep']}</b> <i>({title})</i>")

    lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    lines.append("💡 <i>Поблагодарить друга:</i> <code>+реп</code> (до 3 раз в день)")
    await message.reply("\n".join(lines))


# ================= 22. НАГРАДЫ =================
@router.message(Cmd("наградить", "выдать награду", section=S_AWARD, rank=3,
                    usage="наградить {ссылка} {название}", desc="Выдать награду"))
async def award_give(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid or not rest:
        return await message.reply("Формат: реплай + <code>наградить Лучший мемер</code>")
    await db.execute("INSERT INTO awards (chat_id,user_id,title,by_id,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, uid, rest, message.from_user.id, int(time.time())))
    await message.reply(f"🏅 {mention_id(uid, name)} получает награду: <b>{html.escape(rest)}</b>")


@router.message(Cmd("награды", "мои награды", section=S_AWARD, usage="награды",
                    desc="Список наград"))
async def award_list(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
    rows = await db.fetchall("SELECT title, ts FROM awards WHERE user_id=? ORDER BY id DESC",
                             (uid,))
    if not rows:
        return await message.reply(f"У {mention_id(uid, name)} пока нет наград.")
    lines = [f"🏅 {html.escape(r['title'])} ({time.strftime('%d.%m.%y', time.localtime(r['ts']))})"
             for r in rows]
    await message.reply(f"🏆 <b>Награды</b> {mention_id(uid, name)}\n" + "\n".join(lines))


@router.message(Cmd("снять награду", section=S_AWARD, rank=3, usage="снять награду {ссылка}",
                    desc="Убрать последнюю награду"))
async def award_del(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя.")
    await db.execute("DELETE FROM awards WHERE id=(SELECT id FROM awards WHERE user_id=? "
                     "ORDER BY id DESC LIMIT 1)", (uid,))
    await message.reply(f"✅ Награда снята с {mention_id(uid, name)}.")


# ================= 23. ЗАКЛАДКИ =================
@router.message(Cmd("закладка", "сохранить", "заложить", section=S_BOOK,
                    usage="закладка {название} (реплаем)", desc="Сохранить сообщение"))
async def bm_add(message: Message, args: str = "", **kw):
    r = message.reply_to_message
    if not r:
        return await message.reply("Ответьте командой на сообщение, которое хотите сохранить.")
    name = (args or f"Закладка {int(time.time())}").strip()
    link = ""
    if str(message.chat.id).startswith("-100"):
        link = f"https://t.me/c/{str(message.chat.id)[4:]}/{r.message_id}"
    text = (r.text or r.caption or "медиа")[:200]
    await db.execute("INSERT INTO bookmarks (user_id,name,link,ts) VALUES (?,?,?,?)",
                     (message.from_user.id, name, link or text, int(time.time())))
    await message.reply(f"🔖 Сохранено: <b>{html.escape(name)}</b>\n"
                        f"Список: <code>закладки</code>")


@router.message(Cmd("закладки", "мои закладки", section=S_BOOK, usage="закладки",
                    desc="Список закладок"))
async def bm_list(message: Message, **kw):
    rows = await db.fetchall("SELECT id,name,link FROM bookmarks WHERE user_id=? "
                             "ORDER BY id DESC LIMIT 20", (message.from_user.id,))
    if not rows:
        return await message.reply("Закладок нет.")
    lines = []
    for r in rows:
        v = r["link"]
        v = f'<a href="{v}">открыть</a>' if v.startswith("http") else html.escape(v[:60])
        lines.append(f"#{r['id']} <b>{html.escape(r['name'])}</b> — {v}")
    await message.reply("🔖 <b>Ваши закладки</b>\n" + "\n".join(lines))


@router.message(Cmd("удалить закладку", section=S_BOOK, usage="удалить закладку {id}",
                    desc="Удалить закладку"))
async def bm_del(message: Message, args: str = "", **kw):
    if not args.strip().isdigit():
        return await message.reply("Формат: <code>удалить закладку 5</code>")
    await db.execute("DELETE FROM bookmarks WHERE id=? AND user_id=?",
                     (int(args.strip()), message.from_user.id))
    await message.reply("🗑 Закладка удалена.")


# ================= 24. ЗАМЕТКИ =================
@router.message(Cmd("заметка", "новая заметка", section=S_NOTE,
                    usage="заметка {название} {текст}", desc="Создать заметку"))
async def note_add(message: Message, args: str = "", **kw):
    parts = (args or "").split(maxsplit=1)
    if len(parts) < 2 and not message.reply_to_message:
        return await message.reply("Формат: <code>заметка правила Текст заметки</code>")
    name = parts[0] if parts else "заметка"
    text = parts[1] if len(parts) > 1 else (
        message.reply_to_message.text or message.reply_to_message.caption or "")
    await db.execute("INSERT INTO notes (chat_id,user_id,name,text,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, message.from_user.id, name, text, int(time.time())))
    await message.reply(f"🗒 Заметка <b>{html.escape(name)}</b> сохранена.\n"
                        f"Прочитать: <code>заметка {html.escape(name)}</code>")


@router.message(Cmd("заметки", "мои заметки", section=S_NOTE, usage="заметки",
                    desc="Список заметок"))
async def note_list(message: Message, **kw):
    rows = await db.fetchall("SELECT name FROM notes WHERE chat_id=? AND name<>'__circle__' "
                             "ORDER BY id DESC LIMIT 30", (message.chat.id,))
    if not rows:
        return await message.reply("Заметок нет.")
    await message.reply("🗒 <b>Заметки чата</b>\n" +
                        "\n".join(f"• {html.escape(r['name'])}" for r in rows))


@router.message(Cmd("удалить заметку", section=S_NOTE, usage="удалить заметку {название}",
                    desc="Удалить заметку"))
async def note_del(message: Message, args: str = "", **kw):
    if not args.strip():
        return await message.reply("Укажите название.")
    await db.execute("DELETE FROM notes WHERE chat_id=? AND lower(name)=lower(?)",
                     (message.chat.id, args.strip()))
    await message.reply("🗑 Заметка удалена.")


# ================= 25. ТАЙМЕРЫ =================
@router.message(Cmd("таймер", "напомни", "напоминание", section=S_TIMER,
                    usage="таймер {период} {текст}", desc="Поставить напоминание"))
async def timer_add(message: Message, args: str = "", **kw):
    secs, text = parse_period(args or "")
    if not secs:
        return await message.reply("Формат: <code>таймер 10 минут выключить плиту</code>")
    fire = int(time.time()) + secs
    await db.execute("INSERT INTO timers (chat_id,user_id,text,fire_at) VALUES (?,?,?,?)",
                     (message.chat.id, message.from_user.id, text or "напоминание", fire))
    await message.reply(f"⏰ Напомню через <b>{human_period(secs)}</b>: "
                        f"{html.escape(text or 'напоминание')}")


@router.message(Cmd("таймеры", "мои таймеры", section=S_TIMER, usage="таймеры",
                    desc="Список активных таймеров"))
async def timer_list(message: Message, **kw):
    rows = await db.fetchall("SELECT id,text,fire_at FROM timers WHERE user_id=? AND done=0 "
                             "ORDER BY fire_at", (message.from_user.id,))
    if not rows:
        return await message.reply("Активных таймеров нет.")
    lines = [f"#{r['id']} {html.escape(r['text'])} — через "
             f"{human_period(int(r['fire_at'] - time.time()))}" for r in rows]
    await message.reply("⏰ <b>Ваши таймеры</b>\n" + "\n".join(lines))


@router.message(Cmd("удалить таймер", "отменить таймер", section=S_TIMER,
                    usage="удалить таймер {id}", desc="Отменить таймер"))
async def timer_del(message: Message, args: str = "", **kw):
    if not args.strip().isdigit():
        return await message.reply("Формат: <code>удалить таймер 3</code>")
    await db.execute("UPDATE timers SET done=1 WHERE id=? AND user_id=?",
                     (int(args.strip()), message.from_user.id))
    await message.reply("✅ Таймер отменён.")


# ================= 26. КАТАЛОГ =================
@router.message(Cmd("каталог", "чаты каталог", section=S_CAT, usage="каталог",
                    desc="Каталог чатов бота"))
async def catalog(message: Message, **kw):
    rows = await db.fetchall("SELECT title, chat_id FROM chats ORDER BY added_at DESC LIMIT 20")
    if not rows:
        return await message.reply("Каталог пуст.")
    lines = [f"• {html.escape(r['title'] or 'чат')}" for r in rows]
    await message.reply("📚 <b>Каталог чатов</b>\n" + "\n".join(lines))


@router.message(Cmd("добавить в каталог", section=S_CAT, rank=4, usage="добавить в каталог",
                    desc="Добавить чат в каталог"))
async def catalog_add(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    await db.register_chat(message.chat.id, message.chat.title)
    await message.reply("✅ Чат добавлен в каталог.")


# ================= 27. ИРИС-БИРЖА =================
@router.message(Cmd("биржа", "маркет", section=S_MARKET, usage="биржа",
                    desc="Активные заявки биржи"))
async def market(message: Message, **kw):
    rows = await db.fetchall("SELECT m.*, u.first_name FROM market m LEFT JOIN users u "
                             "ON u.user_id=m.user_id ORDER BY m.id DESC LIMIT 15")
    if not rows:
        return await message.reply("💱 <b>Ирис-биржа</b>\nЗаявок нет.\n"
                                   "Создать: <code>продать 1000 за 500</code>")
    lines = [f"#{r['id']} {mention_id(r['user_id'], r['first_name'])} — "
             f"{r['kind']} {money(r['amount'])} за {money(r['price'])}" for r in rows]
    await message.reply("💱 <b>Ирис-биржа</b>\n" + "\n".join(lines))


@router.message(Cmd("продать", section=S_MARKET, usage="продать {кол-во} за {цена}",
                    desc="Выставить заявку на бирже"))
async def market_sell(message: Message, args: str = "", **kw):
    m = (args or "").replace(" за ", " ").split()
    if len(m) < 2:
        return await message.reply("Формат: <code>продать 1000 за 500</code>")
    u = await db.get_user(message.from_user.id)
    amount = parse_amount(m[0], u["balance"])
    price = parse_amount(m[1], u["balance"])
    if not amount or not price:
        return await message.reply("Некорректные числа.")
    if amount > u["balance"]:
        return await message.reply("Недостаточно ирисок.")
    await db.add_balance(message.from_user.id, -amount, "market_lock")
    await db.execute("INSERT INTO market (user_id,kind,amount,price,ts) VALUES (?,?,?,?,?)",
                     (message.from_user.id, "продажа", amount, price, int(time.time())))
    await message.reply(f"💱 Заявка создана: {money(amount)} за {money(price)}")


@router.message(Cmd("купить", section=S_MARKET, usage="купить {id}", desc="Купить заявку"))
async def market_buy(message: Message, args: str = "", **kw):
    if not args.strip().isdigit():
        return await message.reply("Формат: <code>купить 3</code> (id из списка «биржа»)")
    row = await db.fetchone("SELECT * FROM market WHERE id=?", (int(args.strip()),))
    if not row:
        return await message.reply("Заявка не найдена.")
    if row["user_id"] == message.from_user.id:
        return await message.reply("Это ваша заявка.")
    u = await db.get_user(message.from_user.id)
    if u["balance"] < row["price"]:
        return await message.reply(f"Нужно {money(row['price'])}, у вас {money(u['balance'])}.")
    await db.add_balance(message.from_user.id, -row["price"], "market_buy")
    await db.add_balance(message.from_user.id, row["amount"], "market_get")
    await db.add_balance(row["user_id"], row["price"], "market_sold")
    await db.execute("DELETE FROM market WHERE id=?", (row["id"],))
    await message.reply(f"✅ Сделка совершена: получено {money(row['amount'])} "
                        f"за {money(row['price'])}")


# ================= 30. РЕПОРТЫ =================
@router.message(Cmd("репорт", "жалоба", "report", section=S_REPORT,
                    usage="репорт {причина} (реплаем)", desc="Пожаловаться модераторам"))
async def report(message: Message, bot: Bot, args: str = "", **kw):
    tgt = message.reply_to_message.from_user if message.reply_to_message else None
    await db.execute("INSERT INTO reports (chat_id,user_id,target_id,text,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, message.from_user.id, tgt.id if tgt else 0,
                      args or "без описания", int(time.time())))
    mods = await db.fetchall(
        "SELECT r.user_id,u.first_name,u.username,r.rank,"
        "COALESCE(s.last_seen,0) last_seen FROM ranks r "
        "LEFT JOIN users u ON u.user_id=r.user_id "
        "LEFT JOIN chat_stats s ON s.chat_id=r.chat_id AND s.user_id=r.user_id "
        "WHERE r.chat_id=? AND r.rank>=1 ORDER BY r.rank DESC,last_seen DESC",
        (message.chat.id,))
    me = await bot.me()
    present_mods = await members.verified_members(
        bot, message.chat.id, mods, exclude=(me.id, message.from_user.id))
    tags = " ".join(
        members.summon_mention(m["user_id"], m.get("first_name"),
                               m.get("username"))
        for m in present_mods[:20])
    await message.reply(f"📣 <b>Жалоба отправлена</b>\n"
                        f"На: {mention_id(tgt.id, tgt.first_name) if tgt else '—'}\n"
                        f"Причина: {html.escape(args or 'без описания')}\n\n"
                        f"{tags or '<i>Присутствующие модераторы не найдены.</i>'}")


@router.message(Cmd("репорты", "жалобы", section=S_REPORT, rank=1, usage="репорты",
                    desc="Список жалоб"))
async def report_list(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    rows = await db.fetchall("SELECT * FROM reports WHERE chat_id=? AND status='open' "
                             "ORDER BY id DESC LIMIT 15", (message.chat.id,))
    if not rows:
        return await message.reply("Открытых жалоб нет.")
    lines = [f"#{r['id']} на <code>{r['target_id']}</code>: {html.escape(r['text'][:60])}"
             for r in rows]
    await message.reply("📣 <b>Жалобы</b>\n" + "\n".join(lines))


@router.message(Cmd("закрыть репорт", section=S_REPORT, rank=1, usage="закрыть репорт {id}",
                    desc="Закрыть жалобу"))
async def report_close(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    if not args.strip().isdigit():
        return await message.reply("Формат: <code>закрыть репорт 3</code>")
    await db.execute("UPDATE reports SET status='closed' WHERE id=?", (int(args.strip()),))
    await message.reply("✅ Жалоба закрыта.")


# ================= 31. РОЗЫГРЫШИ =================
@router.message(Cmd("розыгрыш", "конкурс", section=S_GIVE, rank=2,
                    usage="розыгрыш {период} {приз}", desc="Запустить розыгрыш"))
async def giveaway(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    secs, prize = parse_period(args or "")
    secs = secs or 3600
    prize = prize or "приз"
    await db.execute("INSERT INTO giveaways (chat_id,prize,owner_id,until) VALUES (?,?,?,?)",
                     (message.chat.id, prize, message.from_user.id, int(time.time()) + secs))
    row = await db.fetchone("SELECT last_insert_rowid() id")
    gid = row["id"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎁 Участвовать", callback_data=f"ga:{gid}")]])
    await message.answer(f"🎁 <b>Розыгрыш!</b>\nПриз: <b>{html.escape(prize)}</b>\n"
                         f"Итоги через {human_period(secs)}\n\nУчастников: 0", reply_markup=kb)


@router.callback_query(F.data.startswith("ga:"))
async def cb_giveaway(call: CallbackQuery):
    gid = int(call.data.split(":")[1])
    g = await db.fetchone("SELECT * FROM giveaways WHERE id=?", (gid,))
    if not g or g["done"]:
        return await call.answer("Розыгрыш завершён", show_alert=True)
    await db.execute("INSERT OR IGNORE INTO giveaway_members (gid,user_id) VALUES (?,?)",
                     (gid, call.from_user.id))
    cnt = await db.fetchone("SELECT COUNT(*) c FROM giveaway_members WHERE gid=?", (gid,))
    try:
        await call.message.edit_text(
            f"🎁 <b>Розыгрыш!</b>\nПриз: <b>{html.escape(g['prize'])}</b>\n"
            f"Итоги: {time.strftime('%d.%m %H:%M', time.localtime(g['until']))}\n\n"
            f"Участников: {cnt['c']}", reply_markup=call.message.reply_markup)
    except Exception:
        pass
    await call.answer("✅ Вы участвуете!")


@router.message(Cmd("итоги розыгрыша", "завершить розыгрыш", section=S_GIVE, rank=2,
                    usage="итоги розыгрыша", desc="Подвести итоги"))
async def giveaway_end(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return
    g = await db.fetchone("SELECT * FROM giveaways WHERE chat_id=? AND done=0 "
                          "ORDER BY id DESC LIMIT 1", (message.chat.id,))
    if not g:
        return await message.reply("Активных розыгрышей нет.")
    mem = await db.fetchall("SELECT user_id FROM giveaway_members WHERE gid=?", (g["id"],))
    await db.execute("UPDATE giveaways SET done=1 WHERE id=?", (g["id"],))
    if not mem:
        return await message.reply("🎁 Никто не участвовал.")
    w = random.choice(mem)["user_id"]
    u = await db.get_user(w)
    await message.answer(f"🎉 <b>Итоги розыгрыша</b>\nПриз: {html.escape(g['prize'])}\n"
                         f"Победитель: {mention_id(w, u['first_name'])}")
