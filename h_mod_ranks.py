"""Раздел 1: команды модерации — ранги 1–7, состав, созыв, импорт списка."""
from __future__ import annotations

import html
import re
import time

from aiogram import Bot, Router
from aiogram.types import Message

import db
import core_members as members
from core_ranks import effective_rank, get_rank, rank_label, rank_name, require, set_rank
from core_registry import MAX_RANK, RANK_NAMES, RANK_TITLES, Cmd, stars
from core_resolve import resolve_target
from utils import mention_id

router = Router(name="mod_ranks")
S = 1

# «Ирис»-стиль: 🏐 в чате, ➖ вышел из чата
IN_CHAT, LEFT_CHAT = "🏐", "➖"


USERNAME_OK = re.compile(r"^[A-Za-z0-9_]{4,32}$")
USERNAME_IN_ARGS = re.compile(r"@([A-Za-z0-9_]{4,32})")


async def _staff_by_written_username(chat_id: int, args: str):
    """Ищет импортированного сотрудника, даже если Telegram ID ещё неизвестен.

    Bot API не умеет преобразовывать произвольный @username пользователя в ID.
    Но для понижения внутренней должности ID не нужен: достаточно записи staff.
    """
    match = USERNAME_IN_ARGS.search(args or "")
    if not match:
        return None
    username = match.group(1)
    row = await db.fetchone(
        "SELECT chat_id,username,name,rank,user_id FROM staff "
        "WHERE chat_id=? AND lower(username)=lower(?) LIMIT 1",
        (chat_id, username))
    if row:
        return row
    if await db.get_setting(chat_id, "global_ranks", "1") == "1":
        return await db.fetchone(
            "SELECT chat_id,username,name,rank,user_id FROM staff "
            "WHERE lower(username)=lower(?) ORDER BY ts DESC LIMIT 1", (username,))
    return None


async def _change_unresolved_staff(message: Message, actor_rank: int, args: str,
                                   *, remove: bool = False, is_tech: bool = False) -> bool:
    """Понижает/снимает staff-запись по @нику, когда user_id неизвестен."""
    row = await _staff_by_written_username(message.chat.id, args)
    if not row:
        return False
    cur = int(row["rank"] or 0)
    if not is_tech:
        if cur >= MAX_RANK:
            await message.reply(
                f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> неприкосновенен — его нельзя снять.")
            return True
        if cur >= actor_rank and actor_rank < MAX_RANK:
            await message.reply("⛔️ Нельзя изменить должность равного или старшего.")
            return True

    global_mode = await db.get_setting(message.chat.id, "global_ranks", "1") == "1"
    where = "lower(username)=lower(?)" if global_mode else \
            "chat_id=? AND lower(username)=lower(?)"
    params = (row["username"],) if global_mode else (message.chat.id, row["username"])
    new_rank = 0 if remove else max(0, cur - 1)
    if new_rank:
        await db.execute(f"UPDATE staff SET rank=?, ts=? WHERE {where}",
                         (new_rank, int(time.time()), *params))
    else:
        await db.execute(f"DELETE FROM staff WHERE {where}", params)

    person = _link(row["username"], row["name"], int(row["user_id"] or 0))
    if remove or not new_rank:
        await message.reply(f"✅ {person} снят с должности.")
    else:
        await message.reply(
            f"⬇️ {person} понижен до <b>{stars(new_rank)} {rank_name(new_rank)}</b>.")
    return True


INVISIBLE_CHARS = {
    '\u115f', '\u1160', '\u3164', '\uffa0',
    '\u200b', '\u200c', '\u200d', '\ufeff',
    '\u200e', '\u200f', '\u061c',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
    '\u2066', '\u2067', '\u2068', '\u2069',
    '\u2800',
    '\u00a0', '\u202f', '\u205f', '\u3000',
    '\u00ad',
}

def clean_visible_name(s: str | None) -> str:
    if not s:
        return ""
    import unicodedata
    cleaned = []
    for ch in str(s):
        cat = unicodedata.category(ch)
        if ch in INVISIBLE_CHARS or cat in ('Cf', 'Cc', 'Zl', 'Zp'):
            continue
        cleaned.append(ch)
    return "".join(cleaned).strip()


def _link(username: str | None, name: str | None, user_id: int = 0) -> str:
    """Ссылка на профиль: по @нику или tg://user?id=. Без ника — просто имя."""
    clean_u = (username or "").lstrip("@").strip()
    clean_n = clean_visible_name(name)
    display = clean_n or (f"@{clean_u}" if clean_u else "") or (f"Участник [{user_id}]" if user_id else "—")
    label = html.escape(display)
    if clean_u and USERNAME_OK.match(clean_u):
        return f'<a href="https://telegram.me/{clean_u}">{label}</a>'
    if user_id:
        return f'<a href="tg://user?id={user_id}">{label}</a>'
    return label


async def _staff_rows(chat_id: int, bot: Bot | None = None) -> dict[int, list[tuple[str, bool]]]:
    """Собирает состав из таблицы ranks (живые) + staff (импортированные)."""
    out: dict[int, list[tuple[str, bool]]] = {}

    rows = await db.fetchall(
        "SELECT r.user_id, r.rank, u.first_name, u.username FROM ranks r "
        "LEFT JOIN users u ON u.user_id = r.user_id "
        "WHERE r.chat_id=? AND r.rank>0", (chat_id,))
    seen_ids = set()
    for r in rows:
        uid = r["user_id"]
        seen_ids.add(uid)
        fname = r["first_name"]
        uname = r["username"]
        if bot and uid and not clean_visible_name(fname):
            try:
                cm = await bot.get_chat_member(chat_id, uid)
                if cm and cm.user:
                    u_live = cm.user
                    fname = u_live.first_name or fname
                    uname = u_live.username or uname
                    await db.touch_user(uid, uname, fname)
            except Exception:
                pass
        out.setdefault(r["rank"], []).append(
            (_link(uname, fname, uid), False))

    srows = await db.fetchall(
        "SELECT username, name, rank, user_id, left_chat FROM staff "
        "WHERE chat_id=? ORDER BY rank DESC, pos ASC, rowid ASC", (chat_id,))
    for r in srows:
        uid = r["user_id"] or 0
        if uid and uid in seen_ids:
            continue
        fname = r["name"]
        uname = r["username"]
        if bot and uid and not clean_visible_name(fname):
            try:
                cm = await bot.get_chat_member(chat_id, uid)
                if cm and cm.user:
                    u_live = cm.user
                    fname = u_live.first_name or fname
                    uname = u_live.username or uname
                    await db.touch_user(uid, uname, fname)
            except Exception:
                pass
        out.setdefault(r["rank"], []).append(
            (_link(uname, fname, uid), bool(r["left_chat"])))
    return out


def _render_staff(groups: dict[int, list[tuple[str, bool]]], title: str = "А Д М И Н И С Т Р А Ц И Я   Б Е С Е Д Ы") -> str:
    """Стильное VIP Diamond Rainbow дерево оформления состава модерации."""
    from core_registry import RANK_RAINBOW_BULLETS, RANK_RAINBOW_HEADERS, RANK_RAINBOW_PLURAL_HEADERS

    banner = "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦"
    header = f"{banner}\n👑 ✨ <b>{title}</b> ✨ 👑\n{banner}"

    if not groups:
        return (
            f"{header}\n\n"
            "<i>В этой группе ещё не назначен состав модерации.</i>\n\n"
            "👑 Создатель группы автоматически получает ранг.\n"
            "Назначить администратора: <code>+модер 3 @user</code>\n\n"
            "✦ ══════════════════════════════ ✦"
        )

    parts = [header, ""]
    total_staff = sum(len(p) for p in groups.values())

    for rank in sorted(groups, reverse=True):
        people = groups[rank]
        if not people:
            continue
        head = RANK_RAINBOW_PLURAL_HEADERS.get(rank, RANK_RAINBOW_HEADERS.get(rank, f"Ранг {rank}")) if len(people) > 1 \
            else RANK_RAINBOW_HEADERS.get(rank, f"Ранг {rank}")
        parts.append(f"┌ <b>{head}</b>")
        bullet = RANK_RAINBOW_BULLETS.get(rank, "🔹")
        for idx, (link, left) in enumerate(people):
            is_last = (idx == len(people) - 1)
            branch = "└─▸" if is_last else "├─▸"
            if left:
                parts.append(f"{branch} 🔴 <b>{link}</b> <i>(вышел)</i>")
            else:
                parts.append(f"{branch} {bullet} <b>{link}</b>")
        parts.append("")

    parts.append("✦ ══════════════════════════════ ✦")
    parts.append(f"📊 <i>Всего в администрации: <b>{total_staff}</b></i>")
    return "\n".join(parts).strip()


# ---------------- Назначение ----------------
async def _grant(message: Message, bot: Bot, args: str, rank: int, **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    rank = max(1, min(rank, MAX_RANK))
    me = await effective_rank(message, bot)
    import config
    sender_id = message.from_user.id if message.from_user else 0

    from core_access import required_rank
    req_r, _ = await required_rank(message.chat.id, "повысить", 8)
    if me < req_r:
        return await message.reply(
            f"⛔️ Недостаточно прав.\n"
            f"Назначать и изменять ранги могут только администраторы от <b>{rank_label(req_r)}</b> и выше.\n"
            f"Ваш ранг: <b>{rank_label(me)}</b>")

    if rank == 10 and me < 10:
        return await message.reply("⛔️ Назначить <b>Владельца чата</b> может только Создатель/Владелец.")
    if rank == 9 and me < 9:
        return await message.reply("⛔️ Назначить <b>Заместителя владельца</b> может только Владелец чата.")
    if me < min(rank + 1, MAX_RANK):
        return await message.reply(
            f"⛔️ Недостаточно прав.\nЧтобы выдать <b>{rank_label(rank)}</b>, "
            f"нужен ранг выше.\nВаш ранг: <b>{rank_label(me)}</b>")

    uid, name, _ = await resolve_target(message, args, bot)
    uname = None
    if not uid:
        m_u = re.search(r"@([a-zA-Z0-9_]{3,32})", args or "")
        if m_u:
            uname = m_u.group(1)

    if not uid and not uname:
        return await message.reply(
            "❌ Укажите пользователя: ответом на сообщение, @ником или ID.\n"
            "Пример: <code>повысить @user [ранг]</code> или <code>+модер @user [ранг]</code>")

    if uid == sender_id:
        return await message.reply("⛔️ Нельзя повысить самого себя.")

    if not uid and uname:
        clean_uname = uname.lstrip("@")
        sender_uname = (message.from_user.username or "") if message.from_user else ""
        if sender_uname and clean_uname.lower() == sender_uname.lower():
            return await message.reply("⛔️ Нельзя повысить самого себя.")
        u_row = await db.fetchone("SELECT user_id, first_name FROM users WHERE lower(username)=lower(?)", (clean_uname,))
        if u_row and u_row["user_id"] == sender_id:
            return await message.reply("⛔️ Нельзя повысить самого себя.")
        existing = await db.fetchone(
            "SELECT rowid, rank FROM staff WHERE chat_id=? AND lower(username)=lower(?)",
            (message.chat.id, clean_uname)
        )
        if existing:
            tgt_r = existing["rank"]
            if tgt_r >= me and me < MAX_RANK:
                return await message.reply("⛔️ Нельзя менять ранг равного или старшего администратора.")
            await db.execute(
                "UPDATE staff SET rank=?, name=?, ts=? WHERE chat_id=? AND lower(username)=lower(?)",
                (rank, clean_uname, int(time.time()), message.chat.id, clean_uname)
            )
        else:
            await db.execute(
                "INSERT INTO staff (chat_id, username, name, rank, user_id, left_chat, pos, ts) "
                "VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
                (message.chat.id, clean_uname, clean_uname, rank, int(time.time()), int(time.time()))
            )

        if u_row:
            await set_rank(message.chat.id, u_row["user_id"], rank, sender_id)
            await db.execute("UPDATE staff SET user_id=?, name=? WHERE chat_id=? AND lower(username)=lower(?)",
                             (u_row["user_id"], u_row["first_name"] or clean_uname, message.chat.id, clean_uname))

        person = f'<a href="https://telegram.me/{clean_uname}">@{clean_uname}</a>'
        return await message.reply(
            f"✅ {person} назначен:\n<b>{stars(rank)} {rank_name(rank)}</b> (Ранг {rank})"
        )

    tgt_rank = await get_rank(message.chat.id, uid)
    if tgt_rank >= me and me < MAX_RANK:
        return await message.reply("⛔️ Нельзя менять ранг равного или старшего администратора.")
    if me < MAX_RANK and tgt_rank >= MAX_RANK and rank < MAX_RANK:
        return await message.reply(f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> неприкосновенен — его может изменить только Создатель.")
    await set_rank(message.chat.id, uid, rank, sender_id)

    u_info = await db.fetchone("SELECT username, first_name FROM users WHERE user_id=?", (uid,))
    u_uname = u_info["username"] if u_info and u_info["username"] else None
    u_fname = u_info["first_name"] if u_info and u_info["first_name"] else name
    if u_uname:
        await db.execute(
            "INSERT INTO staff (chat_id, username, name, rank, user_id, left_chat, pos, ts) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET rank=excluded.rank, name=excluded.name, ts=excluded.ts",
            (message.chat.id, u_uname, u_fname or u_uname, rank, uid, int(time.time()), int(time.time()))
        )

    await message.reply(
        f"✅ {mention_id(uid, name)} назначен:\n<b>{stars(rank)} {rank_name(rank)}</b> (Ранг {rank})")


def _parse_rank_from_text(text: str) -> tuple[int | None, str]:
    """Извлекает ранг из текста (числом или названием) и возвращает (rank, оставшийся_текст)."""
    t = text.lower().replace("ё", "е")
    mapping = [
        (("владелец чата", "владелец", "создатель чата", "создатель", "лидер чата", "лидер"), 10),
        (("заместитель владельца", "зам владельца", "заместитель", "зам", "заместитель лидера", "зам лидера"), 9),
        (("технический администратор", "технический админ", "техадмин", "тех админ"), 8),
        (("главный администратор", "главный админ", "га"), 7),
        (("старший администратор", "старший админ", "са"), 6),
        (("младший администратор", "младший админ", "ма"), 5),
        (("главный модератор", "главный модер", "гм", "гл"), 4),
        (("старший модератор", "старший модер", "см"), 3),
        (("младший модератор", "младший модер", "мм"), 2),
        (("стажер", "стажёр"), 1),
    ]
    for names, r in mapping:
        for name in sorted(names, key=len, reverse=True):
            pattern = rf"\b{re.escape(name)}\b"
            m = re.search(pattern, t)
            if m:
                rest = (text[:m.start()] + text[m.end():]).strip()
                return r, rest

    m_phrase = re.search(r"\b(?:ранг|ранга|до|на|ур|уровень|уровня|lvl)\s*([1-9]|10)\b", t)
    if m_phrase:
        r = int(m_phrase.group(1))
        rest = (text[:m_phrase.start()] + text[m_phrase.end():]).strip()
        return r, rest

    words = text.split()
    for idx, w in enumerate(words):
        if w.isdigit() and 1 <= int(w) <= MAX_RANK:
            r = int(w)
            rest_words = words[:idx] + words[idx+1:]
            return r, " ".join(rest_words).strip()

    return None, text


# Ранг 10: Владелец чата
@router.message(Cmd("+владелец", "владелец", "+лидер", "лидер", "+создатель", "создатель",
                    section=S, rank=10, usage="+владелец {ссылка}",
                    desc="Назначить Владельцем чата (10 ранг)"))
async def cmd_promote_leader(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 10, **kw)


# Ранг 9: Заместитель владельца
@router.message(Cmd("+зам", "зам", "+заместитель", "заместитель",
                    section=S, rank=9, usage="+зам {ссылка}",
                    desc="Назначить Заместителем владельца (9 ранг)"))
async def cmd_promote_deputy(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 9, **kw)


# Ранг 8: Технический администратор
@router.message(Cmd("+техадмин", "техадмин", "+тех админ", "тех админ", "+технический администратор",
                    section=S, rank=8, usage="+техадмин {ссылка}",
                    desc="Назначить Техническим администратором (8 ранг)"))
async def cmd_promote_tech_admin(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 8, **kw)


# Ранг 7: Главный админ
@router.message(Cmd("+га", "+главный админ", "главный админ", "+главный администратор", "главный администратор",
                    section=S, rank=6, usage="+га {ссылка}",
                    desc="Назначить Главным админом (7 ранг)"))
async def cmd_promote_head_admin(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 7, **kw)


# Ранг 6: Старший админ
@router.message(Cmd("+са", "+старший админ", "старший админ", "+старший администратор", "старший администратор",
                    section=S, rank=5, usage="+са {ссылка}",
                    desc="Назначить Старшим админом (6 ранг)"))
async def cmd_promote_senior_admin(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 6, **kw)


# Ранг 5: Младший админ
@router.message(Cmd("+ма", "+младший админ", "младший админ", "+младший администратор", "младший администратор",
                    section=S, rank=4, usage="+ма {ссылка}",
                    desc="Назначить Младшим админом (5 ранг)"))
async def cmd_promote_junior_admin(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 5, **kw)


# Ранг 4: Главный модератор
@router.message(Cmd("+гм", "+гл", "гл", "+главный модер", "главный модер", "+главный модератор", "главный модератор",
                    section=S, rank=3, usage="+гм {ссылка}",
                    desc="Назначить Главным модератором (4 ранг)"))
async def cmd_promote_head_mod(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 4, **kw)


# Ранг 3: Старший модератор
@router.message(Cmd("+см", "+старший модер", "старший модер", "+старший модератор", "старший модератор",
                    section=S, rank=2, usage="+см {ссылка}",
                    desc="Назначить Старшим модератором (3 ранг)"))
async def cmd_promote_senior_mod(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 3, **kw)


# Ранг 2: Младший модератор
@router.message(Cmd("+мм", "+младший модер", "младший модер", "+младший модератор", "младший модератор",
                    section=S, rank=2, usage="+мм {ссылка}",
                    desc="Назначить Младшим модератором (2 ранг)"))
async def cmd_promote_junior_mod(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 2, **kw)


# Ранг 1: Стажёр
@router.message(Cmd("+стажер", "+стажёр", "стажер", "стажёр",
                    section=S, rank=2, usage="+стажер {ссылка}",
                    desc="Назначить Стажёром (1 ранг)"))
async def cmd_promote_intern(message: Message, bot: Bot, args: str = "", **kw):
    await _grant(message, bot, args, 1, **kw)


# Быстрое снятие должности по короткой команде: -владелец, -зам, -техадмин, -га, -са, -ма, -гм, -см, -мм, -стажер
@router.message(Cmd("-владелец", "-лидер", "-создатель", "-зам", "-заместитель", "-техадмин", "-тех админ",
                    "-га", "-главный админ", "-главный администратор",
                    "-са", "-старший админ", "-старший администратор",
                    "-ма", "-младший админ", "-младший администратор",
                    "-гм", "-гл", "-главный модер", "-главный модератор",
                    "-см", "-старший модер", "-старший модератор",
                    "-мм", "-младший модер", "-младший модератор",
                    "-стажер", "-стажёр",
                    section=S, rank=2, usage="-га {ссылка}",
                    desc="Снять конкретную должность у пользователя"))
async def cmd_quick_demote(message: Message, bot: Bot, args: str = "", **kw):
    await cmd_remove_rank(message, bot, args=args, **kw)


@router.message(Cmd("+модер", "+админ", "модер", "ранг", "дать ранг", "выдать ранг", "назначить", section=S, rank=8,
                    usage="+модер {ссылка} [1-10 / должность]",
                    desc="Назначить ранг модератора (1–10)"))
async def cmd_promote_rank(message: Message, bot: Bot, args: str = "", **kw):
    found_r, clean_args = _parse_rank_from_text(args or "")
    if found_r is not None:
        return await _grant(message, bot, clean_args, found_r, **kw)

    parts = (args or "").split()
    rank = 1
    if parts and parts[0].isdigit() and 1 <= int(parts[0]) <= MAX_RANK:
        rank = int(parts[0])
        args = " ".join(parts[1:]).strip()
    elif len(parts) >= 2 and parts[-1].isdigit() and 1 <= int(parts[-1]) <= MAX_RANK:
        rank = int(parts[-1])
        args = " ".join(parts[:-1]).strip()
    else:
        raw = (message.text or "").strip()
        bangs = len(raw) - len(raw.lstrip("!"))
        if bangs > 1:
            rank = min(bangs, MAX_RANK)
    await _grant(message, bot, args, rank, **kw)


@router.message(Cmd("повысить", "поднять ранг", section=S, rank=8, usage="повысить {ссылка} [ранг]",
                    desc="Повысить на один ранг (или до указанного)"))
async def cmd_promote(message: Message, bot: Bot, args: str = "", **kw):
    found_r, clean_args = _parse_rank_from_text(args or "")
    if found_r is not None:
        return await _grant(message, bot, clean_args, found_r, **kw)

    uid, name, _ = await resolve_target(message, args, bot)
    uname = None
    if not uid:
        m_u = re.search(r"@([a-zA-Z0-9_]{3,32})", args or "")
        if m_u:
            uname = m_u.group(1)

    if not uid and not uname:
        return await message.reply("❌ Укажите пользователя: ответом на сообщение, @ником или ID.\nПример: <code>повысить @user [ранг]</code>")

    if not uid and uname:
        clean_uname = uname.lstrip("@")
        srow = await db.fetchone(
            "SELECT rank FROM staff WHERE chat_id=? AND lower(username)=lower(?)",
            (message.chat.id, clean_uname)
        )
        cur = int(srow["rank"]) if srow else 0
        if cur >= MAX_RANK:
            return await message.reply(f"У пользователя уже максимальный ранг <b>{rank_label(MAX_RANK)}</b>.")
        return await _grant(message, bot, f"@{clean_uname}", cur + 1, **kw)

    cur = await get_rank(message.chat.id, uid)
    if cur >= MAX_RANK:
        return await message.reply(f"У пользователя уже максимальный ранг <b>{rank_label(MAX_RANK)}</b>.")
    await _grant(message, bot, str(uid), cur + 1, **kw)


@router.message(Cmd("понизить", "разжаловать", "снизить", section=S, rank=8,
                    usage="понизить {ссылка}", desc="Понизить на один ранг"))
async def cmd_demote(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    import config
    is_tech = bool(
        me >= 6 or
        (message.from_user and message.from_user.id == config.OWNER_ID)
    )
    if me < 2 and not is_tech:
        return await message.reply(f"⛔️ Недостаточно прав. Ваш ранг: <b>{rank_label(me)}</b>")
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        if await _change_unresolved_staff(message, me, args, is_tech=is_tech):
            return
        return await message.reply(
            "Не удалось определить Telegram ID пользователя.\n"
            "Ответьте командой на его сообщение или укажите числовой ID.\n"
            "Если человек есть в импортированном составе, проверьте его @username.")
    
    cur_effective = await get_rank(message.chat.id, uid)
    l_row = await db.fetchone("SELECT rank FROM ranks WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    s_row = await db.fetchone("SELECT rank FROM staff WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    chat_r = max(int(l_row["rank"]) if l_row else 0, int(s_row["rank"]) if s_row else 0)

    base_r = min(cur_effective, chat_r) if chat_r > 0 else cur_effective

    if base_r <= 0:
        return await message.reply("У пользователя нет ранга.")
    if not is_tech:
        if base_r >= MAX_RANK:
            return await message.reply(
                f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> неприкосновенен — его нельзя понизить.")
        if base_r >= me and me < MAX_RANK:
            return await message.reply("⛔️ Нельзя понизить равного или старшего.")
    elif me < MAX_RANK and base_r >= MAX_RANK:
        return await message.reply(
            f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> может изменить только Создатель.")
    new = max(0, base_r - 1)
    await set_rank(message.chat.id, uid, new, message.from_user.id)
    txt = f"<b>{stars(new)} {rank_name(new)}</b>" if new else "<b>Участник</b> (ранг снят)"
    await message.reply(f"⬇️ {mention_id(uid, name)} понижен до {txt}")


@router.message(Cmd("снять всех", "разжаловать всех", section=S, rank=10,
                    usage="!снять всех", desc="Снять ранги со всех модераторов (Владелец)"))
async def cmd_demote_all(message: Message, bot: Bot, **kw):
    import config
    sender_id = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    if me < 10 and not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Команда «снять всех» доступна только Владельцу чата (10 ранг).")
    await db.execute("DELETE FROM ranks WHERE chat_id=? AND rank < ?",
                     (message.chat.id, MAX_RANK))
    await db.execute("DELETE FROM staff WHERE chat_id=? AND rank < ?",
                     (message.chat.id, MAX_RANK))
    await message.reply(f"🧹 Все ранги сняты.\n"
                        f"👑 {RANK_NAMES[MAX_RANK]} сохраняет свой статус.")


@router.message(Cmd("снять вышедших", "очистить вышедших", "почистить вышедших", "обновить вышедших",
                    section=S, rank=4, usage="очистить вышедших",
                    desc="Снять ранги и очистить базу от покинувших чат"))
async def cmd_demote_left(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    cid = message.chat.id
    if cid >= 0:
        return await message.reply("Команда доступна только в группах.")

    r_rows = await db.fetchall("SELECT user_id FROM ranks WHERE chat_id=?", (cid,))
    m_rows = await db.fetchall("SELECT user_id FROM chat_members WHERE chat_id=?", (cid,))
    p_rows = await db.fetchall("SELECT user_id FROM chat_profiles WHERE chat_id=?", (cid,))
    n_rows = await db.fetchall("SELECT user_id FROM chat_nicks WHERE chat_id=?", (cid,))
    s_rows = await db.fetchall("SELECT user_id FROM chat_stats WHERE chat_id=?", (cid,))
    st_rows = await db.fetchall("SELECT user_id FROM staff WHERE chat_id=? AND user_id>0", (cid,))

    all_uids = {r["user_id"] for r in (r_rows + m_rows + p_rows + n_rows + s_rows + st_rows) if r.get("user_id")}
    if not all_uids:
        return await message.reply("В базе чата нет записанных участников.")

    status_msg = await message.reply(f"⏳ Проверяю {len(all_uids)} участников через Telegram API...")

    sem = asyncio.Semaphore(10)
    left_uids = []
    active_count = 0
    removed_ranks = 0
    ranks_set = {r["user_id"] for r in r_rows if r.get("user_id")}

    async def check_uid(uid: int):
        nonlocal active_count, removed_ranks
        async with sem:
            try:
                m = await bot.get_chat_member(cid, uid)
                if m.status in {"left", "kicked"}:
                    left_uids.append(uid)
                    if uid in ranks_set:
                        removed_ranks += 1
                else:
                    active_count += 1
            except Exception:
                left_uids.append(uid)
                if uid in ranks_set:
                    removed_ranks += 1

    await asyncio.gather(*(check_uid(uid) for uid in all_uids))

    for uid in left_uids:
        await members.remember_member(cid, uid, "left", False)
        if uid in ranks_set:
            await set_rank(cid, uid, 0, message.from_user.id if message.from_user else 0)
        await db.execute("DELETE FROM chat_profiles WHERE chat_id=? AND user_id=?", (cid, uid))
        await db.execute("DELETE FROM chat_nicks WHERE chat_id=? AND user_id=?", (cid, uid))
        await db.execute("UPDATE staff SET left_chat=1 WHERE chat_id=? AND user_id=?", (cid, uid))

    try:
        real_tg_count = await bot.get_chat_member_count(cid)
    except Exception:
        real_tg_count = active_count

    try:
        await status_msg.edit_text(
            f"🧹 <b>Очистка вышедших завершена!</b>\n\n"
            f"🔍 Проверено записей: <b>{len(all_uids)}</b>\n"
            f"🚪 Обнаружено вышедших: <b>{len(left_uids)}</b> (удалены из анкет и ников чата)\n"
            f"👮 Снято рангов с вышедших: <b>{removed_ranks}</b>\n"
            f"👥 Актуально участников в базе: <b>{active_count}</b> (в Telegram: <b>{real_tg_count}</b>)"
        )
    except Exception:
        await message.reply(
            f"🧹 <b>Очистка вышедших завершена!</b>\n\n"
            f"🔍 Проверено записей: <b>{len(all_uids)}</b>\n"
            f"🚪 Обнаружено вышедших: <b>{len(left_uids)}</b>\n"
            f"👮 Снято рангов: <b>{removed_ranks}</b>\n"
            f"👥 Актуально участников: <b>{active_count}</b> (в Telegram: <b>{real_tg_count}</b>)"
        )


@router.message(Cmd("снять", "разжаловать ранг", section=S, rank=8, usage="снять {ссылка}",
                    desc="Полностью снять ранг"))
async def cmd_remove_rank(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    import config
    is_tech = bool(
        me >= 6 or
        (message.from_user and message.from_user.id == config.OWNER_ID)
    )
    if me < 2 and not is_tech:
        return await message.reply(f"⛔️ Недостаточно прав. Ваш ранг: <b>{rank_label(me)}</b>")
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        if await _change_unresolved_staff(message, me, args, remove=True, is_tech=is_tech):
            return
        return await message.reply(
            "Не удалось определить пользователя. Ответьте на его сообщение, "
            "укажите числовой ID или проверьте @username в составе.")
    tgt = await get_rank(message.chat.id, uid)
    if not is_tech:
        if tgt >= MAX_RANK:
            return await message.reply(
                f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> неприкосновенен — с него нельзя снять ранг.")
        if tgt >= me and me < MAX_RANK:
            return await message.reply("⛔️ Нельзя снять равного или старшего.")
    elif me < MAX_RANK and tgt >= MAX_RANK:
        return await message.reply(
            f"👑 <b>{RANK_NAMES[MAX_RANK]}</b> может снять только Создатель.")
    await set_rank(message.chat.id, uid, 0, message.from_user.id)
    await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    await message.reply(f"✅ {mention_id(uid, name)} снят с должности.")


# ---------------- Просмотр состава ----------------
@router.message(Cmd("кто админ", "кто админы", "админы", "кто модер", "кто модеры",
                    "модераторы", "состав", "модерация", "стафф", "персонал",
                    "список админов",
                    section=S, usage="!админы", group_only=True,
                    desc="Показать состав модерации со звёздами"))
async def cmd_staff(message: Message, bot: Bot, **kw):
    groups = await _staff_rows(message.chat.id, bot)
    if MAX_RANK not in groups:
        try:
            admins = await bot.get_chat_administrators(message.chat.id)
            for adm in admins:
                if adm.status == "creator" and adm.user and not adm.user.is_bot:
                    await set_rank(message.chat.id, adm.user.id, MAX_RANK, by=0)
                    await db.touch_user(adm.user.id, adm.user.username, adm.user.first_name)
                    groups = await _staff_rows(message.chat.id, bot)
                    break
        except Exception:
            pass

    text = _render_staff(groups, "Состав администрации")
    await message.reply(text, disable_web_page_preview=True)


@router.message(Cmd("кто создатель", "создатели", "creator", section=S, group_only=True,
                    usage="кто создатель", desc="Показать создателей чата"))
async def cmd_creators(message: Message, bot: Bot, **kw):
    groups = await _staff_rows(message.chat.id, bot)
    if MAX_RANK not in groups:
        try:
            admins = await bot.get_chat_administrators(message.chat.id)
            for adm in admins:
                if adm.status == "creator" and adm.user and not adm.user.is_bot:
                    await set_rank(message.chat.id, adm.user.id, MAX_RANK, by=0)
                    await db.touch_user(adm.user.id, adm.user.username, adm.user.first_name)
                    groups = await _staff_rows(message.chat.id, bot)
                    break
        except Exception:
            pass

    top = {r: p for r, p in groups.items() if r >= 7}
    await message.reply(_render_staff(top, "Руководство чата"),
                        disable_web_page_preview=True)


@router.message(Cmd("ранги", "список рангов", "иерархия", "привилегии", section=S, usage="ранги",
                    desc="Все ранги, короткие команды назначения и их права"))
async def cmd_ranks_help(message: Message, **kw):
    from core_registry import RANK_RAINBOW_HEADERS
    perms = {
        10: "полный контроль, высший иммунитет, передача лидерства",
        9: "заместитель лидера, управление модерацией 1–8 ранга, настройки чата",
        8: "технический доступ, системный аудит, управление правами команд (ДК)",
        7: "главный админ: снятие всех рангов, управление доступом команд (ДК), сброс",
        6: "старший админ: сетка чатов, исключение (кик) участников, автокик, антиспам, анкета чата",
        5: "младший админ: баны, муты, варны, правила чата, приветствие, награды, лимит варнов",
        4: "главный модератор: баны, муты, варны, контроль младшей модерации, розыгрыши, триггеры",
        3: "старший модератор: баны нарушителей, муты, варны, чистка сообщений, теги, триггеры",
        2: "младший модератор: муты, варны, удаление сообщений, созыв",
        1: "стажёр: первичная модерация, варны, базовый мут нарушителей (до 24ч)",
    }
    short_cmds = {
        10: "+владелец / владелец",
        9: "+зам / зам",
        8: "+техадмин",
        7: "+га / главный админ",
        6: "+са / старший админ",
        5: "+ма / младший админ",
        4: "+гм / главный модер",
        3: "+см / старший модер",
        2: "+мм / младший модер",
        1: "+стажер / стажер",
    }
    banner = "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦"
    lines = [
        banner,
        "👑 ✨ <b>И Е Р А Р Х И Я   Р А Н Г О В</b> ✨ 👑",
        banner,
        ""
    ]
    for r in range(MAX_RANK, 0, -1):
        header = RANK_RAINBOW_HEADERS.get(r, f"Ранг {r}")
        cmd_hint = short_cmds.get(r, "")
        lines.append(f"┌ <b>{header}</b> [Ранг {r}] <code>{cmd_hint}</code>")
        lines.append(f"└─▸ <i>{perms.get(r, '')}</i>\n")
    lines.append("✦ ══════════════════════════════ ✦")
    lines.append("💡 <i>Назначить:</i> <code>+га @user</code> · <code>+зам @user</code> · <code>+модер [ранг] @user</code>")
    lines.append("🧹 <i>Снять:</i> <code>-га @user</code> · <code>-зам @user</code> · <code>снять @user</code>")
    lines.append("⬆️ <i>Повысить:</i> <code>повысить @user</code> · ⬇️ <i>Понизить:</i> <code>понизить @user</code>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)


@router.message(Cmd("лог рангов", "лог модерации", section=S, rank=3, group_only=True, usage="лог рангов",
                    desc="История изменений рангов"))
async def cmd_rank_log(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return
    rows = await db.fetchall(
        "SELECT l.*, u.first_name FROM rank_log l LEFT JOIN users u ON u.user_id=l.user_id "
        "WHERE l.chat_id=? ORDER BY l.id DESC LIMIT 15", (message.chat.id,))
    if not rows:
        return await message.reply("Лог пуст.")
    lines = []
    for r in rows:
        lbl = f"{stars(r['rank'])} {rank_name(r['rank'])}" if r["rank"] else "снят"
        lines.append(f"• {mention_id(r['user_id'], r['first_name'])} → {lbl} "
                     f"({time.strftime('%d.%m %H:%M', time.localtime(r['ts']))})")
    await message.reply("📜 <b>Лог изменений рангов</b>\n" + "\n".join(lines))


@router.message(Cmd("созыв", "созвать модерацию", section=S, rank=1, group_only=True, usage="созыв {причина}",
                    desc="Позвать модераторов в чат"))
async def cmd_call_mods(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    rows = await db.fetchall(
        "SELECT r.user_id,u.first_name,u.username,r.rank,"
        "COALESCE(s.last_seen,0) last_seen FROM ranks r "
        "LEFT JOIN users u ON u.user_id=r.user_id "
        "LEFT JOIN chat_stats s ON s.chat_id=r.chat_id AND s.user_id=r.user_id "
        "WHERE r.chat_id=? AND r.rank>=1 ORDER BY r.rank DESC,last_seen DESC",
        (message.chat.id,))
    me = await bot.me()
    people = await members.verified_members(
        bot, message.chat.id, rows, exclude=(me.id, message.from_user.id))
    if not people:
        return await message.reply("В чате нет присутствующих модераторов.")
    tags = " ".join(
        members.summon_mention(p["user_id"], p.get("first_name"),
                               p.get("username"))
        for p in people[:30])
    await message.reply(f"📣 <b>Созыв модерации!</b>\n"
                        f"Причина: {html.escape(args) if args else 'требуется внимание'}\n\n{tags}")


@router.message(Cmd("мой ранг", "ранг", "моя привилегия", section=S, usage="мой ранг", group_only=True,
                    desc="Показать свой ранг"))
async def cmd_my_rank(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if uid:
        r = await get_rank(message.chat.id, uid)
        return await message.reply(
            f"{mention_id(uid, name)} — <b>{stars(r) or '—'} {rank_name(r)}</b> (ранг {r})")
    r = await effective_rank(message, bot)
    db_rank = await get_rank(message.chat.id, message.from_user.id)
    src = "выдан в этом чате"
    if message.from_user.id == __import__("config").OWNER_ID:
        src = "владелец бота"
    elif message.sender_chat:
        src = "анонимный админ"
    elif not db_rank:
        try:
            m = await bot.get_chat_member(message.chat.id, message.from_user.id)
            src = {"creator": "создатель чата в Telegram",
                   "administrator": "админ чата в Telegram"}.get(m.status, "участник")
        except Exception:
            src = "участник"
    await message.reply(
        f"Ваш ранг: <b>{stars(r) or '—'} {rank_name(r)}</b> ({r})\n"
        f"<i>Источник: {src}</i>\n"
        f"<i>Чат: <code>{message.chat.id}</code></i>")


# ---------------- Импорт готового списка ----------------
STAR_RE = re.compile(r"^\s*\**\s*(⭐+|\*+)\s*(.+?)\s*\**\s*$")
PERSON_RE = re.compile(
    r"^\s*(🏐|➖|•|·|-)?\s*(?:\[([^\]]+)\]\s*\(\s*<?(?:https?://)?(?:telegram\.me|t\.me)/"
    r"([A-Za-z0-9_]+)[^)]*\)|@([A-Za-z0-9_]{4,})|(.+?))\s*$")

TITLE_TO_RANK = {
    "лидер чата": 10, "лидеры чата": 10, "лидер клана": 10, "лидеры клана": 10, "лидер": 10, "лидеры": 10, "создатель": 10, "создатели": 10,
    "заместитель лидера": 9, "заместители лидера": 9, "зам лидера": 9, "замы лидера": 9, "зам": 9, "замы": 9, "заместитель": 9, "заместители": 9,
    "технический администратор": 8, "технические администраторы": 8, "тех админ": 8, "техадмин": 8, "техадмины": 8,
    "главный администратор": 7, "главные администраторы": 7, "главный админ": 7, "главные админы": 7, "га": 7,
    "старший администратор": 6, "старшие администраторы": 6, "старший админ": 6, "старшие админы": 6, "са": 6,
    "младший администратор": 5, "младшие администраторы": 5, "младший админ": 5, "младшие админы": 5, "ма": 5,
    "главный модератор": 4, "главные модераторы": 4, "главный модер": 4, "главные модеры": 4, "гм": 4,
    "старший модератор": 3, "старшие модераторы": 3, "старший модер": 3, "старшие модеры": 3, "см": 3,
    "младший модератор": 2, "младшие модераторы": 2, "младший модер": 2, "младшие модеры": 2, "мм": 2,
    "стажер": 1, "стажёр": 1, "стажеры": 1, "стажёры": 1,
}


def _rank_from_title(text: str, star_count: int) -> int:
    t = text.strip().lower().replace("ё", "е")
    for key in sorted(TITLE_TO_RANK, key=len, reverse=True):
        if key in t:
            return TITLE_TO_RANK[key]
    return star_count if 1 <= star_count <= MAX_RANK else 0


def parse_staff_list(text: str) -> list[tuple[str, str, int, bool]]:
    """Разбирает список вида «⭐⭐⭐⭐⭐ Создатели / 🏐 [Имя](ссылка)».

    -> [(username, отображаемое_имя, ранг, вышел_ли)]
    """
    out: list[tuple[str, str, int, bool]] = []
    cur_rank = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        clean = line.replace("*", "").strip()
        stars_found = clean.count("⭐")
        if stars_found or any(k in clean.lower() for k in TITLE_TO_RANK):
            title = clean.replace("⭐", "").strip()
            if title and not title.startswith(("🏐", "➖")):
                r = _rank_from_title(title, stars_found)
                if r:
                    cur_rank = r
                    continue
        if not cur_rank:
            continue
        m = PERSON_RE.match(line)
        if not m:
            continue
        marker, md_name, md_user, at_user, plain = m.groups()
        left = marker == "➖"
        if md_user:
            out.append((md_user, (md_name or md_user).strip(), cur_rank, left))
        elif at_user:
            out.append((at_user, at_user, cur_rank, left))
        elif plain:
            name = plain.strip(" *_")
            if not name or name.lower().startswith(("http", "ирис")):
                continue
            if len(name) > 64:
                continue
            out.append(("", name, cur_rank, left))
    return out


@router.message(Cmd("импорт состава", "загрузить состав", "импорт модерации", section=S,
                    rank=5, usage="импорт состава (реплаем на список)",
                    desc="Загрузить готовый список модерации"))
async def cmd_import_staff(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    src = args or ""
    if message.reply_to_message:
        src = (message.reply_to_message.text or message.reply_to_message.caption or "") or src
    if not src.strip():
        return await message.reply(
            "Ответьте этой командой на сообщение со списком, например:\n\n"
            "<code>⭐⭐⭐⭐⭐ Создатели\n🏐 [Simba](https://telegram.me/simba253)\n\n"
            "⭐⭐⭐⭐ Старшие админы\n🏐 [Филипп](https://telegram.me/fil1003)</code>")
    people = parse_staff_list(src)
    if not people:
        return await message.reply("Не удалось распознать список. "
                                   "Проверьте формат: строка со звёздами, ниже — люди.")
    now = int(time.time())
    added = 0
    await db.execute("DELETE FROM staff WHERE chat_id=?", (message.chat.id,))
    for pos, (username, name, rank, left) in enumerate(people):
        key = username or name
        uid = 0
        if username:
            row = await db.fetchone(
                "SELECT user_id FROM users WHERE lower(username)=lower(?)", (username,))
            if row:
                uid = row["user_id"]
                await set_rank(message.chat.id, uid, rank, message.from_user.id)
        await db.execute(
            "INSERT INTO staff (chat_id,username,name,rank,user_id,left_chat,ts,pos) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(chat_id,username) DO UPDATE SET "
            "name=excluded.name, rank=excluded.rank, user_id=excluded.user_id, "
            "left_chat=excluded.left_chat, pos=excluded.pos",
            (message.chat.id, key, name, rank, uid, int(left), now, pos))
        added += 1
    groups = await _staff_rows(message.chat.id, bot)
    await message.reply(
        f"✅ Загружено записей: <b>{added}</b>\n\n" + _render_staff(groups, "Состав модерации"),
        disable_web_page_preview=True)


@router.message(Cmd("добавить в состав", section=S, rank=4,
                    usage="добавить в состав {ранг} @user Имя",
                    desc="Добавить человека в состав вручную"))
async def cmd_add_staff(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    parts = (args or "").split()
    if not parts or not parts[0].isdigit():
        return await message.reply("Формат: <code>добавить в состав 4 @user Филипп</code>")
    rank = max(1, min(int(parts[0]), MAX_RANK))
    rest = " ".join(parts[1:])
    m = re.search(r"@([A-Za-z0-9_]{4,})", rest)
    username = m.group(1) if m else ""
    name = rest.replace(f"@{username}", "").strip() or username
    if not username and not name:
        return await message.reply("Укажите @ник или имя.")
    row = await db.fetchone("SELECT COALESCE(MAX(pos),0)+1 p FROM staff WHERE chat_id=?",
                            (message.chat.id,))
    await db.execute(
        "INSERT INTO staff (chat_id,username,name,rank,user_id,left_chat,ts,pos) "
        "VALUES (?,?,?,?,0,0,?,?) ON CONFLICT(chat_id,username) DO UPDATE SET "
        "name=excluded.name, rank=excluded.rank",
        (message.chat.id, username or name, name, rank, int(time.time()), row["p"]))
    await message.reply(f"✅ Добавлен в состав: <b>{stars(rank)} {html.escape(name)}</b>")


@router.message(Cmd("удалить из состава", section=S, rank=4,
                    usage="удалить из состава @user", desc="Убрать из состава"))
async def cmd_del_staff(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip().lstrip("@")
    if not a:
        return await message.reply("Формат: <code>удалить из состава @user</code>")
    await db.execute("DELETE FROM staff WHERE chat_id=? AND (lower(username)=lower(?) "
                     "OR lower(name)=lower(?))", (message.chat.id, a, a))
    await message.reply(f"🗑 Удалено из состава: <b>{html.escape(a)}</b>")


@router.message(Cmd("глобальные ранги", "единые ранги", section=S, rank=5,
                    usage="глобальные ранги вкл|выкл",
                    desc="Одно звание во всех чатах"))
async def cmd_global_ranks(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 5):
        return
    a = (args or "").strip().lower()
    if a in {"вкл", "on", "да"}:
        await db.set_setting(message.chat.id, "global_ranks", "1")
        return await message.reply(
            "✅ <b>Глобальные ранги включены</b>\n\n"
            "Звание человека одинаково во всех чатах и темах: "
            "берётся его наивысший ранг.")
    if a in {"выкл", "off", "нет"}:
        await db.set_setting(message.chat.id, "global_ranks", "0")
        return await message.reply(
            "⚠️ <b>Глобальные ранги выключены</b>\n\n"
            "Теперь ранг действует только в том чате, где выдан.")
    cur = await db.get_setting(message.chat.id, "global_ranks", "1")
    await message.reply(
        f"🌐 Глобальные ранги: <b>{'включены' if cur == '1' else 'выключены'}</b>\n\n"
        f"<i>Включено — звание одинаково во всех чатах.</i>\n"
        f"Изменить: <code>глобальные ранги выкл</code>")
