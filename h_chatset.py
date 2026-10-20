"""Разделы 3,4,6,7,8,9,10,11,12,28,32: анкета, статистика, настройки чата,
триггеры, доступ команд, сетка, темы, голосования, антиспам, инлайн, интеграция."""
from __future__ import annotations

import html
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineQuery, InlineQueryResultArticle,
                           InputTextMessageContent, Message)

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
    """Форматирует любой пользовательский текст правил в стильную эстетичную карточку."""
    title = html.escape(chat_title or "Беседа")
    content = (raw_rules or "").strip()

    if len(content) > 3400:
        content = content[:3400] + "…\n<i>(текст правил сокращён)</i>"

    card = (
        f"📜 ✨ <b>ПРАВИЛА БЕСЕДЫ · {title}</b> ✨ 📜\n"
        f"✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        f"<blockquote>✨ <b>Настоящие правила обязательны к исполнению всеми участниками сообщества.</b>\n"
        f"Незнание правил не освобождает от ответственности!</blockquote>\n\n"
        f"<blockquote expandable>{content}</blockquote>\n\n"
        f"✦ ══════════════════════════════ ✦\n"
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


@router.message(Cmd("+правила", "установить правила", "сохранить правила", "задать правила", "изменить правила",
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


@router.message(Cmd("изучить правила", "запомнить правила", "проанализировать правила", "проверить правила",
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


@router.message(Cmd("-правила", "сбросить правила", "удалить правила",
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



@router.message(Cmd("автонастройка", "автонастройка группы", "автонастройка чата", "автосетап", "автонастройка тем",
                    section=S_TOPIC, rank=4, usage="автонастройка",
                    desc="🪄 Автоматически создать и привязать темы: Общение, Правила, Боссы"))
async def cmd_auto_setup_topics(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
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

    status_msg = await message.reply("🪄 <b>Запуск автонастройки группы...</b>\nСоздаю темы и настраиваю привязки, пожалуйста, подождите...")

    try:
        # Создаем тему "💬 Общение"
        topic_chat = await bot.create_forum_topic(chat_id=cid, name="💬 Общение", icon_color=7322096)
        await asyncio.sleep(0.5)

        # Создаем тему "📜 Правила"
        topic_rules = await bot.create_forum_topic(chat_id=cid, name="📜 Правила", icon_color=16766590)
        await asyncio.sleep(0.5)

        # Создаем тему "🐉 Рейдовые Боссы"
        topic_boss = await bot.create_forum_topic(chat_id=cid, name="🐉 Рейдовые Боссы", icon_color=13338331)
        await asyncio.sleep(0.5)

        # Сохраняем настройки в базу данных
        await db.set_setting(cid, "sms_topic", str(topic_chat.message_thread_id))
        await db.set_setting(cid, "boss_topic", str(topic_boss.message_thread_id))
        await db.set_setting(cid, "rules_topic", str(topic_rules.message_thread_id))

        # Отправляем приветственные сообщения в темы
        # 1. В тему общения
        await bot.send_message(
            cid,
            "💬 ✨ <b>ТЕМА «ОБЩЕНИЕ» УСПЕШНО НАСТРОЕНА!</b> ✨ 💬\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Здесь проходит основная переписка участников, анонсы и новости беседы.\n\n"
            "👋 Приятного общения!",
            message_thread_id=topic_chat.message_thread_id
        )

        # 2. В тему правил
        await bot.send_message(
            cid,
            "📜 ✨ <b>ПРАВИЛА БЕСЕДЫ</b> ✨ 📜\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "1. 🤝 <b>Уважение:</b> относитесь взаимоуважительно ко всем участникам.\n"
            "2. 🚫 <b>Спам:</b> запрещены несогласованная реклама, флуд и спам-рассылки.\n"
            "3. 🤬 <b>Токсичность:</b> запрещены оскорбления, травля и провокации.\n"
            "4. 🐉 <b>Рейды:</b> битвы с боссами проводятся исключительно в теме «🐉 Рейдовые Боссы».\n\n"
            "👑 <i>Соблюдайте правила и приятного времяпрепровождения!</i>",
            message_thread_id=topic_rules.message_thread_id
        )

        # 3. В тему рейдовых боссов
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
            message_thread_id=topic_boss.message_thread_id
        )

        from h_userinfo import topic_link
        summary = (
            "🎉 🌟 <b>АВТОНАСТРОЙКА ГРУППЫ УСПЕШНО ЗАВЕРШЕНА!</b> 🌟 🎉\n"
            "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
            "Бот автоматически создал и привязал все необходимые темы:\n\n"
            f"┌ 💬 <b>Общение:</b> {topic_link(cid, topic_chat.message_thread_id)} (привязана для общения)\n"
            f"├ 📜 <b>Правила:</b> {topic_link(cid, topic_rules.message_thread_id)} (опубликованы правила)\n"
            f"└ 🐉 <b>Рейдовые Боссы:</b> {topic_link(cid, topic_boss.message_thread_id)} (привязана для рейдов)\n\n"
            "✦ ══════════════════════════════ ✦\n"
            "🚀 <b>Группа полностью настроена и готова к активному общению и битвам!</b>"
        )
        await status_msg.edit_text(summary, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"⚠️ Ошибка при создании тем: {html.escape(str(e))}")


@router.message(Cmd("тема смс", "тема общения", "тема чата", "тема анонсов",
                    "+тема смс", "+тема общения", "+тема чата", "+тема анонсов",
                    section=S_TOPIC, rank=1,
                    usage="тема смс", desc="Привязать текущую тему для СМС, общения и анонсов"))
async def cmd_set_sms_topic(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 1):
        return

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем анонсы и сообщения отправляются прямо в основной чат.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    here = int(getattr(message, "message_thread_id", None) or 0)
    if not here:
        return await message.reply("⚠️ Напишите эту команду внутри темы «СМС», чтобы привязать её.")
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

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем правила показываются прямо в основном чате.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    here = int(getattr(message, "message_thread_id", None) or 0)
    if not here:
        return await message.reply("⚠️ Напишите эту команду внутри ветки форума «Правила», чтобы привязать её.")
    await db.set_setting(message.chat.id, "rules_topic", str(here))
    await message.reply(
        f"✅ <b>Тема «Правила» успешно установлена!</b>\n"
        f"ID темы: <code>{here}</code>\n"
        f"Теперь кнопка в карточке правил будет ссылаться на эту тему.")


# ================= 10. ТЕМЫ МОДЕРАТОРОВ =================
@router.message(Cmd("тема", "темы", section=S_TOPIC, rank=1, usage="тема",
                    desc="Что настроено в этой теме"))
async def topic(message: Message, bot: Bot, args: str = "", **kw):
    """Показывает назначение ИМЕННО той темы, где написана команда.

    Раньше здесь была общая заметка на весь чат, из-за чего в теме
    описаний могло показываться «граммы». Теперь бот смотрит,
    что реально привязано к текущей теме.
    """
    if not await require(message, bot, 1):
        return

    here = int(getattr(message, "message_thread_id", None) or 0)

    from h_userinfo import get_form_topic, topic_link
    from h_grams import get_gram_topic
    from h_boss import get_boss_topic
    form_t = await get_form_topic(message.chat.id)
    gram_t = await get_gram_topic(message.chat.id)
    sms_t = await get_sms_topic(message.chat.id)
    boss_t = await get_boss_topic(message.chat.id)

    if args:
        # старое поведение: подписать текущую тему вручную
        key = f"topic_note:{here}" if here else "topic"
        await db.set_setting(message.chat.id, key, args)
        return await message.reply(
            f"🧵 Подпись для этой темы: <b>{html.escape(args)}</b>")

    if here and here == form_t:
        return await message.reply(
            "📝 <b>Эта тема: описания</b>\n\n"
            "Здесь новички заполняют анкету.\n"
            "Всё, кроме анкет, удаляется.\n\n"
            "Заполнить: <code>+описание</code> или <code>шаблон</code>")

    if here and here == gram_t:
        return await message.reply(
            "🌑 <b>Эта тема: монеты, бизнесы и игры</b>\n\n"
            "Здесь работают команды монет и рынок.\n"
            "Баланс: <code>б</code> · Игры: <code>игры</code>\n"
            "Бизнесы: <code>бизнесы</code> · Бонус: <code>бонус</code>")

    if here and here == boss_t:
        return await message.reply(
            "🐉 <b>Эта тема: рейдовые боссы</b>\n\n"
            "Здесь проходят регулярные рейды и коллективные битвы с боссами!\n"
            "Атака: <code>ударить</code> · Инфо: <code>босс</code>\n"
            "Помощь: <code>хил</code> · Аптечка: <code>аптечка</code>")

    if here and here == sms_t:
        return await message.reply(
            "💬 <b>Эта тема: СМС и основное общение</b>\n\n"
            "Здесь проходит основная переписка участников, публикуются новости и анонсы обновлений.")

    # прочие темы — показываем подпись и общую карту настроек
    note = await db.get_setting(message.chat.id, f"topic_note:{here}", "")
    if not note and not here:
        note = await db.get_setting(message.chat.id, "topic", "")

    lines = ["🧵 <b>Эта тема: обычное общение</b>"]
    if note:
        lines.append(f"Подпись: <b>{html.escape(note)}</b>")
    lines.append("")
    lines.append("<b>Настроенные темы чата:</b>")
    lines.append(f"💬 СМС: "
                 + (topic_link(message.chat.id, sms_t) if sms_t else "не задана (напишите <code>тема смс</code>)"))
    lines.append(f"🐉 Боссы: "
                 + (topic_link(message.chat.id, boss_t) if boss_t else "не задана (напишите <code>+тема босс</code>)"))
    lines.append(f"📝 Описания: "
                 + (topic_link(message.chat.id, form_t) if form_t else "не задана"))
    lines.append(f"🌑 Монеты: "
                 + (topic_link(message.chat.id, gram_t) if gram_t else "не задана"))
    await message.reply("\n".join(lines), disable_web_page_preview=True)


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


@router.message(Cmd("проверить", "чек", "scam", section=S_SPAM, usage="проверить {ссылка}",
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
