"""Разделы 3,4,6,7,8,9,10,11,12,28,32: анкета, статистика, настройки чата,
триггеры, доступ команд, сетка, темы, голосования, антиспам, инлайн, интеграция."""
from __future__ import annotations

import asyncio
import html
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message)

import db
import core_members as members
from core_ranks import effective_rank, rank_label, rank_name, require
from core_registry import REGISTRY, Cmd, find_commands
from core_resolve import human_period, parse_period, resolve_target
from utils import level_of, mention, mention_id, money

router = Router(name="chatset")
(S_TRIG, S_ACCESS, S_CHAT, S_NET, S_FORM, S_STAT,
 S_TOPIC, S_VOTE, S_SPAM, S_INLINE, S_TG) = (3, 4, 6, 7, 8, 9, 10, 11, 12, 28, 32)


# ================= 8. АНКЕТА =================
FIELDS = {"о себе": "about", "город": "city", "возраст": "age",
          "др": "birthday", "днюха": "birthday", "хобби": "hobby", "контакт": "contact"}



@router.message(Cmd("установить", "заполнить", section=S_FORM,
                    usage="установить город Москва", desc="Заполнить поле анкеты"))
async def form_set(message: Message, args: str = "", **kw):
    a = (args or "").strip()
    for label in sorted(FIELDS, key=len, reverse=True):
        if a.lower().startswith(label):
            val = a[len(label):].strip()
            if not val:
                return await message.reply(f"Укажите значение: <code>установить {label} ...</code>")
            col = FIELDS[label]
            await db.execute("INSERT INTO profiles (user_id) VALUES (?) "
                             "ON CONFLICT(user_id) DO NOTHING", (message.from_user.id,))
            await db.execute(f"UPDATE profiles SET {col}=? WHERE user_id=?",
                             (val, message.from_user.id))
            return await message.reply(f"✅ {label.capitalize()}: <b>{html.escape(val)}</b>")
    await message.reply("Доступные поля: " + ", ".join(FIELDS) +
                        "\nПример: <code>установить город Москва</code>")


# Команды ников («ник», «+ник», «-ник», «никлист») живут в handlers/userinfo.py —
# там они умеют брать ник из описания и синхронизировать его обратно.


@router.message(Cmd("ид", "id", "айди", section=S_FORM, usage="ид {ссылка}",
                    desc="Узнать ID пользователя и чата"))
async def form_id(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    extra = f"\n👤 {html.escape(str(name))}: <code>{uid}</code>" if uid else ""
    await message.reply(f"🆔 Ваш ID: <code>{message.from_user.id}</code>\n"
                        f"💬 Чат: <code>{message.chat.id}</code>{extra}")


# ================= 9. СТАТИСТИКА =================
@router.message(Cmd("стата", "статистика", "моя стата", "stats", section=S_STAT, usage="стата",
                    desc="Статистика активности"))
async def stat_me(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
    row = await db.fetchone("SELECT messages, xp, last_seen FROM chat_stats "
                            "WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    u = await db.get_user(uid)
    pos = await db.fetchone(
        "SELECT COUNT(*)+1 p FROM chat_stats WHERE chat_id=? AND messages > "
        "(SELECT COALESCE(messages,0) FROM chat_stats WHERE chat_id=? AND user_id=?)",
        (message.chat.id, message.chat.id, uid))
    lvl, title, *_ = level_of(u["xp"])
    seen = time.strftime("%d.%m %H:%M", time.localtime(row["last_seen"])) if row else "—"
    await message.reply(
        f"📊 <b>Статистика</b> {mention_id(uid, name)}\n"
        f"💬 Сообщений в чате: <b>{row['messages'] if row else 0}</b>\n"
        f"🏅 Место в чате: <b>{pos['p']}</b>\n"
        f"📈 Уровень: <b>{lvl}</b> ({title}), XP {u['xp']}\n"
        f"🕒 Последняя активность: {seen}")


@router.message(Cmd("топ чата", "топчата", "актив", "топ актив", section=S_STAT, group_only=True,
                    usage="топ чата", desc="Топ активных участников"))
async def stat_top(message: Message, **kw):
    rows = await db.fetchall(
        "SELECT s.user_id, s.messages, u.first_name FROM chat_stats s "
        "LEFT JOIN users u ON u.user_id=s.user_id WHERE s.chat_id=? "
        "ORDER BY s.messages DESC LIMIT 10", (message.chat.id,))
    if not rows:
        return await message.reply("Статистика пока пуста.")
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    lines = [f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — {r['messages']}"
             for i, r in enumerate(rows)]
    await message.reply("💬 <b>Топ активности чата</b>\n" + "\n".join(lines))


@router.message(Cmd("топ уровней", "топлвл", "топ лвл", section=S_STAT, usage="топ уровней",
                    desc="Топ по уровням"))
async def stat_top_lvl(message: Message, **kw):
    rows = await db.fetchall("SELECT user_id, first_name, xp FROM users ORDER BY xp DESC LIMIT 10")
    lines = []
    for i, r in enumerate(rows):
        lvl, title, *_ = level_of(r["xp"])
        lines.append(f"{i+1}. {mention_id(r['user_id'], r['first_name'])} — {lvl} ур. ({title})")
    await message.reply("📈 <b>Топ уровней</b>\n" + ("\n".join(lines) or "пусто"))


@router.message(Cmd("инфо чата", "чат", "информация", section=S_STAT, group_only=True, usage="инфо чата",
                    desc="Информация о чате"))
async def stat_chat(message: Message, bot: Bot, **kw):
    try:
        cnt = await bot.get_chat_member_count(message.chat.id)
    except Exception:
        cnt = "?"
    row = await db.fetchone("SELECT COUNT(*) c, SUM(messages) m FROM chat_stats WHERE chat_id=?",
                            (message.chat.id,))
    mods = await db.fetchone("SELECT COUNT(*) c FROM ranks WHERE chat_id=? AND rank>0",
                             (message.chat.id,))
    await message.reply(
        f"💬 <b>{html.escape(message.chat.title or 'Чат')}</b>\n"
        f"🆔 <code>{message.chat.id}</code>\n"
        f"👥 Участников: <b>{cnt}</b>\n"
        f"👮 Модераторов: <b>{mods['c']}</b>\n"
        f"📊 В базе: <b>{row['c'] or 0}</b> чел., <b>{row['m'] or 0}</b> сообщений")


async def get_rules_topic(chat_id: int) -> int:
    """ID темы, где опубликованы правила чата."""
    v = await db.get_setting(chat_id, "rules_topic", "0")
    try:
        return int(v)
    except Exception:
        return 0


def render_rules_card(chat_title: str, raw_rules: str, is_forum: bool = False, chat_id: int = 0, rules_topic: int = 0) -> tuple[str, InlineKeyboardMarkup | None]:
    """Форматирует любой пользовательский текст правил в стильную эстетичную карточку с темой чата."""
    title = html.escape(chat_title or "Беседа")
    content = (raw_rules or "").strip()

    if len(content) > 3400:
        content = content[:3400] + "…\n<i>(текст правил сокращён)</i>"

    # Динамическая изоляция темы оформления чата
    import core_themes
    theme_id = "rainbow"
    if chat_id:
        try:
            import sqlite3
            from config import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            r = conn.execute("SELECT theme FROM chat_themes WHERE chat_id=?", (chat_id,)).fetchone()
            if r and r[0] in core_themes.ALL_THEMES:
                theme_id = r[0]
            conn.close()
        except Exception:
            pass

    t = core_themes.ALL_THEMES.get(theme_id, core_themes.ALL_THEMES["rainbow"])
    banner = t["banner"]
    footer_banner = t["footer_banner"]
    badge = t["badge"]

    card = (
        f"{badge} ✨ <b>ПРАВИЛА БЕСЕДЫ · {title}</b> ✨ {badge}\n"
        f"{banner}\n\n"
        f"<blockquote>✨ <b>Настоящие правила обязательны к исполнению всеми участниками сообщества.</b>\n"
        f"Незнание правил не освобождает от ответственности!</blockquote>\n\n"
        f"<blockquote expandable>{content}</blockquote>\n\n"
        f"{footer_banner}\n"
        f"👑 <i>Соблюдайте правила и проявляйте уважение ко всем участникам!</i>"
    )

    rows = []
    if is_forum and rules_topic and chat_id:
        from h_userinfo import topic_link
        link = topic_link(chat_id, rules_topic)
        rows.append([InlineKeyboardButton(text="📜 Открыть тему «Правила»", url=link)])

    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    return card, kb


DEFAULT_CHAT_RULES = (
    "<b>1. ОСНОВНЫЕ ПРАВИЛА ОБЩЕНИЯ:</b>\n"
    "1.1. 🤝 Уважайте других участников, соблюдайте нормы приличия и адекватность.\n"
    "1.2. 🚫 <b>Оскорбления:</b> Запрещены прямые оскорбления, травля, токсичность и провокации.\n"
    "1.3. 🚫 <b>Мат и брань:</b> Чрезмерный мат и оскорбительные выражения запрещены.\n"
    "1.4. 🚫 <b>Спам и флуд:</b> Запрещён флуд сообщениями/стикерами/командами, оффтоп и капс.\n"
    "1.5. 🚫 <b>Реклама:</b> Запрещена несанкционированная реклама каналов, бесед, ботов и ссылок.\n"
    "1.6. 🚫 <b>18+ и NSFW:</b> Запрещён любой контент сексуального или шокирующего характера.\n"
    "1.7. 🚫 <b>Скам и обман:</b> Запрещено мошенничество, вымогательство и кража данных (деанон/доксинг).\n\n"
    "⚖️ <b>СИСТЕМА НАКАЗАНИЙ:</b>\n"
    "• За нарушения п. 1.1–1.4: 🔇 <b>Мут от 10м до 24ч</b> или ⚠️ <b>Варн (3/3 = бан)</b>.\n"
    "• За нарушения п. 1.5–1.7: 🔨 <b>Бан навсегда / Кик</b>."
)


# ================= 6. НАСТРОЙКА ЧАТА =================
@router.message(Cmd("правила", "правила клана", "rules", "правила чата", "наши правила", section=S_CHAT, group_only=True, usage="правила", desc="Правила чата"))
async def rules_show(message: Message, **kw):
    txt = await db.get_setting(message.chat.id, "rules_text") or await db.get_setting(message.chat.id, "rules")
    if not txt:
        txt = DEFAULT_CHAT_RULES
        await db.set_setting(message.chat.id, "rules_text", txt)
        await db.set_setting(message.chat.id, "rules", txt)

    frame_on = (await db.get_setting(message.chat.id, "rules_card_frame", "1") == "1")
    rtopic = await get_rules_topic(message.chat.id)
    is_forum = bool(getattr(message.chat, "is_forum", False))
    title = message.chat.title or "Беседа"

    if frame_on:
        card, kb = render_rules_card(title, txt, is_forum=is_forum, chat_id=message.chat.id, rules_topic=rtopic)
        await message.reply(card, reply_markup=kb, disable_web_page_preview=True)
    else:
        # Чистый текст без автоматического заголовка и рамок
        rows = []
        if is_forum and rtopic and message.chat.id:
            from h_userinfo import topic_link
            rows.append([InlineKeyboardButton(text="📜 Открыть тему «Правила»", url=topic_link(message.chat.id, rtopic))])
        kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
        await message.reply(txt, reply_markup=kb, disable_web_page_preview=True)


@router.message(Cmd("+правила", "+ правила", "+правило", "+ правило", "правила:", "новые правила",
                    "установить правила", "установить правило", "сохранить правила", "сохранить правило",
                    "задать правила", "задать правило", "изменить правила", "изменить правило",
                    section=S_CHAT, rank=3, group_only=True,
                    usage="+правила {текст}", desc="Установить текст правил чата"))
async def rules_set(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    txt = args or (message.reply_to_message.text or message.reply_to_message.caption if message.reply_to_message else "")
    if not txt or not txt.strip():
        return await message.reply(
            "⚠️ <b>Чтобы установить правила чата:</b>\n\n"
            "• Напишите: <code>+правила [текст правил]</code>\n"
            "• Или ответьте на сообщение с текстом правил командой: <code>+правила</code>"
        )
    txt = txt.strip()
    await db.set_setting(message.chat.id, "rules_text", txt)
    await db.set_setting(message.chat.id, "rules", txt)

    frame_on = (await db.get_setting(message.chat.id, "rules_card_frame", "1") == "1")
    rtopic = await get_rules_topic(message.chat.id)
    is_forum = bool(getattr(message.chat, "is_forum", False))

    if frame_on:
        preview_card, kb = render_rules_card(message.chat.title or "Беседа", txt, is_forum=is_forum, chat_id=message.chat.id, rules_topic=rtopic)
        await message.reply(
            "✅ <b>Правила чата успешно сохранены и стилизованы!</b>\n\n"
            f"<b>Предпросмотр карточки:</b>\n\n{preview_card}",
            reply_markup=kb,
            disable_web_page_preview=True
        )
    else:
        await message.reply(
            "✅ <b>Правила чата успешно сохранены!</b>\n\n"
            f"<b>Текст правил:</b>\n{txt}",
            disable_web_page_preview=True
        )


@router.message(Cmd("автоправила", "авто правила", "+автоправила", "-автоправила",
                    "автооформление правил", "оформление правил",
                    section=S_CHAT, rank=3, group_only=True,
                    usage="автоправила [вкл/выкл]",
                    desc="Включить/выключить авто-оформление карточки правил"))
async def cmd_auto_rules(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    a = (args or "").strip().lower()
    cmd_text = (message.text or "").strip().lower()

    if cmd_text.startswith(("-автоправила", "- автоправила")) or a in {"выкл", "off", "офф", "нет", "0", "disable"}:
        await db.set_setting(message.chat.id, "rules_card_frame", "0")
        return await message.reply(
            "🛑 <b>Авто-оформление правил выключено!</b>\n\n"
            "Теперь по команде <code>правила</code> бот будет отправлять только чистый текст ваших правил без автоматического заголовка, цитат и рамок."
        )

    if cmd_text.startswith(("+автоправила", "+ автоправила")) or a in {"вкл", "on", "он", "да", "1", "enable"}:
        await db.set_setting(message.chat.id, "rules_card_frame", "1")
        return await message.reply(
            "✅ <b>Авто-оформление правил включено!</b>\n\n"
            "Теперь правила будут красиво оборачиваться в карточку с названием беседы и сворачиваемой цитатой."
        )

    cur = await db.get_setting(message.chat.id, "rules_card_frame", "1")
    st = "🟢 Включено (красивая карточка с рамкой)" if cur == "1" else "⚪️ Выключено (только чистый текст правил)"
    await message.reply(
        f"📜 <b>Настройка авто-оформления правил</b>\n\n"
        f"Текущий режим: <b>{st}</b>\n\n"
        f"• Включить: <code>автоправила вкл</code> (или <code>+автоправила</code>)\n"
        f"• Выключить: <code>автоправила выкл</code> (или <code>-автоправила</code>)"
    )


@router.message(Cmd("изучить правила", "изучить правило", "запомнить правила", "запомнить правило", "запомни правила", "запомни правило", "проанализировать правила", "проверить правила",
                    section=S_CHAT, rank=3, group_only=True,
                    usage="изучить правила", desc="Автоматически найти, изучить и активировать правила чата"))
async def rules_learn(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return

    source_label = ""
    txt = args.strip() if args else ""

    # 1. Если текст передан в аргументах команды
    if txt:
        source_label = "📝 Текст из команды"
    # 2. Если команда отправлена реплаем на сообщение
    elif message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
        txt = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
        source_label = "💬 Сообщение по ответу (reply)"
    # 3. Если правила уже были ранее сохранены в чате (+правила / установить правила)
    if not txt:
        saved = await db.get_setting(message.chat.id, "rules_text") or await db.get_setting(message.chat.id, "rules")
        if saved and saved.strip():
            txt = saved.strip()
            source_label = "💾 Ранее сохранённые правила беседы"

    # 4. Если в базе нет — пробуем найти правила в закреплённом сообщении чата
    if not txt:
        try:
            chat_obj = await bot.get_chat(message.chat.id)
            if chat_obj.pinned_message and (chat_obj.pinned_message.text or chat_obj.pinned_message.caption):
                pin_txt = (chat_obj.pinned_message.text or chat_obj.pinned_message.caption or "").strip()
                if len(pin_txt) >= 20:
                    txt = pin_txt
                    source_label = "📌 Закреплённое сообщение чата"
        except Exception:
            pass

    # 5. Если нигде не нашли — используем стандартные правила беседы
    if not txt:
        txt = DEFAULT_CHAT_RULES
        source_label = "🛡 Стандартный регламент правил"

    # Сохраняем изученные правила в базу данных
    await db.set_setting(message.chat.id, "rules_text", txt)
    await db.set_setting(message.chat.id, "rules", txt)

    # ── Анализ и структурирование правил ──
    import re
    rule_items = re.findall(r"(?:^|\n)\s*(?:(?:\d+(?:\.\d+)?)|[•\-\*])\s*([^\n]+)", txt)
    item_count = len(rule_items) if rule_items else max(1, len(txt.splitlines()))

    txt_low = txt.lower()
    categories = []
    if any(w in txt_low for w in ("оск", "оскорблен", "токсич", "агресс", "буллинг", "травл", "уважен")):
        categories.append("• 🤬 <b>Оскорбления и токсичность</b>")
    if any(w in txt_low for w in ("мат", "брань", "нецензур", "ругательств")):
        categories.append("• 🗯 <b>Мат и нецензурная лексика</b>")
    if any(w in txt_low for w in ("спам", "флуд", "капс", "оффтоп", "засорен")):
        categories.append("• 🛑 <b>Спам, флуд и капс</b>")
    if any(w in txt_low for w in ("реклам", "ссылк", "пиар", "канал", "сторонн")):
        categories.append("• 📢 <b>Реклама и сторонние ссылки</b>")
    if any(w in txt_low for w in ("18+", "nsfw", "порно", "эротик", "интим")):
        categories.append("• 🔞 <b>Контент 18+ / NSFW</b>")
    if any(w in txt_low for w in ("скам", "обман", "мошеннич", "докс", "деанон", "слив")):
        categories.append("• 🦹 <b>Мошенничество, скам и деанон</b>")
    if any(w in txt_low for w in ("чит", "софт", "багоюз", "руин", "помех")):
        categories.append("• 🎮 <b>Читы, софты и помехи игре</b>")

    if not categories:
        categories.append("• 📋 <b>Общие правила поведения и модерации</b>")

    cat_block = "\n".join(categories)

    await message.reply(
        f"🧠 <b>Правила беседы успешно изучены и активированы!</b>\n\n"
        f"📥 <b>Источник:</b> <i>{source_label}</i>\n"
        f"📊 <b>Распознано пунктов/условий:</b> <b>{item_count}</b>\n\n"
        f"🔍 <b>Выявленные категории нарушений:</b>\n"
        f"{cat_block}\n\n"
        f"⚖️ <b>Санкции:</b> 🔇 Муты · ⚠️ Варны · 🔨 Баны · 👢 Кик\n\n"
        f"🛡 <b>Строгий контроль модерации включен:</b>\n"
        f"Теперь при выдаче мутов, варнов и банов бот сверяет причину модератора с текстом этих правил.\n\n"
        f"📖 <i>Посмотреть правила чата: <code>правила</code></i>",
        disable_web_page_preview=True
    )


@router.message(Cmd("-правила", "-правило", "сбросить правила", "сбросить правило", "удалить правила", "удалить правило",
                    section=S_CHAT, rank=3, group_only=True,
                    usage="-правила", desc="Сбросить правила чата до стандартных"))
async def rules_reset(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return
    await db.set_setting(message.chat.id, "rules_text", DEFAULT_CHAT_RULES)
    await db.set_setting(message.chat.id, "rules", DEFAULT_CHAT_RULES)
    await message.reply(
        "🔄 <b>Правила чата сброшены до стандартного регламента.</b>\n\n"
        "📖 <i>Посмотреть правила: <code>правила</code></i>\n"
        "📝 <i>Установить свои: <code>+правила [текст]</code></i>"
    )


@router.message(Cmd("приветствие", "greeting", section=S_CHAT, usage="приветствие",
                    desc="Показать приветствие"))
async def greet_show(message: Message, **kw):
    txt = await db.get_setting(message.chat.id, "greeting")
    await message.reply(f"👋 <b>Приветствие</b>\n\n{txt}" if txt else
                        "Приветствие не установлено.\n"
                        "Установить: <code>установить приветствие Привет, %имя%!</code>")


@router.message(Cmd("+приветствие", "установить приветствие", section=S_CHAT, rank=3,
                    usage="установить приветствие {текст}", desc="Задать приветствие"))
async def greet_set(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    if not args:
        return await message.reply("Доступные переменные: %имя%, %чат%\n"
                                   "Пример: <code>установить приветствие Привет, %имя%!</code>")
    await db.set_setting(message.chat.id, "greeting", args)
    await message.reply("✅ Приветствие установлено.")


@router.message(Cmd("-приветствие", "удалить приветствие", section=S_CHAT, rank=3,
                    usage="удалить приветствие", desc="Убрать приветствие"))
async def greet_del(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 3):
        return
    await db.set_setting(message.chat.id, "greeting", "")
    await message.reply("🗑 Приветствие удалено.")


@router.message(Cmd("закрепить", "пин", section=S_CHAT, rank=2, usage="закрепить (реплаем)",
                    desc="Закрепить сообщение"))
async def pin_msg(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return
    if not message.reply_to_message:
        return await message.reply("Ответьте на сообщение, которое надо закрепить.")
    try:
        await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        await message.reply("📌 Закреплено.")
    except Exception as e:
        await message.reply(f"⚠️ {html.escape(str(e))}")


@router.message(Cmd("открепить", "анпин", section=S_CHAT, rank=2, usage="открепить",
                    desc="Открепить сообщение"))
async def unpin_msg(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 2):
        return
    try:
        if message.reply_to_message:
            await bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
        else:
            await bot.unpin_all_chat_messages(message.chat.id)
        await message.reply("📌 Откреплено.")
    except Exception as e:
        await message.reply(f"⚠️ {html.escape(str(e))}")


@router.message(Cmd("выключить чат", "отключить чат", section=S_CHAT, rank=4,
                    usage="выключить чат", desc="Отключить бота в чате"))
async def chat_off(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    await db.set_setting(message.chat.id, "silent", "1")
    await message.reply("🔕 Бот отключён в этом чате. Включить: <code>включить чат</code>")


@router.message(Cmd("включить чат", section=S_CHAT, rank=4, usage="включить чат",
                    desc="Включить бота в чате"))
async def chat_on(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    await db.set_setting(message.chat.id, "silent", "0")
    await message.reply("🔔 Бот снова активен.")


@router.message(Cmd("автокик", section=S_CHAT, rank=4, usage="автокик {период}",
                    desc="Автокик неактивных"))
async def autokick(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    secs, _ = parse_period(args or "")
    if not secs:
        cur = await db.get_setting(message.chat.id, "autokick", "0")
        return await message.reply(f"Автокик: <b>{human_period(int(cur))}</b>\n"
                                   f"Изменить: <code>автокик 30 дней</code>")
    await db.set_setting(message.chat.id, "autokick", str(secs))
    await message.reply(f"✅ Автокик неактивных: {human_period(secs)}")


@router.message(Cmd("тег всех", "тегнуть всех", "теги", section=S_CHAT, rank=2,
                    need_prefix=True, usage="!теги {текст}",
                    desc="Тегнуть участников"))
async def tag_all(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    rows = await members.known_chat_rows(message.chat.id, limit=100)
    me = await bot.me()
    people = await members.verified_members(
        bot, message.chat.id, rows, exclude=(me.id, message.from_user.id))
    if not people:
        return await message.reply("Некого тегать: присутствующие участники не найдены.")
    people = people[:30]
    tags = " ".join(
        members.summon_mention(p["user_id"], p.get("first_name"),
                               p.get("username"))
        for p in people)
    await message.reply(f"📢 {html.escape(args or 'Внимание!')}\n\n{tags}")


# ================= 3. ТРИГГЕРЫ =================
@router.message(Cmd("добавить триггер", "новый триггер", section=S_TRIG, rank=2,
                    usage="добавить триггер {слово} = {ответ}", desc="Создать автоответ"))
async def trig_add(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    if "=" not in (args or ""):
        return await message.reply("Формат: <code>добавить триггер привет = Привет!</code>")
    pat, ans = args.split("=", 1)
    await db.execute("INSERT INTO triggers (chat_id,pattern,answer,by_id,ts) VALUES (?,?,?,?,?)",
                     (message.chat.id, pat.strip().lower(), ans.strip(),
                      message.from_user.id, int(time.time())))
    await message.reply(f"⚡️ Триггер добавлен: <b>{html.escape(pat.strip())}</b>")


@router.message(Cmd("триггеры", "список триггеров", section=S_TRIG, usage="триггеры",
                    desc="Список триггеров"))
async def trig_list(message: Message, **kw):
    rows = await db.fetchall("SELECT id,pattern,answer FROM triggers WHERE chat_id=? LIMIT 30",
                             (message.chat.id,))
    if not rows:
        return await message.reply("Триггеров нет.")
    lines = [f"#{r['id']} <b>{html.escape(r['pattern'])}</b> → "
             f"{html.escape(r['answer'][:40])}" for r in rows]
    await message.reply("⚡️ <b>Триггеры чата</b>\n" + "\n".join(lines))


@router.message(Cmd("удалить триггер", section=S_TRIG, rank=2, usage="удалить триггер {id|слово}",
                    desc="Удалить триггер"))
async def trig_del(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    a = (args or "").strip()
    if a.isdigit():
        await db.execute("DELETE FROM triggers WHERE id=? AND chat_id=?", (int(a), message.chat.id))
    else:
        await db.execute("DELETE FROM triggers WHERE lower(pattern)=lower(?) AND chat_id=?",
                         (a, message.chat.id))
    await message.reply("🗑 Триггер удалён.")


# ================= 4. ДОСТУП КОМАНД =================





# ================= 7. СЕТКА ЧАТОВ =================
@router.message(Cmd("сетка", "мои чаты", section=S_NET, rank=4, usage="сетка",
                    desc="Список чатов сетки"))
async def net_list(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    rows = await db.fetchall("SELECT c.chat_id, ch.title, c.num FROM net_chats c "
                             "LEFT JOIN chats ch ON ch.chat_id=c.chat_id "
                             "WHERE c.net_id=? ORDER BY c.num", (message.from_user.id,))
    if not rows:
        return await message.reply("Сетка пуста.\nДобавить: <code>сетка добавить</code>")
    lines = [f"{r['num']}. {html.escape(r['title'] or str(r['chat_id']))}" for r in rows]
    await message.reply("🕸 <b>Ваша сетка чатов</b>\n" + "\n".join(lines))


@router.message(Cmd("сетка добавить", "добавить в сетку", section=S_NET, rank=5,
                    usage="сетка добавить", desc="Добавить чат в сетку"))
async def net_add(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    row = await db.fetchone("SELECT COALESCE(MAX(num),0)+1 n FROM net_chats WHERE net_id=?",
                            (message.from_user.id,))
    await db.execute("INSERT OR IGNORE INTO net_chats (net_id,chat_id,num) VALUES (?,?,?)",
                     (message.from_user.id, message.chat.id, row["n"]))
    await message.reply(f"🕸 Чат добавлен в сетку под номером <b>{row['n']}</b>")


async def get_sms_topic(chat_id: int) -> int:
    from core_seed import MAIN_CHAT
    default_val = "4" if (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")) else "0"
    v = await db.get_setting(chat_id, "sms_topic", default_val)
    try:
        val = int(v)
        if val == 0 and (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")):
            return 4
        return val
    except Exception:
        return 4 if (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")) else 0



async def prune_dead_topics(bot: Bot, chat_id: int):
    """Проверяет зарегистрированные темы в Telegram. Если тема была удалена в Telegram,
    автоматически удаляет её из chat_forum_topics и сбрасывает соответствующую привязку в 0."""
    try:
        from aiogram.exceptions import TelegramBadRequest
        rows = await db.get_known_chat_topics(chat_id)
        sys_keys = ["sms_topic", "rules_topic", "boss_topic", "gram_topic", "form_topic"]
        settings_tids: dict[int, list[str]] = {}
        for k in sys_keys:
            val = await db.get_setting(chat_id, k, "0")
            if val and str(val).isdigit() and int(val) > 0:
                tid = int(val)
                settings_tids.setdefault(tid, []).append(k)

        all_tids = set(r["thread_id"] for r in rows) | set(settings_tids.keys())
        if not all_tids:
            return

        name_by_tid = {r["thread_id"]: r["name"] for r in rows}

        async def verify(tid: int):
            try:
                nm = name_by_tid.get(tid) or f"Тема #{tid}"
                # edit_forum_topic бросает TOPIC_ID_INVALID / TOPIC_DELETED если ветка удалена
                await bot.edit_forum_topic(chat_id=chat_id, message_thread_id=tid, name=nm)
                return (tid, True)
            except TelegramBadRequest as e:
                err = (e.message or "").lower()
                if "topic_id_invalid" in err or "topic_deleted" in err or "not found" in err:
                    return (tid, False)
                return (tid, True)
            except Exception:
                return (tid, True)

        results = await asyncio.gather(*(verify(t) for t in all_tids), return_exceptions=True)
        for res in results:
            if isinstance(res, tuple):
                tid, alive = res
                if not alive:
                    await db.execute("DELETE FROM chat_forum_topics WHERE chat_id=? AND thread_id=?", (chat_id, tid))
                    if tid in settings_tids:
                        for k in settings_tids[tid]:
                            await db.set_setting(chat_id, k, "0")
    except Exception:
        pass


@router.message(Cmd("автонастройка", "автонастройка группы", "автонастройка чата", "автосетап", "автонастройка тем",
                    section=S_TOPIC, rank=4, usage="автонастройка",
                    desc="🪄 Автоматически создать и привязать темы: Общение, Правила, Боссы, Казино"))
async def cmd_auto_setup_topics(message: Message, bot: Bot, skip_require: bool = False, **kw):
    if not skip_require and not await require(message, bot, 4):
        return

    cid = message.chat.id

    # 1. Проверяем, включен ли режим тем в группе (форум)
    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Автонастройка доступна только в группах с включенным режимом тем (Форум)!</b>\n\n"
            "Как включить темы:\n"
            "1. Откройте настройки вашей группы в Telegram.\n"
            "2. Перейдите в раздел <b>Темы</b> (или <b>Форум</b>) и включите его.\n"
            "3. После включения повторите команду: <code>автонастройка</code>"
        )

    # 2. Проверяем права бота на управление темами
    try:
        admins = await bot.get_chat_administrators(cid)
        me = await bot.me()
        bot_adm = next((a for a in admins if a.user.id == me.id), None)
        if not bot_adm or not getattr(bot_adm, "can_manage_topics", False):
            return await message.reply(
                "⚠️ <b>У бота нет прав на управление темами!</b>\n\n"
                "Чтобы бот мог автоматически создать и настроить ветки, выдайте ему право:\n"
                "👉 <b>Управление темами (Manage Topics)</b> в списке администраторов группы."
            )
    except Exception as e:
        return await message.reply(f"⚠️ Не удалось проверить права бота: {html.escape(str(e))}")

    # 3. Синхронизируем и очищаем удаленные ветки
    await prune_dead_topics(bot, cid)

    cur_sms = await get_sms_topic(cid)
    cur_rules = await get_rules_topic(cid)
    from h_boss import get_boss_topic
    from h_grams import get_gram_topic
    from h_userinfo import topic_link
    cur_boss = await get_boss_topic(cid)
    cur_gram = await get_gram_topic(cid)

    # Защита от дубликатов: если хотя бы одна системная тема уже привязана — блокируем автонастройку
    bound_topics = []
    if cur_sms > 0:
        bound_topics.append(f"💬 <b>Общение:</b> {topic_link(cid, cur_sms)} [ID: <code>{cur_sms}</code>]")
    if cur_gram > 0:
        bound_topics.append(f"🎰 <b>Казино:</b> {topic_link(cid, cur_gram)} [ID: <code>{cur_gram}</code>]")
    if cur_rules > 0:
        bound_topics.append(f"📜 <b>Правила:</b> {topic_link(cid, cur_rules)} [ID: <code>{cur_rules}</code>]")
    if cur_boss > 0:
        bound_topics.append(f"🐉 <b>Боссы:</b> {topic_link(cid, cur_boss)} [ID: <code>{cur_boss}</code>]")

    if bound_topics:
        bound_list_str = "\n".join(f"• {b}" for b in bound_topics)
        return await message.reply(
            "⚠️ <b>У вас уже привязаны темы в этой группе!</b>\n\n"
            "📋 <b>Сейчас уже привязаны:</b>\n"
            f"{bound_list_str}\n\n"
            "🛡 <b>Защита от дубликатов:</b>\n"
            "Пожалуйста, привяжите все остальные темы сами через меню <code>темы</code>, "
            "так как при повторном автосетапе мы можем создать копии веток!\n\n"
            "👉 <b>Что делать:</b>\n"
            "1. Напишите <code>темы</code> и привяжите нужные зоны вручную в 1 клик.\n"
            "2. Либо, если хотите настроить всё заново с нуля — сначала нажмите <b>«🗑 Сбросить всё»</b> "
            "в меню тем (или напишите команду <code>сбросить темы</code>), после чего запустите <code>автонастройка</code>.",
            disable_web_page_preview=True
        )

    status_msg = await message.reply("🪄 <b>Запуск автонастройки группы...</b>\nСоздаю системные темы и настраиваю привязки, пожалуйста, подождите...")

    try:
        # 1. Создаем тему "💬 Общение"
        topic_chat = await bot.create_forum_topic(chat_id=cid, name="💬 Общение", icon_color=7322096)
        sms_tid = topic_chat.message_thread_id
        await db.set_setting(cid, "sms_topic", str(sms_tid))
        await db.record_chat_topic(cid, sms_tid, "💬 Общение")
        await asyncio.sleep(0.5)
        await bot.send_message(
            cid,
            "💬 ✨ <b>ТЕМА «ОБЩЕНИЕ» УСПЕШНО НАСТРОЕНА!</b> ✨ 💬\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Здесь проходит основная переписка участников, анонсы и новости беседы.\n\n"
            "👋 Приятного общения!",
            message_thread_id=sms_tid
        )

        # 2. Создаем тему "📜 Правила"
        topic_rules = await bot.create_forum_topic(chat_id=cid, name="📜 Правила", icon_color=16766590)
        rules_tid = topic_rules.message_thread_id
        await db.set_setting(cid, "rules_topic", str(rules_tid))
        await db.record_chat_topic(cid, rules_tid, "📜 Правила")
        await asyncio.sleep(0.5)
        await bot.send_message(
            cid,
            "📜 ✨ <b>ПРАВИЛА БЕСЕДЫ</b> ✨ 📜\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "1. 🤝 <b>Уважение:</b> относитесь взаимоуважительно ко всем участникам.\n"
            "2. 🚫 <b>Спам:</b> запрещены несогласованная реклама, флуд и спам-рассылки.\n"
            "3. 🤬 <b>Токсичность:</b> запрещены оскорбления, травля и провокации.\n"
            "4. 🐉 <b>Рейды:</b> битвы с боссами проводятся исключительно в теме «🐉 Рейдовые Боссы».\n"
            "5. 🎰 <b>Игры:</b> казино и мини-игры доступны в теме «🎰 Казино».\n\n"
            "👑 <i>Соблюдайте правила и приятного времяпрепровождения!</i>",
            message_thread_id=rules_tid
        )

        # 3. Создаем тему "🐉 Рейдовые Боссы"
        topic_boss = await bot.create_forum_topic(chat_id=cid, name="🐉 Рейдовые Боссы", icon_color=13338331)
        boss_tid = topic_boss.message_thread_id
        await db.set_setting(cid, "boss_topic", str(boss_tid))
        await db.record_chat_topic(cid, boss_tid, "🐉 Рейдовые Боссы")
        await asyncio.sleep(0.5)
        await bot.send_message(
            cid,
            "🐉 ✨ <b>ТЕМА «РЕЙДОВЫЕ БОССЫ» ПРИВЯЗАНА!</b> ✨ 🐉\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "⚔️ Все рейдовые боссы и битвы будут проходить строго в этой ветке!\n\n"
            "⏰ <b>Расписание рейдов:</b> 08:00, 12:00, 16:00, 20:00 (МСК)\n"
            "⚔️ <b>Атаки:</b> <code>ударить</code>, <code>выстрел</code>, <code>атака</code>\n"
            "🚑 <b>Помощь союзникам:</b> <code>хил @юзер</code> или <code>возродить</code>\n"
            "🛍 <b>Снаряжение:</b> <code>магазин</code> (мечи, бластеры, броня, аптечки)\n\n"
            "🏆 <i>Готовьте оружие и побеждайте боссов!</i>",
            message_thread_id=boss_tid
        )

        # 4. Создаем тему "🎰 Казино"
        topic_casino = await bot.create_forum_topic(chat_id=cid, name="🎰 Казино", icon_color=16766590)
        gram_tid = topic_casino.message_thread_id
        await db.set_setting(cid, "gram_topic", str(gram_tid))
        await db.record_chat_topic(cid, gram_tid, "🎰 Казино")
        await asyncio.sleep(0.5)
        await bot.send_message(
            cid,
            "🎰 ✨ <b>ТЕМА «КАЗИНО И ИГРЫ» ПРИВЯЗАНА!</b> ✨ 🎰\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "🎲 Все игры, рулетки, слоты и ставки теперь проходят строго в этой теме!\n\n"
            "🎮 <b>Популярные мини-игры:</b>\n"
            "• 🎰 <code>казик [ставка]</code> — крутить слоты\n"
            "• 💣 <code>мины [ставка]</code> — опасное минное поле\n"
            "• 🎡 <code>рулетка [ставка] [красное/черное/число]</code>\n"
            "• 📈 <code>краш [ставка]</code> — динамический график умножения\n"
            "• 🃏 <code>блэкджек [ставка]</code> — классическое 21 очко\n"
            "• 🎲 <code>кости [ставка]</code> / <code>кубик</code>\n"
            "• 💰 <code>баланс</code> — проверить баланс монет\n\n"
            "👑 <i>Делайте ставки с умом и пусть удача улыбнется вам!</i>",
            message_thread_id=gram_tid
        )

        summary = (
            "🎉 🌟 <b>АВТОНАСТРОЙКА ГРУППЫ УСПЕШНО ЗАВЕРШЕНА!</b> 🌟 🎉\n"
            "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
            "📋 <b>Созданы и привязаны официальные темы:</b>\n"
            f"• 💬 <b>Общение:</b> {topic_link(cid, sms_tid)}\n"
            f"• 🎰 <b>Казино:</b> {topic_link(cid, gram_tid)}\n"
            f"• 📜 <b>Правила:</b> {topic_link(cid, rules_tid)}\n"
            f"• 🐉 <b>Рейдовые Боссы:</b> {topic_link(cid, boss_tid)}\n\n"
            "✦ ══════════════════════════════ ✦\n"
            "🚀 <b>Группа полностью настроена и готова к активному общению и битвам!</b>"
        )
        await status_msg.edit_text(summary, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"⚠️ Ошибка при создании тем: {html.escape(str(e))}")


@router.message(Cmd("удалить тему", "удалить ветку", section=S_TOPIC, rank=4,
                    usage="удалить тему [номер|ссылка]", desc="Удалить ветку форума"))
async def cmd_delete_forum_topic(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return

    cid = message.chat.id
    if not getattr(message.chat, "is_forum", False):
        return await message.reply("⚠️ Эта команда работает только в группах с темами (Форум).")

    a = (args or "").strip()
    tid = 0
    if a.isdigit():
        tid = int(a)
    else:
        import re as _re
        m = _re.search(r"t\.me/c/\d+/(\d+)", a)
        if m:
            tid = int(m.group(1))
        else:
            tid = int(getattr(message, "message_thread_id", None) or 0)

    if not tid or tid == 1:
        return await message.reply(
            "⚠️ <b>Укажите ID темы или ссылку на неё:</b>\n"
            "Пример: <code>удалить тему 5</code>\n"
            "<i>(Или напишите команду прямо внутри той ветки, которую хотите удалить)</i>"
        )

    try:
        await bot.delete_forum_topic(chat_id=cid, message_thread_id=tid)
        # Если была привязана — сбрасываем
        for k in ("sms_topic", "rules_topic", "boss_topic", "gram_topic", "form_topic"):
            v = await db.get_setting(cid, k, "0")
            if v == str(tid):
                await db.set_setting(cid, k, "0")
        await db.execute("DELETE FROM chat_forum_topics WHERE chat_id=? AND thread_id=?", (cid, tid))
        try:
            if getattr(message, "message_thread_id", None) == tid:
                await bot.send_message(chat_id=cid, text=f"🗑 <b>Тема #{tid} успешно удалена из группы!</b>")
            else:
                await message.reply(f"🗑 <b>Тема #{tid} успешно удалена из группы!</b>")
        except Exception:
            try:
                await bot.send_message(chat_id=cid, text=f"🗑 <b>Тема #{tid} успешно удалена из группы!</b>")
            except Exception:
                pass
    except Exception as e:
        await message.reply(f"⚠️ Не удалось удалить тему #{tid}: {html.escape(str(e))}")


@router.message(Cmd("сбросить темы", "сброс тем", "очистить темы", "сбросить темы чата",
                    section=S_TOPIC, rank=4, usage="сбросить темы",
                    desc="Сбросить все привязки тем и очистить сохраненный список веток"))
async def cmd_reset_topics(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    cid = message.chat.id
    for meta in TOPIC_CATEGORIES.values():
        await db.set_setting(cid, meta["setting"], "0")
    await db.execute("DELETE FROM chat_forum_topics WHERE chat_id=?", (cid,))
    await message.reply(
        "🗑 <b>Все привязки тем и сохраненный список веток успешно сброшены!</b>\n\n"
        "Теперь вы можете запустить <code>автонастройка</code> с чистого листа "
        "или настроить темы через меню <code>темы</code>."
    )



@router.message(Cmd("тема смс", "тема общения", "тема чата", "тема анонсов",
                    "+тема смс", "+тема общения", "+тема чата", "+тема анонсов",
                    section=S_TOPIC, rank=1,
                    usage="тема смс", desc="Привязать текущую тему для СМС, общения и анонсов"))
async def cmd_set_sms_topic(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return

    if (args or "").strip().lower() in {"сброс", "убрать", "выкл", "off", "0"}:
        await db.set_setting(message.chat.id, "sms_topic", "0")
        return await message.reply("🌐 <b>Привязка темы СМС сброшена!</b> Уведомления и анонсы будут отправляться в основной чат.")

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем анонсы и сообщения отправляются прямо в основной чат.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    here = int(getattr(message, "message_thread_id", None) or 0)
    if not here:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧵 Все темы чата", callback_data="topics:main:0")]])
        return await message.reply(
            "⚠️ <b>Напишите эту команду внутри темы «СМС», чтобы привязать её!</b>\n\n"
            "Или откройте интерактивный центр тем кнопкой ниже:",
            reply_markup=kb
        )
    await db.set_setting(message.chat.id, "sms_topic", str(here))
    await message.reply(
        f"✅ <b>Тема «СМС» успешно установлена!</b>\n"
        f"ID темы: <code>{here}</code>\n"
        f"Теперь все анонсы, обновления и общие уведомления будут отправляться в эту тему.")


@router.message(Cmd("тема правила", "+тема правила", "тема правил", "+тема правил",
                    section=S_TOPIC, rank=1,
                    usage="тема правила", desc="Привязать текущую тему для правил чата"))
async def cmd_set_rules_topic(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return

    if (args or "").strip().lower() in {"сброс", "убрать", "выкл", "off", "0"}:
        await db.set_setting(message.chat.id, "rules_topic", "0")
        return await message.reply("🌐 <b>Привязка темы правил сброшена!</b>")

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем правила показываются прямо в основном чате.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    here = int(getattr(message, "message_thread_id", None) or 0)
    if not here:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧵 Все темы чата", callback_data="topics:main:0")]])
        return await message.reply(
            "⚠️ <b>Напишите эту команду внутри ветки форума «Правила», чтобы привязать её!</b>\n\n"
            "Или откройте интерактивный центр тем кнопкой ниже:",
            reply_markup=kb
        )
    await db.set_setting(message.chat.id, "rules_topic", str(here))
    await message.reply(
        f"✅ <b>Тема «Правила» успешно установлена!</b>\n"
        f"ID темы: <code>{here}</code>\n"
        f"Теперь кнопка в карточке правил будет ссылаться на эту тему.")


# ================= 10. ТЕМЫ МОДЕРАТОРОВ =================
@router.message(Cmd("тема", "темы", "теми", "топик", "топики", section=S_TOPIC, rank=1, usage="тема",
                    desc="Что настроено в этой теме"))
async def topic(message: Message, bot: Bot, args: str = "", **kw):
    """Показывает назначение темы, статус прав бота и подсказки быстрых команд.

    Поддерживает быстрые подкоманды:
    - «тема казик» / «тема казино»
    - «тема описание» / «тема анкета»
    - «тема смс» / «тема общение»
    - «тема правила»
    - «тема боссы»
    """
    if not await require(message, bot, 1):
        return

    here = int(getattr(message, "message_thread_id", None) or 0)
    a_lower = (args or "").strip().lower()
    first_word = a_lower.split()[0] if a_lower else ""

    # 1. Быстрые перенаправления на команды привязки тем:
    if first_word in {"казик", "казино", "игры", "монеты", "коины", "грамм", "граммы", "комет", "кометы"}:
        from h_grams import cmd_gram_topic
        sub_args = a_lower[len(first_word):].strip()
        return await cmd_gram_topic(message, bot, args=sub_args, **kw)

    if first_word in {"описание", "описания", "анкета", "анкеты"}:
        from h_userinfo import cmd_form_topic
        sub_args = a_lower[len(first_word):].strip()
        return await cmd_form_topic(message, bot, args=sub_args, **kw)

    if first_word in {"смс", "общение", "чат", "анонс", "анонсы"}:
        sub_args = a_lower[len(first_word):].strip()
        return await cmd_set_sms_topic(message, bot, args=sub_args, **kw)

    if first_word in {"правила", "правило", "правил"}:
        sub_args = a_lower[len(first_word):].strip()
        return await cmd_set_rules_topic(message, bot, args=sub_args, **kw)

    if first_word in {"босс", "боссы", "рейд", "рейды"}:
        from h_boss import cmd_set_boss_topic
        sub_args = a_lower[len(first_word):].strip()
        return await cmd_set_boss_topic(message, bot, args=sub_args, **kw)

    if first_word in {"сброс", "сбросить", "очистить"}:
        return await message.reply(
            "🗑 <b>Сброс привязок тем беседы:</b>\n\n"
            "• <code>игры везде</code> — разрешить казино во всех темах\n"
            "• <code>тема описание сброс</code> — отключить тему анкет\n"
            "• <code>тема смс сброс</code> — отключить тему СМС\n"
            "• <code>тема правила сброс</code> — отключить тему правил\n"
            "• <code>тема боссы сброс</code> — отключить тему боссов"
        )

    if args:
        # Ручная подпись темы участниками
        key = f"topic_note:{here}" if here else "topic"
        await db.set_setting(message.chat.id, key, args)
        return await message.reply(
            f"🧵 Подпись для этой темы сохранена: <b>{html.escape(args)}</b>")

    # 2. Проверка прав бота на управление темами (для закрытых тем форума)
    can_manage = False
    is_forum = bool(getattr(message.chat, "is_forum", False))
    if is_forum:
        try:
            me = await bot.me()
            m = await bot.get_chat_member(message.chat.id, me.id)
            can_manage = getattr(m, "can_manage_topics", False)
        except Exception:
            pass
        try:
            await prune_dead_topics(bot, message.chat.id)
        except Exception:
            pass

    author_id = message.from_user.id if message.from_user else 0
    card_text, kb = await render_topics_card_and_kb(message.chat.id, here, can_manage=can_manage, author_id=author_id)
    sent = await message.reply(card_text, reply_markup=kb, disable_web_page_preview=True)
    if sent and author_id:
        _register_topic_menu_author(message.chat.id, sent.message_id, author_id)


# Реестр открытых меню тем: (chat_id, message_id) -> author_user_id
_topic_menu_authors: dict[tuple[int, int], int] = {}


def _register_topic_menu_author(chat_id: int, message_id: int, author_id: int) -> None:
    if len(_topic_menu_authors) > 2000:
        keys = list(_topic_menu_authors.keys())[:500]
        for k in keys:
            _topic_menu_authors.pop(k, None)
    _topic_menu_authors[(chat_id, message_id)] = author_id


def _get_topic_menu_author(chat_id: int, message_id: int, message: Message | None = None) -> int:
    if (chat_id, message_id) in _topic_menu_authors:
        return _topic_menu_authors[(chat_id, message_id)]
    if message and message.reply_to_message and message.reply_to_message.from_user:
        if not message.reply_to_message.from_user.is_bot:
            author = message.reply_to_message.from_user.id
            _topic_menu_authors[(chat_id, message_id)] = author
            return author
    return 0


TOPIC_CATEGORIES = {
    "gram": {
        "title": "🎰 Казино и мини-игры",
        "emoji": "🎰",
        "setting": "gram_topic",
        "desc": "Слоты, рулетка, мины, краш, блэкджек и динамический рынок. Если привязана, бот перенаправляет игроков в эту тему.",
        "default_state": "Разрешено во всех темах",
    },
    "form": {
        "title": "📝 Анкеты и описания",
        "emoji": "📝",
        "setting": "form_topic",
        "desc": "Заполнение и проверка анкет новичков чата. Если привязана, приветствие приглашает новичков заполнять анкету именно сюда.",
        "default_state": "Не задана",
    },
    "sms": {
        "title": "💬 СМС и анонсы",
        "emoji": "💬",
        "setting": "sms_topic",
        "desc": "Уведомления, клановые анонсы, рассылки и новости чата отправляются в эту тему.",
        "default_state": "Не задана (Основной чат)",
    },
    "boss": {
        "title": "🐉 Рейдовые боссы",
        "emoji": "🐉",
        "setting": "boss_topic",
        "desc": "Появление и рейдовые битвы с боссами беседы происходят в этой ветке.",
        "default_state": "Не задана",
    },
    "rules": {
        "title": "📜 Правила чата",
        "emoji": "📜",
        "setting": "rules_topic",
        "desc": "Официальные правила беседы и кнопка быстрого перехода ведут в эту ветку.",
        "default_state": "Не задана",
    },
}


async def _get_all_chat_topics(chat_id: int) -> dict[str, int]:
    from h_userinfo import get_form_topic
    from h_grams import get_gram_topic
    from h_boss import get_boss_topic
    return {
        "gram": await get_gram_topic(chat_id),
        "form": await get_form_topic(chat_id),
        "sms": await get_sms_topic(chat_id),
        "boss": await get_boss_topic(chat_id),
        "rules": await get_rules_topic(chat_id),
    }


async def render_topics_card_and_kb(chat_id: int, here: int, can_manage: bool = False, author_id: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    from h_userinfo import topic_link
    topics = await _get_all_chat_topics(chat_id)
    gram_t = topics["gram"]
    form_t = topics["form"]
    sms_t = topics["sms"]
    boss_t = topics["boss"]
    rules_t = topics["rules"]

    current_role = "💬 Обычное общение / General"
    if here:
        if here == form_t:
            current_role = "📝 Описания и анкеты"
        elif here == gram_t:
            current_role = "🎰 Казино и мини-игры"
        elif here == boss_t:
            current_role = "🐉 Рейдовые боссы"
        elif here == sms_t:
            current_role = "💬 СМС, общение и анонсы"
        elif here == rules_t:
            current_role = "📜 Правила беседы"

    manage_status = (
        "🟢 <b>Управление темами:</b> Активно (бот отвечает даже в закрытых ветках)"
        if can_manage else
        "🟡 <b>Управление темами:</b> Рекомендуется выдать боту право <b>«Управление темами»</b> (Manage Topics)"
    )

    def _fmt(val: int, is_gram: bool = False) -> str:
        if val > 0:
            return f"{topic_link(chat_id, val)} [ID: <code>{val}</code>]"
        return "<i>разрешено везде</i>" if is_gram else "<i>не задана</i>"

    note = await db.get_setting(chat_id, f"topic_note:{here}", "") if here else await db.get_setting(chat_id, "topic", "")

    lines = [
        "🧵 <b>ЦЕНТР УПРАВЛЕНИЯ ТЕМАМИ ЧАТА</b>",
        "✦ ══════════════════════════════ ✦",
        f"📍 <b>Текущая ветка:</b> {current_role}" + (f" (ID: <code>{here}</code>)" if here else " (Основной чат)"),
    ]
    if note:
        lines.append(f"🏷 <b>Подпись ветки:</b> {html.escape(note)}")
    lines.extend([
        "",
        manage_status,
        "",
        "📋 <b>Статус системных зон беседы:</b>",
        f"🎰 <b>Казино и игры:</b> {_fmt(gram_t, True)}",
        f"📝 <b>Анкеты новичков:</b> {_fmt(form_t)}",
        f"💬 <b>СМС и общение:</b> {_fmt(sms_t)}",
        f"🐉 <b>Рейдовые боссы:</b> {_fmt(boss_t)}",
        f"📜 <b>Правила беседы:</b> {_fmt(rules_t)}",
        "",
        "👇 <i>Нажмите кнопку темы ниже для мгновенной привязки или сброса:</i>"
    ])

    buttons = [
        [
            InlineKeyboardButton(text="🎰 Казино", callback_data=f"topics:cat:gram:{here}:{author_id}"),
            InlineKeyboardButton(text="📝 Анкеты", callback_data=f"topics:cat:form:{here}:{author_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 СМС", callback_data=f"topics:cat:sms:{here}:{author_id}"),
            InlineKeyboardButton(text="🐉 Боссы", callback_data=f"topics:cat:boss:{here}:{author_id}"),
        ],
        [
            InlineKeyboardButton(text="📜 Правила", callback_data=f"topics:cat:rules:{here}:{author_id}"),
        ],
    ]

    action_row = []
    if here:
        action_row.append(InlineKeyboardButton(text=f"📍 Привязать ветку #{here}", callback_data=f"topics:here_menu:{here}:{author_id}"))
    action_row.append(InlineKeyboardButton(text="🪄 Автонастройка", callback_data=f"topics:auto:{here}:{author_id}"))
    buttons.append(action_row)

    buttons.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"topics:refresh:{here}:{author_id}"),
        InlineKeyboardButton(text="🗑 Сбросить всё", callback_data=f"topics:reset_all:{here}:{author_id}"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_chat_selectable_topics(chat_id: int, here: int = 0) -> list[tuple[int, str]]:
    """Собирает список всех доступных тем чата для меню привязки."""
    seen: dict[int, str] = {}

    # 1. Темы из текущих настроек беседы
    sys_configs = [
        ("gram_topic", "🎰 Казино"),
        ("sms_topic", "💬 Общение"),
        ("boss_topic", "🐉 Боссы"),
        ("rules_topic", "📜 Правила"),
        ("form_topic", "📝 Анкеты"),
    ]
    for key, def_name in sys_configs:
        v = await db.get_setting(chat_id, key, "0")
        try:
            tid = int(v)
            if tid > 0 and tid not in seen:
                seen[tid] = def_name
        except Exception:
            pass

    # 2. Темы из базы данных chat_forum_topics
    rows = await db.get_known_chat_topics(chat_id)
    for r in rows:
        tid = r["thread_id"]
        tname = r["name"] or f"Тема #{tid}"
        if tid not in seen or (seen[tid].startswith("Тема #") and r["name"]):
            seen[tid] = tname

    # 3. Текущая ветка вызова, если не General и еще не в списке
    if here > 0 and here not in seen:
        seen[here] = f"Ветка #{here}"

    result = [(tid, name) for tid, name in seen.items()]
    result.sort(key=lambda x: x[0])
    return result


async def _build_topic_category_card(chat_id: int, here: int, cat: str, author_id: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    from h_userinfo import topic_link
    meta = TOPIC_CATEGORIES.get(cat, TOPIC_CATEGORIES["gram"])
    setting_key = meta["setting"]
    v = await db.get_setting(chat_id, setting_key, "0")
    try:
        cur_id = int(v)
    except Exception:
        cur_id = 0

    if cur_id > 0:
        cur_status = f"🔒 <b>Привязана к теме:</b> {topic_link(chat_id, cur_id)} [ID: <code>{cur_id}</code>]"
        mode_hint = (
            "⚠️ <b>Строгий режим:</b> команды этой зоны работают <b>ТОЛЬКО</b> в привязанной ветке!\n"
            "В остальных ветках чата бот перенаправляет игроков в эту тему ссылкой."
        )
    else:
        cur_status = f"🌐 <b>Разрешено во всех темах</b> (свободный доступ)"
        mode_hint = (
            "ℹ️ <b>Свободный режим:</b> команды этой зоны разрешены во всех ветках чата без ограничений."
        )

    loc_str = f"ветка ID <code>{here}</code>" if here else "Основной чат (General)"

    lines = [
        f"{meta['emoji']} <b>НАСТРОЙКА ЗОНЫ: {meta['title']}</b>",
        "✦ ══════════════════════════════ ✦",
        f"ℹ️ {meta['desc']}",
        "",
        f"📊 Текущее состояние: {cur_status}",
        f"{mode_hint}",
        "",
        f"📍 Вы находитесь в: <b>{loc_str}</b>",
        "",
        "👇 <b>Выберите тему для привязки или создайте новую:</b>"
    ]

    rows = []

    # 1. Список известных тем группы в виде аккуратных кнопок (по 2 в ряд)
    topics = await get_chat_selectable_topics(chat_id, here)
    if topics:
        topic_buttons = []
        for tid, tname in topics:
            is_cur = (tid == cur_id)
            mark = " ✅" if is_cur else ""
            btn_text = f"{tname}{mark}"
            topic_buttons.append(
                InlineKeyboardButton(text=btn_text, callback_data=f"topics:bind:{cat}:{tid}:{here}:{author_id}")
            )

        for i in range(0, len(topic_buttons), 2):
            rows.append(topic_buttons[i:i+2])

    # 2. Если пользователь прямо сейчас в ветке форума (here > 0), которой нет в списке:
    if here > 0 and here not in [t[0] for t in topics]:
        rows.append([InlineKeyboardButton(text=f"📍 Привязать к текущей ветке #{here}", callback_data=f"topics:bind:{cat}:{here}:{here}:{author_id}")])

    # 3. Кнопка создания темы в 1 клик
    cat_create_titles = {
        "gram": "🎰 Создать тему «Казино» в 1 клик",
        "form": "📝 Создать тему «Анкеты» в 1 клик",
        "sms": "💬 Создать тему «Общение» в 1 клик",
        "boss": "🐉 Создать тему «Боссы» в 1 клик",
        "rules": "📜 Создать тему «Правила» в 1 клик",
    }
    create_btn_text = cat_create_titles.get(cat, f"Создать тему «{meta['title']}»")
    rows.append([InlineKeyboardButton(text=f"🪄 {create_btn_text}", callback_data=f"topics:create_topic:{cat}:{here}:{author_id}")])

    # 4. Переключатель: Сброс / Разрешить везде
    if cur_id > 0:
        rows.append([InlineKeyboardButton(text="🌐 Разрешить во всех темах (снять привязку)", callback_data=f"topics:unbind:{cat}:{here}:{author_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🌐 Разрешено во всех темах (активно)", callback_data=f"topics:unbind:{cat}:{here}:{author_id}")])

    # 5. Назад
    rows.append([InlineKeyboardButton(text="◀️ Назад в меню тем", callback_data=f"topics:main:{here}:{author_id}")])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _build_bind_here_card(chat_id: int, here: int, author_id: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        f"📍 <b>БЫСТРАЯ ПРИВЯЗКА ВЕТКИ #{here}</b>",
        "✦ ══════════════════════════════ ✦",
        f"Выберите, какую системную зону вы хотите назначить на ветку <b>ID <code>{here}</code></b>:",
    ]
    rows = [
        [InlineKeyboardButton(text="🎰 Казино и мини-игры", callback_data=f"topics:bind:gram:{here}:{here}:{author_id}")],
        [InlineKeyboardButton(text="📝 Анкеты и описания", callback_data=f"topics:bind:form:{here}:{here}:{author_id}")],
        [InlineKeyboardButton(text="💬 СМС, общение и анонсы", callback_data=f"topics:bind:sms:{here}:{here}:{author_id}")],
        [InlineKeyboardButton(text="🐉 Рейдовые боссы", callback_data=f"topics:bind:boss:{here}:{here}:{author_id}")],
        [InlineKeyboardButton(text="📜 Правила беседы", callback_data=f"topics:bind:rules:{here}:{here}:{author_id}")],
        [InlineKeyboardButton(text="◀️ Назад в меню тем", callback_data=f"topics:main:{here}:{author_id}")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("topics:"))
async def cb_topics_dispatcher(call: CallbackQuery, bot: Bot):
    from config import is_bot_owner
    from core_ranks import get_rank
    uid = call.from_user.id
    cid = call.message.chat.id
    msg_id = call.message.message_id

    async def safe_answer(text: str = "", show_alert: bool = False):
        try:
            await call.answer(text, show_alert=show_alert)
        except Exception:
            pass

    async def safe_edit(text: str, reply_markup=None):
        try:
            await call.message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:
            pass

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else "main"

    # 1. Извлекаем author_id (из callback_data, реестра или reply_to_message)
    author_id = 0
    if len(parts) >= 3 and parts[-1].isdigit() and len(parts[-1]) >= 5:
        author_id = int(parts[-1])
    if not author_id:
        author_id = _get_topic_menu_author(cid, msg_id, call.message)

    # 2. ЗАЩИТА: Только автор команды может нажимать на кнопки!
    if author_id and uid != author_id and not is_bot_owner(uid):
        return await safe_answer(
            "🚫 Это меню настроек открыто другим пользователем!\n\n"
            "Напишите команду «темы» самостоятельно, чтобы настроить ветки беседы.",
            show_alert=True
        )

    # 3. Корректная проверка прав нажавшего пользователя:
    is_admin = is_bot_owner(uid)
    admin_rank = 10 if is_admin else 0
    if not is_admin:
        r = await get_rank(cid, uid)
        if r and r >= 1:
            admin_rank = r
            is_admin = True
        else:
            try:
                cm = await bot.get_chat_member(cid, uid)
                if cm.status == "creator":
                    admin_rank = 10
                    is_admin = True
                elif cm.status == "administrator":
                    admin_rank = 5
                    is_admin = True
            except Exception:
                pass

    if not is_admin:
        return await safe_answer("🔒 Настройка тем доступна только администраторам беседы!", show_alert=True)

    is_forum = bool(getattr(call.message.chat, "is_forum", False)) if (call.message and call.message.chat) else False
    can_manage = False
    try:
        me = await bot.me()
        m = await bot.get_chat_member(cid, me.id)
        can_manage = getattr(m, "can_manage_topics", False)
    except Exception:
        pass

    if action in {"main", "refresh"}:
        here = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if is_forum:
            await prune_dead_topics(bot, cid)
        txt, kb = await render_topics_card_and_kb(cid, here, can_manage=can_manage, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)
        await safe_answer("🔄 Список тем обновлён")

    elif action == "cat":
        cat = parts[2] if len(parts) > 2 else "gram"
        here = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        if is_forum:
            await prune_dead_topics(bot, cid)
        txt, kb = await _build_topic_category_card(cid, here, cat, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)
        await safe_answer()

    elif action == "here_menu":
        here = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if not here:
            return await safe_answer("⚠️ Вы находитесь в основном чате! Перейдите в нужную ветку форума.", show_alert=True)
        txt, kb = _build_bind_here_card(cid, here, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)
        await safe_answer()

    elif action == "bind":
        cat = parts[2]
        tid = parts[3] if len(parts) > 3 else "0"
        here = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
        meta = TOPIC_CATEGORIES.get(cat)
        if meta:
            await db.set_setting(cid, meta["setting"], tid)
            await safe_answer(f"✅ Зона «{meta['title']}» привязана к ветке #{tid}!", show_alert=True)
        txt, kb = await _build_topic_category_card(cid, here, cat, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)

    elif action == "unbind":
        cat = parts[2]
        here = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        meta = TOPIC_CATEGORIES.get(cat)
        if meta:
            await db.set_setting(cid, meta["setting"], "0")
            await safe_answer(f"🌐 Зона «{meta['title']}» теперь разрешена во всех темах!", show_alert=True)
        txt, kb = await _build_topic_category_card(cid, here, cat, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)

    elif action == "create_topic":
        if admin_rank < 3 and not is_bot_owner(uid):
            return await safe_answer("🔒 Создание тем доступно администраторам беседы!", show_alert=True)

        is_forum = bool(getattr(call.message.chat, "is_forum", False))
        if not is_forum:
            return await safe_answer("⚠️ В группе должен быть включен режим тем (Форум)!", show_alert=True)

        if not can_manage:
            return await safe_answer("⚠️ У бота нет права «Управление темами» в группе!", show_alert=True)

        cat = parts[2] if len(parts) > 2 else "gram"
        here = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

        topic_defs = {
            "gram": ("🎰 Казино", 16766590, "gram_topic"),
            "form": ("📝 Анкеты", 7322096, "form_topic"),
            "sms": ("💬 Общение", 7322096, "sms_topic"),
            "boss": ("🐉 Рейдовые Боссы", 13338331, "boss_topic"),
            "rules": ("📜 Правила", 16766590, "rules_topic"),
        }
        name, color, setting_key = topic_defs.get(cat, ("🎰 Казино", 16766590, "gram_topic"))

        await safe_answer("🪄 Создаю тему...")
        try:
            new_top = await bot.create_forum_topic(cid, name=name, icon_color=color)
            new_tid = new_top.message_thread_id
            await db.set_setting(cid, setting_key, str(new_tid))
            await db.record_chat_topic(cid, new_tid, name)

            if cat == "gram":
                await bot.send_message(
                    cid,
                    "🎰 ✨ <b>ТЕМА «КАЗИНО И ИГРЫ» УСПЕШНО СОЗДАНА!</b> ✨ 🎰\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "🎲 Все игры, слоты, мины, рулетка и ставки теперь проходят строго в этой теме!\n\n"
                    "🎮 <b>Популярные мини-игры:</b>\n"
                    "• 🎰 <code>казик [ставка]</code> — крутить слоты\n"
                    "• 💣 <code>мины [ставка]</code> — опасное минное поле\n"
                    "• 🎡 <code>рулетка [ставка] [цвет/число]</code>\n"
                    "• 📈 <code>краш [ставка]</code> — динамический график\n"
                    "• 🃏 <code>блэкджек [ставка]</code> — 21 очко\n"
                    "• 🎲 <code>кости [ставка]</code> / <code>кубик</code>\n"
                    "• 💰 <code>баланс</code> — проверить баланс монет\n\n"
                    "👑 <i>Приятной игры и больших выигрышей!</i>",
                    message_thread_id=new_tid
                )
            elif cat == "rules":
                await bot.send_message(
                    cid,
                    "📜 ✨ <b>ПРАВИЛА БЕСЕДЫ</b> ✨ 📜\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "1. 🤝 <b>Уважение:</b> относитесь взаимоуважительно ко всем участникам.\n"
                    "2. 🚫 <b>Спам:</b> запрещены несогласованная реклама, флуд и спам-рассылки.\n"
                    "3. 🤬 <b>Токсичность:</b> запрещены оскорбления, травля и провокации.\n\n"
                    "👑 <i>Соблюдайте правила и приятного времяпрепровождения!</i>",
                    message_thread_id=new_tid
                )
            elif cat == "boss":
                await bot.send_message(
                    cid,
                    "🐉 ✨ <b>ТЕМА «РЕЙДОВЫЕ БОССЫ» ПРИВЯЗАНА!</b> ✨ 🐉\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "⚔️ Все рейдовые боссы и битвы будут проходить строго в этой ветке!\n\n"
                    "⏰ <b>Расписание рейдов:</b> 08:00, 12:00, 16:00, 20:00 (МСК)\n"
                    "⚔️ <b>Атаки:</b> <code>ударить</code>, <code>выстрел</code>, <code>атака</code>\n"
                    "🚑 <b>Помощь союзникам:</b> <code>хил @юзер</code> или <code>возродить</code>\n"
                    "🛍 <b>Снаряжение:</b> <code>магазин</code> (мечи, бластеры, броня, аптечки)",
                    message_thread_id=new_tid
                )
            elif cat == "sms":
                await bot.send_message(
                    cid,
                    "💬 ✨ <b>ТЕМА «ОБЩЕНИЕ» НАСТРОЕНА!</b> ✨ 💬\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "Здесь проходит основная переписка участников, анонсы и новости беседы.\n\n"
                    "👋 Приятного общения!",
                    message_thread_id=new_tid
                )

            txt, kb = await _build_topic_category_card(cid, here, cat, author_id=author_id)
            await safe_edit(txt, reply_markup=kb)
            await safe_answer(f"✅ Тема «{name}» создана и привязана!", show_alert=True)
        except Exception as e:
            await safe_answer(f"⚠️ Ошибка создания темы: {e}", show_alert=True)

    elif action == "reset_all":
        here = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        for meta in TOPIC_CATEGORIES.values():
            await db.set_setting(cid, meta["setting"], "0")
        await db.execute("DELETE FROM chat_forum_topics WHERE chat_id=?", (cid,))
        await safe_answer("🗑 Все привязки тем и список веток успешно сброшены!", show_alert=True)
        txt, kb = await render_topics_card_and_kb(cid, here, can_manage=can_manage, author_id=author_id)
        await safe_edit(txt, reply_markup=kb)

    elif action == "auto":
        if admin_rank < 4 and not is_bot_owner(uid):
            return await safe_answer("🔒 Автонастройка доступна администраторам от 4 ранга!", show_alert=True)
        if is_forum:
            await prune_dead_topics(bot, cid)
        cur_sms = await get_sms_topic(cid)
        cur_rules = await get_rules_topic(cid)
        from h_boss import get_boss_topic
        from h_grams import get_gram_topic
        cur_boss = await get_boss_topic(cid)
        cur_gram = await get_gram_topic(cid)
        if cur_sms > 0 or cur_rules > 0 or cur_boss > 0 or cur_gram > 0:
            return await safe_answer(
                "⚠️ У вас уже привязаны темы в группе!\n\n"
                "Пожалуйста, привяжите остальные темы вручную в меню тем, чтобы не создавать копии веток. "
                "Или нажмите «Сбросить всё», если хотите настроить всё с нуля.",
                show_alert=True
            )
        await safe_answer("🪄 Запуск автонастройки...")
        fake_msg = call.message
        await cmd_auto_setup_topics(fake_msg, bot, skip_require=True)


# ================= 11. ГОЛОСОВАНИЯ =================
@router.message(Cmd("голосование", "голос", "опрос", section=S_VOTE,
                    usage="голосование {вопрос}", desc="Создать голосование"))
async def vote_create(message: Message, bot: Bot, args: str = "", **kw):
    if not args:
        return await message.reply("Формат: <code>голосование Забанить спамера?</code>")
    try:
        await bot.send_poll(message.chat.id, question=args[:255],
                            options=["👍 За", "👎 Против"], is_anonymous=False)
    except Exception as e:
        await message.reply(f"⚠️ {html.escape(str(e))}")


@router.message(Cmd("голосование за бан", "вотбан", section=S_VOTE, rank=1,
                    usage="вотбан {ссылка}", desc="Голосование за бан"))
async def vote_ban(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя.")
    try:
        await bot.send_poll(message.chat.id, question=f"Забанить {name}?",
                            options=["👍 Да", "👎 Нет"], is_anonymous=False)
    except Exception as e:
        await message.reply(f"⚠️ {html.escape(str(e))}")


# ================= 12. АНТИСПАМ =================
@router.message(Cmd("спам", "в спам", "антиспам", section=S_SPAM, rank=4,
                    usage="спам {ссылка} {причина}", desc="Добавить в базу спамеров"))
async def spam_add(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя.")
    await db.execute("INSERT OR REPLACE INTO spam_base (user_id,reason,by_id,ts) VALUES (?,?,?,?)",
                     (uid, rest or "спам", message.from_user.id, int(time.time())))
    await message.reply(f"🛰 {mention_id(uid, name)} добавлен в базу спамеров.\n"
                        f"Причина: {html.escape(rest or 'спам')}")


@router.message(Cmd("проверить спам", "проверить на спам", "спам чек", "scam check", "scam", section=S_SPAM, usage="проверить {ссылка}",
                    desc="Проверить по базе спамеров"))
async def spam_check(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя.")
    row = await db.fetchone("SELECT * FROM spam_base WHERE user_id=?", (uid,))
    if row:
        return await message.reply(f"⛔️ {mention_id(uid, name)} <b>в базе спамеров</b>\n"
                                   f"Причина: {html.escape(row['reason'] or '—')}")
    await message.reply(f"✅ {mention_id(uid, name)} не найден в базе спамеров.")


@router.message(Cmd("убрать из спама", section=S_SPAM, rank=4, usage="убрать из спама {ссылка}",
                    desc="Убрать из базы спамеров"))
async def spam_del(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя.")
    await db.execute("DELETE FROM spam_base WHERE user_id=?", (uid,))
    await message.reply(f"✅ {mention_id(uid, name)} убран из базы.")


# ================= 28. ИНЛАЙН =================
@router.inline_query()
async def inline_mode(q: InlineQuery):
    text = (q.query or "").strip()
    results = []
    found = find_commands(text) if text else REGISTRY[:20]
    for i, c in enumerate(found[:30]):
        results.append(InlineQueryResultArticle(
            id=str(i), title="/".join(c.names[:2]),
            description=c.desc or c.usage,
            input_message_content=InputTextMessageContent(
                message_text=f"<b>{html.escape(c.usage)}</b>\n{html.escape(c.desc)}",
                parse_mode="HTML")))
    if not results:
        results = [InlineQueryResultArticle(
            id="none", title="Ничего не найдено",
            input_message_content=InputTextMessageContent(message_text="Команда не найдена"))]
    await q.answer(results, cache_time=10, is_personal=True)


@router.callback_query(F.data == "chk:rights")
async def cb_check_rights(call: CallbackQuery, bot: Bot):
    """Кнопка «Проверить права» из приветствия."""
    me = await bot.me()
    try:
        m = await bot.get_chat_member(call.message.chat.id, me.id)
    except Exception as e:
        return await call.answer(str(e)[:180], show_alert=True)
    if m.status != "administrator":
        return await call.answer(
            "❌ Бот ещё не администратор этой беседы!\n\n"
            "Как выдать:\n"
            "1. Нажмите «Выдать права администратора» и выберите этот чат в списке.\n"
            "2. Либо: Настройки группы ➔ Администраторы ➔ Добавить MOXXI.", show_alert=True)
    need = {
        "🔧 Управление группой": getattr(m, "can_change_info", False),
        "🗑 Удаление сообщений": getattr(m, "can_delete_messages", False),
        "🚫 Блокировка": getattr(m, "can_restrict_members", False),
        "📌 Закрепление": getattr(m, "can_pin_messages", False),
        "🔗 Пригл. по ссылке": getattr(m, "can_invite_users", False),
    }
    missing = [k for k, v in need.items() if not v]
    if missing:
        return await call.answer("Не хватает:\n" + "\n".join(missing), show_alert=True)
    await call.answer("✅ Все права на месте — бот готов!", show_alert=True)


# ================= 32. ИНТЕГРАЦИЯ =================
@router.message(Cmd("проверка", "check", "права", section=S_TG, group_only=True, usage="проверка",
                    desc="Диагностика прав бота"))
async def tg_check(message: Message, bot: Bot, **kw):
    me = await bot.me()
    try:
        m = await bot.get_chat_member(message.chat.id, me.id)
    except Exception as e:
        return await message.reply(f"⚠️ {html.escape(str(e))}")
    adm = m.status == "administrator"
    restrict = bool(getattr(m, "can_restrict_members", False))
    delete = bool(getattr(m, "can_delete_messages", False))
    pin = bool(getattr(m, "can_pin_messages", False))
    invite = bool(getattr(m, "can_invite_users", False))
    manage = bool(getattr(m, "can_change_info", False))
    priv = me.can_read_all_group_messages
    mark = lambda b: "✅" if b else "❌"
    tips = []
    if not adm:
        tips.append("• Выдайте боту права администратора")
    else:
        if not restrict: tips.append("• Право «Блокировка пользователей» — для мутов и банов")
        if not delete: tips.append("• Право «Удаление сообщений» — для чистки")
        if not pin: tips.append("• Право «Закрепление сообщений» — для пина")
        if not invite: tips.append("• Право «Приглашение по ссылке»")
        if not manage: tips.append("• Право «Управление группой»")
    # про Privacy Mode не пишем: он уже настроен, подсказка только мешает
    r = await effective_rank(message, bot)
    await message.reply(
        f"🩺 <b>Диагностика</b>\n\n"
        f"{mark(adm)} Администратор чата\n"
        f"{mark(restrict)} Может банить и мутить\n"
        f"{mark(delete)} Может удалять сообщения\n"
        f"{mark(pin)} Может закреплять\n"
        f"{mark(invite)} Приглашение по ссылке\n"
        f"{mark(manage)} Управление группой\n\n"
        f"Ваш ранг: <b>{rank_label(r) if r else 'Участник'}</b>"
        + (("\n\n<b>Что исправить:</b>\n" + "\n".join(tips)) if tips else "\n\n🎉 Всё настроено!"))


async def get_effective_chat_mode(chat_id: int, is_forum: bool = False) -> str:
    """Возвращает режим чата: 'single' (одиночная), 'topics' (по темам), 'all' (все команды везде)."""
    mode = await db.get_setting(chat_id, "chat_mode", "auto")
    if mode == "auto":
        return "all" if is_forum else "single"
    return mode


def chat_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    def mark(m: str, label: str) -> str:
        return f"🔘 {label}" if current_mode == m else f"⚪️ {label}"

    kb = [
        [InlineKeyboardButton(text=mark("single", "💬 Одиночная группа"), callback_data="cmode:single")],
        [InlineKeyboardButton(text=mark("topics", "📂 Группа по темам (Форум)"), callback_data="cmode:topics")],
        [InlineKeyboardButton(text=mark("all", "🌐 Все команды (Смешанный режим)"), callback_data="cmode:all")],
        [InlineKeyboardButton(text=mark("auto", "🤖 Авто (по типу группы в ТГ)"), callback_data="cmode:auto")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="h:close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Cmd("режим чата", "режим группы", "тип чата", "тип группы", "chat mode", "chatmode",
                    section=S_CHAT, rank=3, group_only=True,
                    usage="режим чата [одиночный / темы / все / авто]",
                    desc="Выбор режима работы команд бота: Одиночный, По темам, Все команды, Авто"))
async def cmd_chat_mode(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return

    arg = (args or "").strip().lower()
    cid = message.chat.id
    is_forum = getattr(message.chat, "is_forum", False)

    if arg in {"одиночный", "одиночная", "single", "1", "монолит", "без тем"}:
        await db.set_setting(cid, "chat_mode", "single")
        return await message.reply(
            "✅ <b>Установлен режим: 💬 Одиночная группа!</b>\n\n"
            "• Работают стандартные команды единого чата (игры, казик, профили, модерация, отношения).\n"
            "• Бот не требует распределения по темам и не блокирует команды.\n"
            "• В меню <code>/help</code> скрыты лишние команды настройки топиков."
        )

    if arg in {"темы", "по темам", "топики", "форум", "topics", "forum", "2"}:
        await db.set_setting(cid, "chat_mode", "topics")
        return await message.reply(
            "✅ <b>Установлен режим: 📂 Группа по темам (Форум)!</b>\n\n"
            "• Доступны все базовые команды и специализированные команды управления темами.\n"
            "• Действует привязка по веткам (игры в теме игр, анкеты в теме описаний)."
        )

    if arg in {"все", "всё", "все команды", "смешанный", "all", "гибрид", "3"}:
        await db.set_setting(cid, "chat_mode", "all")
        return await message.reply(
            "✅ <b>Установлен режим: 🌐 Все команды (Смешанный режим)!</b>\n\n"
            "• Доступны абсолютно все команды (и одиночные, и для тем).\n"
            "• Команды и игры разрешены в любом месте без каких-либо блокировок по веткам!"
        )

    if arg in {"авто", "auto", "по умолчанию", "сброс", "default", "4"}:
        await db.set_setting(cid, "chat_mode", "auto")
        mode_now = "Группа по темам" if is_forum else "Одиночная группа"
        return await message.reply(
            f"✅ <b>Установлен режим: 🤖 Автоматический!</b>\n\n"
            f"Бот сам определяет тип группы в Telegram.\n"
            f"Текущее состояние вашей группы: <b>{mode_now}</b>."
        )

    cur = await db.get_setting(cid, "chat_mode", "auto")
    eff = await get_effective_chat_mode(cid, is_forum)

    mode_names = {
        "auto": "🤖 Авто (по типу группы в ТГ)",
        "single": "💬 Одиночная группа (без разделения на ветки)",
        "topics": "📂 Группа по темам (Форум)",
        "all": "🌐 Все команды (Смешанный — всё разрешено везде)"
    }
    eff_names = {
        "single": "💬 Одиночная группа",
        "topics": "📂 Группа по темам",
        "all": "🌐 Все команды везде"
    }

    txt = (
        f"⚙️ <b>РЕЖИМ РАБОТЫ КОМАНД БОТА В ЧАТЕ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📌 <b>Выбранный режим:</b> <b>{mode_names.get(cur, cur)}</b>\n"
        f"⚡️ <b>Фактический статус:</b> <b>{eff_names.get(eff, eff)}</b>\n"
        f"💬 <b>Тип группы в Telegram:</b> {'Форум (Темы включены)' if is_forum else 'Обычная группа (без тем)'}\n\n"
        f"<b>Описание режимов:</b>\n"
        f"• <b>Одиночная группа:</b> монолитный чат. Все команды работают прямо здесь, бот не требует топиков, раздел настроек тем скрыт из <code>/help</code>.\n"
        f"• <b>Группа по темам:</b> работают и одиночные, и «темные» команды с распределением по веткам.\n"
        f"• <b>Все команды:</b> режим максимальной свободы — все команды работают в любых темах без ограничений.\n\n"
        f"👇 <i>Выберите нужный режим кнопками ниже:</i>"
    )
    await message.reply(txt, reply_markup=chat_mode_keyboard(cur))


@router.callback_query(F.data.startswith("cmode:"))
async def cb_chat_mode(call: CallbackQuery, bot: Bot):
    if not await require(call, bot, 3):
        return await call.answer("🔒 Требуется ранг 3 (Администратор)", show_alert=True)

    mode = call.data.split(":")[1]
    cid = call.message.chat.id
    is_forum = getattr(call.message.chat, "is_forum", False)

    await db.set_setting(cid, "chat_mode", mode)
    eff = await get_effective_chat_mode(cid, is_forum)

    mode_names = {
        "auto": "🤖 Авто (по типу группы в ТГ)",
        "single": "💬 Одиночная группа (без разделения на ветки)",
        "topics": "📂 Группа по темам (Форум)",
        "all": "🌐 Все команды (Смешанный — всё разрешено везде)"
    }
    eff_names = {
        "single": "💬 Одиночная группа",
        "topics": "📂 Группа по темам",
        "all": "🌐 Все команды везде"
    }

    txt = (
        f"⚙️ <b>РЕЖИМ РАБОТЫ КОМАНД БОТА В ЧАТЕ</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📌 <b>Выбранный режим:</b> <b>{mode_names.get(mode, mode)}</b>\n"
        f"⚡️ <b>Фактический статус:</b> <b>{eff_names.get(eff, eff)}</b>\n"
        f"💬 <b>Тип группы в Telegram:</b> {'Форум (Темы включены)' if is_forum else 'Обычная группа (без тем)'}\n\n"
        f"<b>Описание режимов:</b>\n"
        f"• <b>Одиночная группа:</b> монолитный чат. Все команды работают прямо здесь, бот не требует топиков, раздел настроек тем скрыт из <code>/help</code>.\n"
        f"• <b>Группа по темам:</b> работают и одиночные, и «темные» команды с распределением по веткам.\n"
        f"• <b>Все команды:</b> режим максимальной свободы — все команды работают в любых темах без ограничений.\n\n"
        f"👇 <i>Выберите нужный режим кнопками ниже:</i>"
    )
    try:
        await call.message.edit_text(txt, reply_markup=chat_mode_keyboard(mode))
    except Exception:
        pass
    await call.answer(f"Режим обновлен: {mode}")
