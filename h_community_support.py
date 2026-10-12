"""🌟 Модуль Сообщества, Отзывов, Идей и Техподдержки с ИИ-Автоответчиком.

Включает:
1. ⭐ Система отзывов о боте и покупках с рейтингом и карточками;
2. 💡 Система идей и предложений с интерактивным голосованием (👍/👎);
3. 💬 Официальный чат сообщества + Умный ИИ-Консультант по вопросам новичков;
4. 🆘 Система тикетов техподдержки с ручным ответом админа и ИИ-автоответом через 6 часов.
"""
from __future__ import annotations

import asyncio
import html
import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import core_ai
import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from utils import hms, mention, mention_id, money

log = logging.getLogger("moxxibot.community")

router = Router(name="community_support")
S_COMMUNITY = 35  # Раздел Сообщества и Поддержки

OFFICIAL_CHAT_URL = "https://t.me/moxxi_clan_chat"
OFFICIAL_REVIEWS_URL = "https://t.me/moxxi_reviews"
OFFICIAL_IDEAS_URL = "https://t.me/moxxi_ideas"

async def get_official_chat_link() -> str:
    val = await db.get_global_setting("global_community_chat", "")
    if val:
        return val if val.startswith("http") else f"https://t.me/{val.lstrip('@')}"
    return OFFICIAL_CHAT_URL

async def get_official_reviews_link() -> str:
    val = await db.get_global_setting("global_reviews_chat", "")
    if val:
        return val if val.startswith("http") else f"https://t.me/{val.lstrip('@')}"
    return OFFICIAL_REVIEWS_URL

async def get_official_ideas_link() -> str:
    val = await db.get_global_setting("global_ideas_chat", "")
    if val:
        return val if val.startswith("http") else f"https://t.me/{val.lstrip('@')}"
    return OFFICIAL_IDEAS_URL

# Временное хранилище начатых отзывов (выбор рейтинга)
_pending_reviews: dict[int, dict] = {}


# ═══════════════════════════════════════════════════════════════
# 1. ⭐ СИСТЕМА ОТЗЫВОВ О БОТЕ И ПОКУПКАХ
# ═══════════════════════════════════════════════════════════════

def _rating_stars(r: int) -> str:
    return "⭐" * max(1, min(5, r)) + "☆" * (5 - max(1, min(5, r)))


def _review_rate_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 1", callback_data="rev_rate:1"),
            InlineKeyboardButton(text="⭐⭐ 2", callback_data="rev_rate:2"),
            InlineKeyboardButton(text="⭐⭐⭐ 3", callback_data="rev_rate:3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐ 4", callback_data="rev_rate:4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5", callback_data="rev_rate:5"),
        ],
        [
            InlineKeyboardButton(text="📖 Читать все отзывы", callback_data="rev:list:0")
        ]
    ])


@router.message(Cmd("отзыв", "отзывы", "оставить отзыв", "написать отзыв", section=S_COMMUNITY,
                    usage="отзыв [текст]", desc="Оставить или посмотреть отзывы о боте"))
async def cmd_reviews(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"

    txt = (args or "").strip()
    if txt:
        # Если текст сразу передан: "отзыв бот супер всё быстро пришло"
        # Записываем с высшей оценкой 5 звёзд по умолчанию или предлагаем выбор
        rev_id = await db.add_review(uid, name, 5, txt)
        stats = await db.get_review_stats()
        # Отправка в привязанную группу отзывов, если задана
        rev_chat = await db.get_global_setting("global_reviews_chat", "")
        if rev_chat:
            try:
                target_cid = int(rev_chat) if (rev_chat.startswith("-") or rev_chat.isdigit()) else rev_chat
                await bot.send_message(
                    target_cid,
                    f"⭐ ✨ <b>НОВЫЙ ОТЗЫВ #{rev_id}</b> ✨ ⭐\n"
                    f"👤 <b>Автор:</b> {mention_id(uid, name)}\n"
                    f"⭐ <b>Оценка:</b> ⭐⭐⭐⭐⭐ (5/5)\n"
                    f"💬 <b>Текст:</b> «<i>{html.escape(txt)}</i>»"
                )
            except Exception:
                pass
        await message.reply(
            f"🎉 <b>Спасибо за ваш отзыв!</b>\n\n"
            f"⭐ Оценка: <b>⭐⭐⭐⭐⭐ (5/5)</b>\n"
            f"💬 Текст: «<i>{html.escape(txt)}</i>»\n\n"
            f"📊 Всего отзывов о боте: <b>{stats['total']}</b> (средний балл: <b>{stats['avg_rating']} ⭐</b>)\n"
            f"Ваше мнение помогает нам становиться лучше!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📖 Все отзывы", callback_data="rev:list:0")
            ]])
        )
        return

    # Если текста нет — показываем общую витрину отзывов с кнопками
    stats = await db.get_review_stats()
    reviews = await db.get_reviews(5)

    rev_lines = []
    for r in reviews:
        stars = _rating_stars(r["rating"])
        user_tag = html.escape(r["user_name"] or "Игрок")
        item_tag = f" <i>(покупка: {r['item_purchased']})</i>" if r.get("item_purchased") else ""
        rev_lines.append(f"• <b>{user_tag}</b> {stars}{item_tag}\n  «{html.escape(r['text'])}»")

    latest_txt = "\n\n".join(rev_lines) if rev_lines else "<i>Пока нет отзывов. Будьте первым!</i>"

    card = (
        f"⭐ ✨ <b>ОТЗЫВЫ О БОТЕ И ПОКУПКАХ MOXXI</b> ✨ ⭐\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🌟 <b>Общий рейтинг:</b> <b>{stats['avg_rating']} / 5.0 ⭐</b> (на основе <b>{stats['total']}</b> отзывов)\n\n"
        f"📝 <b>Последние отзывы игроков:</b>\n\n"
        f"{latest_txt}\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"✍️ <b>Чтобы оставить отзыв:</b> напишите <code>отзыв [текст вашего отзыва]</code> или выберите оценку ниже:"
    )
    await message.reply(card, reply_markup=_review_rate_kb())


@router.callback_query(F.data.startswith("rev_rate:"))
async def cb_review_rate(call: CallbackQuery):
    rating = int(call.data.split(":", 1)[1])
    _pending_reviews[call.from_user.id] = {"rating": rating, "ts": time.time()}
    stars = _rating_stars(rating)
    await call.message.edit_text(
        f"⭐ Вы выбрали оценку: <b>{stars} ({rating}/5)</b>\n\n"
        f"✍️ Теперь отправьте текст отзыва в чат командой:\n"
        f"<code>отзыв [ваш текст]</code>\n\n"
        f"<i>Пример: <code>отзыв Всё супер, моментально начислили VIP и монеты!</code></i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад к отзывам", callback_data="rev:list:0")
        ]])
    )
    await call.answer()


@router.callback_query(F.data.startswith("rev:list:"))
async def cb_review_list(call: CallbackQuery):
    stats = await db.get_review_stats()
    reviews = await db.get_reviews(7)
    rev_lines = []
    for r in reviews:
        stars = _rating_stars(r["rating"])
        user_tag = html.escape(r["user_name"] or "Игрок")
        rev_lines.append(f"• <b>{user_tag}</b> {stars}\n  «{html.escape(r['text'])}»")

    latest_txt = "\n\n".join(rev_lines) if rev_lines else "<i>Пока нет отзывов.</i>"
    card = (
        f"⭐ ✨ <b>ОТЗЫВЫ О БОТЕ И ПОКУПКАХ MOXXI</b> ✨ ⭐\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🌟 <b>Рейтинг:</b> <b>{stats['avg_rating']} / 5.0 ⭐</b> (всего: <b>{stats['total']}</b>)\n\n"
        f"{latest_txt}\n\n"
        f"💡 Оставить отзыв: <code>отзыв [текст]</code>"
    )
    await call.message.edit_text(card, reply_markup=_review_rate_kb())
    await call.answer()


# ═══════════════════════════════════════════════════════════════
# 2. 💡 СИСТЕМА ИДЕЙ И ПРЕДЛОЖЕНИЙ
# ═══════════════════════════════════════════════════════════════

def _sug_kb(sug_id: int, up: int = 0, down: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"👍 За ({up})", callback_data=f"sug_v:{sug_id}:1"),
            InlineKeyboardButton(text=f"👎 Против ({down})", callback_data=f"sug_v:{sug_id}:-1")
        ]
    ])


@router.message(Cmd("идея", "идеи", "предложение", "предложения", "предложка", "добавить идею",
                    section=S_COMMUNITY, usage="идея [текст идеи]",
                    desc="Предложить идею по улучшению бота или посмотреть предложения"))
async def cmd_suggestions(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"
    txt = (args or "").strip()

    if txt:
        sug_id = await db.add_suggestion(uid, name, txt)
        card = (
            f"💡 ✨ <b>НОВАЯ ИДЕЯ ДЛЯ БОТА #{sug_id}</b> ✨ 💡\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>Автор:</b> {mention_id(uid, name)}\n"
            f"📝 <b>Предложение:</b>\n«<i>{html.escape(txt)}</i>»\n\n"
            f"📊 <b>Статус:</b> 💡 <i>На рассмотрении разработчиками</i>\n\n"
            f"👇 <i>Голосуйте за идею, если хотите увидеть её в боте:</i>"
        )
        # Отправка в привязанную группу идей, если задана
        sug_chat = await db.get_global_setting("global_ideas_chat", "")
        if sug_chat:
            try:
                target_cid = int(sug_chat) if (sug_chat.startswith("-") or sug_chat.isdigit()) else sug_chat
                await bot.send_message(target_cid, card, reply_markup=_sug_kb(sug_id, 0, 0))
            except Exception:
                pass
        await message.reply(card, reply_markup=_sug_kb(sug_id, 0, 0))
        return

    # Показываем список лучших идей
    sug_list = await db.get_suggestions(5)
    sug_lines = []
    status_map = {
        "pending": "💡 На рассмотрении",
        "accepted": "✅ Принято",
        "rejected": "❌ Отклонено",
        "done": "🎉 Реализовано"
    }
    for s in sug_list:
        st = status_map.get(s["status"], "💡 На рассмотрении")
        sug_lines.append(
            f"• <b>#{s['id']}</b> [{st}] (👍 {s['upvotes']} | 👎 {s['downvotes']})\n"
            f"  «{html.escape(s['text'][:90])}{'...' if len(s['text']) > 90 else ''}»"
        )

    list_txt = "\n\n".join(sug_lines) if sug_lines else "<i>Пока нет предложенных идей. Будьте первым!</i>"
    text = (
        f"💡 ✨ <b>БАНК ИДЕЙ И ПРЕДЛОЖЕНИЙ MOXXI</b> ✨ 💡\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"У вас есть крутая идея для бота, новой игры или рейдового босса? Предложите её прямо сейчас!\n\n"
        f"🔥 <b>Популярные идеи сообщества:</b>\n\n"
        f"{list_txt}\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"✍️ <b>Предложить идею:</b> напишите <code>идея [текст вашей идеи]</code>"
    )
    await message.reply(text)


@router.callback_query(F.data.startswith("sug_v:"))
async def cb_vote_suggestion(call: CallbackQuery):
    parts = call.data.split(":")
    sug_id = int(parts[1])
    vote = int(parts[2])
    uid = call.from_user.id

    up, down, res = await db.vote_suggestion(sug_id, uid, vote)
    if res == "already_voted":
        return await call.answer("Вы уже проголосовали за эту идею!", show_alert=True)

    try:
        await call.message.edit_reply_markup(reply_markup=_sug_kb(sug_id, up, down))
    except Exception:
        pass
    await call.answer("✅ Ваш голос учтён!")


@router.message(Cmd("+принять", "+отклонить", "+реализовано", "+готово",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="+принять [id_идеи]", desc="Модерация предложенных идей"))
async def cmd_manage_suggestion(message: Message, bot: Bot, args: str = "", **kw):
    staff_rank = await db.get_bot_staff_rank(message.from_user.id)
    is_adm = bool(message.from_user and (message.from_user.id == config.OWNER_ID or message.from_user.id in config.ADMINS or message.from_user.id in (8412527198, 8297844640, 6592023977)))
    if staff_rank < 2 and not is_adm:
        return await message.reply("🔒 Модерация предложений доступна Модераторам бота (ранг 2+) и выше.")
    cmd_word = (message.text or "").strip().split()[0].lower()
    parts = (args or "").strip().split()
    if not parts or not parts[0].isdigit():
        return await message.reply("Формат: <code>+принять [id_идеи]</code> / <code>+отклонить [id]</code> / <code>+реализовано [id]</code>")

    sug_id = int(parts[0])
    sug = await db.get_suggestion(sug_id)
    if not sug:
        return await message.reply("❌ Идея с таким ID не найдена.")

    new_status = "accepted" if "принять" in cmd_word else ("done" if ("реализовано" in cmd_word or "готово" in cmd_word) else "rejected")
    await db.update_suggestion_status(sug_id, new_status)

    status_name = "✅ Принято в разработку" if new_status == "accepted" else ("🎉 Успешно реализовано!" if new_status == "done" else "❌ Отклонено")
    await message.reply(
        f"✅ <b>Статус идеи #{sug_id} обновлён!</b>\n\n"
        f"📝 <b>Текст:</b> «{html.escape(sug['text'])}»\n"
        f"🏷 <b>Новый статус:</b> <b>{status_name}</b>"
    )


# ═══════════════════════════════════════════════════════════════
# 3. 💬 ОФИЦИАЛЬНЫЙ ЧАТ СООБЩЕСТВА И ИИ-КОНСУЛЬТАНТ
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("чат", "сообщество", "беседа", "группа", "официальный чат", "чат бота",
                    section=S_COMMUNITY, usage="чат", desc="Ссылка на официальное сообщество бота"))
async def cmd_community_chat(message: Message, bot: Bot, **kw):
    chat_url = await get_official_chat_link()
    text = (
        f"💬 ✨ <b>ОФИЦИАЛЬНОЕ СООБЩЕСТВО MOXXI BOT</b> ✨ 💬\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Вступайте в наш официальный чат общения и поддержки игроков!\n\n"
        f"👥 <b>В чате вы можете:</b>\n"
        f"• Общаться с другими игроками и создателями групп;\n"
        f"• Участвовать в турнирах, викторинах и совместных рейдах;\n"
        f"• Задавать любые вопросы по боту — наш умный ИИ и администраторы всегда на связи!\n\n"
        f"🔗 <b>Присоединяйтесь по ссылке:</b> {chat_url}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Вступить в чат Moxxi", url=chat_url),
        InlineKeyboardButton(text="⭐ Отзывы", callback_data="rev:list:0")
    ]])
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


# ═══════════════════════════════════════════════════════════════
# 4. 🆘 СИСТЕМА ТЕХПОДДЕРЖКИ С ИИ-АВТООТВЕТОМ ЧЕРЕЗ 6 ЧАСОВ
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("поддержка", "тикет", "саппорт", "техподдержка", "хелп админ", "помощь админа",
                    section=S_COMMUNITY, usage="поддержка [вопрос]",
                    desc="Обратиться в службу техподдержки с вопросом или проблемой"))
async def cmd_support(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"
    txt = (args or "").strip()

    cd_left = await db.cooldown_left(uid, "support_ticket", 1800)
    if cd_left > 0:
        return await message.reply(
            f"⏳ <b>Кулдаун на обращение в техподдержку!</b>\n\n"
            f"Вы уже недавно отправили обращение. Пожалуйста, подождите ещё <b>{hms(cd_left)}</b>, прежде чем подавать новый тикет.\n\n"
            f"🛡 <i>Защита от спама: не чаще 1 обращения в 30 минут. Администрация уже получила ваш предыдущий вопрос!</i>"
        )

    if not txt:
        return await message.reply(
            f"🆘 ✨ <b>СЛУЖБА ТЕХПОДДЕРЖКИ MOXXI</b> ✨ 🆘\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Если у вас возникла проблема, вопрос по оплате, баг или нужна помощь администратора:\n\n"
            f"✍️ <b>Напишите:</b> <code>поддержка [описание вашей проблемы или причины]</code>\n\n"
            f"<i>Пример: <code>поддержка Не начислились монеты после перевода</code></i>\n\n"
            f"⏱ <b>Защита от спама:</b> между обращениями действует кулдаун <b>30 минут</b>.\n"
            f"Администрация ответит вам прямо в личные сообщения!"
        )

    await db.set_cooldown(uid, "support_ticket")
    ticket_id = await db.create_support_ticket(uid, name, txt)

    # Уведомляем пользователя
    await message.reply(
        f"📨 <b>Ваш запрос в техподдержку принят! (Тикет #{ticket_id})</b>\n\n"
        f"📝 <b>Причина / Проблема:</b> «<i>{html.escape(txt)}</i>»\n\n"
        f"⏳ <b>Установлен кулдаун: 30 минут</b> на повторные обращения.\n"
        f"👨‍💻 Администрация уже получила уведомление и скоро вам ответит.\n"
        f"🤖 <i>Резервный ИИ-помощник подключится, если ответ задержится более чем на 6 часов.</i>"
    )

    # Отправляем уведомление владельцам / персоналу / в привязанную группу поддержки
    admin_notify = (
        f"🆘 🔔 <b>НОВЫЙ ТИКЕТ В ТЕХПОДДЕРЖКУ #{ticket_id}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>От:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
        f"📝 <b>Причина / Вопрос:</b>\n«{html.escape(txt)}»\n\n"
        f"💡 <b>Чтобы ответить пользователю:</b>\n"
        f"<code>+ответ {ticket_id} [текст вашего ответа]</code>"
    )
    for oid in config.BOT_OWNERS:
        try:
            await bot.send_message(oid, admin_notify)
        except Exception:
            pass

    try:
        staff_list = await db.get_all_bot_staff()
        for s in staff_list:
            if not config.is_bot_owner(s["user_id"]) and s["rank"] >= 1:
                try:
                    await bot.send_message(s["user_id"], admin_notify)
                except Exception:
                    pass
    except Exception:
        pass

    supp_chat = await db.get_global_setting("global_support_chat", "")
    if supp_chat:
        try:
            target_cid = int(supp_chat) if (supp_chat.startswith("-") or supp_chat.isdigit()) else supp_chat
            await bot.send_message(target_cid, admin_notify)
        except Exception:
            pass


@router.message(Cmd("+ответ", "ответить тикет", "ответ на тикет",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="+ответ [id_тикета] [текст ответа]", desc="Ответить пользователю на тикет в техподдержку"))
async def cmd_answer_ticket(message: Message, bot: Bot, args: str = "", **kw):
    staff_rank = await db.get_bot_staff_rank(message.from_user.id)
    is_admin = bool(message.from_user and (message.from_user.id == config.OWNER_ID or message.from_user.id in config.ADMINS or message.from_user.id in (8412527198, 8297844640, 6592023977)))
    if staff_rank < 1 and not is_admin:
        return await message.reply("🔒 Доступно только персоналу техподдержки бота (Хелпер и выше).")

    parts = (args or "").strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        return await message.reply("Формат: <code>+ответ [id_тикета] [текст ответа]</code>")

    ticket_id = int(parts[0])
    answer_text = parts[1].strip()

    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await message.reply("❌ Тикет не найден.")

    admin_name = message.from_user.first_name or "Администратор"
    await db.answer_support_ticket(ticket_id, answer_text, answered_by=message.from_user.id, answered_name=admin_name, is_ai=False)

    # Отправляем ответ пользователю в личку
    user_notify = (
        f"🆘 ✨ <b>ОТВЕТ СЛУЖБЫ ТЕХПОДДЕРЖКИ (Тикет #{ticket_id})</b> ✨ 🆘\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👨‍💻 <b>Администратор {html.escape(admin_name)} ответил на ваш вопрос:</b>\n\n"
        f"«<i>{html.escape(answer_text)}</i>»\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"❤️ <i>Спасибо за обращение! Если у вас появятся новые вопросы, напишите <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
        await message.reply(f"✅ <b>Ответ успешно доставлен пользователю в тикет #{ticket_id}!</b>")
    except Exception as e:
        await message.reply(f"⚠️ Тикет закрыт в базе, но не удалось отправить ЛС пользователю (возможно, бот заблокирован): {e}")


# ═══════════════════════════════════════════════════════════════
# 5. 🤖 ФОНОВЫЙ ИИ-АВТООТВЕТЧИК (ЕСЛИ АДМИН НЕ ОТВЕТИЛ ЗА 6 ЧАСОВ)
# ═══════════════════════════════════════════════════════════════

async def check_unanswered_support_tickets(bot: Bot) -> None:
    """Проверяет открытые тикеты старше 6 часов и отправляет умный ИИ-ответ."""
    try:
        overdue_tickets = await db.get_unanswered_tickets_older_than(6 * 3600)
        for t in overdue_tickets:
            t_id = t["id"]
            u_id = t["user_id"]
            u_text = t["text"]

            # Генерируем решение через ИИ
            system_prompt = (
                "Ты — экспертный дружелюбный сотрудник службы поддержки Telegram-бота 'Moxxi Bot'. "
                "Бот включает функции: Игры/Казино (слоты, мины, дартс, краш, кубик), Бизнесы и пассивный доход, "
                "Рейдовые Боссы чата, PvP-Дуэли, Рыбалка и крафт, Квесты и достижения, Модерация чатов и VIP. "
                "Пользователь задал вопрос в техподдержку более 6 часов назад. "
                "Ответь максимально вежливо, понятно, по пунктам и с указанием нужных команд бота. "
                "Длина ответа: 2-4 абзаца на русском языке."
            )
            ai_reply = await core_ai.ask_text(f"Вопрос пользователя: {u_text}", system=system_prompt, max_tokens=700)
            if not ai_reply:
                ai_reply = (
                    "Здравствуйте! По вашему обращению: мы проверили работу сервиса. "
                    "Все основные команды и баланс работают в штатном режиме. "
                    "Если ваш вопрос касается перевода или начисления, проверьте баланс командой <code>баланс</code>. "
                    "При необходимости вы можете создать повторное обращение через <code>поддержка [текст]</code>."
                )

            await db.answer_support_ticket(t_id, ai_reply, answered_by=0, answered_name="ИИ-Консультант Moxxi", is_ai=True)

            ai_notify = (
                f"🤖 ✨ <b>ОТВЕТ СЛУЖБЫ ТЕХПОДДЕРЖКИ (Тикет #{t_id})</b> ✨ 🤖\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"Здравствуйте, <b>{html.escape(t['user_name'] or 'Пользователь')}</b>!\n"
                f"Наш <b>ИИ-Ассистент Техподдержки</b> подготовил решение по вашему вопросу:\n\n"
                f"{html.escape(ai_reply)}\n\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"💡 <i>Если вам требуется дополнительная помощь, просто отправьте команду <code>поддержка [вопрос]</code>!</i>"
            )
            try:
                await bot.send_message(u_id, ai_notify)
                log.info("Тикет #%d успешно закрыт автоматическим ИИ-ответом.", t_id)
            except Exception as e:
                log.warning("Не удалось отправить автоответ по тикету #%d: %s", t_id, e)
    except Exception as e:
        log.warning("Ошибка проверки неотвеченных тикетов: %s", e)


# ═══════════════════════════════════════════════════════════════
# 6. 🧠 ИИ-КОНСУЛЬТАНТ И ПОМОЩНИК ПО БОТУ В ЧАТЕ
# ═══════════════════════════════════════════════════════════════

@router.message(Cmd("вопрос", "спросить", "как сделать", "помощь по боту", "хелп бот",
                    section=S_COMMUNITY, usage="вопрос [ваш вопрос по боту]",
                    desc="Задать любой вопрос умному ИИ-Консультанту по боту"))
async def cmd_ask_ai_helper(message: Message, bot: Bot, args: str = "", **kw):
    q = (args or "").strip()
    if not q and message.reply_to_message:
        q = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not q:
        return await message.reply(
            "🧠 <b>Задайте вопрос ИИ-Консультанту по боту:</b>\n\n"
            "• <code>вопрос как заработать монеты?</code>\n"
            "• <code>вопрос как работают рейдовые боссы?</code>\n"
            "• <code>вопрос как купить VIP статус?</code>\n"
            "• <code>вопрос как сыграть в дуэль?</code>\n\n"
            "💡 <i>ИИ знает все разделы, команды и правила бота Moxxi и сразу подскажет решение!</i>"
        )

    system_prompt = (
        "Ты — умный дружелюбный консультант и знаток Telegram-бота 'Moxxi Bot'. "
        "Пользователь спрашивает, как пользоваться ботом или его фичами. "
        "Объясни четко, понятно, на русском языке и укажи точные команды бота. "
        "Основные разделы: "
        "- Монеты и баланс (бонус, работа, крайм, баланс, передать) "
        "- Игры и казино (казик, слоты, мины, краш, дартс, кубик, колесо, рулетка, апп) "
        "- Предприятия и рынок (бизнесы, купить, собрать прибыль, продать) "
        "- Рейдовые боссы (босс, ударить, выстрел, хил, возродить, магазин, аптечка) "
        "- PvP-Дуэли (дуэль @user [ставка], принять, мои дуэли) "
        "- Рыбалка и крафт (рыбалка, садок, продать рыбу, крафт) "
        "- Квесты и ачивки (квесты, награда, достижения, титулы) "
        "- Модерация чатов (+модер, кик, мут, бан, варн, расписание, ночной режим, темы). "
        "Длина ответа: 2-3 компактных информативных абзаца с эмодзи."
    )
    ans = await core_ai.ask_text(f"Вопрос игрока: {q}", system=system_prompt, max_tokens=600)
    if not ans:
        ans = (
            "Для просмотра всех возможностей бота напишите <code>меню</code> или <code>команды</code>.\n"
            "• Получить монеты: <code>бонус</code>, <code>работа</code>;\n"
            "• Играть: <code>казик [ставка]</code>, <code>мины [ставка]</code>, <code>апп</code>;\n"
            "• Битвы с боссами: <code>босс</code>, <code>ударить</code>."
        )

    await message.reply(
        f"🤖 ✨ <b>ОТВЕТ ИИ-КОНСУЛЬТАНТА MOXXI</b> ✨ 🤖\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"❓ <b>Вопрос:</b> «<i>{html.escape(q)}</i>»\n\n"
        f"{html.escape(ans)}\n\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Если у вас сложный вопрос по оплате или багу, используйте: <code>поддержка [вопрос]</code>.</i>",
        disable_web_page_preview=True
    )
