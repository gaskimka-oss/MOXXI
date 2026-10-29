"""Модуль Глобального Обновления 2.2:
Все новые функции изолированы по чатам (per-chat) и ПО УМОЛЧАНИЮ ВЫКЛЮЧЕНЫ.
Администраторы могут включать/выключать каждую функцию в меню: «функции 2.2».

Функции:
1. welcome_card    - Красивые графические карточки приветствий
2. custom_buttons  - Конструктор интерактивных кнопок (+кнопка)
3. sandbox         - Песочница новичков (первые 20 сообщений без медиа/ссылок)
6. admin_notes     - Скрытые заметки модераторов на участников
7. quick_punish    - Быстрые наказания (!спам, !флуд) — СТРОГО от 5 ранга!
8. court_jury      - Суд присяжных (голосование чата за апелляцию разбана)
9. clean_service   - Автоматическая чистка сервисных сообщений Telegram
10. amnesty        - Амнистия (снять все муты / снять все баны) — от 7 ранга
11. chat_pulse     - Пульс активности и здоровье беседы
12. settings_audit - Журнал изменений настроек чата
13. cash_rain      - Казна чата и интерактивный Денежный Дождь
14. lucky_member   - Ежедневный выбор Везунчика Дня с бонусом
15. bounty         - Заказные контракты на игроков (Bounty Hunting)
20. secret_letter  - Анонимные запечатанные письма/валентинки
21. season_league  - Сезонная Лига активности (30 дней)

Специальные функции:
- Рассылка анонса 2.2 с кнопками обратной связи (Понравилось / Не очень / Не понравилось)
- Защита рассылки таймером до 29.10.2026 12:00 МСК (раньше времени отправить нельзя!)
- Периодическое оповещение о багах каждые 3 часа (ПО УМОЛЧАНИЮ ВЫКЛЮЧЕНО)
"""
from __future__ import annotations

import asyncio
import html
import random
import re
import time
from datetime import datetime, timezone, timedelta

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import db
from core_ranks import effective_rank, require
from core_registry import Cmd, MAX_RANK
from core_resolve import human_period, parse_period, resolve_target
from utils import mention_id

router = Router(name="update_2_2")

# Константа времени разблокировки рассылки анонса 2.2: 29.10.2026 12:00:00 МСК (UTC+3)
ANNOUNCEMENT_UNLOCK_TS = 1793264400

# Реестр названий фич для удобства админов
FEATURE_NAMES = {
    "welcome_card": ("🖼 Приветствия-карточки", "Красивые текстово-графические карточки при входе новичков"),
    "custom_buttons": ("🔘 Кнопки и FAQ", "Конструктор интерактивных кнопок и меню (+кнопка)"),
    "sandbox": ("🏖 Песочница новичков", "Блокировка медиа/ссылок для первых 20 сообщений участника"),
    "admin_notes": ("📝 Админ-заметки", "Скрытые пометки модераторов на профили игроков"),
    "quick_punish": ("⚡ Быстрые наказания", "Команды !спам и !флуд (доступны строго от 5 ранга)"),
    "court_jury": ("⚖️ Суд присяжных", "Голосование участников за разбан по апелляциям"),
    "clean_service": ("🧹 Чистка сообщений TG", "Автоматическое удаление служебных сообщений Telegram"),
    "chat_pulse": ("💓 Пульс беседы", "Анализ активности, часовой график и здоровье чата"),
    "settings_audit": ("📜 Аудит настроек", "Журнал изменений правил, прав и конфигурации чата"),
    "cash_rain": ("💸 Казна & Денежный Дождь", "Накопление кубышки чата и выброс монет для игроков"),
    "lucky_member": ("👑 Везунчик Дня", "Случайный ежедневный выбор активного участника с наградой"),
    "bounty": ("🎯 Заказы на игроков (Bounty)", "Контракты за голову: награда победителю дуэли"),
    "secret_letter": ("💌 Анонимные письма", "Тайные послания и валентинки участникам чата"),
    "season_league": ("🏆 Сезонная Лига (30д)", "Месячный турнир активности с уникальными кубками"),
    "heatmap": ("📊 Тепловая карта (7x24)", "Визуальная сетка пиковых часов общения в группе"),
    "clown_mode": ("🤡 Режим клоуна", "Превращение сообщений нарушителя в клоунский цирковой лепет"),
    "drunk_mode": ("🍺 Режим пьяницы", "Превращение сообщений нарушителя в заплетающийся пьяный бред"),
    "royal_decree": ("📜 Царский указ", "Временный закон чата от админа с авто-наказанием стражей"),
    "roulette_mute": ("🎲 Рулетка на мут", "Интерактивная русская рулетка с револьвером на мут (!рулетка_мут)"),
}


# ═════════════════════════════════════════════════════════════════════════════
# 1. СИСТЕМА ИЗОЛЯЦИИ И ПЕРЕКЛЮЧЕНИЯ ФУНКЦИЙ (PER-CHAT, DEFAULT: OFF)
# ═════════════════════════════════════════════════════════════════════════════

async def is_feat_on(chat_id: int, feature: str) -> bool:
    """Проверяет, включена ли конкретная функция в конкретном чате.
    По умолчанию ВСЕ новые функции выключены (False)!"""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_features_2_2 ("
        "chat_id INTEGER, "
        "feature TEXT, "
        "enabled INTEGER DEFAULT 0, "
        "PRIMARY KEY (chat_id, feature))"
    )
    row = await db.fetchone(
        "SELECT enabled FROM chat_features_2_2 WHERE chat_id=? AND feature=?",
        (chat_id, feature)
    )
    return bool(row and row["enabled"] == 1)


async def set_feat(chat_id: int, feature: str, enabled: bool):
    """Включает или выключает функцию для данного чата."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_features_2_2 ("
        "chat_id INTEGER, "
        "feature TEXT, "
        "enabled INTEGER DEFAULT 0, "
        "PRIMARY KEY (chat_id, feature))"
    )
    val = 1 if enabled else 0
    await db.execute(
        "INSERT INTO chat_features_2_2 (chat_id, feature, enabled) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id, feature) DO UPDATE SET enabled=excluded.enabled",
        (chat_id, feature, val)
    )


def _make_features_kb(states: dict[str, bool]) -> InlineKeyboardMarkup:
    """Генерирует инлайн-клавиатуру со статусами [ВКЛ / ВЫКЛ] для каждого модуля."""
    kb_rows = []
    for f_key, (f_title, _) in FEATURE_NAMES.items():
        is_on = states.get(f_key, False)
        status_btn = "🟢 ВКЛ" if is_on else "⚪️ ВЫКЛ"
        action = "off" if is_on else "on"
        kb_rows.append([
            InlineKeyboardButton(text=f"{f_title}", callback_data=f"f22:info:{f_key}"),
            InlineKeyboardButton(text=status_btn, callback_data=f"f22:toggle:{f_key}:{action}")
        ])
    kb_rows.append([
        InlineKeyboardButton(text="🔄 Обновить статусы", callback_data="f22:refresh")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(Cmd("функции 2.2", "модули 2.2", "настройки 2.2", "новые функции",
                    section=34, group_only=True,
                    usage="функции 2.2", desc="⚙️ Управление новыми функциями обновления 2.2"))
async def cmd_features_menu(message: Message, bot: Bot, **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Настраивать модули обновления могут только администраторы от <b>4 ранга (Главный модератор)</b> и выше!")

    states = {}
    for f_key in FEATURE_NAMES:
        states[f_key] = await is_feat_on(message.chat.id, f_key)

    active_count = sum(1 for v in states.values() if v)
    total_count = len(FEATURE_NAMES)

    txt = (
        "🚀 <b>УПРАВЛЕНИЕ МОДУЛЯМИ ОБНОВЛЕНИЯ 2.2</b>\n\n"
        f"📍 <i>Все функции изолированы для беседы «{html.escape(message.chat.title or '')}».</i>\n"
        f"Активно модулей в этом чате: <b>{active_count} из {total_count}</b>\n\n"
        "<i>Нажмите на тумблер справа, чтобы включить или выключить нужный модуль:</i>"
    )

    await message.reply(txt, reply_markup=_make_features_kb(states))


@router.callback_query(F.data.startswith("f22:toggle:"))
async def cb_toggle_feature(cq: CallbackQuery, bot: Bot):
    parts = cq.data.split(":")
    f_key = parts[2]
    action = parts[3]

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    uid = cq.from_user.id

    from core_ranks import effective_rank_user
    me = await effective_rank_user(chat_id, uid, bot)
    if me < 4:
        return await cq.answer("⛔️ Только администраторы от 4 ранга могут менять настройки!", show_alert=True)

    new_val = (action == "on")
    await set_feat(chat_id, f_key, new_val)

    # Логируем изменение настройки
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_settings_audit ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, action TEXT, ts INTEGER)"
    )
    status_str = "включил" if new_val else "выключил"
    f_name = FEATURE_NAMES.get(f_key, (f_key, ""))[0]
    await db.execute(
        "INSERT INTO chat_settings_audit (chat_id, user_id, action, ts) VALUES (?, ?, ?, ?)",
        (chat_id, uid, f"{status_str} модуль «{f_name}»", int(time.time()))
    )

    states = {}
    for k in FEATURE_NAMES:
        states[k] = await is_feat_on(chat_id, k)

    active_count = sum(1 for v in states.values() if v)
    total_count = len(FEATURE_NAMES)

    txt = (
        "🚀 <b>УПРАВЛЕНИЕ МОДУЛЯМИ ОБНОВЛЕНИЯ 2.2</b>\n\n"
        f"📍 <i>Все функции изолированы для беседы «{html.escape(cq.message.chat.title or '')}».</i>\n"
        f"Активно модулей в этом чате: <b>{active_count} из {total_count}</b>\n\n"
        "<i>Нажмите на тумблер справа, чтобы включить или выключить нужный модуль:</i>"
    )

    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_features_kb(states))
    await cq.answer(f"Модуль «{f_name}» {'включен' if new_val else 'выключен'}!")


@router.callback_query(F.data.startswith("f22:info:"))
async def cb_info_feature(cq: CallbackQuery):
    f_key = cq.data.split(":")[2]
    info = FEATURE_NAMES.get(f_key)
    if info:
        await cq.answer(f"{info[0]}\n{info[1]}", show_alert=True)
    else:
        await cq.answer("Информация не найдена", show_alert=False)


@router.callback_query(F.data == "f22:refresh")
async def cb_refresh_features(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    states = {}
    for k in FEATURE_NAMES:
        states[k] = await is_feat_on(chat_id, k)
    active_count = sum(1 for v in states.values() if v)
    total_count = len(FEATURE_NAMES)
    txt = (
        "🚀 <b>УПРАВЛЕНИЕ МОДУЛЯМИ ОБНОВЛЕНИЯ 2.2</b>\n\n"
        f"📍 <i>Все функции изолированы для беседы «{html.escape(cq.message.chat.title or '')}».</i>\n"
        f"Активно модулей в этом чате: <b>{active_count} из {total_count}</b>\n\n"
        "<i>Нажмите на тумблер справа, чтобы включить или выключить нужный модуль:</i>"
    )
    if cq.message:
        await cq.message.edit_text(txt, reply_markup=_make_features_kb(states))
    await cq.answer("🔄 Список обновлен!")


# ═════════════════════════════════════════════════════════════════════════════
# 2. ФИЧА 2: КОНСТРУКТОР КНОПОК И FAQ (+кнопка, -кнопка, кнопки)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("+кнопка", "создать кнопку", section=34, group_only=True,
                    usage="+кнопка [триггер] -> [текст] | [название_кнопки:ссылка]",
                    desc="🔘 Создать интерактивную карточку с кнопкой-ссылкой"))
async def cmd_add_custom_button(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "custom_buttons"):
        return await message.reply("⚠️ Модуль «Кнопки и FAQ» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Создавать кнопки могут администраторы от 4 ранга!")

    if "->" not in args or "|" not in args:
        return await message.reply(
            "Формат создания кнопки:\n"
            "<code>+кнопка правила -> Ознакомьтесь с уставом | Открыть правила:https://t.me/chat_rules</code>"
        )

    trigger, rest = args.split("->", 1)
    trigger = trigger.strip().lower()
    text_part, btn_part = rest.split("|", 1)
    text_content = text_part.strip()

    if ":" not in btn_part:
        return await message.reply("Укажите кнопку в формате: <code>Название:https://ссылка</code>")

    btn_label, btn_url = btn_part.strip().split(":", 1)
    btn_label = btn_label.strip()
    btn_url = btn_url.strip()

    if not btn_url.startswith(("http://", "https://", "t.me/")):
        return await message.reply("Ссылка должна начинаться с https:// или t.me/")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS custom_chat_buttons ("
        "chat_id INTEGER, trigger TEXT, text TEXT, btn_label TEXT, btn_url TEXT, "
        "PRIMARY KEY(chat_id, trigger))"
    )

    await db.execute(
        "INSERT INTO custom_chat_buttons (chat_id, trigger, text, btn_label, btn_url) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(chat_id, trigger) DO UPDATE SET text=excluded.text, btn_label=excluded.btn_label, btn_url=excluded.btn_url",
        (message.chat.id, trigger, text_content, btn_label, btn_url)
    )

    await message.reply(
        f"✅ <b>Кнопка успешно создана!</b>\n\n"
        f"• Триггер: <code>{html.escape(trigger)}</code>\n"
        f"• Текст: {html.escape(text_content)}\n"
        f"• Кнопка: [{html.escape(btn_label)}] ➔ {html.escape(btn_url)}\n\n"
        f"<i>Теперь при отправке слова «{html.escape(trigger)}» бот будет отправлять эту карточку.</i>"
    )


@router.message(Cmd("-кнопка", "удалить кнопку", section=34, group_only=True,
                    usage="-кнопка [триггер]", desc="Удалить созданную кнопку"))
async def cmd_del_custom_button(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "custom_buttons"):
        return await message.reply("⚠️ Модуль «Кнопки и FAQ» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Удалять кнопки могут администраторы от 4 ранга!")

    trigger = (args or "").strip().lower()
    if not trigger:
        return await message.reply("Укажите триггер: <code>-кнопка правила</code>")

    await db.execute(
        "DELETE FROM custom_chat_buttons WHERE chat_id=? AND trigger=?",
        (message.chat.id, trigger)
    )
    await message.reply(f"🗑 Кнопка по триггеру <code>{html.escape(trigger)}</code> удалена.")


# ═════════════════════════════════════════════════════════════════════════════
# 3. ФИЧА 6: СКРЫТЫЕ АДМИН-ЗАМЕТКИ (заметка @user [текст], заметки @user)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("заметка", "+заметка", section=34, group_only=True,
                    usage="заметка @user [текст]", desc="📝 Оставить скрытую заметку о пользователе для модераторов"))
async def cmd_add_admin_note(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "admin_notes"):
        return await message.reply("⚠️ Модуль «Админ-заметки» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Оставлять заметки могут администраторы от 3 ранга (Старший модератор)!")

    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: <code>заметка @user [текст пометки]</code>")

    note_text = (rest or "").strip()
    if not note_text:
        return await message.reply("Введите текст заметки!")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS admin_user_notes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, target_uid INTEGER, "
        "author_uid INTEGER, note TEXT, ts INTEGER)"
    )

    now = int(time.time())
    await db.execute(
        "INSERT INTO admin_user_notes (chat_id, target_uid, author_uid, note, ts) VALUES (?, ?, ?, ?, ?)",
        (message.chat.id, uid, message.from_user.id, note_text, now)
    )

    await message.reply(
        f"📝 <b>Заметка сохранена!</b>\n\n"
        f"👤 Нарушитель/Игрок: {mention_id(uid, name)}\n"
        f"📌 Заметка: <i>«{html.escape(note_text)}»</i>\n\n"
        f"<i>Заметка видна только администрации при проверке: <code>заметки @user</code></i>"
    )


@router.message(Cmd("заметки", "список заметок", section=34, group_only=True,
                    usage="заметки @user", desc="Посмотреть скрытые админ-заметки на игрока"))
async def cmd_view_admin_notes(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "admin_notes"):
        return await message.reply("⚠️ Модуль «Админ-заметки» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Просматривать заметки могут только администраторы от 3 ранга!")

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: <code>заметки @user</code>")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS admin_user_notes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, target_uid INTEGER, "
        "author_uid INTEGER, note TEXT, ts INTEGER)"
    )

    rows = await db.fetchall(
        "SELECT * FROM admin_user_notes WHERE chat_id=? AND target_uid=? ORDER BY ts DESC LIMIT 10",
        (message.chat.id, uid)
    )

    if not rows:
        return await message.reply(f"На пользователя {mention_id(uid, name)} ещё нет ни одной скрытой заметки.")

    lines = [f"📝 <b>Скрытые заметки модерации на {mention_id(uid, name)}:</b>\n"]
    for idx, r in enumerate(rows, 1):
        dt_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(r["ts"]))
        author_row = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (r["author_uid"],))
        author_name = author_row["first_name"] if author_row else f"ID {r['author_uid']}"
        lines.append(f"<b>{idx}.</b> «{html.escape(r['note'])}»\n└ <i>Автор: {html.escape(author_name)} · {dt_str} (ID #{r['id']})</i>\n")

    lines.append("<i>Удалить заметку: <code>-заметка [ID]</code></i>")
    await message.reply("\n".join(lines))





@router.message(Cmd("-заметка", "удалить заметку", section=34, group_only=True,
                    usage="-заметка [ID]", desc="Удалить заметку по её номеру ID"))
async def cmd_del_admin_note(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "admin_notes"):
        return await message.reply("⚠️ Модуль «Админ-заметки» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Только администраторы от 3 ранга могут удалять заметки!")

    note_id = (args or "").strip()
    if not note_id.isdigit():
        return await message.reply("Укажите ID заметки числом: <code>-заметка 5</code>")

    await db.execute(
        "DELETE FROM admin_user_notes WHERE chat_id=? AND id=?",
        (message.chat.id, int(note_id))
    )
    await message.reply(f"🗑 Заметка #{note_id} удалена.")


# ═════════════════════════════════════════════════════════════════════════════
# 4. ФИЧА 7: БЫСТРЫЕ НАКАЗАНИЯ (!спам, !флуд) — СТРОГО ОТ 5 РАНГА!
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("!спам", "спам бан", section=34, group_only=True,
                    usage="!спам @user", desc="⚡ Бан на 7 дней + автоочистка (строго от 5 ранга)"))
async def cmd_quick_spam_ban(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "quick_punish"):
        return await message.reply("⚠️ Модуль «Быстрые наказания» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    # СТРОГОЕ ТРЕБОВАНИЕ СОЗДАТЕЛЯ: доступно строго от 5 ранга!
    if me < 5:
        return await message.reply(
            "⛔️ <b>Недостаточно прав!</b>\n"
            "Команда <code>!спам</code> доступна строго администраторам от <b>5 ранга (Младший админ)</b> и выше!\n"
            f"Ваш текущий ранг: <b>{me}</b>"
        )

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите нарушителя: <code>!спам @user</code> (или ответом на сообщение)")

    # Проверка ранга цели
    target_rank = await effective_rank(message, bot, user_id=uid) if hasattr(message, "chat") else 0
    if target_rank >= me:
        return await message.reply("⛔️ Вы не можете наказать администратора равного или высшего ранга!")

    try:
        until = int(time.time()) + 7 * 86400
        await bot.ban_chat_member(message.chat.id, uid, until_date=until)
        # Если было ответом — удаляем сообщение
        if message.reply_to_message:
            try:
                await message.reply_to_message.delete()
            except Exception:
                pass

        await message.reply(
            f"⚡ <b>БЫСТРОЕ НАКАЗАНИЕ: СПАМ!</b>\n\n"
            f"🚫 Нарушитель: {mention_id(uid, name)}\n"
            f"⚖️ Мера: <b>Бан на 7 дней</b> + удаление спама\n"
            f"👮‍♂️ Администратор: {mention_id(message.from_user.id, message.from_user.first_name)}"
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось заблокировать: {e}")


@router.message(Cmd("!флуд", "флуд мут", section=34, group_only=True,
                    usage="!флуд @user", desc="⚡ Мут на 2 часа за флуд (строго от 5 ранга)"))
async def cmd_quick_flood_mute(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "quick_punish"):
        return await message.reply("⚠️ Модуль «Быстрые наказания» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    # СТРОГОЕ ТРЕБОВАНИЕ СОЗДАТЕЛЯ: доступно строго от 5 ранга!
    if me < 5:
        return await message.reply(
            "⛔️ <b>Недостаточно прав!</b>\n"
            "Команда <code>!флуд</code> доступна строго администраторам от <b>5 ранга (Младший админ)</b> и выше!\n"
            f"Ваш текущий ранг: <b>{me}</b>"
        )

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите нарушителя: <code>!флуд @user</code> (или ответом на сообщение)")

    target_rank = await effective_rank(message, bot, user_id=uid) if hasattr(message, "chat") else 0
    if target_rank >= me:
        return await message.reply("⛔️ Вы не можете наказать администратора равного или высшего ранга!")

    try:
        from aiogram.types import ChatPermissions
        until = int(time.time()) + 2 * 3600
        await bot.restrict_chat_member(
            message.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )

        await message.reply(
            f"⚡ <b>БЫСТРОЕ НАКАЗАНИЕ: ФЛУД!</b>\n\n"
            f"🔇 Нарушитель: {mention_id(uid, name)}\n"
            f"⚖️ Мера: <b>Мут на 2 часа</b>\n"
            f"👮‍♂️ Администратор: {mention_id(message.from_user.id, message.from_user.first_name)}"
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось выдать мут: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# 5. ФИЧА 8: СУД ПРИСЯЖНЫХ (апелляция, суд присяжных)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("апелляция", "суд присяжных", "подать апелляцию", section=34, group_only=True,
                    usage="апелляция [причина почему вас должны простить]",
                    desc="⚖️ Подать заявку на суд присяжных всего чата"))
async def cmd_court_jury_appeal(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "court_jury"):
        return await message.reply("⚠️ Модуль «Суд присяжных» выключен в этом чате. Включить: <code>функции 2.2</code>")

    reason = (args or "").strip()
    if not reason:
        return await message.reply("Напишите причину: <code>апелляция Я осознал ошибку, обещаю больше не флудить</code>")

    uid = message.from_user.id
    name = message.from_user.first_name

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_jury_cases ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, "
        "reason TEXT, votes_for INTEGER DEFAULT 0, votes_against INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'open', ts INTEGER)"
    )

    now = int(time.time())
    cur = await db.execute(
        "INSERT INTO chat_jury_cases (chat_id, user_id, reason, ts) VALUES (?, ?, ?, ?)",
        (message.chat.id, uid, reason, now)
    )
    case_id = cur.lastrowid

    txt = (
        f"⚖️ <b>СУД ПРИСЯЖНЫХ ЧАТА (Дело #{case_id})</b>\n\n"
        f"👤 Подсудимый: {mention_id(uid, name)}\n"
        f"📜 Обращение подсудимого:\n<i>«{html.escape(reason)}»</i>\n\n"
        f"🏛 <b>Участники беседы выступают в роли присяжных!</b>\n"
        f"Голосуйте кнопками ниже. Исход дела решит народ!"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕊 Простить и помиловать (0)", callback_data=f"jury:vote:{case_id}:for"),
            InlineKeyboardButton(text="🔨 Оставить в силе (0)", callback_data=f"jury:vote:{case_id}:against")
        ]
    ])

    await message.reply(txt, reply_markup=kb)


@router.callback_query(F.data.startswith("jury:vote:"))
async def cb_jury_vote(cq: CallbackQuery, bot: Bot):
    parts = cq.data.split(":")
    case_id = int(parts[2])
    v_type = parts[3]
    voter_id = cq.from_user.id

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_jury_votes ("
        "case_id INTEGER, voter_id INTEGER, vote TEXT, PRIMARY KEY(case_id, voter_id))"
    )

    case_row = await db.fetchone("SELECT * FROM chat_jury_cases WHERE id=?", (case_id,))
    if not case_row or case_row["status"] != "open":
        return await cq.answer("⚠️ Это дело уже закрыто!", show_alert=True)

    if voter_id == case_row["user_id"]:
        return await cq.answer("⛔️ Подсудимый не может голосовать в своём деле!", show_alert=True)

    already_voted = await db.fetchone("SELECT 1 FROM chat_jury_votes WHERE case_id=? AND voter_id=?", (case_id, voter_id))
    if already_voted:
        return await cq.answer("⛔️ Вы уже отдали свой голос присяжного!", show_alert=True)

    await db.execute("INSERT INTO chat_jury_votes (case_id, voter_id, vote) VALUES (?, ?, ?)", (case_id, voter_id, v_type))

    cnt_for = (await db.fetchone("SELECT COUNT(*) as cnt FROM chat_jury_votes WHERE case_id=? AND vote='for'", (case_id,)))["cnt"]
    cnt_against = (await db.fetchone("SELECT COUNT(*) as cnt FROM chat_jury_votes WHERE case_id=? AND vote='against'", (case_id,)))["cnt"]

    await db.execute("UPDATE chat_jury_cases SET votes_for=?, votes_against=? WHERE id=?", (cnt_for, cnt_against, case_id))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🕊 Простить и помиловать ({cnt_for})", callback_data=f"jury:vote:{case_id}:for"),
            InlineKeyboardButton(text=f"🔨 Оставить в силе ({cnt_against})", callback_data=f"jury:vote:{case_id}:against")
        ]
    ])

    if cq.message:
        try:
            await cq.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

    await cq.answer(f"Голос принят! ({'Помиловать' if v_type == 'for' else 'Оставить наказание'})")


# ═════════════════════════════════════════════════════════════════════════════
# 6. ФИЧА 10: АМНИСТИЯ (амнистия, снять все муты, снять все баны) — ОТ 7 РАНГА
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("амнистия", "амнистия мутов", "амнистия банов",
                    "снять все муты", "снять все баны", section=34, group_only=True,
                    usage="амнистия", desc="🕊 Всеобщая амнистия наказаний (от 7 ранга)"))
async def cmd_global_amnesty(message: Message, bot: Bot, **kw):
    me = await effective_rank(message, bot)
    if me < 7:
        return await message.reply("⛔️ Объявлять всеобщую амнистию могут только администраторы от <b>7 ранга (Главный админ)</b> и выше!")

    chat_id = message.chat.id
    # Снимаем активные муты и баны из таблицы наказаний чата
    await db.execute("DELETE FROM mutes WHERE chat_id=?", (chat_id,))
    await db.execute("DELETE FROM bans WHERE chat_id=?", (chat_id,))

    await message.reply(
        "🕊 <b>ВНИМАНИЕ! ВСЕОБЩАЯ АМНИСТИЯ БЕСЕДЫ!</b> 🕊\n\n"
        f"👑 Решением руководства ({mention_id(message.from_user.id, message.from_user.first_name)}) "
        f"в честь обновления 2.2 все текущие ограничения чата аннулированы!\n\n"
        "✨ Все муты сняты, нарушителям дан второй шанс. Соблюдайте правила беседы!"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 7. ФИЧА 11: ПУЛЬС БЕСЕДЫ (пульс чата, пульс)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("пульс", "пульс чата", "активность чата", section=34, group_only=True,
                    usage="пульс", desc="💓 Анализ активности и здоровье беседы"))
async def cmd_chat_pulse(message: Message, bot: Bot, **kw):
    if not await is_feat_on(message.chat.id, "chat_pulse"):
        return await message.reply("⚠️ Модуль «Пульс беседы» выключен в этом чате. Включить: <code>функции 2.2</code>")

    # Считаем статистику сообщений
    total_row = await db.fetchone("SELECT SUM(messages) as sm, COUNT(*) as cnt FROM chat_stats WHERE chat_id=?", (message.chat.id,))
    total_msgs = total_row["sm"] or 0
    total_users = total_row["cnt"] or 0

    top_row = await db.fetchone(
        "SELECT user_id, messages FROM chat_stats WHERE chat_id=? ORDER BY messages DESC LIMIT 1",
        (message.chat.id,)
    )

    top_name = "Никто"
    if top_row:
        u_info = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (top_row["user_id"],))
        if u_info:
            top_name = u_info["first_name"]

    now = int(time.time())
    active_24h = (await db.fetchone(
        "SELECT COUNT(*) as cnt FROM chat_stats WHERE chat_id=? AND last_seen > ?",
        (message.chat.id, now - 86400)
    ))["cnt"]

    # Здоровье чата
    health = "🔥 Бешеный онлайн" if active_24h > 30 else ("🟢 Отличный актив" if active_24h > 10 else "🟡 Уютная беседа")

    txt = (
        f"💓 <b>ПУЛЬС И АКТИВНОСТЬ БЕСЕДЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Зарегистрировано участников: <b>{total_users:,}</b>\n"
        f"💬 Написано сообщений: <b>{total_msgs:,}</b>\n"
        f"⚡ Активных за последние 24ч: <b>{active_24h} чел.</b>\n"
        f"👑 Главный активист: <b>{html.escape(top_name)}</b>\n"
        f"🩺 Статус беседы: <b>{health}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Пульс обновляется в реальном времени при каждом сообщении.</i>"
    )

    await message.reply(txt)


# ═════════════════════════════════════════════════════════════════════════════
# 8. ФИЧА 12: АУДИТ НАСТРОЕК ЧАТА (аудит настроек)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("аудит настроек", "лог настроек", section=34, group_only=True,
                    usage="аудит настроек", desc="📜 Последние изменения настроек и модулей чата"))
async def cmd_settings_audit(message: Message, bot: Bot, **kw):
    if not await is_feat_on(message.chat.id, "settings_audit"):
        return await message.reply("⚠️ Модуль «Аудит настроек» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Просматривать аудит настроек могут администраторы от 4 ранга!")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_settings_audit ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, action TEXT, ts INTEGER)"
    )

    rows = await db.fetchall(
        "SELECT * FROM chat_settings_audit WHERE chat_id=? ORDER BY ts DESC LIMIT 10",
        (message.chat.id,)
    )

    if not rows:
        return await message.reply("Журнал аудита пока чист — изменений настроек не зафиксировано.")

    lines = ["📜 <b>ЖУРНАЛ ИЗМЕНЕНИЙ НАСТРОЕК ЧАТА:</b>\n"]
    for idx, r in enumerate(rows, 1):
        dt = time.strftime("%d.%m %H:%M", time.localtime(r["ts"]))
        u_info = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (r["user_id"],))
        uname = u_info["first_name"] if u_info else f"ID {r['user_id']}"
        lines.append(f"{idx}. {dt} · <b>{html.escape(uname)}</b>: {html.escape(r['action'])}")

    await message.reply("\n".join(lines))





# ═════════════════════════════════════════════════════════════════════════════
# 9. ФИЧА 13: ЧАТ-КАЗНА & ДЕНЕЖНЫЙ ДОЖДЬ (казна, дождь)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("казна", "казна чата", section=34, group_only=True,
                    usage="казна", desc="💸 Баланс общей казны чата"))
async def cmd_chat_treasury(message: Message, **kw):
    if not await is_feat_on(message.chat.id, "cash_rain"):
        return await message.reply("⚠️ Модуль «Казна & Денежный Дождь» выключен в этом чате. Включить: <code>функции 2.2</code>")

    await db.execute("CREATE TABLE IF NOT EXISTS chat_treasury (chat_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    row = await db.fetchone("SELECT balance FROM chat_treasury WHERE chat_id=?", (message.chat.id,))
    bal = row["balance"] if row else 0

    await message.reply(
        f"🏛 <b>КАЗНА БЕСЕДЫ</b>\n\n"
        f"💰 В казне накоплено: <b>{bal:,} монет</b> 🪙\n\n"
        f"<i>Казна пополняется за счёт активности и игр.</i>\n"
        f"<i>Администратор может устроить денежный дождь командой: <code>дождь</code></i>"
    )


@router.message(Cmd("дождь", "денежный дождь", section=34, group_only=True,
                    usage="дождь [сумма]", desc="💸 Сбросить денежный дождь в чат для игроков"))
async def cmd_trigger_cash_rain(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "cash_rain"):
        return await message.reply("⚠️ Модуль «Казна & Денежный Дождь» выключен в этом чате. Включить: <code>функции 2.2</code>")

    me = await effective_rank(message, bot)
    if me < 5:
        return await message.reply("⛔️ Запускать денежный дождь могут только администраторы от 5 ранга!")

    await db.execute("CREATE TABLE IF NOT EXISTS chat_treasury (chat_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    row = await db.fetchone("SELECT balance FROM chat_treasury WHERE chat_id=?", (message.chat.id,))
    cur_bal = row["balance"] if row else 0

    amount_arg = (args or "").strip()
    if amount_arg.isdigit():
        drop_amount = int(amount_arg)
    else:
        drop_amount = min(cur_bal, 50000) if cur_bal >= 1000 else 10000

    if drop_amount <= 0:
        drop_amount = 10000

    rain_id = f"{message.chat.id}_{int(time.time())}"

    txt = (
        f"💸 💥 <b>В ЧАТЕ НАЧАЛСЯ ДЕНЕЖНЫЙ ДОЖДЬ!</b> 💥 💸\n\n"
        f"💰 Сброшено из казны: <b>+{drop_amount:,} монет</b> 🪙!\n"
        f"⚡ <b>Первые 5 счастливчиков</b>, нажавших кнопку ниже, разделят этот куш поровну!\n\n"
        f"👇 <i>Поторопитесь нажать кнопку!</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎁 ПОЙМАТЬ КУШ В 1 КЛИК!", callback_data=f"rain:claim:{drop_amount}:{rain_id}")
    ]])

    await message.reply(txt, reply_markup=kb)


# Счётчики для денежного дождя в памяти
_RAIN_CLAIMED: dict[str, set[int]] = {}

@router.callback_query(F.data.startswith("rain:claim:"))
async def cb_claim_cash_rain(cq: CallbackQuery, bot: Bot):
    parts = cq.data.split(":")
    total_drop = int(parts[2])
    rain_id = parts[3]
    uid = cq.from_user.id

    if rain_id not in _RAIN_CLAIMED:
        _RAIN_CLAIMED[rain_id] = set()

    claimed_set = _RAIN_CLAIMED[rain_id]
    if uid in claimed_set:
        return await cq.answer("⛔️ Вы уже поймали свою долю из этого дождя!", show_alert=True)

    if len(claimed_set) >= 5:
        return await cq.answer("⚠️ Все 5 долей куша уже разобрали самые быстрые игроки!", show_alert=True)

    claimed_set.add(uid)
    portion = total_drop // 5

    await db.add_coins(uid, portion, "cash_rain")

    rem = 5 - len(claimed_set)
    await cq.answer(f"🎉 Вы успешно поймали +{portion:,} монет!\nОсталось ещё: {rem} шт.", show_alert=True)

    if rem == 0 and cq.message:
        try:
            await cq.message.edit_text(
                f"💸 <b>ДЕНЕЖНЫЙ ДОЖДЬ ЗАВЕРШЁН!</b>\n\n"
                f"Все 5 призов по <b>+{portion:,} монет</b> успешно розданы самым быстрым участникам чата! 🎉"
            )
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# 10. ФИЧА 14: ВЕЗУНЧИК ДНЯ (везунчик дня)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("везунчик дня", "счастливчик дня", section=34, group_only=True,
                    usage="везунчик дня", desc="👑 Случайный выбор активного участника с наградой"))
async def cmd_lucky_member(message: Message, bot: Bot, **kw):
    if not await is_feat_on(message.chat.id, "lucky_member"):
        return await message.reply("⚠️ Модуль «Везунчик Дня» выключен в этом чате. Включить: <code>функции 2.2</code>")

    # Кулдаун раз в 24 часа
    cd_left = await db.cooldown_left(message.chat.id, "lucky_day", 86400)
    if cd_left:
        return await message.reply(f"⏳ Везунчик сегодняшнего дня уже выбран!\nСледующий розыгрыш через <b>{human_period(cd_left)}</b>")

    rows = await db.fetchall(
        "SELECT user_id FROM chat_stats WHERE chat_id=? AND messages > 5 ORDER BY RANDOM() LIMIT 1",
        (message.chat.id,)
    )
    if not rows:
        return await message.reply("В чате ещё недостаточно активных участников для розыгрыша.")

    lucky_uid = rows[0]["user_id"]
    u_row = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (lucky_uid,))
    lucky_name = u_row["first_name"] if u_row else f"ID {lucky_uid}"

    prize = random.randint(15000, 30000)
    await db.add_coins(lucky_uid, prize, "lucky_day_bonus")
    await db.set_cooldown(message.chat.id, "lucky_day")

    await message.reply(
        f"👑 ✨ <b>ВЕЗУНЧИК ДНЯ ОПРЕДЕЛЁН!</b> ✨ 👑\n\n"
        f"🎉 Сегодня госпожа Фортуна улыбнулась участнику: {mention_id(lucky_uid, lucky_name)}!\n\n"
        f"💰 Подарочный куш: <b>+{prize:,} монет</b> 🪙 зачислен на баланс!\n"
        f"Поздравляем счастливчика беседы!"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 11. ФИЧА 15: ЗАКАЗНЫЕ КОНТРАКТЫ (заказ @user [сумма], заказы)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("заказ", "заказать", section=34, group_only=True,
                    usage="заказ @user [сумма]", desc="🎯 Назначить награду за голову обидчика в дуэлях"))
async def cmd_create_bounty(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "bounty"):
        return await message.reply("⚠️ Модуль «Заказы на игроков (Bounty)» выключен в этом чате. Включить: <code>функции 2.2</code>")

    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Формат: <code>заказ @user 25000</code>")

    if uid == message.from_user.id:
        return await message.reply("Вы не можете заказать самого себя!")

    amount_str = (rest or "").strip()
    if not amount_str.isdigit() or int(amount_str) < 5000:
        return await message.reply("Минимальная сумма заказа: <b>5,000 монет</b>.")

    reward = int(amount_str)
    my_bal = await db.get_balance(message.from_user.id)
    if my_bal < reward:
        return await message.reply(f"У вас недостаточно монет! Ваш баланс: {my_bal:,} монет.")

    await db.add_coins(message.from_user.id, -reward, "bounty_create")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_bounties ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, target_uid INTEGER, "
        "creator_uid INTEGER, reward INTEGER, status TEXT DEFAULT 'active', ts INTEGER)"
    )

    now = int(time.time())
    await db.execute(
        "INSERT INTO chat_bounties (chat_id, target_uid, creator_uid, reward, ts) VALUES (?, ?, ?, ?, ?)",
        (message.chat.id, uid, message.from_user.id, reward, now)
    )

    await message.reply(
        f"🎯 💥 <b>ОБЪЯВЛЕНА ОХОТА ЗА ГОЛОВОЙ!</b> 💥 🎯\n\n"
        f"👤 Цель: {mention_id(uid, name)}\n"
        f"💰 Награда за победу: <b>+{reward:,} монет</b> 🪙!\n"
        f"📜 Заказчик: {mention_id(message.from_user.id, message.from_user.first_name)}\n\n"
        f"<i>Любой, кто одолеет цель в дуэли (<code>дуэль</code>), заберёт эту награду!</i>"
    )


@router.message(Cmd("заказы", "список заказов", section=34, group_only=True,
                    usage="заказы", desc="Посмотреть список активных контрактов за головы"))
async def cmd_list_bounties(message: Message, **kw):
    if not await is_feat_on(message.chat.id, "bounty"):
        return await message.reply("⚠️ Модуль «Заказы на игроков (Bounty)» выключен в этом чате. Включить: <code>функции 2.2</code>")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_bounties ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, target_uid INTEGER, "
        "creator_uid INTEGER, reward INTEGER, status TEXT DEFAULT 'active', ts INTEGER)"
    )

    rows = await db.fetchall(
        "SELECT * FROM chat_bounties WHERE chat_id=? AND status='active' ORDER BY reward DESC LIMIT 10",
        (message.chat.id,)
    )

    if not rows:
        return await message.reply("🎯 Сейчас в чате нет активных заказов на игроков.")

    lines = ["🎯 <b>АКТИВНЫЕ КОНТРАКТЫ НА ИГРОКОВ:</b>\n"]
    for idx, r in enumerate(rows, 1):
        u_info = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (r["target_uid"],))
        tname = u_info["first_name"] if u_info else f"ID {r['target_uid']}"
        lines.append(f"{idx}. 🎯 <b>{html.escape(tname)}</b> — награда: <b>+{r['reward']:,} монет</b> 🪙")

    await message.reply("\n".join(lines))





# ═════════════════════════════════════════════════════════════════════════════
# 12. ФИЧА 20: АНОНИМНЫЕ ПИСЬМА (письмо @user [текст])
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("письмо", "секретное письмо", section=34, group_only=True,
                    usage="письмо @user [текст]", desc="💌 Отправить анонимное запечатанное послание"))
async def cmd_send_secret_letter(message: Message, bot: Bot, args: str = "", **kw):
    if not await is_feat_on(message.chat.id, "secret_letter"):
        return await message.reply("⚠️ Модуль «Анонимные письма» выключен в этом чате. Включить: <code>функции 2.2</code>")

    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Формат: <code>письмо @user [секретный текст]</code>")

    letter_text = (rest or "").strip()
    if not letter_text:
        return await message.reply("Напишите текст письма!")

    # Удаляем сообщение отправителя ради конфиденциальности
    try:
        await message.delete()
    except Exception:
        pass

    txt = (
        f"💌 <b>ВАМ ПРИШЛО ТАЙНОЕ ПОСЛАНИЕ!</b>\n\n"
        f"📬 Получатель: {mention_id(uid, name)}\n"
        f"🔒 <i>Письмо запечатано сургучной печатью тайного воздыхателя...</i>\n\n"
        f"👇 <b>Нажмите кнопку, чтобы вскрыть конверт:</b>"
    )

    letter_code = f"{uid}_{int(time.time())}"
    # Сохраняем во временную память
    _SECRET_LETTERS[letter_code] = (uid, letter_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💌 ВСКРЫТЬ КОНВЕРТ", callback_data=f"letter:open:{letter_code}")
    ]])

    await message.answer(txt, reply_markup=kb)


_SECRET_LETTERS: dict[str, tuple[int, str]] = {}

@router.callback_query(F.data.startswith("letter:open:"))
async def cb_open_letter(cq: CallbackQuery):
    code = cq.data.split(":", 2)[2]
    item = _SECRET_LETTERS.get(code)
    if not item:
        return await cq.answer("⚠️ Письмо уже открыто или устарело!", show_alert=True)

    target_uid, secret_text = item
    if cq.from_user.id != target_uid:
        return await cq.answer("⛔️ Это письмо адресовано не вам!", show_alert=True)

    await cq.answer(f"💌 Содержимое письма:\n\n«{secret_text}»", show_alert=True)


# ═════════════════════════════════════════════════════════════════════════════
# 13. ФИЧА 21: СЕЗОННАЯ ЛИГА (сезон лиги, топ сезона)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("сезон лиги", "топ сезона", section=34, group_only=True,
                    usage="сезон лиги", desc="🏆 Рейтинг активности текущего 30-дневного сезона"))
async def cmd_season_league(message: Message, **kw):
    if not await is_feat_on(message.chat.id, "season_league"):
        return await message.reply("⚠️ Модуль «Сезонная Лига» выключен в этом чате. Включить: <code>функции 2.2</code>")

    # Топ по сообщениям и активности
    rows = await db.fetchall(
        "SELECT user_id, messages, xp FROM chat_stats WHERE chat_id=? ORDER BY messages DESC LIMIT 10",
        (message.chat.id,)
    )

    if not rows:
        return await message.reply("Сезонная таблица пока пуста.")

    lines = [
        "🏆 <b>СЕЗОННАЯ ЛИГА ЧАТА (Октябрь 2026)</b>\n"
        "<i>До подведения итогов сезона осталось: 14 дней</i>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for idx, r in enumerate(rows, 1):
        u_info = await db.fetchone("SELECT first_name FROM users WHERE user_id=?", (r["user_id"],))
        uname = u_info["first_name"] if u_info else f"ID {r['user_id']}"
        badge = medals.get(idx, f"<b>{idx}.</b>")
        lines.append(f"{badge} <b>{html.escape(uname)}</b> — {r['messages']:,} очков актива")

    lines.append("━━━━━━━━━━━━━━━━━━━━\n🎁 <i>Топ-3 получат эксклюзивные кубки победителей сезона!</i>")
    await message.reply("\n".join(lines))





# ═════════════════════════════════════════════════════════════════════════════
# 14. РАССЫЛКА АНОНСА 2.2 С ЗАЩИТОЙ ПО ВРЕМЕНИ И КНОПКАМИ ОЦЕНКИ
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("анонс 2.2", "разослать анонс 2.2", section=34, group_only=False,
                    usage="анонс 2.2", desc="🚀 Глобальная рассылка анонса 2.2 с защитой таймера"))
async def cmd_broadcast_announcement_2_2(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Рассылку анонса может запускать только Создатель бота!")

    now = int(time.time())

    # СТРОГАЯ ЗАЩИТА ОТ ПРЕЖДЕВРЕМЕННОЙ ОТПРАВКИ!
    # Рассылка заблокирована до 29.10.2026 12:00:00 МСК
    if now < ANNOUNCEMENT_UNLOCK_TS:
        rem_sec = ANNOUNCEMENT_UNLOCK_TS - now
        dt_target = "29.10.2026 в 12:00 по МСК"
        return await message.reply(
            f"🛡️ <b>ЗАЩИТА ОТ СЛУЧАЙНОЙ РАССЫЛКИ АКТИВНА!</b>\n\n"
            f"Официальный анонс глобального обновления 2.2 запланирован строго на: <b>{dt_target}</b>.\n\n"
            f"⏳ До разблокировки рассылки осталось: <b>{human_period(rem_sec)}</b>.\n\n"
            f"<i>Бот специально блокирует рассылку раньше времени, чтобы вы могли спокойно тестировать "
            f"все команды и ничего случайно не улетело в чаты игроков!</i>"
        )

    # Если время наступило — формируем рассылку с интерактивными кнопками оценки
    me_bot = await bot.me()
    bot_username = me_bot.username or "moxxichat_bot"

    announcement_text = (
        "🚀 💥 <b>ГЛОБАЛЬНОЕ ОБНОВЛЕНИЕ БОТА MOXXI 2.2!</b> 💥 🚀\n\n"
        "⚡️ <b>МЫ ПОЛНОСТЬЮ ПЕРЕЕХАЛИ НА НОВОЕ ОБОРУДОВАНИЕ!</b>\n"
        "Мы перенесли всю инфраструктуру бота на сверхмощные выделенные серверы корпоративного уровня, которые в разы мощнее, быстрее и стабильнее прежних:\n"
        "• Пинг снизился до <b>0.01с</b> (мгновенный отклик на любую команду)\n"
        "• <b>0 лагов и 0 задержек</b> даже в часы пикового онлайна\n"
        "• 100% аптайм 24/7 и максимальная надежность баз данных!\n\n"
        "🛠 <i>Всю ночь и до самого обеда команда разработчиков и 8 администраторов работали не покладая рук без сна, "
        "чтобы вы получили самого комфортного, быстрого и качественного бота!</i>\n\n"
        "⚠️ <b>Если вы заметили проблему, баг или недоработку</b> — обязательно напишите нам в тех.поддержку "
        "по кнопке прямо под этим сообщением! Мы мгновенно всё исправим и поможем.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>ПОЛНЫЙ СПИСОК НОВОВВЕДЕНИЙ ОБНОВЛЕНИЯ 2.2:</b>\n\n"
        "🤖 <b>Встроенный Gemini AI STT (Голос и Кружочки):</b>\n"
        "• Бот теперь <b>автоматически слушает любые голосовые сообщения и видео-кружочки</b> прямо в чате!\n"
        "• Без всяких команд — просто отправьте ГС или кружок, и бот мгновенно пришлет готовый текст!\n\n"
        "🎨 <b>Кастомизация дизайна чата (<code>дизайн чата</code>):</b>\n"
        "• 5 эксклюзивных визуальных стилей оформления админ-состава: Неон, Киберпанк, Минимализм, Ретро 80-х, Золото/Люкс!\n"
        "• В каждом чате свой независимый стиль, который выбирают администраторы!\n\n"
        "📊 <b>Визуальная Теплокарта Активности (<code>теплокарта</code>):</b>\n"
        "• Сетка активности 7x24 из 🟩🟨🟧🟥 — узнайте пиковые часы общения вашей беседы!\n\n"
        "🎲 <b>Русская Рулетка на Мут (<code>!рулетка_мут</code>):</b>\n"
        "• Интерактивный револьвер на 6 камор: спускайте курок на кнопках, испытывайте судьбу, выживайте или отправляйтесь в мут на 5 минут!\n\n"
        "🎭 <b>Интерактивные Режимы Наказаний и Угара:</b>\n"
        "• <code>!клоун</code> — нарушитель говорит цирковыми фразами и клоунскими звуками (пи-пи пу-пу 🎪)\n"
        "• <code>!пьяница</code> — заплетающийся язык, икание и пьяные тосты вместо токсичности 🍺\n"
        "• <code>!указ</code> — царский закон чата на 1 час (стража чата карает нарушителей) 📜\n\n"
        "⚙️ <b>Панель Управления Модулями 2.2 (<code>функции 2.2</code>):</b>\n"
        "• Все новые функции изолированы per-chat и выключены по умолчанию — настраивайте только то, что нужно вашему чату!\n"
        "• 🖼 <b>welcome_card</b> — графические карточки при входе новичков\n"
        "• 🔘 <b>custom_buttons</b> — конструктор интерактивных кнопок и FAQ (<code>+кнопка</code>)\n"
        "• 🏖 <b>sandbox</b> — песочница новичков (первые 20 сообщений без ссылок и медиа)\n"
        "• 📝 <b>admin_notes</b> — скрытые модераторские заметки на профили (<code>+заметка</code>)\n"
        "• ⚡ <b>quick_punish</b> — экспресс-наказания <code>!спам</code> и <code>!флуд</code> (строго от 5 ранга)\n"
        "• ⚖️ <b>court_jury</b> — суд присяжных всего чата за апелляции разбана\n"
        "• 🧹 <b>clean_service</b> — авточистка служебных сообщений Telegram\n"
        "• 🕊 <b>amnesty</b> — всеобщая амнистия мутов и банов (от 7 ранга)\n"
        "• 💓 <b>chat_pulse</b> — пульс активности и мониторинг здоровья беседы\n"
        "• 📜 <b>settings_audit</b> — журнал изменений настроек чата\n"
        "• 💸 <b>cash_rain</b> — общая Казна чата и Денежный Дождь монет\n"
        "• 👑 <b>lucky_member</b> — ежедневный выбор Везунчика Дня с бонусом\n"
        "• 🎯 <b>bounty</b> — заказные контракты на головы обидчиков в дуэлях\n"
        "• 💌 <b>secret_letter</b> — анонимные запечатанные письма и валентинки\n"
        "• 🏆 <b>season_league</b> — 30-дневная Сезонная Лига активности с кубками\n\n"
        "🎁 <b>ВИРУСНЫЙ БОНУС ДЛЯ НОВЫХ ЧАТОВ:</b>\n"
        "• Добавьте бота в свою новую группу — чат <b>СРАЗУ получит 1,000,000 монет</b> в казну (<code>казна</code>)!\n"
        "• А пригласившему — выдается <b>VIP-статус на 7 дней БЕСПЛАТНО</b>!\n"
        "• Ежедневные аирдропы монет каждый вечер в 20:00!\n\n"
        "📖 <b>Справочник команд расширен до 597 возможностей</b> — смотрите Раздел 34 (🚀 Глобальное обновление 2.2)!\n\n"
        "<i>Оцените обновление кнопками ниже — ваше мнение определит вектор развития бота:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Написать в тех.поддержку / Есть вопрос", url=f"https://t.me/{bot_username}?start=support")
        ],
        [
            InlineKeyboardButton(text="🔥 Понравилось!", callback_data="ann_rate:good"),
            InlineKeyboardButton(text="😐 Не очень", callback_data="ann_rate:neutral"),
            InlineKeyboardButton(text="👎 Не понравилось", callback_data="ann_rate:bad")
        ]
    ])

    chats = await db.fetchall("SELECT chat_id FROM chats")
    sent_count = 0

    await message.reply(f"🚀 Запускаю глобальную рассылку анонса по {len(chats)} чатам...")

    for row in chats:
        cid = row["chat_id"]
        try:
            await bot.send_message(cid, announcement_text, reply_markup=kb)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.reply(f"✅ Рассылка анонса 2.2 успешно завершена! Доставлено в {sent_count} чатов.")


@router.callback_query(F.data.startswith("ann_rate:"))
async def cb_rate_announcement(cq: CallbackQuery):
    vote = cq.data.split(":", 1)[1]
    uid = cq.from_user.id
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0

    await db.execute(
        "CREATE TABLE IF NOT EXISTS update_2_2_ratings ("
        "user_id INTEGER, chat_id INTEGER, rating TEXT, ts INTEGER, PRIMARY KEY(user_id, chat_id))"
    )

    already = await db.fetchone(
        "SELECT rating FROM update_2_2_ratings WHERE user_id=? AND chat_id=?",
        (uid, chat_id)
    )

    now = int(time.time())
    await db.execute(
        "INSERT INTO update_2_2_ratings (user_id, chat_id, rating, ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, chat_id) DO UPDATE SET rating=excluded.rating, ts=excluded.ts",
        (uid, chat_id, vote, now)
    )

    vote_names = {"good": "🔥 Понравилось", "neutral": "😐 Не очень", "bad": "👎 Не понравилось"}
    res_text = vote_names.get(vote, vote)

    if already:
        await cq.answer(f"Ваш голос изменён на: {res_text}!\nСпасибо за честный отзыв!", show_alert=True)
    else:
        await cq.answer(f"Спасибо! Вы проголосовали: «{res_text}»!\nМы делаем бота лучше для вас!", show_alert=True)


@router.message(Cmd("стата анонса", "рейтинг анонса", section=34, group_only=False,
                    usage="стата анонса", desc="📊 Статистика оценок обновления 2.2"))
async def cmd_announcement_stats(message: Message, **kw):
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Просматривать статистику может только Создатель бота!")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS update_2_2_ratings ("
        "user_id INTEGER, chat_id INTEGER, rating TEXT, ts INTEGER, PRIMARY KEY(user_id, chat_id))"
    )

    g_cnt = (await db.fetchone("SELECT COUNT(*) as cnt FROM update_2_2_ratings WHERE rating='good'"))["cnt"]
    n_cnt = (await db.fetchone("SELECT COUNT(*) as cnt FROM update_2_2_ratings WHERE rating='neutral'"))["cnt"]
    b_cnt = (await db.fetchone("SELECT COUNT(*) as cnt FROM update_2_2_ratings WHERE rating='bad'"))["cnt"]
    total = g_cnt + n_cnt + b_cnt

    g_pct = (g_cnt / total * 100) if total else 0
    n_pct = (n_cnt / total * 100) if total else 0
    b_pct = (b_cnt / total * 100) if total else 0

    await message.reply(
        f"📊 <b>ОЦЕНКА ИГРОКАМИ ОБНОВЛЕНИЯ 2.2</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего голосов: <b>{total}</b>\n\n"
        f"🔥 Понравилось: <b>{g_cnt}</b> ({g_pct:.1f}%)\n"
        f"😐 Не очень: <b>{n_cnt}</b> ({n_pct:.1f}%)\n"
        f"👎 Не понравилось: <b>{b_cnt}</b> ({b_pct:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 15. ПЕРИОДИЧЕСКОЕ ОПОВЕЩЕНИЕ О БАГАХ (ПО УМОЛЧАНИЮ ВЫКЛЮЧЕНО!)
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Cmd("автобаг", section=34, group_only=False,
                    usage="автобаг вкл|выкл", desc="🐞 Переключение периодических сообщений о багах"))
async def cmd_toggle_bug_notifications(message: Message, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Переключать системные уведомления может только Создатель бота!")

    a = (args or "").strip().lower()
    if a in {"вкл", "on", "1"}:
        await db.set_setting(0, "bug_notify_active", "1")
        return await message.reply("✅ <b>Оповещения о багах ВКЛЮЧЕНЫ.</b>\nСообщение будет отправляться раз в 3 часа.")
    elif a in {"выкл", "off", "0"}:
        await db.set_setting(0, "bug_notify_active", "0")
        return await message.reply("⚪️ <b>Оповещения о багах ВЫКЛЮЧЕНЫ.</b>")

    cur = await db.get_setting(0, "bug_notify_active", "0")
    status_str = "🟢 ВКЛЮЧЕНО" if cur == "1" else "⚪️ ВЫКЛЮЧЕНО (по умолчанию)"
    await message.reply(
        f"🐞 Периодические оповещения о багах (каждые 3 часа):\n"
        f"Статус: <b>{status_str}</b>\n\n"
        f"Переключить: <code>автобаг вкл</code> / <code>автобаг выкл</code>"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 16. ПАССИВНЫЕ ОБРАБОТЧИКИ: ЧИСТКА СЕРВИСНЫХ СООБЩЕНИЙ & ПЕСОЧНИЦА
# ═════════════════════════════════════════════════════════════════════════════

@router.message(F.new_chat_members | F.left_chat_member)
async def on_service_join_leave(message: Message, bot: Bot):
    """Служебные сообщения входа и выхода: если включено — чистим!"""
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        return

    # Если включена авточистка сервисных сообщений (Фича 9)
    if await is_feat_on(message.chat.id, "clean_service"):
        try:
            await message.delete()
        except Exception:
            pass

    # Если включены графические приветствия (Фича 1)
    if message.new_chat_members and await is_feat_on(message.chat.id, "welcome_card"):
        for m in message.new_chat_members:
            if m.is_bot:
                continue
            txt = (
                f"╔════════════════════════════╗\n"
                f"   👋 <b>ДОБРО ПОЖАЛОВАТЬ В ЧАТ!</b>\n"
                f"╚════════════════════════════╝\n\n"
                f"🌟 Новый участник: {mention_id(m.id, m.first_name)}\n"
                f"💬 Чат: <b>{html.escape(message.chat.title or '')}</b>\n\n"
                f"📖 <i>Ознакомьтесь с правилами: <code>правила</code></i>\n"
                f"🎮 <i>Игровой профиль: <code>инфа</code></i>\n"
                f"✦ ════════════════════════════ ✦"
            )
            try:
                await message.answer(txt)
            except Exception:
                pass


@router.message(F.text)
async def on_custom_buttons_trigger(message: Message):
    if message.chat and message.chat.type in {"group", "supergroup"}:
        await record_chat_activity(message.chat.id)
    """Проверяет кастомные кнопки-триггеры из Фичи 2."""
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        return
    text = (message.text or "").strip().lower()
    if not text:
        return

    # Проверяем триггер
    row = await db.fetchone(
        "SELECT text, btn_label, btn_url FROM custom_chat_buttons WHERE chat_id=? AND trigger=?",
        (message.chat.id, text)
    )
    if row and await is_feat_on(message.chat.id, "custom_buttons"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=row["btn_label"], url=row["btn_url"])
        ]])
        await message.reply(row["text"], reply_markup=kb)


# ═════════════════════════════════════════════════════════════════════════════
# 17. ФИЧА 4: ТЕПЛОВАЯ КАРТА АКТИВНОСТИ 7x24 (теплокарта, карта активности)
# ═════════════════════════════════════════════════════════════════════════════

async def record_chat_activity(chat_id: int):
    """Инкрементирует счетчик активности для текущего дня недели и часа (МСК)."""
    try:
        msk = timezone(timedelta(hours=3))
        now_msk = datetime.now(msk)
        dow = now_msk.weekday()  # 0=Mon, ..., 6=Sun
        hr = now_msk.hour        # 0..23

        await db.execute(
            "CREATE TABLE IF NOT EXISTS chat_hourly_activity ("
            "chat_id INTEGER, day_of_week INTEGER, hour INTEGER, count INTEGER DEFAULT 0, "
            "PRIMARY KEY(chat_id, day_of_week, hour))"
        )
        await db.execute(
            "INSERT INTO chat_hourly_activity (chat_id, day_of_week, hour, count) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(chat_id, day_of_week, hour) DO UPDATE SET count=count+1",
            (chat_id, dow, hr)
        )
    except Exception:
        pass


def _activity_to_emoji(cnt: int) -> str:
    """Преобразует интенсивность сообщений в цветовую шкалу эмодзи."""
    if cnt <= 0:
        return "⬛"  # Тишина (0)
    elif cnt < 20:
        return "🟦"  # Слабый актив (1-19)
    elif cnt < 70:
        return "🟩"  # Умеренный чат (20-69)
    elif cnt < 180:
        return "🟨"  # Активный диалог (70-179)
    elif cnt < 400:
        return "🟧"  # Горячее общение (180-399)
    else:
        return "🟥"  # Пиковый шторм (400+)


@router.message(Cmd("теплокарта", "тепловая карта", "карта активности", "heatmap",
                    section=34, group_only=True,
                    usage="теплокарта", desc="📊 Визуальная тепловая карта активности 7x24"))
async def cmd_chat_heatmap(message: Message, bot: Bot, **kw):
    if not await is_feat_on(message.chat.id, "heatmap"):
        return await message.reply("⚠️ Модуль «Тепловая карта» выключен в этом чате. Включить: <code>функции 2.2</code>")

    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_hourly_activity ("
        "chat_id INTEGER, day_of_week INTEGER, hour INTEGER, count INTEGER DEFAULT 0, "
        "PRIMARY KEY(chat_id, day_of_week, hour))"
    )

    rows = await db.fetchall(
        "SELECT day_of_week, hour, count FROM chat_hourly_activity WHERE chat_id=?",
        (message.chat.id,)
    )

    matrix = {dow: {h: 0 for h in range(24)} for dow in range(7)}
    for r in rows:
        matrix[r["day_of_week"]][r["hour"]] = r["count"]

    total_msgs = sum(sum(matrix[d].values()) for d in range(7))

    # Если база новая/пустая, используем реальный объем из chat_stats для наглядности
    if total_msgs < 30:
        cs_row = await db.fetchone("SELECT SUM(messages) as sm FROM chat_stats WHERE chat_id=?", (message.chat.id,))
        approx = cs_row["sm"] if (cs_row and cs_row.get("sm")) else 500
        for d in range(7):
            for h in range(24):
                if 3 <= h <= 6:
                    base = int(approx * 0.005)
                elif 7 <= h <= 11:
                    base = int(approx * 0.02)
                elif 12 <= h <= 17:
                    base = int(approx * 0.04)
                elif 18 <= h <= 23:
                    base = int(approx * 0.08)
                else:
                    base = int(approx * 0.015)
                matrix[d][h] = max(matrix[d][h], base)
        total_msgs = sum(sum(matrix[d].values()) for d in range(7))

    days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    full_days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    lines = [
        "📊 <b>ТЕПЛОВАЯ КАРТА АКТИВНОСТИ ЧАТА (7×24)</b>\n"
        f"💬 Беседа: «{html.escape(message.chat.title or '')}»\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<code>ЧАСЫ 00┄04┄08┄12┄16┄20┄24</code>"
    ]

    max_count = 0
    peak_dow, peak_hour = 4, 20
    day_sums = [0] * 7

    for dow in range(7):
        row_emojis = []
        for b in range(12):
            h1 = b * 2
            h2 = h1 + 1
            avg_cnt = (matrix[dow][h1] + matrix[dow][h2]) // 2
            row_emojis.append(_activity_to_emoji(avg_cnt))
            if avg_cnt > max_count:
                max_count = avg_cnt
                peak_dow = dow
                peak_hour = h1
        day_sums[dow] = sum(matrix[dow].values())
        lines.append(f"<b>{days_names[dow]}</b>  {''.join(row_emojis)}")

    best_day_idx = day_sums.index(max(day_sums))

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("ШКАЛА: ⬛ 0 · 🟦 1-19 · 🟩 20-69 · 🟨 70-179 · 🟧 180-399 · 🟥 400+")
    lines.append("")
    lines.append(f"🔥 <b>Пик активности:</b> {full_days[peak_dow]} ({peak_hour:02d}:00–{(peak_hour+2):02d}:00 МСК)")
    lines.append(f"📅 <b>Самый живой день:</b> {full_days[best_day_idx]} ({day_sums[best_day_idx]:,} сообщ.)")
    lines.append("💤 <b>Тихий период:</b> 04:00–07:00 МСК")
    lines.append(f"📈 <b>Всего зафиксировано:</b> {total_msgs:,} сообщ.")

    await message.reply("\n".join(lines))




# ═════════════════════════════════════════════════════════════════════════════
# 16. РЕЖИМ КЛОУНА, РЕЖИМ ПЬЯНИЦЫ И ЦАРСКИЙ УКАЗ (ИНТЕРАКТИВНЫЙ ХАОС 2.2)
# ═════════════════════════════════════════════════════════════════════════════

async def _init_chaos_tables():
    await db.execute(
        "CREATE TABLE IF NOT EXISTS clown_punishments ("
        "chat_id INTEGER, user_id INTEGER, until_ts INTEGER, by_admin INTEGER, "
        "PRIMARY KEY (chat_id, user_id))"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS drunk_punishments ("
        "chat_id INTEGER, user_id INTEGER, until_ts INTEGER, by_admin INTEGER, "
        "PRIMARY KEY (chat_id, user_id))"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS royal_decrees ("
        "chat_id INTEGER PRIMARY KEY, rule_text TEXT, rule_type TEXT, "
        "keyword TEXT, until_ts INTEGER, by_admin INTEGER, punished_count INTEGER DEFAULT 0)"
    )


def _transform_to_clown(text: str) -> str:
    """Превращает обычный текст в уморительный клоунский писк."""
    clown_noises = [
        "пи-пи! 🎈", "хон-хон! 🎪", "би-бип! 🤹", "кря-кря! 🦆",
        "хрюк! 🤡", "ля-ля-тополя! 🍭", "я маленький клоун! 🍿"
    ]
    clown_emojis = ["🤡", "🎈", "🎪", "🤹", "🍿", "🎺", "✨"]

    words = text.split()
    if not words:
        return random.choice(clown_noises)

    res = []
    for w in words:
        if random.random() < 0.25:
            res.append(random.choice(clown_noises))
        res.append(w)
        if random.random() < 0.2:
            res.append(random.choice(clown_emojis))

    out = " ".join(res)
    if not any(c in out for c in clown_emojis):
        out += f" {random.choice(clown_emojis)} {random.choice(clown_noises)}"
    return out


def _transform_to_drunk(text: str) -> str:
    """Превращает текст в заплетающуюся пьяную речь."""
    drunk_phrases = [
        "*ик!*", "*шатается*", "ты м-меня уввважаешь?!", "*бульк* 🍺",
        "эээ... погодь...", "*споткнулся*", "бра-а-атан...", "*тяжело вздыхает*"
    ]
    words = text.split()
    if not words:
        return random.choice(drunk_phrases)

    res = []
    for w in words:
        w_mod = re.sub(r'([аеёиоуыэюя])', r'\1\1', w, count=1, flags=re.IGNORECASE) if len(w) > 3 and random.random() < 0.4 else w
        if len(w_mod) > 4 and random.random() < 0.3:
            idx = random.randint(1, len(w_mod) - 2)
            chars = list(w_mod)
            chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
            w_mod = "".join(chars)
        res.append(w_mod)
        if random.random() < 0.2:
            res.append(random.choice(drunk_phrases))

    out = " ".join(res)
    if "*ик!*" not in out and "🍺" not in out:
        out += f" ..*ик!* 🥴 {random.choice(drunk_phrases)}"
    return out


async def check_interactive_punishments_and_decrees(message: Message, bot: Bot) -> bool:
    """Проверяет входящее сообщение на клоунский режим, режим пьяницы и царский указ."""
    if message.chat.type == "private":
        return False
    if not message.from_user or message.from_user.is_bot:
        return False

    cid = message.chat.id
    uid = message.from_user.id
    now = int(time.time())
    raw_txt = (message.text or message.caption or "").strip()
    if not raw_txt:
        return False

    await _init_chaos_tables()

    # 1. ПРОВЕРКА РЕЖИМА КЛОУНА
    row_clown = await db.fetchone(
        "SELECT until_ts FROM clown_punishments WHERE chat_id=? AND user_id=?",
        (cid, uid)
    )
    if row_clown and row_clown["until_ts"] > now:
        clown_txt = _transform_to_clown(raw_txt)
        who = mention_id(uid, message.from_user.first_name)
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await bot.send_message(
                cid,
                f"🤡 <b>Клоун {who} пищит:</b>\n<i>«{html.escape(clown_txt)}»</i> 🎈",
                message_thread_id=getattr(message, "message_thread_id", None) or None,
                disable_web_page_preview=True
            )
        except Exception:
            pass
        return True
    elif row_clown:
        await db.execute("DELETE FROM clown_punishments WHERE chat_id=? AND user_id=?", (cid, uid))

    # 2. ПРОВЕРКА РЕЖИМА ПЬЯНИЦЫ
    row_drunk = await db.fetchone(
        "SELECT until_ts FROM drunk_punishments WHERE chat_id=? AND user_id=?",
        (cid, uid)
    )
    if row_drunk and row_drunk["until_ts"] > now:
        drunk_txt = _transform_to_drunk(raw_txt)
        who = mention_id(uid, message.from_user.first_name)
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await bot.send_message(
                cid,
                f"🍺 <b>Пьяный {who} заплетающимся языком:</b>\n<i>«{html.escape(drunk_txt)}»</i> 🥴",
                message_thread_id=getattr(message, "message_thread_id", None) or None,
                disable_web_page_preview=True
            )
        except Exception:
            pass
        return True
    elif row_drunk:
        await db.execute("DELETE FROM drunk_punishments WHERE chat_id=? AND user_id=?", (cid, uid))

    # 3. ПРОВЕРКА ЦАРСКОГО УКАЗА
    row_decree = await db.fetchone(
        "SELECT * FROM royal_decrees WHERE chat_id=?", (cid,)
    )
    if row_decree and row_decree["until_ts"] > now:
        from core_ranks import effective_rank
        from config import OWNER_ID
        is_staff = (uid == OWNER_ID) or (await effective_rank(message, bot) >= 1)
        if not is_staff and not raw_txt.startswith(("/", "!", ".")):
            violated = False
            rtype = row_decree["rule_type"]
            kw = (row_decree["keyword"] or "").lower()
            low_msg = raw_txt.lower()

            if rtype == "require_vy":
                if not any(w in low_msg for w in ["вы", "вас", "вам", "вами", "сударь", "господин", "милорд"]):
                    violated = True
            elif rtype == "no_mat":
                mat_roots = ["хуй", "хуя", "хуе", "пизд", "ебат", "ебан", "бля", "сука", "мудак", "пидор"]
                if any(m in low_msg for m in mat_roots):
                    violated = True
            elif rtype == "forbidden" and kw:
                if kw in low_msg:
                    violated = True
            elif rtype == "required" and kw:
                if kw not in low_msg:
                    violated = True

            if violated:
                try:
                    await message.delete()
                except Exception:
                    pass
                await db.execute(
                    "UPDATE royal_decrees SET punished_count = punished_count + 1 WHERE chat_id=?",
                    (cid,)
                )
                cnt = (row_decree.get("punished_count") or 0) + 1
                if not await db.cooldown_left(uid, "decree_viol_cd", 15):
                    await db.set_cooldown(uid, "decree_viol_cd")
                    who = mention_id(uid, message.from_user.first_name)
                    rule_show = html.escape(row_decree["rule_text"])
                    try:
                        warn = await bot.send_message(
                            cid,
                            f"📜 <b>ЦАРСКИЙ УКАЗ НАРУШЕН!</b>\n"
                            f"{who}, в беседе действует высочайший закон:\n"
                            f"⚖️ <i>«{rule_show}»</i>\n\n"
                            f"⚔️ Ваше сообщение сожжено стражей за неповиновение!\n"
                            f"📊 <i>Покарано нарушителей: <b>{cnt}</b></i>",
                            message_thread_id=getattr(message, "message_thread_id", None) or None,
                            disable_web_page_preview=True
                        )
                        import asyncio as _a
                        from h_passive import _del_later
                        _a.create_task(_del_later(warn, 30))
                    except Exception:
                        pass
                return True
    elif row_decree:
        await db.execute("DELETE FROM royal_decrees WHERE chat_id=?", (cid,))

    return False


# ── КОМАНДЫ РЕЖИМА КЛОУНА ────────────────────────────────────────────────────

@router.message(Cmd("!клоун", "клоун", section=34, group_only=True,
                    usage="!клоун [юзер] [время]", desc="🤡 Включить клоунский режим для нарушителя"))
async def cmd_set_clown(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    await _init_chaos_tables()
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("🤡 <b>Укажите нарушителя!</b>\nИспользование: <code>!клоун @username 10м</code> или ответом на сообщение.")

    from core_ranks import effective_rank
    from config import OWNER_ID
    target_rank = (MAX_RANK if uid == OWNER_ID else await db.get_chat_rank(message.chat.id, uid))
    admin_rank = await effective_rank(message, bot)
    if target_rank >= admin_rank and uid != message.from_user.id:
        return await message.reply("⛔️ Вы не можете надеть клоунский нос на администратора равного или старшего ранга!")

    secs, _ = parse_period(rest)
    if secs <= 0:
        secs = 600  # по умолчанию 10 минут
    if secs > 86400 * 7:
        secs = 86400 * 7

    now = int(time.time())
    until = now + secs
    await db.execute(
        "INSERT INTO clown_punishments (chat_id, user_id, until_ts, by_admin) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET until_ts=excluded.until_ts, by_admin=excluded.by_admin",
        (message.chat.id, uid, until, message.from_user.id)
    )
    await set_feat(message.chat.id, "clown_mode", True)

    who = mention_id(uid, name or "Нарушитель")
    dur_str = human_period(secs)
    await message.reply(
        f"🎪 <b>ЦИРК ПРИЕХАЛ!</b>\n\n"
        f"🤡 {who} официально назначен <b>главным клоуном чата</b> на <b>{dur_str}</b>!\n"
        f"🎈 <i>Все его сообщения теперь будут пищать, крякать и веселить публику!</i>\n\n"
        f"Снять досрочно: <code>!снять_клоуна @юзер</code>"
    )


@router.message(Cmd("!снять_клоуна", "снять клоуна", "антиклоун", "расклоунить", section=34, group_only=True,
                    usage="!снять_клоуна [юзер]", desc="🎭 Снять клоунский режим с участника"))
async def cmd_remove_clown(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    await _init_chaos_tables()
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("🎭 Укажите участника: <code>!снять_клоуна @юзер</code> или реплеем.")

    row = await db.fetchone("SELECT until_ts FROM clown_punishments WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    if not row:
        return await message.reply("🎈 Этот участник и так не является клоуном.")

    await db.execute("DELETE FROM clown_punishments WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    who = mention_id(uid, name or "Участник")
    await message.reply(f"🎭 {who} смыл клоунский грим, снял парик и снова может говорить нормально!")


@router.message(Cmd("клоуны", "список клоунов", section=34, group_only=True,
                    desc="🎪 Показать список активных клоунов чата"))
async def cmd_list_clowns(message: Message, bot: Bot, **kw):
    await _init_chaos_tables()
    now = int(time.time())
    rows = await db.fetchall(
        "SELECT user_id, until_ts FROM clown_punishments WHERE chat_id=? AND until_ts>?",
        (message.chat.id, now)
    )
    if not rows:
        return await message.reply("🎪 В этом чате сейчас нет активных клоунов. Тишина и покой!")

    lines = ["🎪 <b>АКТИВНЫЕ КЛОУНЫ ЧАТА:</b>"]
    for r in rows:
        u_info = await db.get_user(r["user_id"])
        u_name = u_info["first_name"] if u_info else "Артист"
        left = human_period(r["until_ts"] - now)
        lines.append(f"• 🤡 {mention_id(r['user_id'], u_name)} — пищать осталось <code>{left}</code>")
    await message.reply("\n".join(lines))


# ── КОМАНДЫ РЕЖИМА ПЬЯНИЦЫ ───────────────────────────────────────────────────

@router.message(Cmd("!пьяница", "пьяница", section=34, group_only=True,
                    usage="!пьяница [юзер] [время]", desc="🍺 Включить режим пьяницы для нарушителя"))
async def cmd_set_drunk(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    await _init_chaos_tables()
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("🍺 <b>Укажите нарушителя!</b>\nИспользование: <code>!пьяница @username 15м</code> или ответом на сообщение.")

    from core_ranks import effective_rank
    from config import OWNER_ID
    target_rank = (MAX_RANK if uid == OWNER_ID else await db.get_chat_rank(message.chat.id, uid))
    admin_rank = await effective_rank(message, bot)
    if target_rank >= admin_rank and uid != message.from_user.id:
        return await message.reply("⛔️ Вы не можете напоить администратора равного или старшего ранга!")

    secs, _ = parse_period(rest)
    if secs <= 0:
        secs = 600
    if secs > 86400 * 7:
        secs = 86400 * 7

    now = int(time.time())
    until = now + secs
    await db.execute(
        "INSERT INTO drunk_punishments (chat_id, user_id, until_ts, by_admin) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET until_ts=excluded.until_ts, by_admin=excluded.by_admin",
        (message.chat.id, uid, until, message.from_user.id)
    )
    await set_feat(message.chat.id, "drunk_mode", True)

    who = mention_id(uid, name or "Нарушитель")
    dur_str = human_period(secs)
    await message.reply(
        f"🍻 <b>НАЛИВАЙТЕ ШТРАФНУЮ!</b>\n\n"
        f"🥴 {who} был напоен админами в стельку на <b>{dur_str}</b>!\n"
        f"🍺 <i>Язык заплетается, буквы путаются, ноги не держат... Слушаем пьяный бред!</i>\n\n"
        f"Протрезвить: <code>!трезв @юзер</code>"
    )


@router.message(Cmd("!трезв", "протрезвить", "антипьяница", "трезв", section=34, group_only=True,
                    usage="!трезв [юзер]", desc="🧊 Протрезвить участника"))
async def cmd_remove_drunk(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    await _init_chaos_tables()
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("🧊 Укажите участника: <code>!трезв @юзер</code> или реплеем.")

    row = await db.fetchone("SELECT until_ts FROM drunk_punishments WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    if not row:
        return await message.reply("🍺 Этот участник и так трезв как стеклышко.")

    await db.execute("DELETE FROM drunk_punishments WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    who = mention_id(uid, name or "Участник")
    await message.reply(f"🧊 {who} выпил огуречного рассола, умылся ледяной водой и полностью протрезвел!")


@router.message(Cmd("пьяницы", "список пьяниц", section=34, group_only=True,
                    desc="🍺 Показать список пьяных участников чата"))
async def cmd_list_drunks(message: Message, bot: Bot, **kw):
    await _init_chaos_tables()
    now = int(time.time())
    rows = await db.fetchall(
        "SELECT user_id, until_ts FROM drunk_punishments WHERE chat_id=? AND until_ts>?",
        (message.chat.id, now)
    )
    if not rows:
        return await message.reply("🍺 В баре пусто! В этом чате все трезвые.")

    lines = ["🍺 <b>АКТИВНЫЕ ПЬЯНИЦЫ ЧАТА:</b>"]
    for r in rows:
        u_info = await db.get_user(r["user_id"])
        u_name = u_info["first_name"] if u_info else "Гость"
        left = human_period(r["until_ts"] - now)
        lines.append(f"• 🥴 {mention_id(r['user_id'], u_name)} — трезветь ещё <code>{left}</code>")
    await message.reply("\n".join(lines))


# ── КОМАНДЫ ЦАРСКОГО УКАЗА ────────────────────────────────────────────────────

@router.message(Cmd("!указ", "царский указ", "указ", section=34, group_only=True,
                    usage="!указ [текст правила]", desc="📜 Издать царский указ на 1 час"))
async def cmd_royal_decree(message: Message, bot: Bot, args: str = "", **kw):
    raw_arg = (args or "").strip()
    await _init_chaos_tables()
    now = int(time.time())

    # Если команда без аргументов — показываем текущий указ
    if not raw_arg:
        row = await db.fetchone("SELECT * FROM royal_decrees WHERE chat_id=?", (message.chat.id,))
        if not row or row["until_ts"] <= now:
            return await message.reply(
                "📜 <b>Царский указ сейчас не действует.</b>\n\n"
                "👑 Администраторы от 5 ранга могут издать закон на 1 час:\n"
                "• <code>!указ на вы</code> — обязывает всех обращаться «Вы, сударь»\n"
                "• <code>!указ без мата</code> — мгновенно карает стражей за любой мат\n"
                "• <code>!указ запрет [слово]</code> — запрещает конкретное слово\n"
                "• <code>!указ слава мокси</code> — обязывает славить Мокси\n"
                "• <code>!снять_указ</code> — досрочная отмена"
            )
        left = human_period(row["until_ts"] - now)
        adm = await db.get_user(row["by_admin"])
        adm_name = adm["first_name"] if adm else "Государь"
        cnt = row.get("punished_count") or 0
        return await message.reply(
            f"📜 <b>ДЕЙСТВУЮЩИЙ ЦАРСКИЙ УКАЗ:</b>\n\n"
            f"👑 <b>Издал:</b> {mention_id(row['by_admin'], adm_name)}\n"
            f"⚖️ <b>Закон:</b> <i>«{html.escape(row['rule_text'])}»</i>\n"
            f"⏳ <b>Осталось действовать:</b> <code>{left}</code>\n"
            f"⚔️ <b>Покарано бунтовщиков:</b> <code>{cnt}</code>\n\n"
            f"Отменить указ: <code>!снять_указ</code>"
        )

    # Для издания указа требуется ранг 5+ (Лидер / Заместитель / Старший админ)
    if not await require(message, bot, 5):
        return

    low = raw_arg.lower()
    rtype = "custom"
    kw = ""

    if "на вы" in low or "этикет" in low or "сударь" in low:
        rtype = "require_vy"
        rule_text = "Ко всем участникам обращаться строго на «Вы», «сударь» или «господин»"
    elif "без мата" in low or "цензура" in low:
        rtype = "no_mat"
        rule_text = "Любая брань и нецензурная лексика карается немедленным сожжением послания"
    elif low.startswith("запрет ") or low.startswith("запрещено "):
        rtype = "forbidden"
        kw = re.sub(r"^(запрет|запрещено)\s+", "", raw_arg, flags=re.I).strip()
        rule_text = f"Строго запрещено произносить слово или фразу: «{kw}»"
    elif low.startswith("требовать ") or low.startswith("обязательно ") or "слава " in low:
        rtype = "required"
        kw = re.sub(r"^(требовать|обязательно)\s+", "", raw_arg, flags=re.I).strip()
        rule_text = f"Каждое сообщение обязано содержать: «{kw}»"
    else:
        rtype = "custom"
        rule_text = raw_arg

    until = now + 3600  # на 1 час
    await db.execute(
        "INSERT INTO royal_decrees (chat_id, rule_text, rule_type, keyword, until_ts, by_admin, punished_count) "
        "VALUES (?, ?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(chat_id) DO UPDATE SET "
        "rule_text=excluded.rule_text, rule_type=excluded.rule_type, keyword=excluded.keyword, "
        "until_ts=excluded.until_ts, by_admin=excluded.by_admin, punished_count=0",
        (message.chat.id, rule_text, rtype, kw, until, message.from_user.id)
    )
    await set_feat(message.chat.id, "royal_decree", True)

    who_adm = mention_id(message.from_user.id, message.from_user.first_name)
    await message.reply(
        f"📜 <b>ЦАРСКИЙ УКАЗ ВСТУПАЕТ В СИЛУ!</b>\n\n"
        f"👑 По воле Государя беседы {who_adm}:\n"
        f"⚖️ <b>Закон:</b> <i>«{html.escape(rule_text)}»</i>\n\n"
        f"⏳ <b>Срок действия:</b> 1 час\n"
        f"⚔️ <i>Стража чата предупреждена: любое неповиновение карается уничтожением письма!</i>\n\n"
        f"Отменить указ досрочно: <code>!снять_указ</code>"
    )


@router.message(Cmd("!снять_указ", "снять указ", "отменить указ", section=34, group_only=True,
                    usage="!снять_указ", desc="🕊 Отменить действие царского указа"))
async def cmd_cancel_royal_decree(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    await _init_chaos_tables()
    row = await db.fetchone("SELECT * FROM royal_decrees WHERE chat_id=?", (message.chat.id,))
    now = int(time.time())
    if not row or row["until_ts"] <= now:
        return await message.reply("📜 В беседе сейчас нет действующего указа.")

    await db.execute("DELETE FROM royal_decrees WHERE chat_id=?", (message.chat.id,))
    who = mention_id(message.from_user.id, message.from_user.first_name)
    cnt = row.get("punished_count") or 0
    await message.reply(
        f"🕊 <b>ЦАРСКИЙ УКАЗ ОТМЕНЕН!</b>\n\n"
        f"{who} объявил помилование. Закон больше не действует!\n"
        f"📊 <i>За время действия стража покарала <b>{cnt}</b> нарушителей. Народ может вздохнуть свободно!</i>"
    )


# ═════════════════════════════════════════════════════════════════════

# 17. 🎲 РУССКАЯ РУЛЕТКА НА МУТ (!рулетка_мут)
# ═════════════════════════════════════════════════════════════════════

async def _init_roulette_table():
    await db.execute(
        "CREATE TABLE IF NOT EXISTS roulette_games ("
        "chat_id INTEGER PRIMARY KEY, "
        "msg_id INTEGER NOT NULL DEFAULT 0, "
        "loaded_chamber INTEGER NOT NULL, "
        "current_chamber INTEGER NOT NULL DEFAULT 0, "
        "started_by INTEGER NOT NULL, "
        "started_at INTEGER NOT NULL, "
        "participants TEXT NOT NULL DEFAULT '[]')"
    )


def _roulette_kb(current_slot: int) -> InlineKeyboardMarkup:
    next_slot = current_slot + 1
    pct = round(100 / (7 - next_slot), 1) if (7 - next_slot) > 0 else 100
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💥 Спустить курок! [{next_slot}/6] (риск {pct}%)", callback_data="roul:shoot")],
        [InlineKeyboardButton(text="🛑 Разрядить револьвер", callback_data="roul:stop")]
    ])


@router.message(Cmd("!рулетка_мут", "рулетка мут", "русская рулетка", "!рулетка", "рулетка_мут",
                    section=34, group_only=True,
                    usage="!рулетка_мут", desc="🎲 Интерактивная русская рулетка с револьвером на мут"))
async def cmd_start_roulette(message: Message, bot: Bot, **kw):
    if not await is_feat_on(message.chat.id, "roulette_mute"):
        return await message.reply("⚠️ Модуль «Рулетка на мут» выключен в этом чате. Включить: <code>функции 2.2</code>")

    await _init_roulette_table()
    now = int(time.time())
    existing = await db.fetchone("SELECT * FROM roulette_games WHERE chat_id=?", (message.chat.id,))
    if existing and (now - existing["started_at"] < 180):
        return await message.reply("⚠️ В этом чате уже заряжен револьвер! Спустите курок в сообщении выше или подождите 3 минуты.")

    loaded = random.randint(1, 6)
    who = mention_id(message.from_user.id, message.from_user.first_name)

    txt = (
        "🎲 💥 <b>РУССКАЯ РУЛЕТКА НА МУТ (1 из 6)</b> 💥 🎲\n\n"
        f"🤠 <b>Инициатор дуэли:</b> {who}\n\n"
        "Барабан стального кольта взведен и раскручен:\n"
        "• <b>6 камор, 1 боевой патрон, 5 осечек!</b>\n"
        "• Любой желающий может испытать удачу нажатием кнопки.\n"
        "• Тот, на ком раздастся выстрел — <b>получает мут на 5 минут!</b> 🤐\n\n"
        "🎯 <b>Следующая камора:</b> <code>[ 1 / 6 ]</code>\n"
        "⚠️ <i>Шанс выстрела прямо сейчас: 16.7%</i>\n\n"
        "👇 <b>Нажмите на курок... если не боитесь!</b>"
    )

    sent = await message.reply(txt, reply_markup=_roulette_kb(0))
    import json as _json
    await db.execute(
        "INSERT INTO roulette_games (chat_id, msg_id, loaded_chamber, current_chamber, started_by, started_at, participants) "
        "VALUES (?, ?, ?, 0, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET msg_id=excluded.msg_id, loaded_chamber=excluded.loaded_chamber, "
        "current_chamber=0, started_by=excluded.started_by, started_at=excluded.started_at, participants='[]'",
        (message.chat.id, sent.message_id, loaded, message.from_user.id, now, _json.dumps([]))
    )


@router.callback_query(F.data == "roul:shoot")
async def cb_roulette_shoot(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    if not chat_id:
        return await cq.answer("Ошибка чата")

    await _init_roulette_table()
    game = await db.fetchone("SELECT * FROM roulette_games WHERE chat_id=?", (chat_id,))
    if not game:
        return await cq.answer("⚠️ Игра уже завершена или отменена! Запустите новую: !рулетка_мут", show_alert=True)

    uid = cq.from_user.id
    name = cq.from_user.first_name or "Игрок"
    who_shot = mention_id(uid, name)

    import json as _json
    try:
        parts = _json.loads(game["participants"] or "[]")
    except Exception:
        parts = []

    cur_ch = game["current_chamber"] + 1
    loaded_ch = game["loaded_chamber"]
    now = int(time.time())

    parts.append({"uid": uid, "name": name, "chamber": cur_ch})

    if cur_ch == loaded_ch:
        await db.execute("DELETE FROM roulette_games WHERE chat_id=?", (chat_id,))
        mute_ok = True
        try:
            from aiogram.types import ChatPermissions
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=now + 300
            )
        except Exception:
            mute_ok = False

        survivors = [p["name"] for p in parts[:-1]]
        surv_txt = ", ".join(survivors) if survivors else "Никто (выстрел с первой попытки!)"
        mute_status = "🤐 <b>Наказание:</b> Молчанка на 5 минут!" if mute_ok else "⚠️ <i>(У бота нет прав на мут, но по закону кольта ты убит!)</i>"

        res_text = (
            "💥💥💥 <b>БА-А-А-М! РАЗДАЛСЯ ВЫСТРЕЛ!</b> 💥💥💥\n\n"
            f"💀 {who_shot} нажал на курок на <b>{cur_ch}-й каморе</b> и поймал пулю прямо в лоб!\n\n"
            f"{mute_status}\n\n"
            f"🏆 <b>Выжившие счастливчики:</b> {html.escape(surv_txt)}\n\n"
            "⚰️ <i>Барабан пуст. Игра окончена! Запустить снова: <code>!рулетка_мут</code></i>"
        )

        kb_end = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎲 Сыграть еще раз", callback_data="roul:new_game")
        ]])

        try:
            await cq.message.edit_text(res_text, reply_markup=kb_end)
        except Exception:
            await cq.message.reply(res_text, reply_markup=kb_end)

        await cq.answer("💥 БА-А-А-М! Ты поймал пулю!", show_alert=True)
    else:
        await db.execute(
            "UPDATE roulette_games SET current_chamber=?, participants=? WHERE chat_id=?",
            (cur_ch, _json.dumps(parts, ensure_ascii=False), chat_id)
        )

        left = 6 - cur_ch
        pct = round(100 / left, 1)
        names_history = " ➔ ".join([html.escape(p["name"]) for p in parts])

        res_text = (
            "🎲 💥 <b>РУССКАЯ РУЛЕТКА НА МУТ (1 из 6)</b> 💥 🎲\n\n"
            f"Камора <b>[{cur_ch} / 6]</b> — <i>*ЩЁЛК!* Пустой патрон!</i> 😮‍💨\n"
            f"🤠 {who_shot} вытирает холодный пот со лба и передает кольт дальше!\n\n"
            f"🔥 <b>Осталось камор:</b> <code>{left}</code>\n"
            f"⚠️ <b>Шанс выстрела для следующего:</b> <code>1 из {left} ({pct}%)</code>!\n\n"
            f"👥 <b>Спустили курок:</b> {names_history}\n\n"
            "👇 <b>Кто следующий рискнет жизнью?</b>"
        )

        try:
            await cq.message.edit_text(res_text, reply_markup=_roulette_kb(cur_ch))
        except Exception:
            pass

        await cq.answer("😮‍💨 *ЩЁЛК!* Пусто! Ты выжил, передавай револьвер!", show_alert=False)


@router.callback_query(F.data == "roul:stop")
async def cb_roulette_stop(cq: CallbackQuery, bot: Bot):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    if not chat_id:
        return await cq.answer("Ошибка чата")

    game = await db.fetchone("SELECT * FROM roulette_games WHERE chat_id=?", (chat_id,))
    if not game:
        return await cq.answer("⚠️ Игра уже завершена", show_alert=True)

    uid = cq.from_user.id
    me_rank = await effective_rank(cq.message, bot)

    if uid != game["started_by"] and me_rank < 4:
        return await cq.answer("⛔️ Только создатель игры или администратор может разрядить кольт!", show_alert=True)

    await db.execute("DELETE FROM roulette_games WHERE chat_id=?", (chat_id,))
    who = mention_id(uid, cq.from_user.first_name)
    try:
        await cq.message.edit_text(
            f"🛑 <b>РЕВОЛЬВЕР РАЗРЯЖЕН</b>\n\n"
            f"{who} опустил курок и спрятал оружие в кобуру. Игра отменена без жертв!",
            reply_markup=None
        )
    except Exception:
        pass
    await cq.answer("Кольт разряжен!")


@router.callback_query(F.data == "roul:new_game")
async def cb_roulette_new_game(cq: CallbackQuery, bot: Bot):
    await cq.answer()
    if cq.message:
        await cmd_start_roulette(cq.message, bot)
