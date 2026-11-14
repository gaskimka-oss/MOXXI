"""Раздел 1: команды модерации — ранги 1–7, состав, созыв, импорт списка."""
from __future__ import annotations

import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
import core_members as members
from core_ranks import effective_rank, get_rank, rank_label, rank_name, require, set_rank
from core_registry import MAX_RANK, RANK_NAMES, RANK_TITLES, Cmd, stars
from core_resolve import resolve_target
from utils import mention_id

router = Router(name="mod_ranks")
S = 1

# Стиль MOXXI: 🏐 в чате, ➖ вышел из чата
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
    """Собирает состав администрации. Исключает снятых, забаненных и вышедших участников."""
    out: dict[int, list[tuple[str, bool]]] = {}

    # 1. Получаем список забаненных в чате (навсегда или действующие)
    now_ts = int(time.time())
    b_rows = await db.fetchall(
        "SELECT user_id FROM bans WHERE chat_id=? AND (until=0 OR until>?)",
        (chat_id, now_ts)
    )
    banned_uids = {b["user_id"] for b in b_rows}

    # Сразу очищаем забаненных из таблицы рангов и стаффа
    for b_uid in banned_uids:
        await db.execute("DELETE FROM ranks WHERE chat_id=? AND user_id=?", (chat_id, b_uid))
        await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (chat_id, b_uid))

    rows = await db.fetchall(
        "SELECT r.user_id, r.rank, u.first_name, u.username FROM ranks r "
        "LEFT JOIN users u ON u.user_id = r.user_id "
        "WHERE r.chat_id=? AND r.rank>0", (chat_id,))
    seen_ids = set()

    for r in rows:
        uid = r["user_id"]
        if uid in banned_uids:
            continue

        fname = r["first_name"]
        uname = r["username"]

        # Живая проверка через Telegram API
        if bot and uid:
            try:
                cm = await bot.get_chat_member(chat_id, uid)
                if cm.status in {"left", "kicked"}:
                    # Пользователь вышел или забанен в Telegram — удаляем ранг и не показываем!
                    await db.execute("DELETE FROM ranks WHERE chat_id=? AND user_id=?", (chat_id, uid))
                    await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (chat_id, uid))
                    continue
                if cm and cm.user:
                    u_live = cm.user
                    fname = u_live.first_name or fname
                    uname = u_live.username or uname
                    await db.touch_user(uid, uname, fname)
            except Exception:
                pass

        seen_ids.add(uid)
        out.setdefault(r["rank"], []).append((_link(uname, fname, uid), False, uid))

    # Из таблицы staff берем ТОЛЬКО тех, у кого нет user_id (нераспознанные при импорте @ники), и кто НЕ вышел!
    srows = await db.fetchall(
        "SELECT username, name, rank, user_id, left_chat FROM staff "
        "WHERE chat_id=? AND (left_chat=0 OR left_chat IS NULL) "
        "ORDER BY rank DESC, pos ASC, rowid ASC", (chat_id,))
    for r in srows:
        uid = r["user_id"] or 0
        uname = r["username"]
        fname = r["name"]
        if uid:
            if uid in seen_ids or uid in banned_uids:
                continue
            # Если пользователь есть в staff, но удален из ranks — он был снят! Чистим staff
            await db.execute("DELETE FROM staff WHERE chat_id=? AND user_id=?", (chat_id, uid))
            continue

        if uname:
            # Проверяем, не забанен ли этот username в chat_id
            b_u = await db.fetchone(
                "SELECT user_id FROM bans WHERE chat_id=? AND user_id IN "
                "(SELECT user_id FROM users WHERE lower(username)=lower(?)) "
                "AND (until=0 OR until>?)",
                (chat_id, uname.lstrip("@"), now_ts)
            )
            if b_u:
                await db.execute("DELETE FROM staff WHERE chat_id=? AND lower(username)=lower(?)",
                                 (chat_id, uname.lstrip("@")))
                continue

        out.setdefault(r["rank"], []).append((_link(uname, fname, 0), False, 0))

    return out


import core_themes
import core_hierarchies
STAFF_THEMES = core_themes.ALL_THEMES


def _render_staff(
    groups: dict[int, list[tuple]],
    title: str = "А Д М И Н И С Т Р А Ц И Я   Б Е С Е Д Ы",
    theme: str = "rainbow",
    hierarchy: str = "default",
    genders: dict[int, str] | None = None
) -> str:
    """Оформление состава модерации с поддержкой кастомных тем чата, типов сообществ и гендера."""
    from core_registry import RANK_RAINBOW_BULLETS, RANK_RAINBOW_HEADERS, RANK_RAINBOW_PLURAL_HEADERS

    t = STAFF_THEMES.get(theme) or STAFF_THEMES["rainbow"]
    h_info = core_hierarchies.COMMUNITY_TYPES.get(hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])
    genders = genders or {}

    banner = t["banner"]
    header = f"{banner}\n" + t["header_title"].format(title=title) + f"\n{banner}"

    if not groups:
        return (
            f"{header}\n\n"
            "<i>В этой группе ещё не назначен состав модерации.</i>\n\n"
            "👑 Создатель группы автоматически получает ранг.\n"
            "Назначить администратора: <code>+модер 3 @user</code>\n\n"
            f"{t['footer_banner']}"
        )

    parts = [header, ""]
    total_staff = sum(len(p) for p in groups.values())

    for rank in sorted(groups, reverse=True):
        people = groups[rank]
        if not people:
            continue

        rank_genders = [genders.get(item[2], "none") for item in people if len(item) >= 3 and item[2]]

        if len(people) == 1:
            p_gender = rank_genders[0] if rank_genders else "none"
            raw_title = core_hierarchies.get_rank_title(rank, gender=p_gender, hierarchy_id=hierarchy)
        else:
            all_female = len(rank_genders) > 0 and all(g == "female" for g in rank_genders)
            raw_title = core_hierarchies.get_rank_plural_title(rank, hierarchy_id=hierarchy, all_female=all_female)

        rank_icon = h_info["icons"].get(rank, t["bullets"].get(rank, "🔹"))
        head = f"{rank_icon} {raw_title}"

        parts.append(t["group_box"].format(head=head))
        bullet = t["bullets"].get(rank, RANK_RAINBOW_BULLETS.get(rank, "🔹"))
        for idx, item in enumerate(people):
            link = item[0]
            left = item[1]
            uid = item[2] if len(item) >= 3 else 0
            is_last = (idx == len(people) - 1)
            branch = t["branch_last"] if is_last else t["branch_mid"]
            if left:
                parts.append(f"{branch} 🔴 <b>{link}</b> <i>(вышел)</i>")
            else:
                parts.append(f"{branch} {bullet} <b>{link}</b>")
        parts.append("")

    parts.append(t["footer_banner"])
    parts.append(t["footer_fmt"].format(total=total_staff))
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
            "ON CONFLICT(chat_id, username) DO UPDATE SET rank=excluded.rank, name=excluded.name, user_id=excluded.user_id, ts=excluded.ts",
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
            pattern = rf"(?:\b|\+){re.escape(name)}\b"
            m = re.search(pattern, t)
            if m:
                start = m.start()
                if start > 0 and text[start-1] in "+-!":
                    start -= 1
                rest = (text[:start] + text[m.end():]).strip()
                rest = re.sub(r"^[+\-!\s]+|[+\-!\s]+$", "", rest).strip()
                return r, rest

    m_phrase = re.search(r"\b(?:ранг|ранга|до|на|ур|уровень|уровня|lvl)\s*([1-9]|10)\b", t)
    if m_phrase:
        r = int(m_phrase.group(1))
        rest = (text[:m_phrase.start()] + text[m_phrase.end():]).strip()
        rest = re.sub(r"^[+\-!\s]+|[+\-!\s]+$", "", rest).strip()
        return r, rest

    words = text.split()
    for idx, w in enumerate(words):
        clean_w = w.lstrip("+-!#")
        if clean_w.isdigit() and 1 <= int(clean_w) <= MAX_RANK:
            r = int(clean_w)
            rest_words = words[:idx] + words[idx+1:]
            rest = " ".join(rest_words).strip()
            rest = re.sub(r"^[+\-!\s]+|[+\-!\s]+$", "", rest).strip()
            return r, rest

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


@router.message(Cmd("+модер", "+админ", "+ранг", "+ра", "+ra", "дать ранг", "выдать ранг", "назначить ранг", "назначить", section=S, rank=6,
                    usage="+ра {ссылка} [1-10 / должность]",
                    desc="Назначить ранг модератора (1–10)"))
async def cmd_promote_rank(message: Message, bot: Bot, args: str = "", **kw):
    found_r, clean_args = _parse_rank_from_text(args or "")
    if found_r is not None:
        return await _grant(message, bot, clean_args, found_r, **kw)

    parts = (args or "").split()
    rank = None
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

    if rank is None:
        # Если ранг не указан (например "+ra @user" или "+модер @user" или реплай "+ra")
        uid, name, _ = await resolve_target(message, args, bot)
        uname = None
        if not uid:
            m_u = re.search(r"@([a-zA-Z0-9_]{3,32})", args or "")
            if m_u:
                uname = m_u.group(1)
        if uid:
            cur = await get_rank(message.chat.id, uid)
            rank = min(MAX_RANK, cur + 1)
        elif uname:
            clean_u = uname.lstrip("@")
            srow = await db.fetchone("SELECT rank FROM staff WHERE chat_id=? AND lower(username)=lower(?)", (message.chat.id, clean_u))
            cur = int(srow["rank"]) if srow else 0
            rank = min(MAX_RANK, cur + 1)
        else:
            rank = 1

    await _grant(message, bot, args, rank, **kw)


@router.message(Cmd("повысить", "поднять ранг", "+повысить", "!повысить", section=S, rank=6, usage="повысить {ссылка} [ранг]",
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


@router.message(Cmd("понизить", "разжаловать", "снизить", "-понизить", "-ра", "-ra", "-ранг", section=S, rank=6,
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
    # Защита от перехвата банковских/экономических команд (снять вклад, снять депозит)
    if args and args.lower().split()[0] in {"вклад", "депозит", "банк", "монеты", "деньги", "кассу"}:
        return
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

    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (message.chat.id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    uids = [item[2] for people in groups.values() for item in people if len(item) >= 3 and item[2]]
    genders = {}
    if uids:
        placeholders = ",".join("?" for _ in uids)
        rows = await db.fetchall(f"SELECT user_id, gender FROM users WHERE user_id IN ({placeholders})", tuple(uids))
        for r in rows:
            g = core_hierarchies.normalize_gender(r.get("gender"))
            if g != "none":
                genders[r["user_id"]] = g
        missing = [uid for uid in uids if uid not in genders]
        if missing:
            p_placeholders = ",".join("?" for _ in missing)
            p_rows = await db.fetchall(f"SELECT user_id, gender FROM profiles WHERE user_id IN ({p_placeholders})", tuple(missing))
            for r in p_rows:
                g = core_hierarchies.normalize_gender(r.get("gender"))
                if g != "none":
                    genders[r["user_id"]] = g

    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])
    title_text = f"Состав: {h_info['short_name']}"
    text = _render_staff(groups, title_text, theme=cur_theme, hierarchy=cur_hierarchy, genders=genders)
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
    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (message.chat.id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"
    uids = [item[2] for people in top.values() for item in people if len(item) >= 3 and item[2]]
    genders = {}
    if uids:
        placeholders = ",".join("?" for _ in uids)
        rows = await db.fetchall(f"SELECT user_id, gender FROM users WHERE user_id IN ({placeholders})", tuple(uids))
        for r in rows:
            g = core_hierarchies.normalize_gender(r.get("gender"))
            if g != "none":
                genders[r["user_id"]] = g
    await message.reply(_render_staff(top, "Руководство чата", theme=cur_theme, hierarchy=cur_hierarchy, genders=genders),
                        disable_web_page_preview=True)


@router.message(Cmd("ранги", "список рангов", "иерархия", "привилегии", section=S, usage="ранги",
                    desc="Все ранги, короткие команды назначения и их права"))
async def cmd_ranks_help(message: Message, **kw):
    from core_registry import RANK_RAINBOW_HEADERS
    perms = {
        10: "полный контроль, высший иммунитет, передача лидерства",
        9: "заместитель: управление модерацией 1–8 ранга, настройки чата",
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
    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (message.chat.id,))
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])

    uid, name, _ = await resolve_target(message, args, bot)
    if uid:
        r = await get_rank(message.chat.id, uid)
        u_gender = await core_hierarchies.get_user_gender(uid)
        title_str = core_hierarchies.get_rank_title(r, gender=u_gender, hierarchy_id=cur_hierarchy)
        icon = h_info["icons"].get(r, stars(r))
        g_badge = " ♀" if u_gender == "female" else (" ♂" if u_gender == "male" else "")
        return await message.reply(
            f"{mention_id(uid, name)} — <b>{icon} {title_str}</b>{g_badge} (ранг {r})\n"
            f"<i>Стиль чата: {h_info['name']}</i>")

    r = await effective_rank(message, bot)
    my_uid = message.from_user.id if message.from_user else 0
    my_gender = await core_hierarchies.get_user_gender(my_uid)
    title_str = core_hierarchies.get_rank_title(r, gender=my_gender, hierarchy_id=cur_hierarchy)
    icon = h_info["icons"].get(r, stars(r))
    g_text = "🙋‍♀️ Девушка" if my_gender == "female" else ("🙋‍♂️ Парень" if my_gender == "male" else "Не указан (нажмите «дизайн» для выбора)")

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
        f"Ваш ранг: <b>{icon} {title_str}</b> ({r})\n"
        f"🏰 <i>Стиль группы: {h_info['name']}</i>\n"
        f"👤 <i>Ваш пол: {g_text}</i>\n"
        f"<i>Источник: {src}</i>\n"
        f"<i>Чат: <code>{message.chat.id}</code></i>")


# ---------------- Импорт готового списка ----------------
STAR_RE = re.compile(r"^\s*\**\s*(⭐+|\*+)\s*(.+?)\s*\**\s*$")
PERSON_RE = re.compile(
    r"^\s*(🏐|➖|•|·|-)?\s*(?:\[([^\]]+)\]\s*\(\s*<?(?:https?://)?(?:telegram\.me|t\.me)/"
    r"([A-Za-z0-9_]+)[^)]*\)|@([A-Za-z0-9_]{4,})|(.+?))\s*$")

TITLE_TO_RANK = {
    # 10 ранг (Создатели, лидеры, главы кланов)
    "лидер чата": 10, "лидеры чата": 10, "лидер клана": 10, "лидеры клана": 10, "лидер": 10, "лидеры": 10,
    "создатель": 10, "создатели": 10, "владелец": 10, "владельцы": 10, "владелец чата": 10,
    "лидерша": 10, "лидерши": 10, "лидерша чата": 10, "лидерши чата": 10, "лидерша клана": 10, "предводительница": 10,
    "владелица": 10, "владелицы": 10, "владелица чата": 10, "создательница": 10, "создательницы": 10,
    "глава клана": 10, "главы клана": 10, "вождь": 10, "босс синдиката": 10, "госпожа синдиката": 10,
    "сегун": 10, "сёгун": 10, "императрица": 10, "князь тьмы": 10, "владычица ночи": 10, "император": 10,
    # 9 ранг (Заместители, советники, канцлеры)
    "заместитель лидера": 9, "заместители лидера": 9, "зам лидера": 9, "замы лидера": 9, "зам": 9, "замы": 9,
    "заместитель": 9, "заместители": 9, "заместительница": 9, "заместительницы": 9, "замка": 9, "замки": 9,
    "советница": 9, "советницы": 9, "советник": 9, "советники": 9, "советница клана": 9, "зам главы": 9,
    "вице-президент": 9, "правая рука": 9, "архивампир": 9, "верховная жрица": 9, "канцлер": 9, "канцлерша": 9,
    # 8 ранг (Тех. админы, архитекторы, стратеги)
    "технический администратор": 8, "технические администраторы": 8, "тех админ": 8, "техадмин": 8, "техадмины": 8,
    "тех. администраторша": 8, "тех администраторша": 8, "стратег": 8, "стратегиня": 8, "архитектор": 8, "архивариус": 8,
    # 7 ранг (Главные админы, маршалы, директора)
    "главный администратор": 7, "главные администраторы": 7, "главный админ": 7, "главные админы": 7, "га": 7,
    "главная админша": 7, "главная администраторша": 7, "маршал": 7, "маршальша": 7, "верховный маршал": 7,
    "директор": 7, "директриса": 7, "дайме": 7, "даймё": 7, "герцог": 7, "герцогиня": 7,
    # 6 ранг (Старшие админы, командоры)
    "старший администратор": 6, "старшие администраторы": 6, "старший админ": 6, "старшие админы": 6, "са": 6,
    "старшая админша": 6, "старшая администраторша": 6, "командор": 6, "командорша": 6, "старший самурай": 6, "инквизитор": 6,
    # 5 ранг (Младшие админы, центурионы, валькирии)
    "младший администратор": 5, "младшие администраторы": 5, "младший админ": 5, "младшие админы": 5, "ма": 5,
    "младшая админша": 5, "младшая администраторша": 5, "центурион": 5, "валькирия": 5, "нетраннер": 5, "нетраннерша": 5, "рыцарь": 5,
    # 4 ранг (Главные модеры, ветераны, воительницы)
    "главный модератор": 4, "главные модераторы": 4, "главный модер": 4, "главные модеры": 4, "гм": 4,
    "главная модераторша": 4, "ветеран": 4, "воительница": 4, "синоби": 4, "куноити": 4,
    # 3 ранг (Старшие модеры, бойцы, защитницы)
    "старший модератор": 3, "старшие модераторы": 3, "старший модер": 3, "старшие модеры": 3, "см": 3,
    "старшая модераторша": 3, "боец": 3, "старший боец": 3, "защитница": 3, "старшая защитница": 3, "гвардеец": 3,
    # 2 ранг (Младшие модеры, асигару, стражи)
    "младший модератор": 2, "младшие модераторы": 2, "младший модер": 2, "младшие модеры": 2, "мм": 2,
    "младшая модераторша": 2, "младший боец": 2, "асигару": 2, "страж": 2, "младшая стражница": 2,
    # 1 ранг (Стажеры, рекруты, пиарщики)
    "стажер": 1, "стажёр": 1, "стажеры": 1, "стажёры": 1, "стажерка": 1, "стажёрка": 1, "стажерки": 1, "стажёрки": 1,
    "рекрут": 1, "рекрутка": 1, "неофит": 1, "неофитка": 1, "ученик": 1, "ученица": 1, "оруженосец": 1,
    "пиарщик": 1, "пиарщица": 1, "пиар": 1, "пр": 1,
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
            if not name or name.lower().startswith(("http", "бот", "мокси")):
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


# ═════════════════════════════════════════════════════════════════════
# 🎨 КАСТОМИЗАЦИЯ ДИЗАЙНА ЧАТА, ИЕРАРХИИ И ГЕНДЕРОВ (Обновление 3.0)
# ═════════════════════════════════════════════════════════════════════

def _make_design_hub_kb(cur_theme: str, cur_hierarchy: str, user_gender: str) -> InlineKeyboardMarkup:
    """Главная клавиатура Центра дизайна MOXXI 3.0."""
    t_info = STAFF_THEMES.get(cur_theme, STAFF_THEMES["rainbow"])
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])

    if user_gender == "female":
        gender_btn = "👤 Мой пол: 🙋‍♀️ Девушка (Сменить на 🙋‍♂️)"
    elif user_gender == "male":
        gender_btn = "👤 Мой пол: 🙋‍♂️ Парень (Сменить на 🙋‍♀️)"
    else:
        gender_btn = "👤 Мой пол: ❓ Не выбран (Выбрать 🙋‍♀️ / 🙋‍♂️)"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🎨 Тема: {t_info['badge']} {t_info['name'].split('(')[0].strip()}",
                callback_data="chat_theme:themes"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🏰 Иерархия: {h_info['icon']} {h_info['short_name']}",
                callback_data="chat_theme:hierarchies"
            )
        ],
        [
            InlineKeyboardButton(
                text=gender_btn,
                callback_data="chat_theme:toggle_gender"
            )
        ],
        [
            InlineKeyboardButton(text="👁 Живой пример", callback_data="chat_theme:live_preview"),
            InlineKeyboardButton(text="📋 Состав чата", callback_data="chat_theme:view_staff")
        ]
    ])


def _make_theme_menu_kb(cur_theme: str) -> InlineKeyboardMarkup:
    """Генерирует инлайн-кнопки для выбора из 15 тем чата."""
    kb_rows = []
    themes_list = list(STAFF_THEMES.values())
    for i in range(0, len(themes_list), 2):
        row = []
        for t in themes_list[i:i+2]:
            mark = " ✅" if t["id"] == cur_theme else ""
            row.append(InlineKeyboardButton(text=f"{t['badge']} {t['name'].split('(')[0].strip()}{mark}",
                                              callback_data=f"chat_theme:select:{t['id']}"))
        kb_rows.append(row)
    kb_rows.append([
        InlineKeyboardButton(text="◀️ В главное меню дизайна", callback_data="chat_theme:hub")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


def _make_hierarchies_menu_kb(cur_hierarchy: str) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру выбора типа сообщества (Клан, Чат, Синдикат, Самураи, Ковен, Империя)."""
    kb_rows = []
    h_list = list(core_hierarchies.COMMUNITY_TYPES.values())
    for i in range(0, len(h_list), 2):
        row = []
        for h in h_list[i:i+2]:
            mark = " ✅" if h["id"] == cur_hierarchy else ""
            row.append(InlineKeyboardButton(text=f"{h['icon']} {h['short_name']}{mark}",
                                              callback_data=f"chat_theme:h_select:{h['id']}"))
        kb_rows.append(row)
    kb_rows.append([
        InlineKeyboardButton(text="◀️ В главное меню дизайна", callback_data="chat_theme:hub")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(Cmd("дизайн", "дизайн чата", "дизайн группы", "стиль оформления", "тема оформления",
                    "дизайн состава", "тема состава", "стиль состава", "стиль чата", "оформление состава", "оформление чата",
                    section=34, group_only=True,
                    usage="дизайн чата", desc="🎨 Настройка дизайна оформления, иерархии рангов и пола"))
async def cmd_chat_design(message: Message, bot: Bot, **kw):
    from config import is_bot_owner
    uid = message.from_user.id if message.from_user else 0

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_themes ("
        "chat_id INTEGER PRIMARY KEY, "
        "theme TEXT NOT NULL DEFAULT 'rainbow', "
        "hierarchy TEXT NOT NULL DEFAULT 'default', "
        "gender_mode TEXT NOT NULL DEFAULT 'auto', "
        "updated_at INTEGER NOT NULL DEFAULT 0, "
        "updated_by INTEGER NOT NULL DEFAULT 0)"
    )

    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (message.chat.id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    t_info = STAFF_THEMES.get(cur_theme, STAFF_THEMES["rainbow"])
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])

    user_gender = await core_hierarchies.get_user_gender(uid)
    gender_text = "🙋‍♀️ Девушка" if user_gender == "female" else ("🙋‍♂️ Парень" if user_gender == "male" else "Не указан (нажмите кнопку ниже)")

    leader_sample = core_hierarchies.get_rank_title(10, gender=user_gender, hierarchy_id=cur_hierarchy)
    zam_sample = core_hierarchies.get_rank_title(9, gender=user_gender, hierarchy_id=cur_hierarchy)

    txt = (
        "🎨 ════════════ • 💎 • ════════════ 🎨\n"
        "👑 ✨ <b>ЦЕНТР ДИЗАЙНА И ОФОРМЛЕНИЯ ЧАТА</b> ✨ 👑\n"
        "🎨 ════════════ • 💎 • ════════════ 🎨\n\n"
        "Добро пожаловать в центр кастомизации MOXXI 3.0!\n"
        "Настройте оформление, стиль сообщества и титулы рангов для вашей группы:\n\n"
        f"• 🎨 <b>Цветовая тема:</b> {t_info['badge']} <b>{t_info['name']}</b>\n"
        f"• 🏰 <b>Тип группы:</b> {h_info['icon']} <b>{h_info['name']}</b>\n"
        f"• 👤 <b>Ваш личный пол:</b> <b>{gender_text}</b>\n"
        f"• 👑 <b>Титул лидера:</b> <b>{leader_sample}</b>\n"
        f"• 🔱 <b>Титул зама:</b> <b>{zam_sample}</b>\n\n"
        "💡 <i>Девушки могут включить отображение в женском роде (Лидерша чата, Заместительница, Админша, Модераторша) кликом по кнопке «Мой пол»!</i>\n\n"
        "👇 <b>Выберите категорию для настройки:</b>"
    )

    await message.reply(txt, reply_markup=_make_design_hub_kb(cur_theme, cur_hierarchy, user_gender))


@router.callback_query(F.data == "chat_theme:hub")
async def cb_theme_hub(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    uid = cq.from_user.id

    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    t_info = STAFF_THEMES.get(cur_theme, STAFF_THEMES["rainbow"])
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])
    user_gender = await core_hierarchies.get_user_gender(uid)
    gender_text = "🙋‍♀️ Девушка" if user_gender == "female" else ("🙋‍♂️ Парень" if user_gender == "male" else "Не указан")

    leader_sample = core_hierarchies.get_rank_title(10, gender=user_gender, hierarchy_id=cur_hierarchy)
    zam_sample = core_hierarchies.get_rank_title(9, gender=user_gender, hierarchy_id=cur_hierarchy)

    txt = (
        "🎨 ════════════ • 💎 • ════════════ 🎨\n"
        "👑 ✨ <b>ЦЕНТР ДИЗАЙНА И ОФОРМЛЕНИЯ ЧАТА</b> ✨ 👑\n"
        "🎨 ════════════ • 💎 • ════════════ 🎨\n\n"
        "Добро пожаловать в центр кастомизации MOXXI 3.0!\n\n"
        f"• 🎨 <b>Цветовая тема:</b> {t_info['badge']} <b>{t_info['name']}</b>\n"
        f"• 🏰 <b>Тип группы:</b> {h_info['icon']} <b>{h_info['name']}</b>\n"
        f"• 👤 <b>Ваш личный пол:</b> <b>{gender_text}</b>\n"
        f"• 👑 <b>Титул лидера:</b> <b>{leader_sample}</b>\n"
        f"• 🔱 <b>Титул зама:</b> <b>{zam_sample}</b>\n\n"
        "👇 <b>Выберите категорию для настройки:</b>"
    )

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_design_hub_kb(cur_theme, cur_hierarchy, user_gender))
    await cq.answer()


@router.callback_query(F.data.in_({"chat_theme:themes", "chat_theme:menu"}))
async def cb_theme_themes_menu(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT theme FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    t_info = STAFF_THEMES.get(cur_theme, STAFF_THEMES["rainbow"])

    txt = (
        "🎨 <b>ВЫБОР ЦВЕТОВОЙ ТЕМЫ ОФОРМЛЕНИЯ</b>\n\n"
        f"📌 Текущий стиль: <b>{t_info['name']}</b>\n"
        f"📝 <i>{t_info['desc']}</i>\n\n"
        "👇 Выберите тему ниже, чтобы увидеть превью или установить её для этого чата:"
    )

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_theme_menu_kb(cur_theme))
    await cq.answer()


@router.callback_query(F.data.startswith("chat_theme:select:"))
async def cb_theme_select(cq: CallbackQuery, bot: Bot):
    theme_id = cq.data.split(":", 2)[2]
    t = STAFF_THEMES.get(theme_id)
    if not t:
        return await cq.answer("⚠️ Неизвестная тема", show_alert=True)

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT theme FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    is_active = (theme_id == cur_theme)

    txt = (
        f"🎨 <b>ВЫБРАН СТИЛЬ: {t['name']}</b>\n\n"
        f"📝 <b>Описание:</b> {t['desc']}\n"
        f"Статус в этом чате: <b>{'🟢 Активен сейчас' if is_active else '⚪️ Не активен'}</b>\n\n"
        "<i>Нажмите кнопку ниже, чтобы увидеть пример прямо в чате или применить стиль:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Посмотреть как будет выглядеть в чате",
                                 callback_data=f"chat_theme:preview:{theme_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Установить для этого чата",
                                 callback_data=f"chat_theme:apply:{theme_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад ко всем темам",
                                 callback_data="chat_theme:themes")
        ]
    ])

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("chat_theme:apply:"))
async def cb_theme_apply(cq: CallbackQuery, bot: Bot):
    from config import is_bot_owner
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    uid = cq.from_user.id
    me = await effective_rank(cq.message, bot) if cq.message else 0
    if me < 3 and not is_bot_owner(uid):
        return await cq.answer("⛔️ Устанавливать стиль беседы могут администраторы от 3 ранга!", show_alert=True)

    theme_id = cq.data.split(":", 2)[2]
    t = STAFF_THEMES.get(theme_id)
    if not t:
        return await cq.answer("⚠️ Неизвестная тема", show_alert=True)

    now = int(time.time())
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_themes ("
        "chat_id INTEGER PRIMARY KEY, "
        "theme TEXT NOT NULL DEFAULT 'rainbow', "
        "hierarchy TEXT NOT NULL DEFAULT 'default', "
        "gender_mode TEXT NOT NULL DEFAULT 'auto', "
        "updated_at INTEGER NOT NULL DEFAULT 0, "
        "updated_by INTEGER NOT NULL DEFAULT 0)"
    )
    await db.execute(
        "INSERT INTO chat_themes (chat_id, theme, updated_at, updated_by) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET theme=excluded.theme, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (chat_id, theme_id, now, uid)
    )

    success_txt = (
        "🎉 <b>СТИЛЬ УСПЕШНО УСТАНОВЛЕН!</b>\n\n"
        f"Для этого чата активирована тема: <b>{t['name']}</b> {t['badge']}\n\n"
        "✨ Теперь списки администрации и модерации оформлены в этом дизайне!\n"
        "🔍 Проверьте командой: <code>админы</code> или <code>состав</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Посмотреть в чате", callback_data=f"chat_theme:preview:{theme_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ В меню дизайна", callback_data="chat_theme:hub")
        ]
    ])

    if cq.message:
        await cq.message.edit_text(success_txt, reply_markup=kb)
    await cq.answer(f"✅ Стиль «{t['name']}» установлен!", show_alert=True)


@router.callback_query(F.data.startswith("chat_theme:preview:"))
async def cb_theme_preview(cq: CallbackQuery, bot: Bot):
    theme_id = cq.data.split(":", 2)[2]
    t = STAFF_THEMES.get(theme_id)
    if not t:
        return await cq.answer("⚠️ Неизвестная тема", show_alert=True)

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_h = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    uid = cq.from_user.id
    u_gender = await core_hierarchies.get_user_gender(uid)

    sample_groups = {
        10: [("👑 " + core_hierarchies.get_rank_title(10, u_gender, cur_h), False, uid)],
        7: [("💎 " + core_hierarchies.get_rank_title(7, "male", cur_h), False, 0)],
        4: [("⚔️ " + core_hierarchies.get_rank_title(4, "female", cur_h), False, 0),
            ("🛡️ " + core_hierarchies.get_rank_title(4, "male", cur_h), False, 0)]
    }
    sample_genders = {uid: u_gender}

    rendered_sample = _render_staff(sample_groups, "СОСТАВ АДМИНИСТРАЦИИ (ПРЕВЬЮ)",
                                    theme=theme_id, hierarchy=cur_h, genders=sample_genders)

    preview_msg = (
        f"👁 <b>ПРЕДПРОСМОТР СТИЛЯ: {t['name']}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{rendered_sample}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Если вам нравится этот вид — нажмите кнопку «✅ Установить» в меню настроек!</i>"
    )

    if cq.message:
        await cq.message.reply(preview_msg, disable_web_page_preview=True)
    await cq.answer("👁 Превью отправлено в чат!", show_alert=False)


# ---------------- Иерархии и типы групп ----------------

@router.callback_query(F.data == "chat_theme:hierarchies")
async def cb_hierarchies_menu(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_h = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_h, core_hierarchies.COMMUNITY_TYPES["default"])

    txt = (
        "🏰 <b>ВЫБОР ТИПА СООБЩЕСТВА И ИЕРАРХИИ РАНГОВ</b>\n\n"
        "В зависимости от формата чата вы можете выбрать подходящие звания:\n"
        "• <b>Клан / Гильдия</b> — звания: Глава, Советница, Маршалы, Валькирии, Ветераны, Рекруты.\n"
        "• <b>Обычная беседа</b> — звания: Владелец, Заместительница, Админы, Модеры, Стажёры.\n"
        "• <b>Кибер-Синдикат</b> — звания: Босс, Госпожа Синдиката, Вице-Президент, Нетраннеры.\n"
        "• <b>Самураи / Аниме</b> — звания: Сёгун, Императрица, Советница, Даймё, Самураи, Куноити.\n"
        "• <b>Тёмный Ковен</b> — звания: Князь Тьмы, Владычица Ночи, Жрицы, Лорды Крови.\n"
        "• <b>Императорский Двор</b> — звания: Император, Канцлерша, Герцоги, Рыцари.\n\n"
        f"📌 Текущий тип: {h_info['icon']} <b>{h_info['name']}</b>\n\n"
        "👇 Выберите тип группы ниже для просмотра деталей и установки:"
    )

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_hierarchies_menu_kb(cur_h))
    await cq.answer()


@router.callback_query(F.data.startswith("chat_theme:h_select:"))
async def cb_h_select(cq: CallbackQuery, bot: Bot):
    h_id = cq.data.split(":", 2)[2]
    h = core_hierarchies.COMMUNITY_TYPES.get(h_id)
    if not h:
        return await cq.answer("⚠️ Неизвестный тип сообщества", show_alert=True)

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_h = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"
    is_active = (h_id == cur_h)

    txt = (
        f"🏰 <b>ТИП СООБЩЕСТВА: {h['name']}</b>\n\n"
        f"📝 <b>Описание:</b> {h['desc']}\n"
        f"Статус в этом чате: <b>{'🟢 Активен сейчас' if is_active else '⚪️ Не активен'}</b>\n\n"
        "👑 <b>Примеры званий (Парень / Девушка):</b>\n"
        f"• Ранг 10: <b>{h['male'][10]}</b> / <b>{h['female'][10]}</b>\n"
        f"• Ранг 9: <b>{h['male'][9]}</b> / <b>{h['female'][9]}</b>\n"
        f"• Ранг 6: <b>{h['male'][6]}</b> / <b>{h['female'][6]}</b>\n"
        f"• Ранг 5: <b>{h['male'][5]}</b> / <b>{h['female'][5]}</b>\n"
        f"• Ранг 1: <b>{h['male'][1]}</b> / <b>{h['female'][1]}</b>\n\n"
        "<i>Нажмите кнопку ниже, чтобы применить этот стиль для всей беседы:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Посмотреть пример в чате",
                                 callback_data=f"chat_theme:h_preview:{h_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Установить этот тип для группы",
                                 callback_data=f"chat_theme:h_apply:{h_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к выбору типов",
                                 callback_data="chat_theme:hierarchies")
        ]
    ])

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("chat_theme:h_apply:"))
async def cb_h_apply(cq: CallbackQuery, bot: Bot):
    from config import is_bot_owner
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    uid = cq.from_user.id
    me = await effective_rank(cq.message, bot) if cq.message else 0
    if me < 3 and not is_bot_owner(uid):
        return await cq.answer("⛔️ Менять тип группы могут администраторы от 3 ранга!", show_alert=True)

    h_id = cq.data.split(":", 2)[2]
    h = core_hierarchies.COMMUNITY_TYPES.get(h_id)
    if not h:
        return await cq.answer("⚠️ Неизвестный тип сообщества", show_alert=True)

    await core_hierarchies.set_chat_hierarchy(chat_id, h_id, updated_by=uid)

    success_txt = (
        "🎉 <b>ТИП СООБЩЕСТВА УСПЕШНО ИЗМЕНЁН!</b>\n\n"
        f"Для этого чата установлена иерархия: <b>{h['name']}</b> {h['icon']}\n\n"
        "✨ Теперь все списки администрации, модерации и профили используют звания этой темы!\n"
        "🔍 Проверьте командой: <code>состав</code> или <code>мой ранг</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Посмотреть пример в чате", callback_data=f"chat_theme:h_preview:{h_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ В меню дизайна", callback_data="chat_theme:hub")
        ]
    ])

    if cq.message:
        await cq.message.edit_text(success_txt, reply_markup=kb)
    await cq.answer(f"✅ Стиль «{h['short_name']}» активирован!", show_alert=True)


@router.callback_query(F.data.startswith("chat_theme:h_preview:"))
async def cb_h_preview(cq: CallbackQuery, bot: Bot):
    h_id = cq.data.split(":", 2)[2]
    h = core_hierarchies.COMMUNITY_TYPES.get(h_id)
    if not h:
        return await cq.answer("⚠️ Неизвестный тип", show_alert=True)

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT theme FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"

    uid = cq.from_user.id
    u_gender = await core_hierarchies.get_user_gender(uid)

    sample_groups = {
        10: [(core_hierarchies.get_rank_title(10, u_gender, h_id), False, uid)],
        9: [(core_hierarchies.get_rank_title(9, "female", h_id), False, 0)],
        5: [(core_hierarchies.get_rank_title(5, "female", h_id), False, 0),
            (core_hierarchies.get_rank_title(5, "male", h_id), False, 0)],
        1: [(core_hierarchies.get_rank_title(1, "male", h_id), False, 0)]
    }
    sample_genders = {uid: u_gender}

    rendered_sample = _render_staff(sample_groups, f"СОСТАВ: {h['name'].upper()}",
                                    theme=cur_theme, hierarchy=h_id, genders=sample_genders)

    preview_msg = (
        f"👁 <b>ПРЕДПРОСМОТР ИЕРАРХИИ: {h['name']}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{rendered_sample}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Нажмите «Установить этот тип для группы», чтобы применить его!</i>"
    )

    if cq.message:
        await cq.message.reply(preview_msg, disable_web_page_preview=True)
    await cq.answer("👁 Превью отправлено в чат!", show_alert=False)


# ---------------- Интерактивная смена пола ----------------

@router.callback_query(F.data == "chat_theme:toggle_gender")
async def cb_toggle_gender(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    current_g = await core_hierarchies.get_user_gender(uid)
    new_g = "male" if current_g == "female" else "female"
    await core_hierarchies.set_user_gender(uid, new_g)

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    t_info = STAFF_THEMES.get(cur_theme, STAFF_THEMES["rainbow"])
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])

    gender_text = "🙋‍♀️ Девушка" if new_g == "female" else "🙋‍♂️ Парень"
    leader_sample = core_hierarchies.get_rank_title(10, gender=new_g, hierarchy_id=cur_hierarchy)
    zam_sample = core_hierarchies.get_rank_title(9, gender=new_g, hierarchy_id=cur_hierarchy)

    txt = (
        "🎨 ════════════ • 💎 • ════════════ 🎨\n"
        "👑 ✨ <b>ЦЕНТР ДИЗАЙНА И ОФОРМЛЕНИЯ ЧАТА</b> ✨ 👑\n"
        "🎨 ════════════ • 💎 • ════════════ 🎨\n\n"
        "Добро пожаловать в центр кастомизации MOXXI 3.0!\n\n"
        f"• 🎨 <b>Цветовая тема:</b> {t_info['badge']} <b>{t_info['name']}</b>\n"
        f"• 🏰 <b>Тип группы:</b> {h_info['icon']} <b>{h_info['name']}</b>\n"
        f"• 👤 <b>Ваш личный пол:</b> <b>{gender_text}</b>\n"
        f"• 👑 <b>Титул лидера:</b> <b>{leader_sample}</b>\n"
        f"• 🔱 <b>Титул зама:</b> <b>{zam_sample}</b>\n\n"
        "👇 <b>Выберите категорию для настройки:</b>"
    )

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_design_hub_kb(cur_theme, cur_hierarchy, new_g))

    if new_g == "female":
        alert_txt = (
            "💖 Ваш пол изменён на: 🙋‍♀️ ДЕВУШКА!\n\n"
            "✨ Теперь ваши ранги в списках администрации, командах и профиле:\n"
            "• Лидерша чата / Лидерша Клана (10 ранг)\n"
            "• Заместительница (Замка) / Советница (9 ранг)\n"
            "• Старшая админша (6 ранг)\n"
            "• Модераторша / Валькирия (4–5 ранг)\n"
            "• Стажёрка / Рекрутка (1 ранг)"
        )
    else:
        alert_txt = (
            "⚡ Ваш пол изменён на: 🙋‍♂️ ПАРЕНЬ!\n\n"
            "Ваши ранги в списках администрации:\n"
            "• Владелец чата / Глава Клана (10 ранг)\n"
            "• Заместитель / Зам. Главы (9 ранг)\n"
            "• Администратор / Модератор"
        )
    await cq.answer(alert_txt, show_alert=True)


@router.callback_query(F.data == "chat_theme:live_preview")
async def cb_live_preview(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    uid = cq.from_user.id

    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    u_gender = await core_hierarchies.get_user_gender(uid)
    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])

    fname = cq.from_user.first_name or "Лидер"
    sample_groups = {
        10: [(fname, False, uid)],
        9: [("Анна", False, 0)],
        4: [("Максим", False, 0), ("Катя", False, 0)]
    }
    sample_genders = {uid: u_gender, 0: "female"}

    rendered_sample = _render_staff(sample_groups, f"СОСТАВ: {h_info['name'].upper()}",
                                    theme=cur_theme, hierarchy=cur_hierarchy, genders=sample_genders)

    preview_msg = (
        f"👁 <b>ЖИВОЙ ПРИМЕР ОФОРМЛЕНИЯ ВАШЕГО ЧАТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{rendered_sample}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Сменить тему, иерархию или пол можно прямо в интерактивном меню выше!</i>"
    )

    if cq.message:
        await cq.message.reply(preview_msg, disable_web_page_preview=True)
    await cq.answer("👁 Живой пример отправлен в чат!", show_alert=False)


@router.callback_query(F.data == "chat_theme:view_staff")
async def cb_view_staff(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    groups = await _staff_rows(chat_id, bot)

    t_row = await db.fetchone("SELECT theme, hierarchy FROM chat_themes WHERE chat_id=?", (chat_id,))
    cur_theme = t_row["theme"] if (t_row and t_row.get("theme")) else "rainbow"
    cur_hierarchy = t_row["hierarchy"] if (t_row and t_row.get("hierarchy")) else "default"

    uids = [item[2] for people in groups.values() for item in people if len(item) >= 3 and item[2]]
    genders = {}
    if uids:
        placeholders = ",".join("?" for _ in uids)
        rows = await db.fetchall(f"SELECT user_id, gender FROM users WHERE user_id IN ({placeholders})", tuple(uids))
        for r in rows:
            g = core_hierarchies.normalize_gender(r.get("gender"))
            if g != "none":
                genders[r["user_id"]] = g

    h_info = core_hierarchies.COMMUNITY_TYPES.get(cur_hierarchy, core_hierarchies.COMMUNITY_TYPES["default"])
    text = _render_staff(groups, f"Состав: {h_info['short_name']}", theme=cur_theme, hierarchy=cur_hierarchy, genders=genders)

    if cq.message:
        await cq.message.reply(text, disable_web_page_preview=True)
    await cq.answer()


# ---------------- Интерактивный выбор пола (кнопками) ----------------

def _make_gender_selection_kb(current_gender: str, user_id: int) -> InlineKeyboardMarkup:
    f_mark = " 💖 (Выбрано)" if current_gender == "female" else ""
    m_mark = " ⚡ (Выбрано)" if current_gender == "male" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🙋‍♀️ Девушка{f_mark}", callback_data=f"set_user_gender:female:{user_id}"),
            InlineKeyboardButton(text=f"🙋‍♂️ Парень{m_mark}", callback_data=f"set_user_gender:male:{user_id}")
        ]
    ])


@router.message(Cmd("пол", "мой пол", "сменить пол", "выбрать пол",
                    section=34, group_only=False, usage="пол [@юзер]",
                    desc="👤 Интерактивный выбор пола и титулов (кнопками)"))
async def cmd_gender_buttons(message: Message, bot: Bot, args: str = "", **kw):
    target_id = message.from_user.id if message.from_user else 0
    target_name = message.from_user.first_name if message.from_user else "Пользователь"

    # Если админ указал @юзер или реплай — проверяем права
    from core_resolve import real_reply
    if args or real_reply(message) is not None:
        from core_ranks import require
        if await require(message, bot, 3):
            uid, name, _ = await resolve_target(message, args, bot)
            if uid:
                target_id = uid
                target_name = name or str(uid)

    cur_gender = await core_hierarchies.get_user_gender(target_id)
    if cur_gender == "female":
        cur_str = "🙋‍♀️ <b>Девушка</b> (женские титулы: Лидерша, Заместительница, Советница, Валькирия)"
    elif cur_gender == "male":
        cur_str = "🙋‍♂️ <b>Парень</b> (мужские титулы: Владелец, Заместитель, Маршал, Центурион)"
    else:
        cur_str = "⚪️ <b>Не указан</b> (по умолчанию мужские титулы)"

    is_self = (target_id == (message.from_user.id if message.from_user else 0))
    who_str = "Ваш текущий пол" if is_self else f"Текущий пол {mention_id(target_id, target_name)}"

    text = (
        "👤 <b>ВЫБОР ПОЛА И ОТОБРАЖЕНИЯ ТИТУЛОВ</b>\n\n"
        f"• {who_str}: {cur_str}\n\n"
        "👇 <b>Нажмите кнопку ниже, чтобы переключить пол:</b>\n"
        "• <b>Девушка</b> — включает женские титулы во всех списках и командах (Лидерша, Заместительница, Админша, Модераторша);\n"
        "• <b>Парень</b> — возвращает стандартные мужские титулы (Владелец, Заместитель, Администратор, Модератор)."
    )

    kb = _make_gender_selection_kb(cur_gender, target_id)
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("set_user_gender:"))
async def cb_set_user_gender(cq: CallbackQuery, bot: Bot):
    parts = cq.data.split(":")
    if len(parts) < 3:
        return await cq.answer("⚠️ Ошибка параметров", show_alert=True)
    new_gender = parts[1]
    try:
        target_id = int(parts[2])
    except ValueError:
        target_id = cq.from_user.id

    from config import is_bot_owner
    caller_id = cq.from_user.id
    if caller_id != target_id and not is_bot_owner(caller_id):
        # Проверяем, может ли кликнувший менять пол другому (нужен ранг 3+)
        from core_ranks import get_rank
        chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
        r = await get_rank(chat_id, caller_id) if chat_id else 0
        if r < 3:
            return await cq.answer("⛔️ Вы можете менять пол только себе! Либо обратитесь к администрации.", show_alert=True)

    await core_hierarchies.set_user_gender(target_id, new_gender)

    if new_gender == "female":
        alert_txt = (
            "💖 Пол установлен: 🙋‍♀️ ДЕВУШКА!\n\n"
            "✨ Включены женские титулы:\n"
            "• Лидерша чата / Лидерша Клана\n"
            "• Заместительница (Замка) / Советница\n"
            "• Старшая админша / Модераторша / Валькирия"
        )
    else:
        alert_txt = (
            "⚡ Пол установлен: 🙋‍♂️ ПАРЕНЬ!\n\n"
            "Включены стандартные титулы:\n"
            "• Владелец чата / Глава Клана\n"
            "• Заместитель / Зам. Главы\n"
            "• Администратор / Модератор"
        )

    # Обновляем клавиатуру и текст в сообщении
    try:
        new_kb = _make_gender_selection_kb(new_gender, target_id)
        if cq.message:
            cur_str = "🙋‍♀️ <b>Девушка</b> (женские титулы)" if new_gender == "female" else "🙋‍♂️ <b>Парень</b> (мужские титулы)"
            who_str = "Ваш текущий пол" if target_id == caller_id else "Текущий пол участника"
            updated_text = (
                "👤 <b>ВЫБОР ПОЛА И ОТОБРАЖЕНИЯ ТИТУЛОВ</b>\n\n"
                f"• {who_str}: {cur_str}\n\n"
                "👇 <b>Нажмите кнопку ниже, чтобы переключить пол:</b>\n"
                "• <b>Девушка</b> — включает женские титулы во всех списках и командах (Лидерша, Заместительница, Админша, Модераторша);\n"
                "• <b>Парень</b> — возвращает стандартные мужские титулы (Владелец, Заместитель, Администратор, Модератор)."
            )
            await cq.message.edit_text(updated_text, reply_markup=new_kb, disable_web_page_preview=True)
    except Exception:
        pass

    await cq.answer(alert_txt, show_alert=True)


@router.message(Cmd("тип чата", "тип группы", "стиль группы", "иерархия чата",
                    section=34, group_only=True,
                    usage="тип чата [клан / беседа / синдикат / самураи / ковен / империя]",
                    desc="🏰 Быстрая смена формата сообщества и названий рангов"))
async def cmd_set_chat_type(message: Message, bot: Bot, args: str = "", **kw):
    from config import is_bot_owner
    uid = message.from_user.id if message.from_user else 0
    me = await effective_rank(message, bot)
    if me < 3 and not is_bot_owner(uid):
        return await message.reply("⛔️ Менять тип группы могут администраторы беседы (от <b>3 ранга</b>) и выше!")

    arg = (args or "").strip().lower()
    mapping = {
        "клан": "clan", "гильдия": "clan", "clan": "clan",
        "беседа": "default", "чат": "default", "сообщество": "default", "default": "default",
        "синдикат": "syndicate", "кибер": "syndicate", "syndicate": "syndicate",
        "самураи": "samurai", "аниме": "samurai", "сегунат": "samurai", "samurai": "samurai",
        "ковен": "coven", "вампиры": "coven", "тьма": "coven", "coven": "coven",
        "империя": "royalty", "двор": "royalty", "королевство": "royalty", "royalty": "royalty",
    }
    target_id = mapping.get(arg)
    if not target_id:
        return await message.reply(
            "🏰 <b>ДОСТУПНЫЕ ТИПЫ СООБЩЕСТВ:</b>\n\n"
            "• <code>тип чата клан</code> — ⚔️ Клан / Игровая Гильдия (Глава, Советница, Маршалы, Валькирии)\n"
            "• <code>тип чата беседа</code> — 💬 Обычная беседа (Владелец, Лидерша, Заместительница, Админы)\n"
            "• <code>тип чата синдикат</code> — 🌌 Кибер-Синдикат (Босс, Госпожа, Вице-Президент, Нетраннеры)\n"
            "• <code>тип чата самураи</code> — 🏮 Самурайский Орден (Сёгун, Императрица, Даймё, Куноити)\n"
            "• <code>тип чата ковен</code> — 🩸 Тёмный Ковен (Князь Тьмы, Владычица Ночи, Жрицы, Лорды)\n"
            "• <code>тип чата империя</code> — 👑 Императорский Двор (Император, Императрица, Канцлеры)\n\n"
            "💡 Или откройте интерактивное меню: <code>дизайн</code>"
        )

    await core_hierarchies.set_chat_hierarchy(message.chat.id, target_id, updated_by=uid)
    h = core_hierarchies.COMMUNITY_TYPES[target_id]
    await message.reply(
        f"🎉 <b>Стиль сообщества изменён: {h['name']} {h['icon']}!</b>\n\n"
        f"📝 <i>{h['desc']}</i>\n"
        "✨ Теперь все списки модерации используют звания этой темы!\n"
        "🔍 Проверьте командой: <code>состав</code> или <code>мой ранг</code>"
    )


# ---------------- Реферальная система пиарщиков групп ----------------

@router.message(Cmd("рефералка", "моя рефералка", "ссылка пиарщика", "пр ссылка", "пиар ссылка",
                    section=34, group_only=True,
                    desc="📢 Получить персональную реферальную ссылку на эту группу для пиара"))
async def cmd_group_referral_link(message: Message, bot: Bot, args: str = "", **kw):
    chat_id = message.chat.id
    uid = message.from_user.id if message.from_user else 0

    # Если передан аргумент (рефералка @user), показываем статистику этого пользователя
    if args.strip():
        tgt_uid, tgt_name, _ = await resolve_target(message, args, bot)
        if tgt_uid:
            row = await db.fetchone(
                "SELECT COUNT(*) as cnt FROM group_referrals WHERE chat_id=? AND inviter_id=?",
                (chat_id, tgt_uid)
            )
            count = row["cnt"] if row else 0

            # Топ пиарщиков в чате
            pos_row = await db.fetchone(
                "SELECT COUNT(*)+1 as pos FROM ("
                "SELECT inviter_id, COUNT(*) as c FROM group_referrals WHERE chat_id=? GROUP BY inviter_id"
                ") WHERE c > ?",
                (chat_id, count)
            )
            pos = pos_row["pos"] if pos_row else 1

            return await message.reply(
                f"📊 <b>РЕФЕРАЛЬНАЯ СТАТИСТИКА ПИАРЩИКА</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Участник: {mention_id(tgt_uid, tgt_name)}\n"
                f"👥 Приглашено в эту группу: <b>{count} человек</b>\n"
                f"🏆 Место в топе пиарщиков чата: <b>#{pos}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Получить свою ссылку:</i> <code>рефералка</code>"
            )

    # Проверяем, есть ли уже созданная ссылка
    link_row = await db.fetchone(
        "SELECT invite_link FROM group_pr_links WHERE chat_id=? AND user_id=?",
        (chat_id, uid)
    )
    invite_url = link_row["invite_link"] if link_row else None

    if not invite_url:
        try:
            link_obj = await bot.create_chat_invite_link(
                chat_id=chat_id,
                name=f"PR_{uid}_{int(time.time())}"
            )
            invite_url = link_obj.invite_link
            await db.execute(
                "INSERT INTO group_pr_links (chat_id, user_id, invite_link, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET invite_link=excluded.invite_link",
                (chat_id, uid, invite_url, int(time.time()))
            )
        except Exception as e:
            return await message.reply(
                "⚠️ <b>Не удалось создать персональную ссылку!</b>\n\n"
                "Убедитесь, что у бота есть право «Пригласительные ссылки» в администраторах этой группы."
            )

    cnt_row = await db.fetchone(
        "SELECT COUNT(*) as cnt FROM group_referrals WHERE chat_id=? AND inviter_id=?",
        (chat_id, uid)
    )
    joined_count = cnt_row["cnt"] if cnt_row else 0

    txt = (
        "📢 <b>ВАША ПЕРСОНАЛЬНАЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Приведено участников в эту группу: <b>{joined_count}</b>\n\n"
        "🔗 <b>Ваша ссылка для пиара:</b>\n"
        f"<code>{invite_url}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Отправляйте эту ссылку друзьям и в другие беседы!\n"
        "Все игроки, зашедшие по ней в эту группу, автоматически засчитаются вам в актив пиарщика!</i>\n\n"
        "📊 Посмотреть статистику любого пиарщика: <code>рефералка @юзер</code>\n"
        "🏆 Топ пригласивших: <code>топ пиарщиков</code>"
    )
    await message.reply(txt, disable_web_page_preview=True)


@router.message(Cmd("топ пиарщиков", "пиарщики топ", "рефералы топ", "топ рефералов",
                    section=34, group_only=True,
                    desc="🏆 Топ участников, пригласивших больше всего людей в эту группу"))
async def cmd_top_pr(message: Message, bot: Bot, **kw):
    chat_id = message.chat.id
    rows = await db.fetchall(
        "SELECT r.inviter_id, COUNT(*) as cnt, u.first_name, u.username "
        "FROM group_referrals r LEFT JOIN users u ON r.inviter_id = u.user_id "
        "WHERE r.chat_id=? GROUP BY r.inviter_id ORDER BY cnt DESC LIMIT 10",
        (chat_id,)
    )
    if not rows:
        return await message.reply(
            "📊 <b>ТОП ПИАРЩИКОВ ЭТОЙ ГРУППЫ</b>\n\n"
            "<i>В этой группе ещё никто не пригласил участников по своей реферальной ссылке.</i>\n\n"
            "💡 Создайте свою ссылку прямо сейчас командой: <code>рефералка</code>"
        )

    lines = [
        "🏆 <b>ТОП ПИАРЩИКОВ ЭТОЙ ГРУППЫ</b>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, r in enumerate(rows):
        m = medals[idx] if idx < len(medals) else f"{idx+1}."
        u_mention = mention_id(r["inviter_id"], r["first_name"] or r["username"] or f"ID {r['inviter_id']}")
        lines.append(f"{m} {u_mention} — <b>{r['cnt']}</b> приведено")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Получить свою ссылку:</i> <code>рефералка</code>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)

