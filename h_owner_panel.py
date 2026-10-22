"""👑 Панель Управления Владельца и Иерархия Стаффа Бота (Owner & Global Staff Panel).

Иерархия рангов стаффа:
Ранг 1: 🥉 Хелпер (Helper) — просмотр открытых тикетов, ответы пользователям (+ответ);
Ранг 2: 🥈 Модератор (Moderator) — права Хелпера + модерация идей (+принять/+отклонить) + глобан нарушителей;
Ранг 3: 🥇 Администратор (Admin) — права Модератора + отключение/включение бота в группах + глобальная статистика;
Ранг 4: 👑 Владелец (Owner, Simba / 8412527198) — полный абсолютный контроль:
        назначение и снятие стаффа (+стафф/-стафф),
        привязка официальных групп (+чат идей, +чат отзывов, +чат общения, +чат поддержки),
        экстренное удаление и ЧС нарушающих групп (интим/18+, спам, коммерция) с выходом бота.
"""
from __future__ import annotations

import html
import logging
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import db
from core_registry import Cmd
from utils import mention_id

log = logging.getLogger("moxxibot.owner_panel")
router = Router(name="owner_panel")

S_OWNER = 40  # Раздел панели владельца

STAFF_RANKS_DESC = {
    1: "🥉 Хелпер (Техподдержка)",
    2: "🥈 Модератор (Идеи & Глобан)",
    3: "🥇 Администратор (Управление чатами)",
    4: "👑 Владелец (Полный контроль)"
}


async def _require_staff(message: Message, min_rank: int = 1, silent: bool = False) -> tuple[bool, int]:
    uid = message.from_user.id if message.from_user else 0
    rank = await db.get_bot_staff_rank(uid)
    if rank >= min_rank:
        return True, rank
    if not silent:
        await message.reply(f"🔒 <b>Доступ ограничен!</b>\nТребуется ранг персонала: <b>{STAFF_RANKS_DESC.get(min_rank, 'Администрация')}</b> (у вас: {rank}).")
    return False, rank


def _owner_panel_kb(rank: int) -> InlineKeyboardMarkup:
    buttons = []
    # Ранг 1+: Тикеты техподдержки
    buttons.append([InlineKeyboardButton(text="🆘 Тикеты поддержки", callback_data="op:tickets:0")])

    # Ранг 2+: Модерация идей и Глобан
    if rank >= 2:
        buttons.append([
            InlineKeyboardButton(text="💡 Модерация идей", callback_data="op:ideas:0"),
            InlineKeyboardButton(text="🚫 Черный список игроков", callback_data="op:globan_list")
        ])

    # Ранг 3+: Управление чатами и Статистика
    if rank >= 3:
        buttons.append([
            InlineKeyboardButton(text="📊 Глобальная статистика", callback_data="op:stats"),
            InlineKeyboardButton(text="🛑 Чаты бота", callback_data="op:chats_status")
        ])

    # Ранг 4: Владелец — Стафф, Привязка групп, Удаление групп нарушителей
    if rank >= 4:
        buttons.append([
            InlineKeyboardButton(text="👑 Состав стаффа", callback_data="op:staff_list"),
            InlineKeyboardButton(text="🔗 Привязанные группы", callback_data="op:bound_chats")
        ])
        buttons.append([
            InlineKeyboardButton(text="⛔ Черный список групп (ЧС)", callback_data="op:bl_chats")
        ])

    buttons.append([InlineKeyboardButton(text="🔄 Обновить панель", callback_data="op:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════════════════════════════
# 1. ГЛАВНОЕ МЕНЮ АДМИН-ПАНЕЛИ (В ЛС)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("панель", "овнер", "adminpanel", "админка", "стафф панель", "owner",
                    section=S_OWNER, rank=0, group_only=False,
                    desc="Панель управления стаффа и владельца бота в ЛС"))
async def cmd_owner_panel(message: Message, bot: Bot, **kw):
    ok, rank = await _require_staff(message, 1)
    if not ok:
        return

    uid = message.from_user.id
    name = message.from_user.first_name or "Сотрудник"
    stats = await db.get_global_bot_stats()

    rank_name = STAFF_RANKS_DESC.get(rank, f"Ранг {rank}")
    text = (
        f"👑 ✨ <b>ПАНЕЛЬ УПРАВЛЕНИЯ MOXXI BOT</b> ✨ 👑\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>Сотрудник:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
        f"🔰 <b>Ваш статус:</b> <b>{rank_name}</b>\n\n"
        f"📊 <b>Сводка системы:</b>\n"
        f"• Пользователей в базе: <b>{stats['users_count']}</b>\n"
        f"• Подключенных чатов: <b>{stats['chats_count']}</b>\n"
        f"• Открытых тикетов техподдержки: <b>{stats['open_tickets']} 🆘</b>\n"
        f"• Идей на рассмотрении: <b>{stats['pending_ideas']} 💡</b>\n"
        f"• Всего отзывов: <b>{stats['reviews_count']} ⭐</b>\n"
        f"• Заблокированных групп (ЧС): <b>{stats['blacklisted_chats']} ⛔</b>\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👇 <i>Выберите нужный раздел панели ниже:</i>"
    )
    await message.reply(text, reply_markup=_owner_panel_kb(rank))


@router.callback_query(F.data == "op:refresh")
async def cb_owner_panel_refresh(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 1:
        return await call.answer("🔒 Нет доступа.", show_alert=True)
    stats = await db.get_global_bot_stats()
    rank_name = STAFF_RANKS_DESC.get(rank, f"Ранг {rank}")
    text = (
        f"👑 ✨ <b>ПАНЕЛЬ УПРАВЛЕНИЯ MOXXI BOT</b> ✨ 👑\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>Сотрудник:</b> {mention_id(call.from_user.id, call.from_user.first_name)}\n"
        f"🔰 <b>Ваш статус:</b> <b>{rank_name}</b>\n\n"
        f"📊 <b>Сводка системы:</b>\n"
        f"• Пользователей в базе: <b>{stats['users_count']}</b>\n"
        f"• Подключенных чатов: <b>{stats['chats_count']}</b>\n"
        f"• Открытых тикетов техподдержки: <b>{stats['open_tickets']} 🆘</b>\n"
        f"• Идей на рассмотрении: <b>{stats['pending_ideas']} 💡</b>\n"
        f"• Всего отзывов: <b>{stats['reviews_count']} ⭐</b>\n"
        f"• Заблокированных групп (ЧС): <b>{stats['blacklisted_chats']} ⛔</b>\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👇 <i>Выберите нужный раздел панели ниже:</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=_owner_panel_kb(rank))
    except Exception:
        pass
    await call.answer("✅ Данные обновлены")


# ═══════════════════════════════════════════════════════════════
# 2. РАЗДЕЛ ТИКЕТОВ ТЕХПОДДЕРЖКИ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("op:tickets:"))
async def cb_tickets_list(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 1:
        return await call.answer("🔒 Доступно только стаффу.", show_alert=True)

    open_tickets = await db.get_open_tickets(limit=6)
    if not open_tickets:
        text = (
            f"🆘 <b>ТИКЕТЫ ТЕХПОДДЕРЖКИ</b>\n\n"
            f"🎉 <i>Все тикеты обработаны! В данный момент открытых обращений нет.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ В панель", callback_data="op:refresh")
        ]])
        return await call.message.edit_text(text, reply_markup=kb)

    lines = []
    kb_rows = []
    for t in open_tickets:
        t_id = t["id"]
        u_name = html.escape(t["user_name"] or "Игрок")
        u_text = html.escape(t["text"][:70]) + ("..." if len(t["text"]) > 70 else "")
        lines.append(f"• <b>Тикет #{t_id}</b> от <b>{u_name}</b> (ID <code>{t['user_id']}</code>):\n  «<i>{u_text}</i>»")
        kb_rows.append([InlineKeyboardButton(text=f"✉️ Ответить на #{t_id}", callback_data=f"op:ans_hint:{t_id}")])

    kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="op:refresh")])

    text = (
        f"🆘 <b>ОТКРЫТЫЕ ТИКЕТЫ В ТЕХПОДДЕРЖКУ ({len(open_tickets)})</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n\n".join(lines) + "\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <b>Чтобы ответить пользователю, напишите в чат:</b>\n"
        f"<code>+ответ [id] [текст вашего ответа]</code>\n"
        f"<i>Пример: <code>+ответ {open_tickets[0]['id']} Здравствуйте! Баланс начислен.</code></i>"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("op:ans_hint:"))
async def cb_ans_hint(call: CallbackQuery):
    t_id = call.data.split(":")[2]
    ticket = await db.get_support_ticket(int(t_id))
    if not ticket:
        return await call.answer("Тикет не найден", show_alert=True)
    msg = (
        f"Чтобы ответить на тикет #{t_id}, отправьте команду:\n\n"
        f"<code>+ответ {t_id} Ваш ответ...</code>"
    )
    await call.message.reply(msg)
    await call.answer()


# ═══════════════════════════════════════════════════════════════
# 3. НАЗНАЧЕНИЕ И СНЯТИЕ СТАФФА БОТА (ТОЛЬКО ВЛАДЕЛЕЦ)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("+стафф", "+staff", "+модербота", "+хелпер",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="+стафф [id/@user] [ранг 1-3] [титул]",
                    desc="Назначить сотрудника стаффа бота (только Владелец)"))
async def cmd_add_staff(message: Message, bot: Bot, args: str = "", **kw):
    ok, rank = await _require_staff(message, 4)
    if not ok:
        return

    parts = (args or "").strip().split()
    target_id: Optional[int] = None
    target_name: str = "Сотрудник"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or str(target_id)
        rank_to_set = int(parts[0]) if (parts and parts[0].isdigit()) else 1
        title = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif parts:
        raw_target = parts[0]
        if raw_target.isdigit():
            target_id = int(raw_target)
        elif raw_target.startswith("@"):
            row = await db.fetchone("SELECT user_id, first_name FROM users WHERE lower(username)=lower(?)", (raw_target.lstrip("@"),))
            if row:
                target_id = int(row["user_id"])
                target_name = row["first_name"] or str(target_id)
            else:
                return await message.reply("❌ Пользователь с таким @username не найден в базе бота.")
        if len(parts) > 1 and parts[1].isdigit():
            rank_to_set = int(parts[1])
            title = " ".join(parts[2:]) if len(parts) > 2 else ""
        else:
            rank_to_set = 1
            title = " ".join(parts[1:]) if len(parts) > 1 else ""
    else:
        return await message.reply(
            "Формат: <code>+стафф [id/@user] [ранг 1-3] [титул]</code>\n\n"
            "• <b>1</b> — Хелпер (ответы на тикеты);\n"
            "• <b>2</b> — Модератор (идеи + глобан);\n"
            "• <b>3</b> — Администратор (управление чатами)."
        )

    if not target_id:
        return await message.reply("❌ Не удалось определить целевого пользователя.")

    if config.is_bot_owner(target_id):
        return await message.reply("👑 Пользователь уже является Владельцем бота.")

    if rank_to_set < 1 or rank_to_set > 3:
        return await message.reply("❌ Ранг стаффа должен быть от 1 до 3.")

    await db.set_bot_staff_rank(target_id, rank_to_set, title=title, granted_by=message.from_user.id)
    r_name = STAFF_RANKS_DESC.get(rank_to_set, f"Ранг {rank_to_set}")

    # Уведомляем целевого пользователя
    try:
        await bot.send_message(
            target_id,
            f"🎉 <b>Поздравляем! Вы назначены в персонал Moxxi Bot!</b>\n\n"
            f"🔰 <b>Должность:</b> <b>{r_name}</b>" + (f" (<i>{title}</i>)" if title else "") + f"\n"
            f"👨‍💻 <b>Назначил:</b> {mention_id(message.from_user.id, message.from_user.first_name)}\n\n"
            f"Откройте меню стаффа командой <code>панель</code> в личных сообщениях с ботом!"
        )
    except Exception:
        pass

    await message.reply(
        f"✅ <b>Сотрудник успешно назначен!</b>\n\n"
        f"👤 <b>Пользователь:</b> {mention_id(target_id, target_name)} (<code>{target_id}</code>)\n"
        f"🔰 <b>Ранг:</b> <b>{r_name}</b>" + (f" (<i>{title}</i>)" if title else "")
    )


@router.message(Cmd("-стафф", "-staff", "снять стафф",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="-стафф [id/@user]", desc="Снять сотрудника из стаффа бота"))
async def cmd_remove_staff(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 4)
    if not ok:
        return

    parts = (args or "").strip().split()
    target_id: Optional[int] = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    elif parts:
        raw_target = parts[0]
        if raw_target.isdigit():
            target_id = int(raw_target)
        elif raw_target.startswith("@"):
            row = await db.fetchone("SELECT user_id FROM users WHERE lower(username)=lower(?)", (raw_target.lstrip("@"),))
            if row:
                target_id = int(row["user_id"])

    if not target_id:
        return await message.reply("Формат: <code>-стафф [id/@user]</code> (или ответом на сообщение)")

    if config.is_bot_owner(target_id):
        return await message.reply("👑 Нельзя снять Владельца бота.")

    await db.remove_bot_staff(target_id)
    try:
        await bot.send_message(target_id, "ℹ️ Ваши полномочия сотрудника Moxxi Bot были отозваны владельцем.")
    except Exception:
        pass
    await message.reply(f"✅ Пользователь <code>{target_id}</code> удален из стаффа бота.")


@router.message(Cmd("стафф", "персонал", "команда бота",
                    section=S_OWNER, rank=0, group_only=False,
                    desc="Список всего персонала бота"))
async def cmd_list_staff(message: Message, bot: Bot, **kw):
    ok, _ = await _require_staff(message, 1)
    if not ok:
        return

    staff_list = await db.get_all_bot_staff()
    owners_str = ", ".join(mention_id(oid, "Владелец") + f" (<code>{oid}</code>)" for oid in sorted(config.BOT_OWNERS))
    lines = [f"👑 <b>Владельцы проекта:</b> {owners_str}\n"]
    if staff_list:
        lines.append("👥 <b>Действующий состав:</b>")
        for s in staff_list:
            r_title = STAFF_RANKS_DESC.get(s["rank"], f"Ранг {s['rank']}")
            custom_t = f" • <i>{html.escape(s['title'])}</i>" if s.get("title") else ""
            u_name = s.get("first_name") or s.get("username") or str(s["user_id"])
            lines.append(f"• <b>{r_title}</b>: {mention_id(s['user_id'], u_name)} (<code>{s['user_id']}</code>){custom_t}")
    else:
        lines.append("<i>Других сотрудников пока не назначено. Назначить: <code>+стафф [id] [1-3]</code></i>")

    await message.reply("\n".join(lines))


@router.callback_query(F.data == "op:staff_list")
async def cb_staff_list(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 4:
        return await call.answer("🔒 Доступно только Владельцу.", show_alert=True)
    staff_list = await db.get_all_bot_staff()
    owners_str = ", ".join(mention_id(oid, "Владелец") + f" (<code>{oid}</code>)" for oid in sorted(config.BOT_OWNERS))
    lines = [f"👑 <b>Владельцы:</b> {owners_str}\n"]
    if staff_list:
        for s in staff_list:
            r_title = STAFF_RANKS_DESC.get(s["rank"], f"Ранг {s['rank']}")
            u_name = s.get("first_name") or str(s["user_id"])
            lines.append(f"• <b>{r_title}</b>: {mention_id(s['user_id'], u_name)} (<code>{s['user_id']}</code>)")
    else:
        lines.append("<i>Дополнительного персонала нет.</i>")

    lines.append("\n💡 Назначить: <code>+стафф [id] [1-3]</code>\nСнять: <code>-стафф [id]</code>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")]])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════════════
# 4. ПРИВЯЗКА ОФИЦИАЛЬНЫХ ГРУПП (ТОЛЬКО ВЛАДЕЛЕЦ)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("+чат идей", "+чат идеи", "+чат отзывов", "+чат отзывы",
                    "+чат общения", "+чат общение", "+чат поддержки", "+чат поддержка",
                    "+чат команды", "+чат команд",
                    "чат идей", "чат идеи", "чат отзывов", "чат отзывы",
                    "чат общения", "чат общение", "чат поддержки", "чат поддержка",
                    "чат команды", "чат команд",
                    "привязать чат", "+привязать чат",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="+чат отзывов [chat_id или ссылка]",
                    desc="Привязать официальную группу (Владелец и Администрация)"))
async def cmd_bind_official_chat(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 3, silent=True)
    if not ok:
        return

    full_txt = (message.text or "").strip().lower()
    target_val = (args or "").strip()

    # Если аргумент не указан, но команда вызвана внутри чата — привязываем текущий чат!
    if not target_val and message.chat.type in {"group", "supergroup"}:
        target_val = str(message.chat.id)

    # Если в args было указано название чата: например «привязать чат отзывы»
    parts = target_val.split(maxsplit=1)
    if parts and any(k in parts[0].lower() for k in ["иде", "отзыв", "общен", "поддерж", "команд"]):
        full_txt += " " + parts[0].lower()
        target_val = parts[1].strip() if len(parts) > 1 else str(message.chat.id)

    if not target_val:
        return await message.reply(
            "📌 <b>Формат привязки официальных групп:</b>\n\n"
            "• <code>+чат отзывов</code> (прямо в группе отзывов)\n"
            "• <code>+чат отзывов @username_или_ссылка</code>\n"
            "• <code>+чат идей</code> (в группе предложений)\n"
            "• <code>+чат общения</code> (в главном чате)\n"
            "• <code>+чат поддержки</code> (в чате саппорта)\n"
            "• <code>+чат команды</code> (в чате вопросов по командам)\n\n"
            "💡 <i>Посмотреть текущие привязки: <code>привязанные чаты</code></i>"
        )

    key_map = {
        "иде": ("global_ideas_chat", "💡 Группа идей и предложений"),
        "отзыв": ("global_reviews_chat", "⭐ Группа отзывов и оценок"),
        "общен": ("global_community_chat", "💬 Официальный чат общения"),
        "поддерж": ("global_support_chat", "🆘 Группа службы техподдержки"),
        "команд": ("global_commands_chat", "🤖 Группа/Тема команд и вопросов")
    }

    matched_key = None
    matched_title = ""
    for k, (db_k, t) in key_map.items():
        if k in full_txt:
            matched_key = db_k
            matched_title = t
            break

    if not matched_key:
        return await message.reply(
            "❌ Неизвестная группа. Доступны:\n"
            "• <code>+чат отзывов</code>\n"
            "• <code>+чат идей</code>\n"
            "• <code>+чат общения</code>\n"
            "• <code>+чат поддержки</code>\n"
            "• <code>+чат команды</code>"
        )

    await db.set_global_setting(matched_key, target_val)

    # Если команда отправлена в теме форума — также запоминаем ID темы!
    tid = getattr(message, "message_thread_id", None)
    if tid and tid > 1:
        await db.set_global_setting(matched_key + "_topic", str(tid))
        if matched_key == "global_commands_chat":
            await db.set_global_setting("global_commands_topic", str(tid))

    topic_note = f"\n🧵 <b>ID топика форума:</b> <code>{tid}</code>" if (tid and tid > 1) else ""
    await message.reply(
        f"✅ <b>Группа успешно привязана!</b>\n\n"
        f"🏷 <b>Категория:</b> {matched_title}\n"
        f"🔗 <b>Значение:</b> <code>{html.escape(target_val)}</code>{topic_note}\n\n"
        f"<i>Теперь все уведомления и ссылки в боте автоматически используют эту группу!</i>"
    )


@router.message(Cmd("привязанные чаты", "официальные чаты",
                    section=S_OWNER, rank=0, group_only=False,
                    desc="Показать привязанные официальные чаты"))
async def cmd_show_bound_chats(message: Message, bot: Bot, **kw):
    ok, _ = await _require_staff(message, 1, silent=True)
    if not ok:
        return
    ideas = await db.get_global_setting("global_ideas_chat", "Не привязана")
    reviews = await db.get_global_setting("global_reviews_chat", "Не привязана")
    chat = await db.get_global_setting("global_community_chat", "Не привязана")
    supp = await db.get_global_setting("global_support_chat", "Не привязана")
    cmds = await db.get_global_setting("global_commands_chat", "Не привязана")

    text = (
        f"🔗 <b>ПРИВЯЗАННЫЕ ОФИЦИАЛЬНЫЕ ЧАТЫ MOXXI</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <b>Идеи и предложения:</b> <code>{ideas}</code>\n"
        f"⭐ <b>Отзывы о боте:</b> <code>{reviews}</code>\n"
        f"💬 <b>Главный чат общения:</b> <code>{chat}</code>\n"
        f"🆘 <b>Техподдержка:</b> <code>{supp}</code>\n"
        f"🤖 <b>Тема команд/ИИ:</b> <code>{cmds}</code>\n\n"
        f"👑 <i>Изменить привязку может владелец командами <code>+чат [тип] [значение]</code>.</i>"
    )
    await message.reply(text)


@router.callback_query(F.data == "op:bound_chats")
async def cb_bound_chats(call: CallbackQuery):
    ideas = await db.get_global_setting("global_ideas_chat", "Не привязана")
    reviews = await db.get_global_setting("global_reviews_chat", "Не привязана")
    chat = await db.get_global_setting("global_community_chat", "Не привязана")
    supp = await db.get_global_setting("global_support_chat", "Не привязана")
    cmds = await db.get_global_setting("global_commands_chat", "Не привязана")
    text = (
        f"🔗 <b>ПРИВЯЗАННЫЕ ОФИЦИАЛЬНЫЕ ГРУППЫ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <b>Идеи:</b> <code>{ideas}</code>\n"
        f"⭐ <b>Отзывы:</b> <code>{reviews}</code>\n"
        f"💬 <b>Общение:</b> <code>{chat}</code>\n"
        f"🆘 <b>Саппорт:</b> <code>{supp}</code>\n"
        f"🤖 <b>Команды:</b> <code>{cmds}</code>\n\n"
        f"💡 Для привязки используйте команды:\n"
        f"• <code>+чат идей [id/ссылка]</code>\n"
        f"• <code>+чат отзывов [id/ссылка]</code>\n"
        f"• <code>+чат общения [id/ссылка]</code>\n"
        f"• <code>+чат поддержки [id/ссылка]</code>\n"
        f"• <code>+чат команды [id/ссылка]</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════════════
# 5. УДАЛЕНИЕ И БАН НАРУШАЮЩИХ ГРУПП (ИНТИМ, СПАМ, СКАМ, ПРОДАЖИ)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("удалить группу", "чс группы", "бан группы",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="удалить группу [chat_id] [причина]",
                    desc="Удалить бота из группы с занесением в ЧС (только Владелец)"))
async def cmd_delete_and_blacklist_chat(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 4)
    if not ok:
        return

    parts = (args or "").strip().split(maxsplit=1)
    target_chat_id: Optional[int] = None
    reason = "Нарушение условий использования (интим/18+, спам, коммерция)"

    if parts and (parts[0].startswith("-") or parts[0].isdigit()):
        target_chat_id = int(parts[0])
        if len(parts) > 1 and parts[1].strip():
            reason = parts[1].strip()
    elif message.chat.type in {"group", "supergroup"}:
        target_chat_id = message.chat.id
        if args.strip():
            reason = args.strip()
    else:
        return await message.reply("Формат: <code>удалить группу [chat_id] [причина]</code>")

    # Заносим в черный список
    await db.blacklist_chat(target_chat_id, reason=reason, banned_by=message.from_user.id)

    # Пытаемся отправить сообщение в нарушающий чат и выйти
    left_ok = False
    try:
        await bot.send_message(
            target_chat_id,
            f"⛔ ⚠️ <b>БОТ MOXXI УДАЛЁН ИЗ ЭТОЙ ГРУППЫ!</b> ⚠️ ⛔\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🛡 <b>Решение:</b> Администрация проекта Moxxi отозвала доступ боту.\n"
            f"🚫 <b>Причина:</b> <i>{html.escape(reason)}</i>\n\n"
            f"Группа внесена в глобальный чёрный список. До свидания!"
        )
        await bot.leave_chat(target_chat_id)
        left_ok = True
    except Exception as e:
        log.warning("Не удалось корректно выйти из чата %s: %s", target_chat_id, e)

    await message.reply(
        f"✅ <b>Группа {target_chat_id} успешно удалена и занесена в ЧС!</b>\n\n"
        f"📝 <b>Причина:</b> <i>{html.escape(reason)}</i>\n"
        f"🚪 <b>Выход бота:</b> {'успешно вышел' if left_ok else 'не удалось отправить сообщение (возможно уже исключен)'}\n\n"
        f"🛡 <i>Если бот когда-либо будет снова добавлен в этот чат, он автоматически покинет его моментально.</i>"
    )


@router.message(Cmd("снять чс группы", "разбан группы",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="снять чс группы [chat_id]", desc="Снять группу из черного списка"))
async def cmd_unblacklist_chat(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 4)
    if not ok:
        return
    parts = (args or "").strip().split()
    if not parts or not (parts[0].startswith("-") or parts[0].isdigit()):
        return await message.reply("Формат: <code>снять чс группы [chat_id]</code>")
    cid = int(parts[0])
    await db.unblacklist_chat(cid)
    await message.reply(f"✅ Чат <code>{cid}</code> исключён из чёрного списка.")


@router.callback_query(F.data == "op:bl_chats")
async def cb_bl_chats_list(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 4:
        return await call.answer("🔒 Доступно только Владельцу.", show_alert=True)
    bl_chats = await db.get_blacklisted_chats()
    if not bl_chats:
        text = "⛔ <b>ЧЁРНЫЙ СПИСОК ГРУПП</b>\n\n<i>В чёрном списке пока нет групп.</i>"
    else:
        lines = [f"⛔ <b>ЧЁРНЫЙ СПИСОК ГРУПП ({len(bl_chats)}):</b>\n"]
        for c in bl_chats[:15]:
            lines.append(f"• <code>{c['chat_id']}</code>: <i>{html.escape(c.get('reason') or 'Нарушение')}</i>")
        lines.append("\n💡 <i>Чтобы удалить группу: <code>удалить группу [id] [причина]</code></i>")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════════════
# 6. ВРЕМЕННОЕ ОТКЛЮЧЕНИЕ / ВКЛЮЧЕНИЕ БОТА В ЧАТЕ (АДМИН 3+)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("выкл чат", "отключить чат",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="выкл чат [chat_id]", desc="Отключить работу бота в группе (Админ 3+)"))
async def cmd_disable_chat(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 3)
    if not ok:
        return

    cid: Optional[int] = None
    parts = (args or "").strip().split()
    if parts and (parts[0].startswith("-") or parts[0].isdigit()):
        cid = int(parts[0])
    elif message.chat.type in {"group", "supergroup"}:
        cid = message.chat.id
    else:
        return await message.reply("Формат: <code>выкл чат [chat_id]</code>")

    await db.set_chat_disabled(cid, True, by_id=message.from_user.id)
    await message.reply(f"🛑 <b>Бот временно отключен в чате <code>{cid}</code>!</b>\nОн больше не будет реагировать на команды в этом чате. Включить обратно: <code>вкл чат {cid}</code>.")


@router.message(Cmd("вкл чат", "включить чат",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="вкл чат [chat_id]", desc="Включить работу бота в группе (Админ 3+)"))
async def cmd_enable_chat(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 3)
    if not ok:
        return

    cid: Optional[int] = None
    parts = (args or "").strip().split()
    if parts and (parts[0].startswith("-") or parts[0].isdigit()):
        cid = int(parts[0])
    elif message.chat.type in {"group", "supergroup"}:
        cid = message.chat.id
    else:
        return await message.reply("Формат: <code>вкл чат [chat_id]</code>")

    await db.set_chat_disabled(cid, False)
    await message.reply(f"✅ <b>Работа бота в чате <code>{cid}</code> возобновлена!</b>")


# ═══════════════════════════════════════════════════════════════
# 7. ГЛОБАЛЬНЫЙ БАН НАРУШИТЕЛЕЙ (МОДЕРАТОР 2+)
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("глобан", "глобальный бан",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="глобан [uid/@user] [причина]", desc="Глобальный бан игрока во всех чатах бота"))
async def cmd_globan(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 2)
    if not ok:
        return

    parts = (args or "").strip().split(maxsplit=1)
    target_id: Optional[int] = None
    reason = "Нарушение правил экосистемы бота"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        if parts:
            reason = args.strip()
    elif parts:
        raw_target = parts[0]
        if raw_target.isdigit():
            target_id = int(raw_target)
        elif raw_target.startswith("@"):
            row = await db.fetchone("SELECT user_id FROM users WHERE lower(username)=lower(?)", (raw_target.lstrip("@"),))
            if row:
                target_id = int(row["user_id"])
        if len(parts) > 1 and parts[1].strip():
            reason = parts[1].strip()

    if not target_id:
        return await message.reply("Формат: <code>глобан [uid/@user] [причина]</code> (или реплаем)")

    # Нельзя забанить стафф или владельца
    target_rank = await db.get_bot_staff_rank(target_id)
    if target_rank >= 2:
        return await message.reply("❌ Нельзя выдать глобальный бан сотруднику стаффа бота.")

    await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (target_id,))
    await message.reply(
        f"🚫 <b>Пользователь {target_id} заблокирован глобально!</b>\n\n"
        f"📝 <b>Причина:</b> <i>{html.escape(reason)}</i>\n"
        f"Бот больше не будет отвечать на его сообщения ни в одном чате и личке."
    )


@router.message(Cmd("разглобан", "снять глобан",
                    section=S_OWNER, rank=0, group_only=False,
                    usage="разглобан [uid/@user]", desc="Снять глобальный бан с игрока"))
async def cmd_ungloban(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _require_staff(message, 2)
    if not ok:
        return
    parts = (args or "").strip().split()
    target_id: Optional[int] = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    elif parts and parts[0].isdigit():
        target_id = int(parts[0])

    if not target_id:
        return await message.reply("Формат: <code>разглобан [uid]</code>")

    await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (target_id,))
    await message.reply(f"✅ Глобальный бан с пользователя <code>{target_id}</code> снят.")


# ═══════════════════════════════════════════════════════════════
# 8. СТАТИСТИКА БОТА И МОДЕРАЦИЯ ИДЕЙ ЧЕРЕЗ CALLBACKS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "op:stats")
async def cb_stats(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 3:
        return await call.answer("🔒 Требуется ранг Администратора.", show_alert=True)
    st = await db.get_global_bot_stats()
    text = (
        f"📊 <b>ГЛОБАЛЬНАЯ СТАТИСТИКА MOXXI BOT</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 Пользователей в базе: <b>{st['users_count']}</b>\n"
        f"💰 Монет в обороте у игроков: <b>{st['total_coins']:,} 🍬</b>\n"
        f"💬 Подключено чатов: <b>{st['chats_count']}</b>\n"
        f"🆘 Открытых обращений техподдержки: <b>{st['open_tickets']}</b>\n"
        f"⭐ Оставлено отзывов: <b>{st['reviews_count']}</b>\n"
        f"💡 Идей в предложке: <b>{st['pending_ideas']}</b>\n"
        f"⛔ Групп в чёрном списке: <b>{st['blacklisted_chats']}</b>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("op:ideas:"))
async def cb_ideas_list(call: CallbackQuery):
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 2:
        return await call.answer("🔒 Требуется ранг Модератора.", show_alert=True)
    ideas = await db.get_suggestions(limit=6)
    pending_ideas = [i for i in ideas if i["status"] == "pending"]
    if not pending_ideas:
        text = "💡 <b>МОДЕРАЦИЯ ИДЕЙ</b>\n\n🎉 <i>Все идеи проверены! Новых предложений на рассмотрении нет.</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")]])
        return await call.message.edit_text(text, reply_markup=kb)

    lines = []
    kb_rows = []
    for i in pending_ideas:
        i_id = i["id"]
        lines.append(f"• <b>#{i_id}</b> от {html.escape(i.get('user_name') or 'Игрок')} (👍 {i['upvotes']} | 👎 {i['downvotes']}):\n  «{html.escape(i['text'][:60])}...»")
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ #{i_id} Принять", callback_data=f"op:sug_act:{i_id}:acc"),
            InlineKeyboardButton(text=f"❌ #{i_id} Отклонить", callback_data=f"op:sug_act:{i_id}:rej")
        ])

    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="op:refresh")])
    text = (
        f"💡 <b>ИДЕИ НА РАССМОТРЕНИИ ({len(pending_ideas)}):</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n\n".join(lines)
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("op:sug_act:"))
async def cb_sug_action(call: CallbackQuery):
    parts = call.data.split(":")
    s_id = int(parts[2])
    action = parts[3]
    rank = await db.get_bot_staff_rank(call.from_user.id)
    if rank < 2:
        return await call.answer("🔒 Доступно Модераторам.", show_alert=True)

    new_st = "accepted" if action == "acc" else "rejected"
    await db.update_suggestion_status(s_id, new_st)
    await call.answer(f"Идея #{s_id} {'принята' if action == 'acc' else 'отклонена'}!")
    # Перерисовываем список
    await cb_ideas_list(call)
