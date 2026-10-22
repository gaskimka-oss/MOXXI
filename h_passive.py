"""Пассивные обработчики: вход в группу, запрос прав, автовыдача ранга владельцу,
приветствие участников, триггеры, учёт активности.
Подключается ПОСЛЕДНИМ, чтобы не перехватывать команды."""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.types import (CallbackQuery, ChatMemberUpdated, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
from config import MSG_REWARD, MSG_REWARD_COOLDOWN, XP_PER_MESSAGE
from core_ranks import get_rank, require, set_rank
from core_registry import Cmd, MAX_RANK, RANK_NAMES, stars
from utils import mention, mention_id, money

router = Router(name="passive")

# Права, которые бот просит при добавлении в группу.
# Telegram сам покажет чекбоксы при выдаче админки по этой ссылке.
NEEDED_RIGHTS = (
    "change_info+delete_messages+restrict_members+invite_users+pin_messages+manage_chat"
)

RIGHTS_TEXT = """👋 <b>Спасибо за добавление!</b>

Чтобы команды работали без слэша (<code>бан</code>, <code>мут</code>, <code>команды</code>) и бот видел сообщения, выдайте мне права администратора:

🔧 <b>Управление группой</b>
🗑 <b>Удаление сообщений</b>
🚫 <b>Блокировка пользователей</b>
📌 <b>Закрепление сообщений</b>
🔗 <b>Приглашение по ссылке</b>

👇 <b>Как выдать права:</b>
• <b>Способ 1:</b> Нажмите кнопку ниже ➔ <u>выберите в списке этот чат</u> ➔ Telegram сразу откроет галочки прав!
• <b>Способ 2 (вручную):</b> <i>Настройки группы → Администраторы → Добавить администратора → MOXXI</i>."""


def _rights_kb(bot_username: str, chat_id: int) -> InlineKeyboardMarkup:
    """Кнопка добавления бота админом с уже отмеченными правами."""
    url = (f"https://t.me/{bot_username}?startgroup&admin={NEEDED_RIGHTS}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Выдать права администратора", url=url)],
        [InlineKeyboardButton(text="🩺 Проверить права", callback_data="chk:rights")],
    ])


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_added(event: ChatMemberUpdated, bot: Bot):
    """Бота добавили в группу: просим права и выдаем высший ранг создателю."""
    if event.chat.type not in {"group", "supergroup"}:
        return
    await db.register_chat(event.chat.id, event.chat.title)
    await db.track_daily_group_add(event.chat.id)

    creator_info = ""
    try:
        admins = await bot.get_chat_administrators(event.chat.id)
        for adm in admins:
            if adm.status == "creator" and adm.user and not adm.user.is_bot:
                await set_rank(event.chat.id, adm.user.id, MAX_RANK, by=0)
                await db.touch_user(adm.user.id, adm.user.username, adm.user.first_name)
                creator_info = f"\n\n👑 <b>Создателю беседы {mention_id(adm.user.id, adm.user.first_name)} присвоен высший ранг: ⭐⭐⭐⭐⭐⭐⭐ Лидер чата!</b>"
                break
    except Exception:
        pass

    me = await bot.me()
    text = RIGHTS_TEXT + creator_info
    text += "\n\n📖 <code>команды</code> — все возможности\n🔐 <code>ДК</code> — доступ команд"

    try:
        await bot.send_message(event.chat.id, text,
                               reply_markup=_rights_kb(me.username, event.chat.id),
                               disable_web_page_preview=True)
    except Exception:
        pass


@router.my_chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_MEMBER))
async def on_rights_changed(event: ChatMemberUpdated, bot: Bot):
    """Боту изменили права — подтверждаем, чего не хватает."""
    new = event.new_chat_member
    if getattr(new, "status", "") != "administrator":
        return
    missing = []
    if not getattr(new, "can_delete_messages", False):
        missing.append("🗑 Удаление сообщений")
    if not getattr(new, "can_restrict_members", False):
        missing.append("🚫 Блокировка пользователей")
    if not getattr(new, "can_pin_messages", False):
        missing.append("📌 Закрепление сообщений")
    if not getattr(new, "can_invite_users", False):
        missing.append("🔗 Приглашение по ссылке")
    if not getattr(new, "can_change_info", False):
        missing.append("🔧 Управление группой")

    try:
        if missing:
            await bot.send_message(
                event.chat.id,
                "⚠️ Я администратор, но не хватает прав:\n" + "\n".join(f"• {m}" for m in missing)
                + "\n\nБез них часть команд работать не будет.")
        else:
            await bot.send_message(
                event.chat.id,
                "✅ Все права получены — я полностью готов к работе!\n"
                "📖 <code>команды</code> · 🔐 <code>ДК</code> · 🩺 <code>проверка</code>")
    except Exception:
        pass


@router.my_chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_removed(event: ChatMemberUpdated):
    await db.execute("DELETE FROM chats WHERE chat_id=?", (event.chat.id,))


@router.message(F.new_chat_members)
async def on_new_members(message: Message, bot: Bot):
    me = await bot.me()
    tmpl = await db.get_setting(message.chat.id, "greeting")
    for u in message.new_chat_members or []:
        if u.id == me.id or u.is_bot:
            continue
        await db.touch_user(u.id, u.username, u.first_name)
        try:
            import core_members
            await core_members.remember_member(message.chat.id, u.id, "member", True)
        except Exception:
            pass
        # Проверка включена ли капча «Я человек»
        captcha_on = (await db.get_setting(message.chat.id, "captcha", "0") == "1")
        if captcha_on:
            from h_mod_bans import MUTE_OFF
            try:
                await bot.restrict_chat_member(message.chat.id, u.id, MUTE_OFF)
            except Exception:
                pass
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🤖 Я человек, впустите! ✅", callback_data=f"cpt:{message.chat.id}:{u.id}")
            ]])
            c_msg = await message.answer(
                f"👋 Приветствуем, {mention(u)}!\n\n"
                f"🛡 <b>В чате включена капча-защита от ботов.</b>\n"
                f"Нажмите кнопку ниже в течение 3 минут, чтобы подтвердить, что вы человек, и получить право писать в чат:",
                reply_markup=kb
            )
            import asyncio as _a
            _a.create_task(_del_later(c_msg, 180))
            continue

        # Специальное приветствие для официального чата сообщества Moxxi
        comm_chat = await db.get_global_setting("global_community_chat", "")
        chat_u = getattr(message.chat, "username", "") or ""
        is_official = False
        if comm_chat:
            if str(message.chat.id) == comm_chat:
                is_official = True
            elif chat_u and (f"@{chat_u.lower()}" == comm_chat.lower() or f"https://t.me/{chat_u.lower()}" == comm_chat.lower()):
                is_official = True
        if chat_u.lower() == "moxxi_chat":
            is_official = True

        if is_official:
            card = (
                f"💜 ✨ <b>ДОБРО ПОЖАЛОВАТЬ В MOXXI COMMUNITY!</b> ✨ 💜\n"
                f"✦ ════════ • ⊰ 💖 🔮 🎰 🏢 ⚔️ 🪙 👑 ⊱ • ════════ ✦\n\n"
                f"👋 Приветствуем тебя в нашем официальном чате, {mention(u)}!\n"
                f"Ты попал в эпицентр азарта, клановых войн, экономики и умного ИИ!\n\n"
                f"🔮 <b>Навигация по темам сообщества:</b>\n"
                f"• 💬 <b>Общение</b> — знакомства, флуд, поиск союзников и кланов;\n"
                f"• 🤖 <b>Команды & ИИ</b> — тесты команд и ответы ИИ-помощника;\n"
                f"• 💡 <b>Идеи & Фидбек</b> — ваши предложения для обновлений;\n"
                f"• ⭐ <b>Отзывы & Звёзды</b> — честные отзывы игроков о покупках.\n\n"
                f"🎁 <b>Быстрый старт для новичка:</b>\n"
                f"• <code>бонус</code> — забрать ежедневный куш (до 30 000 🪙);\n"
                f"• <code>рулетка</code> — крутить Колесо Фортуны раз в день бесплатно;\n"
                f"• <code>квесты</code> — 3 ежедневных задания за щедрую награду;\n"
                f"• <code>меню</code> — открыть интерактивное главное меню.\n\n"
                f"🤖 <b>Нужна помощь?</b> Просто напиши <code>ии [твой вопрос]</code> в ветке команд или ответь на сообщение бота!\n"
                f"✦ ══════════════════════════════════ ✦\n"
                f"🍷 <i>Желаем приятного отдыха, верных друзей и лёгких побед!</i>"
            )
            comm_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎁 Забрать бонус", url=f"https://t.me/{me.username}?start=bonus"),
                    InlineKeyboardButton(text="🤖 Задать вопрос ИИ", switch_inline_query_current_chat="ии как начать игру?")
                ],
                [
                    InlineKeyboardButton(text="📜 Правила сообщества", callback_data="chat_rules_btn"),
                    InlineKeyboardButton(text="📖 Меню бота", url=f"https://t.me/{me.username}?start=menu")
                ]
            ])
            await message.answer(card, reply_markup=comm_kb)
            continue

        ai_welc = (await db.get_setting(message.chat.id, "ai_welcome", "0") == "1")
        if ai_welc:
            try:
                from h_ai_features import generate_ai_welcome
                w_text = await generate_ai_welcome(u.first_name or "Боец", message.chat.title or "наш чат")
                await message.answer(f"{mention(u)}, {w_text}")
            except Exception:
                bal = (await db.get_user(u.id))["balance"]
                await message.answer(f"👋 Добро пожаловать, {mention(u)}!\n"
                                     f"🍬 Стартовый баланс: <b>{money(bal)}</b> — /команды")
        elif tmpl:
            text = (tmpl.replace("%имя%", html.escape(u.first_name or ""))
                        .replace("%чат%", html.escape(message.chat.title or "")))
            await message.answer(text)
        else:
            bal = (await db.get_user(u.id))["balance"]
            await message.answer(f"👋 Добро пожаловать, {mention(u)}!\n"
                                 f"🍬 Стартовый баланс: <b>{money(bal)}</b> — /команды")

        import time as _t
        await db.execute(
            "INSERT OR IGNORE INTO first_seen (chat_id, user_id, ts) VALUES (?,?,?)",
            (message.chat.id, u.id, int(_t.time())))

        from h_userinfo import (TEMPLATE, get_form_topic, needs_form,
                                topic_link)
        if await needs_form(message.chat.id, u.id):
            ft = await get_form_topic(message.chat.id)
            # Шаблон шлём ТОЛЬКО в тему описаний. В общий чат — короткую
            # ссылку, чтобы не засорять его простынёй из анкеты.
            try:
                if ft:
                    hello = await message.bot.send_message(
                        message.chat.id,
                        f"📝 {mention(u)}, добро пожаловать!\n\n"
                        f"Чтобы писать в чат, заполните описание:\n"
                        f"<code>{TEMPLATE}</code>",
                        message_thread_id=ft,
                        disable_web_page_preview=True)
                    import asyncio as _a
                    _a.create_task(_del_later(hello, 600))
                else:
                    hello = await message.answer(
                        f"📝 {mention(u)}, заполните описание, чтобы писать "
                        f"в чат.\n\n<code>{TEMPLATE}</code>",
                        disable_web_page_preview=True)
                    import asyncio as _a
                    _a.create_task(_del_later(hello, 300))
            except Exception:
                pass


async def _del_later(msg, delay: int = 60) -> None:
    try:
        import asyncio
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ================== КАПЧА: ОБРАБОТЧИКИ И КОМАНДЫ ==================

@router.callback_query(F.data.startswith("cpt:"))
async def cb_captcha_verify(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[1])
    uid = int(parts[2])
    if call.from_user.id != uid:
        return await call.answer("⛔️ Эта проверка предназначена для другого участника!", show_alert=True)
    from h_mod_bans import MUTE_ON
    try:
        await bot.restrict_chat_member(cid, uid, MUTE_ON)
    except Exception:
        pass
    await call.answer("✅ Проверка успешно пройдена! Добро пожаловать!", show_alert=False)
    try:
        await call.message.edit_text(f"✅ {mention(call.from_user)} успешно прошёл проверку «Я человек»! Добро пожаловать в чат! 🎉")
    except Exception:
        pass
    import asyncio as _a
    _a.create_task(_del_later(call.message, 5))


@router.message(Cmd("капча", "защита от ботов", "антибот", section=6, rank=3,
                    usage="капча вкл|выкл", desc="Проверка новых участников кнопкой «Я человек»"))
async def cmd_captcha_toggle(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 3):
        return
    a = (args or "").strip().lower()
    if a in {"вкл", "on", "1", "да"}:
        await db.set_setting(message.chat.id, "captcha", "1")
        return await message.reply("🛡 <b>Капча включена!</b>\nНовые участники будут замьючены, пока не нажмут кнопку «✅ Я человек».")
    if a in {"выкл", "off", "0", "нет"}:
        await db.set_setting(message.chat.id, "captcha", "0")
        return await message.reply("⚪️ <b>Капча выключена.</b> Новые участники сразу могут писать в чат.")
    cur = await db.get_setting(message.chat.id, "captcha", "0")
    state = "🟢 включена" if cur == "1" else "🔴 выключена"
    await message.reply(
        f"🤖 <b>Защита от ботов (Капча):</b> {state}\n\n"
        f"Включить: <code>капча вкл</code>\n"
        f"Выключить: <code>капча выкл</code>"
    )


async def transcribe_voice(message: Message, bot: Bot) -> None:
    """Слушает голосовое или кружок и присылает текст ответом.

    Само сообщение не трогаем — просто добавляем расшифровку,
    чтобы можно было прочитать, если некогда слушать.
    """
    try:
        import core_stt as stt
        if not stt.available():
            return
        if await db.get_setting(message.chat.id, "stt", "1") != "1":
            return

        obj = message.voice or message.video_note
        if obj is None:
            return
        if (obj.duration or 0) > stt.MAX_SECONDS:
            return
        if (obj.file_size or 0) > stt.MAX_BYTES:
            return

        f = await bot.get_file(obj.file_id)
        buf = await bot.download_file(f.file_path)
        audio = buf.read()
        name = "voice.ogg" if message.voice else "circle.mp4"

        text = await stt.transcribe(audio, name)
        if not text:
            return

        kind = "🎙 Голосовое" if message.voice else "⭕️ Кружок"
        who = mention(message.from_user)
        mm, ss = divmod(int(obj.duration or 0), 60)
        dur = f"{mm}:{ss:02d}"
        body = html.escape(text[:3500])
        try:
            await message.reply(
                f"{kind} от {who} · {dur}\n\n💬 {body}",
                disable_web_page_preview=True)
        except Exception:
            pass
    except Exception as e:
        import logging
        logging.getLogger("irisbot").warning("расшифровка: %s", str(e)[:150])


# ── Медиа от тех, кто без описания ──────────────────────────────────
MEDIA_BLOCK = (F.voice | F.video_note | F.sticker | F.animation | F.photo
               | F.video | F.audio | F.document)


@router.message(MEDIA_BLOCK)
async def media_gate(message: Message, bot: Bot):
    """Пока описание не заполнено — никаких кружочков, голосовых и медиа."""
    if message.chat.type == "private":
        return
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id

    # Проверка ночного режима («Тихий час»: запрет стикеров/медиа)
    try:
        from h_nightmode import check_night_restrictions
        if await check_night_restrictions(message, bot):
            return
    except Exception:
        pass

    from core_ranks import effective_rank
    from config import OWNER_ID
    is_staff = (uid == OWNER_ID) or (await effective_rank(message, bot) >= 1)
    if is_staff or message.reply_to_message:
        if message.voice or message.video_note:
            import asyncio as _a
            from h_ai_features import process_voice_message
            _a.create_task(process_voice_message(message, bot))
        return

    from h_userinfo import (get_form_topic, needs_form, topic_id,
                                   topic_link)
    if not await needs_form(message.chat.id, uid):
        # голосовое или кружок — расшифруем в текст
        if message.voice or message.video_note:
            import asyncio as _a
            from h_ai_features import process_voice_message
            _a.create_task(process_voice_message(message, bot))
        return

    try:
        await message.delete()
    except Exception:
        pass

    if await db.cooldown_left(uid, "form_media", 90):
        return
    await db.set_cooldown(uid, "form_media")
    ft = await get_form_topic(message.chat.id)
    link = topic_link(message.chat.id, ft) if ft else ""
    try:
        warn = await message.bot.send_message(
            message.chat.id,
            f"🔇 {mention(message.from_user)}, голосовые, кружочки и медиа "
            f"будут доступны после описания.\n\n"
            + (f"✍️ Заполнить: {link}" if link else
               "✍️ Заполнить: команда <code>шаблон</code>"),
            message_thread_id=ft or None,
            disable_web_page_preview=True)
        import asyncio as _a
        _a.create_task(_del_later(warn, 60))
    except Exception:
        pass


@router.message(F.text | F.caption)
async def activity(message: Message, bot: Bot):
    """XP, монеты, триггеры и проверка обязательной анкеты."""
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    text_raw = (message.text or message.caption or "").strip()

    # --- проверка ночного режима («Тихий час»: кулдаун сообщений) ---
    try:
        from h_nightmode import check_night_restrictions
        if await check_night_restrictions(message, bot):
            return
    except Exception:
        pass

    # --- буфер для контекста в логах модерации ---
    try:
        import core_modlog as _ml
        await _ml.remember(message)
    except Exception:
        pass

    # --- автомодерация: оскорбления и мат ---
    try:
        from h_automod import handle as _automod
        if await _automod(message, bot):
            return
    except Exception:
        pass

    # --- автообразец для темы команд (ИИ + команды) ---
    try:
        from h_community_support import check_and_send_commands_sample
        if await check_and_send_commands_sample(message, bot):
            pass
    except Exception:
        pass

    # --- присланная анкета: сохраняем в любом чате ----------------------
    from h_userinfo import (LINE_RE as _LR, parse_form as _pf,
                                   _save_form as _sf, _split_lines as _sl,
                                   looks_like_form as _lf,
                                   is_topping_up as _top)
    _lines = _sl(text_raw)
    _hits = sum(1 for l in _lines if _LR.match(l.strip()))
    if len(_lines) >= 2 and _hits >= 2:
        if _pf(text_raw):
            await _sf(message, text_raw)
            return
    # дозаполнение начатой анкеты: «☆ Айди: 123» одной строкой
    elif _hits >= 1:
        _d = _pf(text_raw)
        if _d and await _top(uid, _d):
            await _sf(message, text_raw)
            return

    # --- обязательная анкета -------------------------------------------
    if message.chat.type != "private":
        from core_ranks import effective_rank
        from config import OWNER_ID
        is_staff = (uid == OWNER_ID) or (await effective_rank(message, bot) >= 1)
        is_reply = message.reply_to_message is not None

        # Стафф (хелперы, модераторы, админы, владелец) и ответы на сообщения НИКОГДА не блокируются
        if not is_staff and not is_reply:
            from h_userinfo import (LINE_RE, TEMPLATE, _save_form,
                                           _split_lines, get_form_topic,
                                           is_topping_up, looks_like_form,
                                           needs_form, parse_form,
                                           topic_id, topic_link)
            if await needs_form(message.chat.id, uid):
                form_topic = await get_form_topic(message.chat.id)
                here = topic_id(message)
                in_form_topic = (not form_topic) or (here == form_topic)

                # анкету принимаем только в назначенной теме
                lines = _split_lines(text_raw)
                hits = sum(1 for l in lines if LINE_RE.match(l.strip()))
                # в теме описаний принимаем свободный рассказ и дозаполнение
                if in_form_topic and (
                        hits >= 2 or looks_like_form(text_raw)
                        or (hits >= 1 and await is_topping_up(
                            uid, parse_form(text_raw)))):
                    await _save_form(message, text_raw)
                    return

                try:
                    await message.delete()
                except Exception:
                    pass

                if not await db.cooldown_left(uid, "form_warn", 60):
                    await db.set_cooldown(uid, "form_warn")
                    if in_form_topic:
                        note = (f"📝 {mention(message.from_user)}, чтобы писать в чате, "
                                f"сначала заполните описание.\n\n"
                                f"Скопируйте, заполните и отправьте сюда:\n\n"
                                f"<code>{TEMPLATE}</code>")
                        target_thread = here or None
                    else:
                        link = topic_link(message.chat.id, form_topic)
                        note = (f"📝 {mention(message.from_user)}, вам пока нельзя "
                                f"писать здесь.\n\n"
                                f"✍️ <b>Сначала заполните описание:</b>\n{link}")
                        target_thread = here or None
                    try:
                        warn = await message.bot.send_message(
                            message.chat.id, note,
                            message_thread_id=target_thread,
                            disable_web_page_preview=True)
                        import asyncio as _a
                        _a.create_task(_del_later(warn, 90))
                    except Exception:
                        try:
                            await message.answer(note, disable_web_page_preview=True)
                        except Exception:
                            pass
                return
            else:
                # Описание уже заполнено: закрываем тему описаний для обычных участников (ранг < 3)
                form_topic = await get_form_topic(message.chat.id)
                if form_topic and topic_id(message) == form_topic:
                    from core_ranks import effective_rank
                    staff_r = await effective_rank(message, bot)
                    if staff_r < 3:
                        try:
                            await message.delete()
                        except Exception:
                            pass
                        if not await db.cooldown_left(uid, "form_done_lock", 60):
                            await db.set_cooldown(uid, "form_done_lock")
                            note = (f"🔒 {mention(message.from_user)}, ваше описание уже принято и сохранено!\n\n"
                                    f"Тема описаний закрыта для общения.\n"
                                    f"Вы можете свободно общаться в остальных темах беседы!")
                            try:
                                warn = await message.bot.send_message(
                                    message.chat.id, note,
                                    message_thread_id=form_topic,
                                    disable_web_page_preview=True)
                                import asyncio as _a
                                _a.create_task(_del_later(warn, 60))
                            except Exception:
                                pass
                        return
    await db.add_xp(uid, XP_PER_MESSAGE)
    # Фиксация суточной активности и прогресса квестов игрока
    try:
        await db.track_daily_activity(uid, action="msg", is_group=(message.chat.type != "private"))
        await db.update_quest_progress(uid, "chat_msgs", 1)
    except Exception:
        pass

    if message.chat.type != "private":
        # Автоматическое запоминание активной темы общения, если sms_topic ещё не задан
        tid = int(getattr(message, "message_thread_id", None) or 0)
        if tid and tid > 1:
            cur_sms = await db.get_setting(message.chat.id, "sms_topic", "0")
            if cur_sms == "0":
                from h_userinfo import get_form_topic
                from h_grams import get_gram_topic
                ft = await get_form_topic(message.chat.id)
                gt = await get_gram_topic(message.chat.id)
                if tid != ft and tid != gt:
                    await db.set_setting(message.chat.id, "sms_topic", str(tid))

        await db.bump_chat_stat(message.chat.id, uid, XP_PER_MESSAGE)
        import time as _t
        await db.execute(
            "INSERT INTO daily_stats (day, chat_id, user_id, messages) VALUES (?,?,?,1) "
            "ON CONFLICT(day, chat_id, user_id) DO UPDATE SET messages = messages + 1",
            (_t.strftime("%Y-%m-%d"), message.chat.id, uid))
        await db.execute(
            "INSERT OR IGNORE INTO first_seen (chat_id, user_id, ts) VALUES (?,?,?)",
            (message.chat.id, uid, int(_t.time())))
    if not await db.cooldown_left(uid, "msg_reward", MSG_REWARD_COOLDOWN):
        await db.add_balance(uid, MSG_REWARD)
        await db.set_cooldown(uid, "msg_reward")

    raw_txt = (message.text or message.caption or "").strip()
    # ── ИИ-Автоответчик в теме команд и по вопросам новичков ────────────────
    if message.chat.type != "private" and raw_txt and not (message.from_user and message.from_user.is_bot):
        if not raw_txt.startswith(("/", "!", ".")):
            cmd_t = await db.get_setting(message.chat.id, "commands_topic", "0")
            tid = getattr(message, "message_thread_id", None) or 0
            global_c_chat = await db.get_global_setting("global_commands_chat", "")
            global_c_topic = await db.get_global_setting("global_commands_topic", "")
            if not global_c_topic:
                global_c_topic = await db.get_global_setting("global_commands_chat_topic", "")

            is_cmd_topic = False
            if cmd_t != "0" and str(tid) == cmd_t:
                is_cmd_topic = True
            elif global_c_chat and str(message.chat.id) == global_c_chat:
                if not global_c_topic or str(tid) == global_c_topic:
                    is_cmd_topic = True

            low_text = raw_txt.lower()
            starts_as_question = any(low_text.startswith(p) for p in (
                "как сделать ", "как работает ", "как грабить", "как завести ", "как играть ",
                "как заработать ", "как поднять ", "как купить ", "как создать ", "как перевести ",
                "как настроить ", "как получить ", "что делает команда ", "подскажите как "
            ))

            if is_cmd_topic or starts_as_question:
                # Если включен образец оформления темы
                sample_on = (await db.get_setting(message.chat.id, "sample_topic_enabled", "0") == "1")
                if sample_on and not await db.cooldown_left(uid, "sample_hint_cd", 180):
                    await db.set_cooldown(uid, "sample_hint_cd")
                    try:
                        await message.reply(
                            "💡 <b>Образец правильного вопроса:</b>\n"
                            "<code>❓ Вопрос: [ваш вопрос]</code>\n"
                            "<code>💬 Подробности: [название команды / описание ситуации]</code>"
                        )
                    except Exception:
                        pass

                from h_community_support import handle_ai_command_question
                await handle_ai_command_question(message, bot, raw_txt)
                return

    text = raw_txt.lower()
    if message.chat.type != "private" and text:
        rows = await db.fetchall("SELECT pattern, answer FROM triggers WHERE chat_id=?",
                                 (message.chat.id,))
        for r in rows:
            p = (r["pattern"] or "").lower()
            if p and (p == text or p in text):
                try:
                    await message.reply(r["answer"])
                except Exception:
                    pass
                break
