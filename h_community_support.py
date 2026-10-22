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

OFFICIAL_CHAT_URL = "https://t.me/moxxi_chat"
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


@router.message(Cmd("отзыв", "отзывы", "оставить отзыв", "написать отзыв", "посмотреть отзывы", section=S_COMMUNITY,
                    usage="отзыв [текст]", desc="Оставить или посмотреть отзывы о боте"))
async def cmd_reviews(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"

    txt = (args or "").strip()
    if txt:
        # Проверка кулдауна на оставление отзыва: 10 часов (36000 сек)
        cd_left = await db.cooldown_left(uid, "leave_review", 36000)
        if cd_left > 0:
            return await message.reply(
                f"⏳ <b>Кулдаун на отзыв!</b>\n\n"
                f"Оставлять отзывы можно не чаще одного раза в <b>10 часов</b>.\n"
                f"Пожалуйста, подождите ещё <b>{hms(cd_left)}</b>, прежде чем писать следующий отзыв.\n\n"
                f"📖 Чтобы читать чужие отзывы: <code>отзывы</code> или кнопка «Все отзывы».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📖 Все отзывы", callback_data="rev:list:0")
                ]])
            )

        await db.set_cooldown(uid, "leave_review")
        rev_id = await db.add_review(uid, name, 5, txt)
        stats = await db.get_review_stats()
        # Отправка в привязанную группу отзывов, если задана
        rev_chat = await db.get_global_setting("global_reviews_chat", "")
        rev_topic = await db.get_global_setting("global_reviews_chat_topic", "")
        if rev_chat:
            try:
                target_cid = int(rev_chat) if (rev_chat.startswith("-") or rev_chat.isdigit()) else rev_chat
                tid = int(rev_topic) if rev_topic and rev_topic.isdigit() else None
                await bot.send_message(
                    target_cid,
                    f"⭐ ✨ <b>НОВЫЙ ОТЗЫВ #{rev_id}</b> ✨ ⭐\n"
                    f"👤 <b>Автор:</b> {mention_id(uid, name)}\n"
                    f"⭐ <b>Оценка:</b> ⭐⭐⭐⭐⭐ (5/5)\n"
                    f"💬 <b>Текст:</b> «<i>{html.escape(txt)}</i>»",
                    message_thread_id=tid
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
                    "написать идею", "посмотреть идеи",
                    section=S_COMMUNITY, usage="идея [текст идеи]",
                    desc="Предложить идею по улучшению бота или посмотреть предложения"))
async def cmd_suggestions(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    name = message.from_user.first_name or "Пользователь"
    txt = (args or "").strip()

    if txt:
        # Проверка кулдауна на предложение идеи: 1 час (3600 сек)
        cd_left = await db.cooldown_left(uid, "leave_idea", 3600)
        if cd_left > 0:
            return await message.reply(
                f"⏳ <b>Кулдаун на предложение идеи!</b>\n\n"
                f"Предлагать новые идеи можно не чаще одного раза в <b>1 час</b>.\n"
                f"Пожалуйста, подождите ещё <b>{hms(cd_left)}</b>, прежде чем отправлять следующую идею.\n\n"
                f"💡 Чтобы посмотреть уже предложенные идеи: <code>идеи</code>."
            )

        await db.set_cooldown(uid, "leave_idea")
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
        sug_topic = await db.get_global_setting("global_ideas_chat_topic", "")
        if sug_chat:
            try:
                target_cid = int(sug_chat) if (sug_chat.startswith("-") or sug_chat.isdigit()) else sug_chat
                tid = int(sug_topic) if sug_topic and sug_topic.isdigit() else None
                await bot.send_message(target_cid, card, reply_markup=_sug_kb(sug_id, 0, 0), message_thread_id=tid)
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
# 4. 🆘 СИСТЕМА ТЕХПОДДЕРЖКИ С АНОНИМНЫМИ ОТВЕТАМИ И АВТООТВЕТАМИ
# ═══════════════════════════════════════════════════════════════

AUTO_ANSWERS = {
    1: ("✅ Принято в работу", "Здравствуйте! Ваше обращение принято администрацией. Проблема уже в процессе решения, скоро всё перепроверим. Спасибо за обращение!"),
    2: ("💰 Монеты / Баланс", "Здравствуйте! Проверили транзакцию по вашему балансу. Начисление перепроверено и скорректировано. Приятной игры в Moxxi!"),
    3: ("🛠 Ошибка / Баг", "Спасибо за информацию о баге! Данные переданы разработчикам, ошибка будет устранена в ближайшем обновлении."),
    4: ("⛔️ Отказ по правилам", "Здравствуйте! Ваше обращение рассмотрено. В удовлетворении запроса отказано в соответствии с правилами сообщества."),
    5: ("🔓 Снятие наказания", "Здравствуйте! Ситуация пересмотрена администрацией. Ограничения сняты. Пожалуйста, соблюдайте правила бота!"),
}


def ticket_admin_kb(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡️ Быстрый автоответ", callback_data=f"supp_autokb:{ticket_id}"),
            InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"supp_close:{ticket_id}")
        ]
    ])


def _auto_answer_templates_kb(ticket_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="1. ✅ Принято в работу", callback_data=f"supp_sendauto:{ticket_id}:1")],
        [InlineKeyboardButton(text="2. 💰 Монеты / Баланс", callback_data=f"supp_sendauto:{ticket_id}:2")],
        [InlineKeyboardButton(text="3. 🛠 Ошибка / Баг", callback_data=f"supp_sendauto:{ticket_id}:3")],
        [InlineKeyboardButton(text="4. ⛔️ Отказ по правилам", callback_data=f"supp_sendauto:{ticket_id}:4")],
        [InlineKeyboardButton(text="5. 🔓 Снятие наказания", callback_data=f"supp_sendauto:{ticket_id}:5")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"supp_back:{ticket_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


import re

async def analyze_support_ticket(text: str) -> tuple[bool, str]:
    """Умный анализ обращений в техподдержку (эвристики + ИИ Gemini).
    Возвращает (is_valid, reason).
    """
    t = (text or "").strip()
    if len(t) < 4:
        return False, "Обращение слишком короткое или не содержит сути проблемы"

    low = t.lower()
    words = low.split()

    # 1. Простые бессмысленные слова
    if len(words) == 1 and words[0] in {
        "да", "нет", "ок", "хай", "ку", "прив", "привет", "чо", "че", "хз", "ппп", "ааа",
        "test", "тест", "123", "что", "почему", "ало", "алло", "пж", "помоги", "help",
        "куку", "гы", "лол", "lol", "хмм", "ммм", "ну", "ага", "угу", "э", "эй", "ясн", "пон"
    }:
        return False, f"Обращение состоит только из слова «{words[0]}» без описания проблемы"

    # 2. Очевидный бытовой оффтоп и бессмысленные фразы
    offtop_phrases = [
        "не хочу гулять", "пойдем гулять", "пойдём гулять", "го гулять", "хочу гулять",
        "хочу спать", "пошел спать", "пошёл спать", "спокойной ночи", "доброе утро",
        "я покушал", "покушал", "я покакал", "покакал", "мне скучно", "очень скучно",
        "как дела", "что делаешь", "чем занят", "го играть", "го в доту", "го в бравл",
        "ты кто", "кто ты", "ты бот", "ты человек", "сколько тебе лет"
    ]
    for op in offtop_phrases:
        if op in low:
            return False, f"Бытовой оффтоп («{op}»), не относящийся к боту и игре"

    # 3. Очевидные валидные ключевые слова бота (быстрый пропуск)
    valid_keywords = [
        "донат", "звезд", "stars", "star", "юкасс", "сбп", "оплат", "чек", "рубл", "покупк",
        "баланс", "монет", "не пришл", "не начисл", "пропал", "списал", "ошибк", "баг",
        "слетел", "краш", "завис", "разбан", "бан", "мут", "варн", "наказан", "жалоб",
        "клан", "брак", "свадьб", "ферм", "бизнес", "рынок", "перевод", "обман", "скам",
        "айди", "id", "команд", "не работает", "не могу", "помогите с", "почему не"
    ]
    if any(k in low for k in valid_keywords) and len(words) >= 3:
        return True, "Технический вопрос по функционалу бота"

    # 4. Глубокий семантический анализ через ИИ (Gemini / OpenAI)
    try:
        import core_ai
        system = (
            "Ты — строгий классификатор тикетов в службу технической поддержки игрового Telegram-бота 'MOXXI' "
            "(игры, казино, баланс, донат, команды, баги, блокировки, кланы, рейды).\n"
            "Проанализируй текст обращения пользователя и определи, является ли это РЕАЛЬНЫМ техническим или игровым вопросом/проблемой/жалобой по боту, "
            "или это БЕССМЫСЛИЦА, СПАМ, БЫТОВОЙ ОФФТОП, ГЛУПОСТЬ или пустая болтовня "
            "(например: 'я не хочу гулять', 'привет как дела', 'скучно', 'го в доту', бессвязный набор символов).\n\n"
            "Ответь СТРОГО в формате JSON:\n"
            "{\"valid\": true/false, \"reason\": \"краткая причина на русском языке\"}"
        )
        ai_res = await asyncio.wait_for(core_ai.ask(system, f"Текст обращения: «{t}»"), timeout=6.0)
        if ai_res and isinstance(ai_res, dict) and "valid" in ai_res:
            is_val = bool(ai_res["valid"])
            reason = str(ai_res.get("reason") or ("Технический вопрос" if is_val else "Бессмысленное обращение"))
            return is_val, reason
    except Exception as e:
        log.warning("AI analyze_support_ticket error: %s", e)

    if len(words) >= 3:
        return True, "Обращение передано на рассмотрение администрации"
    return False, "Обращение слишком короткое или не содержит сути"


def is_nonsense_support_ticket(text: str) -> bool:
    """Определяет бессмысленные, слишком короткие или спам-обращения (устаревший синхронный метод)."""
    t = text.strip().lower()
    if len(t) < 4:
        return True
    words = t.split()
    if len(words) == 1 and words[0] in {
        "да", "нет", "ок", "хай", "ку", "прив", "привет", "чо", "че", "хз", "ппп", "ааа",
        "test", "тест", "123", "что", "почему", "ало", "алло", "пж", "помоги", "help",
        "куку", "гы", "лол", "lol", "хмм", "ммм", "ну", "ага", "угу", "э", "эй"
    }:
        return True
    return False


def detect_staff_abuse(text: str) -> tuple[bool, str]:
    """Проверяет ответ сотрудника поддержки на оскорбления, мат и упоминание родных ('мать', 'мамка' и т.д.)."""
    t = text.lower()
    subs = {'@': 'а', 'a': 'а', 'm': 'м', 't': 'т', 'b': 'б', '0': 'о', 'o': 'о', 'e': 'е'}
    norm = "".join(subs.get(c, c) for c in t)

    # 1. Оскорбления родных (мать, мамка, отчим, батя в грубом контексте, mq)
    parent_patterns = [
        r'\b(мать|матери|матерью|мамаша|мамашу|мамка|мамку|мамке|мамок|мамки|мку|mq|матери)\b',
        r'(твой|твою|твоя|твоей|твоем)\s+(мать|мамк|мамаш)',
        r'(сын|дочь|отродье)\s+(шлюхи|бляди|собаки)',
        r'(ебал|ебем|ебут|сношал)\s+.*(мать|мамк)',
    ]
    for pat in parent_patterns:
        if re.search(pat, norm):
            return True, "Упоминание/оскорбление родных"

    # 2. Грубый мат и прямые оскорбления игрока
    insult_patterns = [
        r'\b(шлюх|блядин|уебищ|уёбищ|хуесос|пидорас|пидар|гандон|мразь|тварь)\w*',
        r'(пошел|пошёл|иди)\s+на\s*хуй',
        r'рот\s+(твой\s+)?ебал',
        r'\b(долбоеб|долбоёб|даун|ублюдок)\b',
    ]
    for pat in insult_patterns:
        if re.search(pat, norm):
            return True, "Нецензурная брань / оскорбление игрока"

    return False, ""


@router.message(Cmd("поддержка", "тикет", "саппорт", "техподдержка", "support", "ticket", "хелп админ", "помощь админа",
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

    is_valid, reason = await analyze_support_ticket(txt)
    ticket_status = "open" if is_valid else "auto_rejected"
    ticket_id = await db.create_support_ticket(uid, name, txt, status=ticket_status)

    if not is_valid:
        # Автоматический отказ ИИ с разъяснением
        user_msg = (
            f"❌ 🤖 <b>Обращение отклонено ИИ (Тикет #{ticket_id})</b>\n\n"
            f"📝 <b>Ваш текст:</b> «<i>{html.escape(txt)}</i>»\n"
            f"⚠️ <b>Причина отказа ИИ:</b> {html.escape(reason)}\n\n"
            f"💡 <i>Техподдержка принимает только вопросы по работе бота (оплата, звёзды, баланс, баги, команды или жалобы). Бытовой оффтоп и бессмысленные сообщения отклоняются автоматически.</i>\n\n"
            f"👨‍💻 <b>Вторичная проверка:</b> Ваше обращение всё равно передано администрации. Если ИИ ошибся, администратор ответит вам лично!"
        )
        await message.reply(user_msg)

        admin_notify = (
            f"🆘 🔔 <b>НОВЫЙ ТИКЕТ В ТЕХПОДДЕРЖКУ #{ticket_id}</b>\n"
            f"⚠️ <b>СТАТУС: ❌ ОТКЛОНЁН ИИ</b>\n"
            f"🤖 <b>Причина ИИ:</b> {html.escape(reason)}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>От:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
            f"📝 <b>Причина / Проблема:</b>\n«{html.escape(txt)}»\n\n"
            f"💡 <i>ИИ посчитал обращение бессмысленным или оффтопом и выдал автоотказ. "
            f"Если ИИ ошибся, вы можете ответить пользователю или закрыть тикет:</i>\n\n"
            f"• Свой ответ: <code>+ответ {ticket_id} [текст вашего ответа]</code>\n"
            f"• Быстрый шаблон: <code>автоответ тикет {ticket_id} [1-5]</code>\n"
            f"• Закрыть тикет: <code>закрыть тикет {ticket_id}</code>"
        )
    else:
        # Валидный тикет
        await message.reply(
            f"✅ <b>Ваше обращение принято! (Тикет #{ticket_id})</b>\n\n"
            f"📝 <b>Причина / Проблема:</b> «<i>{html.escape(txt)}</i>»\n\n"
            f"⏳ <b>Установлен кулдаун: 30 минут</b> на повторные обращения (защита от спама).\n"
            f"👨‍💻 Администрация рассмотрит ваш вопрос и пришлёт ответ прямо сюда в личные сообщения.\n"
            f"🤖 <i>Резервный ИИ-помощник подключится, если ответ задержится более чем на 6 часов.</i>"
        )
        admin_notify = (
            f"🆘 🔔 <b>НОВЫЙ ТИКЕТ В ТЕХПОДДЕРЖКУ #{ticket_id}</b>\n"
            f"✅ <b>СТАТУС: ПРИНЯТ (ПРОВЕРЕН ИИ)</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>От:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
            f"📝 <b>Причина / Вопрос:</b>\n«{html.escape(txt)}»\n\n"
            f"💡 <b>Команды для ответа:</b>\n"
            f"• Свой ответ: <code>+ответ {ticket_id} [текст вашего ответа]</code>\n"
            f"• Быстрый шаблон: <code>автоответ тикет {ticket_id} [1-5]</code>\n"
            f"• Закрыть тикет: <code>закрыть тикет {ticket_id}</code>"
        )

    # Оповещаем владельцев бота (Fanat & Simba) и стафф
    recipients = set(getattr(config, "BOT_OWNERS", {config.OWNER_ID}))
    try:
        staff_rows = await db.get_all_bot_staff()
        for sm in staff_rows:
            if sm.get("rank", 0) >= 1:
                recipients.add(sm["user_id"])
    except Exception:
        pass

    supp_chat = await db.get_global_setting("global_support_chat", "")
    supp_topic = await db.get_global_setting("global_support_chat_topic", "")
    if supp_chat:
        try:
            target_cid = int(supp_chat) if (supp_chat.startswith("-") or supp_chat.isdigit()) else supp_chat
            tid = int(supp_topic) if supp_topic and supp_topic.isdigit() else None
            await bot.send_message(target_cid, admin_notify, reply_markup=ticket_admin_kb(ticket_id), message_thread_id=tid)
        except Exception:
            pass

    for rid in recipients:
        try:
            await bot.send_message(rid, admin_notify, reply_markup=ticket_admin_kb(ticket_id))
        except Exception:
            pass


@router.message(Cmd("+ответ", "ответить тикет", "ответ на тикет", "ответить",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="+ответ [id_тикета] [текст ответа]", desc="Ответить пользователю на тикет в техподдержку"))
async def cmd_answer_ticket(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    is_admin = config.is_bot_owner(sender_id) or (sender_id in config.ADMINS) or (staff_rank >= 1)
    if not is_admin:
        return await message.reply("⛔️ Отвечать на тикеты и закрывать их может <b>ТОЛЬКО официальная администрация бота</b>!")

    # Проверка на мут сотрудника стаффа
    muted, sec_left = await db.is_staff_muted(sender_id)
    if muted:
        return await message.reply(
            f"🔇 <b>Вы временно заглушены в стаффе бота!</b>\n"
            f"Осталось времени: <b>{hms(sec_left)}</b>. Вы не можете отправлять ответы игрокам."
        )

    parts = (args or "").strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        return await message.reply("Формат: <code>+ответ [id_тикета] [текст ответа]</code>")

    ticket_id = int(parts[0])
    answer_text = parts[1].strip()

    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await message.reply("❌ Тикет не найден.")

    if ticket.get("status") == "closed":
        return await message.reply(f"⚠️ Тикет #{ticket_id} уже закрыт!")

    # Проверка на мат / упоминание родных сотрудником стаффа
    is_abuse, abuse_reason = detect_staff_abuse(answer_text)
    if is_abuse:
        warns = await db.add_staff_warn(sender_id)
        rank_title = db.BOT_STAFF_TITLES.get(staff_rank, f"Ранг {staff_rank}")
        sender_name = message.from_user.first_name or "Сотрудник"
        sender_tag = mention_id(sender_id, sender_name)

        penalty_action = ""
        if staff_rank in (1, 2) and warns >= 3:
            await db.remove_bot_staff(sender_id)
            penalty_action = "🚫 <b>СНЯТ С ДОЛЖНОСТИ СТАФФА</b> (3/3 варнов)"
            try:
                await bot.send_message(
                    sender_id,
                    "🚫 <b>Вы были сняты с должности сотрудника стаффа Moxxi!</b>\n"
                    "Причина: получение 3/3 варнов за оскорбления / нецензурную брань в ответах поддержки."
                )
            except Exception:
                pass
        elif staff_rank == 3 and warns >= 3:
            await db.set_bot_staff_rank(sender_id, 2, "Модератор")
            await db.reset_staff_warns(sender_id)
            penalty_action = "⚠️ <b>ПОНИЖЕН С АДМИНИСТРАТОРА ДО МОДЕРАТОРА</b> (варны сброшены на 0)"
            try:
                await bot.send_message(
                    sender_id,
                    "⚠️ <b>Вы были понижены с Администратора до Модератора!</b>\n"
                    "Причина: получение 3/3 варнов за нецензурную брань в поддержке. Ваши варны сброшены на 0."
                )
            except Exception:
                pass
        else:
            penalty_action = f"⚠️ <b>ВЫДАН ВАРН</b> ({warns}/3)"
            try:
                await bot.send_message(
                    sender_id,
                    f"⚠️ <b>Вам начислен выговор (варн) стаффа! ({warns}/3)</b>\n"
                    f"Причина: обнаружена нецензурная брань / упоминание родных в ответе на тикет #{ticket_id}.\n"
                    f"<i>Сообщение игроку заблокировано и не отправлено.</i>"
                )
            except Exception:
                pass

        await message.reply(
            f"❌ <b>ОТВЕТ ЗАБЛОКИРОВАН СИСТЕМОЙ БЕЗОПАСНОСТИ!</b>\n\n"
            f"Обнаружено: <b>{abuse_reason}</b>.\n"
            f"Ваш ответ <b>НЕ был отправлен игроку</b>.\n"
            f"Статус: {penalty_action}."
        )

        # Оповещаем Высшую Администрацию (Fanat & Simba) с интерактивными кнопками
        u_name = ticket.get("user_name") or str(ticket["user_id"])
        u_tag = mention_id(ticket["user_id"], u_name)

        higher_admin_msg = (
            f"🚨 <b>НАРУШЕНИЕ ПРАВИЛ СОТРУДНИКОМ СТАФФА В ПОДДЕРЖКЕ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>Сотрудник:</b> {sender_tag} (ID: <code>{sender_id}</code>, {rank_title})\n"
            f"⚠️ <b>Варны сотрудника:</b> <b>{warns}/3</b>\n"
            f"🎫 <b>Тикет:</b> #{ticket_id} от игрока {u_tag}\n\n"
            f"❓ <b>Вопрос игрока:</b>\n«<i>{html.escape(ticket['text'])}</i>»\n\n"
            f"🚫 <b>Заблокированный ответ сотрудника:</b>\n«<b>{html.escape(answer_text)}</b>»\n\n"
            f"🛡 <i>Бот автоматически заблокировал отправку игроку. Выберите решение:</i>"
        )
        kb_higher = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Оправдать (Снять варн)", callback_data=f"staff_act:unwarn:{sender_id}:{ticket_id}"),
                InlineKeyboardButton(text="⚖️ Выбрать наказание", callback_data=f"staff_act:choose:{sender_id}:{ticket_id}")
            ]
        ])
        for owner_id in getattr(config, "BOT_OWNERS", {config.OWNER_ID}):
            try:
                await bot.send_message(owner_id, higher_admin_msg, reply_markup=kb_higher)
            except Exception:
                pass
        return

    await db.answer_support_ticket(ticket_id, answer_text, answered_by=sender_id, answered_name="Администрация", is_ai=False)

    # Отправляем ответ пользователю в личку: СТРОГО АНОНИМНО, БЕЗ ИМЕНИ АДМИНИСТРАТОРА!
    user_notify = (
        f"📩 🔔 <b>ВЫ ПОЛУЧИЛИ ОТВЕТ ОТ ТЕХПОДДЕРЖКИ! (Тикет #{ticket_id})</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 <b>Ваше обращение:</b>\n"
        f"«<i>{html.escape(ticket['text'])}</i>»\n\n"
        f"👨‍💻 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{html.escape(answer_text)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 <i>Тикет закрыт администрацией. Если потребуется дополнительная помощь, вы можете подать новое обращение: <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
        await message.reply(f"✅ <b>Ответ успешно доставлен пользователю в тикет #{ticket_id}, тикет закрыт!</b>")
    except Exception as e:
        await message.reply(f"⚠️ Тикет закрыт в базе, но не удалось отправить ЛС пользователю (возможно, бот заблокирован): {e}")


@router.message(Cmd("закрыть тикет", "закрытьтикет", "+закрыть тикет", "+закрыть", "тикет закрыть",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="закрыть тикет [id] [причина]", desc="Закрыть тикет в техподдержке"))
async def cmd_close_ticket(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    is_admin = config.is_bot_owner(sender_id) or (sender_id in config.ADMINS) or (staff_rank >= 1)
    if not is_admin:
        return await message.reply("⛔️ Закрывать тикеты может <b>ТОЛЬКО официальная администрация бота</b>!")

    parts = (args or "").strip().split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        return await message.reply("Формат: <code>закрыть тикет [id] [причина (опционально)]</code>")

    ticket_id = int(parts[0])
    reason = parts[1].strip() if len(parts) > 1 else ""

    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await message.reply("❌ Тикет не найден.")

    if ticket.get("status") == "closed":
        return await message.reply(f"⚠️ Тикет #{ticket_id} уже закрыт!")

    await db.close_support_ticket(ticket_id, closed_by=sender_id, closed_name="Администрация")

    user_notify = (
        f"🔒 <b>Ваше обращение (Тикет #{ticket_id}) закрыто администрацией!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 <b>Тема обращения:</b> «<i>{html.escape(ticket['text'])}</i>»\n"
        + (f"📌 <b>Причина закрытия:</b> <i>{html.escape(reason)}</i>\n\n" if reason else "\n")
        + "<i>Если у вас возникнет новый вопрос, вы можете создать новое обращение: <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
    except Exception:
        pass

    await message.reply(f"✅ <b>Тикет #{ticket_id} успешно закрыт!</b>" + (f" Причина: {html.escape(reason)}" if reason else ""))


@router.message(Cmd("автоответ тикет", "автоответтикет", "автоответ", "+автоответ",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="автоответ тикет [id] [1-5]", desc="Отправить готовый автоответ в тикет"))
async def cmd_auto_answer_ticket(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    is_admin = config.is_bot_owner(sender_id) or (sender_id in config.ADMINS) or (staff_rank >= 1)
    if not is_admin:
        return await message.reply("⛔️ Отправлять автоответы может <b>ТОЛЬКО официальная администрация бота</b>!")

    parts = (args or "").strip().split()
    if not parts or not parts[0].isdigit():
        return await message.reply(
            "Формат: <code>автоответ тикет [id] [номер 1-5]</code>\n\n"
            "<b>Шаблоны:</b>\n"
            "1. Принято в работу (по умолчанию)\n"
            "2. Монеты / Баланс скорректирован\n"
            "3. Ошибка / Баг передан разработчикам\n"
            "4. Отказ в удовлетворении по правилам\n"
            "5. Наказание / Ограничения сняты"
        )

    ticket_id = int(parts[0])
    tpl_idx = int(parts[1]) if (len(parts) > 1 and parts[1].isdigit()) else 1
    tpl_title, answer_text = AUTO_ANSWERS.get(tpl_idx, AUTO_ANSWERS[1])

    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await message.reply("❌ Тикет не найден.")

    if ticket.get("status") == "closed":
        return await message.reply(f"⚠️ Тикет #{ticket_id} уже закрыт!")

    await db.answer_support_ticket(ticket_id, answer_text, answered_by=sender_id, answered_name="Администрация", is_ai=False)

    user_notify = (
        f"📩 🔔 <b>ВЫ ПОЛУЧИЛИ ОТВЕТ ОТ ТЕХПОДДЕРЖКИ! (Тикет #{ticket_id})</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 <b>Ваше обращение:</b>\n"
        f"«<i>{html.escape(ticket['text'])}</i>»\n\n"
        f"👨‍💻 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{html.escape(answer_text)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 <i>Тикет закрыт администрацией. Если потребуется дополнительная помощь, вы можете подать новое обращение: <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
        await message.reply(f"✅ <b>Тикет #{ticket_id} успешно закрыт автоответом:</b> «{tpl_title}»")
    except Exception as e:
        await message.reply(f"⚠️ Тикет закрыт в базе, но не удалось отправить ЛС пользователю: {e}")


# --- Интерактивные callback-кнопки под тикетом ---
@router.callback_query(F.data.startswith("supp_autokb:"))
async def cb_supp_autokb(cq: CallbackQuery):
    sender_id = cq.from_user.id if cq.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    if not (config.is_bot_owner(sender_id) or sender_id in config.ADMINS or staff_rank >= 1):
        return await cq.answer("⛔️ Доступно только администрации!", show_alert=True)
    ticket_id = int(cq.data.split(":", 1)[1])
    await cq.message.edit_reply_markup(reply_markup=_auto_answer_templates_kb(ticket_id))
    await cq.answer()


@router.callback_query(F.data.startswith("supp_back:"))
async def cb_supp_back(cq: CallbackQuery):
    ticket_id = int(cq.data.split(":", 1)[1])
    await cq.message.edit_reply_markup(reply_markup=ticket_admin_kb(ticket_id))
    await cq.answer()


@router.callback_query(F.data.startswith("supp_sendauto:"))
async def cb_supp_sendauto(cq: CallbackQuery, bot: Bot):
    sender_id = cq.from_user.id if cq.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    if not (config.is_bot_owner(sender_id) or sender_id in config.ADMINS or staff_rank >= 1):
        return await cq.answer("⛔️ Доступно только администрации!", show_alert=True)

    parts = cq.data.split(":")
    ticket_id = int(parts[1])
    tpl_idx = int(parts[2])
    tpl_title, answer_text = AUTO_ANSWERS.get(tpl_idx, AUTO_ANSWERS[1])

    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await cq.answer("❌ Тикет не найден!", show_alert=True)

    if ticket.get("status") == "closed":
        return await cq.answer("⚠️ Тикет уже закрыт!", show_alert=True)

    await db.answer_support_ticket(ticket_id, answer_text, answered_by=sender_id, answered_name="Администрация", is_ai=False)

    user_notify = (
        f"📩 🔔 <b>ВЫ ПОЛУЧИЛИ ОТВЕТ ОТ ТЕХПОДДЕРЖКИ! (Тикет #{ticket_id})</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 <b>Ваше обращение:</b>\n"
        f"«<i>{html.escape(ticket['text'])}</i>»\n\n"
        f"👨‍💻 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{html.escape(answer_text)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 <i>Тикет закрыт администрацией. Если потребуется дополнительная помощь, вы можете подать новое обращение: <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
    except Exception:
        pass

    try:
        await cq.message.edit_text(
            cq.message.html_text + f"\n\n✅ <b>Тикет закрыт автоответом:</b> «{tpl_title}»",
            reply_markup=None
        )
    except Exception:
        pass
    await cq.answer("✅ Автоответ отправлен, тикет закрыт!")


@router.callback_query(F.data.startswith("supp_close:"))
async def cb_supp_close(cq: CallbackQuery, bot: Bot):
    sender_id = cq.from_user.id if cq.from_user else 0
    staff_rank = await db.get_bot_staff_rank(sender_id)
    if not (config.is_bot_owner(sender_id) or sender_id in config.ADMINS or staff_rank >= 1):
        return await cq.answer("⛔️ Доступно только администрации!", show_alert=True)

    ticket_id = int(cq.data.split(":", 1)[1])
    ticket = await db.get_support_ticket(ticket_id)
    if not ticket:
        return await cq.answer("❌ Тикет не найден!", show_alert=True)

    if ticket.get("status") == "closed":
        return await cq.answer("⚠️ Тикет уже закрыт!", show_alert=True)

    await db.close_support_ticket(ticket_id, closed_by=sender_id, closed_name="Администрация")

    user_notify = (
        f"🔒 <b>Ваше обращение (Тикет #{ticket_id}) закрыто администрацией!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 <b>Тема обращения:</b> «<i>{html.escape(ticket['text'])}</i>»\n\n"
        f"<i>Если у вас возникнет новый вопрос, вы можете создать новое обращение: <code>поддержка [вопрос]</code>.</i>"
    )
    try:
        await bot.send_message(ticket["user_id"], user_notify)
    except Exception:
        pass

    try:
        await cq.message.edit_text(
            cq.message.html_text + "\n\n🔒 <b>Тикет закрыт администратором.</b>",
            reply_markup=None
        )
    except Exception:
        pass
    await cq.answer("🔒 Тикет закрыт!")


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
                    "Если ваш вопрос касается перевода или начисления, проверьте баланс командой «баланс». "
                    "При необходимости вы можете создать повторное обращение через команду «поддержка [текст]»."
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
# 6. 🧠 ИИ-КОНСУЛЬТАНТ И ТЕМА КОМАНД ПОДДЕРЖКИ
# ═══════════════════════════════════════════════════════════════

def get_command_quick_answer(q: str) -> str:
    """Точный структурированный ответ на популярные вопросы о системах бота."""
    ql = q.lower()
    if any(k in ql for k in ["ребен", "ребён", "родить", "малыш", "дети", "игрушк", "покормить"]):
        return (
            "🍼 <b>Система детей в отношениях и уход:</b>\n\n"
            "• <b>Завести ребёнка</b> (с 3 уровня отношений):\n"
            "  • <code>отн ребенок мальчик Максим</code>\n"
            "  • <code>отн ребенок девочка Алиса</code>\n"
            "  • Или напишите <code>отн ребенок [Имя]</code> — и выберите пол кнопкой!\n\n"
            "• <b>Профиль малыша:</b> <code>ребенок</code> или <code>мой ребенок</code>\n"
            "  (шкалы сытости, настроения, здоровья, стадия от Младенца до Взрослого)\n\n"
            "• <b>Забота за валюту (🌑):</b>\n"
            "  • <code>покормить ребенка [1-3]</code> — молочная смесь, каша, обед\n"
            "  • <code>купить игрушку [1-4]</code> — погремушка, плюшевый мишка, LEGO, приставка\n"
            "  • <code>одеть ребенка [1-3]</code> — бодик, костюмчик, тёплая куртка\n"
            "  • <code>полечить ребенка [1-2]</code> — витамины, семейный врач\n"
            "  • <code>учить ребенка [1-3]</code> — азбука, секции, академия\n"
            "  <i>Каждая покупка повышает характеристики малыша и даёт очки любви к паре!</i>"
        )
    if any(k in ql for k in ["отн", "отношен", "брак", "поженит", "свадьб", "пара", "обид", "задобрить"]):
        return (
            "💖 <b>Система отношений и браков:</b>\n\n"
            "• <b>Предложить отношения:</b> <code>отн @юзер</code> (или реплаем)\n"
            "• <b>Принять предложение:</b> <code>отн принять</code>\n"
            "• <b>Карточка пары:</b> <code>отн</code> или <code>меню отношений</code>\n"
            "• <b>Семейный банк пары:</b>\n"
            "  • <code>семейный банк положить [сумма]</code>\n"
            "  • <code>семейный банк снять [сумма]</code>\n"
            "• <b>Имущество пары:</b> <code>отн купить [название]</code>\n"
            "• <b>Помириться, если партнёр обижен:</b> <code>отн задобрить</code> (раз в 5 минут)\n"
            "• <b>Заключить брак (ЗАГС):</b> <code>брак @юзер</code> -> <code>свадьба</code>\n"
            "• <b>Развод:</b> <code>развод</code>"
        )
    if any(k in ql for k in ["дк", "доступ команд", "права команды", "ранг команды"]):
        return (
            "🔐 <b>Система Доступа Команд (ДК):</b>\n\n"
            "• <b>Список всех прав:</b> <code>дк</code> или <code>доступ команд</code>\n"
            "• <b>Назначить ранг для команды:</b> <code>дк [команда] [ранг 0-5]</code>\n"
            "  <i>Пример:</i> <code>дк бан 3</code> (команда бан доступна с 3 ранга)\n"
            "  <i>Пример:</i> <code>дк казик 0</code> (разрешить казино всем участникам)\n"
            "• <b>Сбросить права к базовым:</b> <code>дк сброс</code>"
        )
    if any(k in ql for k in ["бизнес", "бизнесы", "предприят", "доход", "прибыль"]):
        return (
            "🏢 <b>Бизнесы и пассивный доход:</b>\n\n"
            "• <b>Каталог предприятий:</b> <code>бизнесы</code>\n"
            "• <b>Купить предприятие:</b> <code>купить бизнес [1-5]</code>\n"
            "• <b>Ваш активный бизнес:</b> <code>бизнес</code>\n"
            "• <b>Собрать накопленный доход:</b> <code>собрать прибыль</code> или <code>снять прибыль</code>\n"
            "• <b>Улучшить бизнес:</b> <code>улучшить бизнес</code> (повышает ежечасную прибыль)"
        )
    if any(k in ql for k in ["перевод", "передать", "п ", "скинуть деньги", "отдать монеты"]):
        return (
            "💸 <b>Перевод монет игрокам:</b>\n\n"
            "• <b>Быстрый перевод по ID или нику:</b>\n"
            "  <code>п [id_или_ник] [сумма]</code>\n"
            "  <i>Пример:</i> <code>п 1301522 5000</code>\n"
            "• <b>Перевод ответом на сообщение:</b>\n"
            "  <code>передать [сумма]</code> (ответом на сообщение получателя)\n"
            "• <b>Проверить свой баланс:</b> <code>баланс</code>"
        )
    if any(k in ql for k in ["казик", "казино", "слоты", "мины", "краш", "дартс", "кубик", "рулетк"]):
        return (
            "🎰 <b>Игровая система и казино:</b>\n\n"
            "• <b>Слоты (автомат):</b> <code>казик [ставка]</code> или <code>слоты [ставка]</code>\n"
            "• <b>Минное поле:</b> <code>мины [ставка] [кол-во мин 2-24]</code>\n"
            "• <b>Краш (ракета):</b> <code>краш [ставка]</code>\n"
            "• <b>Дартс:</b> <code>дартс [ставка]</code>\n"
            "• <b>Кубик:</b> <code>кубик [ставка]</code>\n"
            "• <b>Общий джекпот чата:</b> <code>джекпот</code>"
        )
    if any(k in ql for k in ["босс", "боссы", "рейд"]):
        return (
            "🐉 <b>Рейдовые Боссы чата:</b>\n\n"
            "• Боссы появляются 4 раза в день (08:00, 12:00, 16:00, 20:00).\n"
            "• <b>Привязать тему для боёв:</b> <code>+тема босс</code>\n"
            "• <b>Текущий босс:</b> <code>босс</code>\n"
            "• <b>Атака в ближнем бою:</b> <code>ударить</code> или <code>атака</code>\n"
            "• <b>Выстрел из лука/оружия:</b> <code>выстрел</code>\n"
            "• <b>Лечение союзников:</b> <code>хил</code> или <code>аптечка</code>\n"
            "• <b>Магазин снаряжения:</b> <code>магазин босса</code>"
        )
    if any(k in ql for k in ["мут", "бан", "варн", "кик", "модер", "наказан"]):
        return (
            "🛡 <b>Команды модерации чата:</b>\n\n"
            "• <b>Временный мут (ответом):</b> <code>мут 2 часа спам</code>, <code>мут 10м флуд</code>\n"
            "• <b>Предупреждение:</b> <code>варн [причина]</code> (3 варна = автомут/бан)\n"
            "• <b>Блокировка:</b> <code>бан [время] [причина]</code> (ответом или <code>бан @ник</code>)\n"
            "• <b>Исключение из чата:</b> <code>кик</code> (ответом на нарушителя)\n"
            "• <b>Снятие наказания:</b> <code>размут</code>, <code>разбан</code>, <code>снять варн</code>"
        )
    if any(k in ql for k in ["рп", "обнять", "поцеловать", "погладить", "ударить"]):
        return (
            "🎭 <b>РП-команды и взаимодействия:</b>\n\n"
            "• <b>Как использовать:</b>\n"
            "  • Ответьте реплаем на сообщение: <code>обнять</code>, <code>поцеловать</code>\n"
            "  • Или укажите юзернейм: <code>поцеловать @user</code>, <code>погладить @user</code>\n"
            "• <b>Список всех 40+ действий:</b> <code>рп</code>\n"
            "• <b>Ваша статистика:</b> <code>рп статистика</code>"
        )
    if any(k in ql for k in ["описан", "анкет", "шаблон"]):
        return (
            "📝 <b>Система описаний и анкет:</b>\n\n"
            "• <b>Просмотреть описание:</b> <code>описание</code> (своё или ответом)\n"
            "• <b>Заполнить по шаблону:</b> <code>+описание</code>\n"
            "• <b>Сбросить описание:</b> <code>-описание</code>\n"
            "• <b>Тема анкет в форуме:</b> <code>тема описания</code>"
        )
    return (
        "📖 <b>Справочник команд бота Moxxi:</b>\n\n"
        "• <b>Главное меню:</b> <code>меню</code> или <code>команды</code>\n"
        "• <b>Экономика:</b> <code>баланс</code>, <code>бонус</code>, <code>работа</code>, <code>п [id] [сумма]</code>\n"
        "• <b>Отношения и дети:</b> <code>отн @юзер</code>, <code>отн ребенок [Имя]</code>, <code>ребенок</code>\n"
        "• <b>Игры:</b> <code>казик [ставка]</code>, <code>мины [ставка]</code>, <code>апп</code>\n"
        "• <b>Модерация:</b> <code>мут [время]</code>, <code>варн</code>, <code>бан</code>, <code>дк</code>\n"
        "• <b>Боссы:</b> <code>босс</code>, <code>ударить</code>, <code>+тема босс</code>"
    )


async def handle_ai_command_question(message: Message, bot: Bot, query: str) -> None:
    """Универсальная обработка вопроса по командам с мгновенным таймером ответа."""
    q = (query or "").strip()
    if not q and message.reply_to_message:
        q = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not q:
        return await message.reply(
            "🧠 <b>Задайте любой вопрос по командам бота:</b>\n\n"
            "• <code>как сделать отн?</code>\n"
            "• <code>как завести и растить ребенка?</code>\n"
            "• <code>как настроить дк?</code>\n"
            "• <code>как купить бизнес и собирать прибыль?</code>\n"
            "• <code>как передать деньги другому игроку?</code>\n\n"
            "💡 <i>ИИ Moxxi проанализирует вопрос и сразу выдаст инструкцию с точным синтаксисом команд!</i>"
        )

    # 1. МГНОВЕННЫЙ СТАТУС С РАСЧЁТНЫМ ВРЕМЕНЕМ (чтобы пользователь видел, что бот не завис!)
    status_msg = None
    try:
        status_msg = await message.reply(
            "⏳ <b>Анализирую ваш вопрос...</b>\n"
            "🤖 <i>ИИ Moxxi изучает команды и механику бота. Ответ появится через ~3-5 сек...</i>"
        )
    except Exception:
        pass

    try:
        from aiogram.enums import ChatAction
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception:
        pass

    # 2. ФОРМИРОВАНИЕ ИИ-ОТВЕТА
    system_prompt = (
        "Ты — официальный дружелюбный эксперт-консультант русскоязычного Telegram-бота 'Moxxi Bot'. "
        "Твоя задача — точно, понятно и пошагово объяснить игроку, как работает та или иная команда или система бота, "
        "чтобы разгрузить живую техподдержку. "
        "Всегда пиши команды строго в тегах <code>команда</code> и давай краткие наглядные примеры.\n\n"
        "Главные системы бота Moxxi:\n"
        "1. Отношения и брак: «отн @юзер» — предложить, «отн принять», «отн» — карточка пары, "
        "«семейный банк положить/снять [сумма]», «отн задобрить» (при обиде), «брак @юзер», «свадьба», «развод».\n"
        "2. Дети в отношениях: «отн ребенок мальчик/девочка [Имя]» (с 3 ур. отношений, пол можно выбрать текстом или кнопками). "
        "«ребенок» — карточка малыша со шкалами сытости, настроения, здоровья и стадиями взросления. "
        "Уход за валюту 🌑: «покормить ребенка [1-3]», «купить игрушку [1-4]», «одеть ребенка [1-3]», «полечить ребенка [1-2]», «учить ребенка [1-3]».\n"
        "3. Доступ команд (ДК): «дк» — просмотр прав чата, «дк [команда] [ранг 0-5]» — смена ранга доступа, «дк сброс».\n"
        "4. Экономика: «баланс», «бонус» (ежедневный), «работа» (профессии), «крайм», «п [id/@ник] [сумма]» или «передать [сумма]» ответом.\n"
        "5. Предприятия: «бизнесы» (каталог 1-5), «купить бизнес [номер]», «бизнес», «собрать прибыль», «улучшить бизнес».\n"
        "6. Игры и Казино: «казик [ставка]», «мины [ставка]», «краш [ставка]», «дартс [ставка]», «кубик [ставка]», «джекпот».\n"
        "7. Рейдовые Боссы: появляются 4 раза в день, «+тема босс» — привязка темы, «босс», «ударить», «выстрел», «хил», «аптечка».\n"
        "8. PvP-Дуэли: «дуэль @user [ставка]», «принять», «отклонить», «мои дуэли».\n"
        "9. РП-действия: «обнять», «поцеловать», «погладить», «ударить» реплаем или с «@ником» (например, «обнять @user»). Список: «рп».\n"
        "10. Модерация: «мут [время] [причина]», «варн», «бан», «кик», «расписание», «настройки».\n\n"
        "Ответь структурированно, красиво, с эмодзи и выдели ключевые команды. Длина: 2-4 коротких абзаца."
    )

    ai_reply = None
    try:
        import core_ai
        ai_reply = await core_ai.ask_text(f"Вопрос пользователя по боту: {q}", system=system_prompt, max_tokens=700)
    except Exception as e:
        log.warning("AI ask error: %s", e)

    # Если ИИ недоступен — мгновенный умный фолбэк по ключевым словам!
    if not ai_reply or len(ai_reply.strip()) < 15:
        ai_reply = get_command_quick_answer(q)

    final_text = (
        f"🤖 💡 <b>ОТВЕТ ИИ-КОНСУЛЬТАНТА ПО КОМАНДАМ:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ <b>Вопрос:</b> «<i>{html.escape(q)}</i>»\n\n"
        f"{ai_reply}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Если вам требуется помощь администрации по оплате или багу: <code>поддержка [вопрос]</code>.</i>"
    )

    if status_msg:
        try:
            return await status_msg.edit_text(final_text, disable_web_page_preview=True)
        except Exception:
            pass
    await message.reply(final_text, disable_web_page_preview=True)


@router.message(Cmd("вопрос", "спросить", "как сделать", "помощь по боту", "хелп бот",
                    section=S_COMMUNITY, usage="вопрос [ваш вопрос по боту]",
                    desc="Задать любой вопрос умному ИИ-Консультанту по боту"))
async def cmd_ask_ai_helper(message: Message, bot: Bot, args: str = "", **kw):
    await handle_ai_command_question(message, bot, args)


@router.message(Cmd("тема команды", "тема команд", "тема помощь", "тема вопросов",
                    "+тема команды", "+тема команд", "+тема помощь", "+тема вопросов",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="тема команды [номер|ссылка]",
                    desc="Привязать ветку чата для вопросов по командам с ИИ-ответами"))
async def cmd_bind_commands_topic(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id if message.from_user else 0
    staff_rank = await db.get_bot_staff_rank(uid)
    is_bot_owner_or_admin = config.is_bot_owner(uid) or uid in config.ADMINS or staff_rank >= 3
    if not is_bot_owner_or_admin:
        return  # Молча игнорируем! Обычные игроки, модераторы и создатели групп не имеют доступа, сообщение остаётся обычным текстом в чате.

    if message.chat.type == "private":
        return await message.reply("⚠️ Команда привязки темы работает только в группах с включенными темами (форум).")

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в супергруппах с включенными Темами (Форум)!</b>\n\n"
            "Чтобы включить темы в Telegram: <i>Настройки группы → Темы (Вкл)</i>."
        )

    a = (args or "").strip()
    if a.lower() in {"сброс", "убрать", "выкл", "off", "del"}:
        await db.set_setting(message.chat.id, "commands_topic", "0")
        await db.set_global_setting("global_commands_chat_topic", "0")
        await db.set_global_setting("global_commands_topic", "0")
        return await message.reply("✅ <b>Привязка темы команд снята.</b>\nИИ-консультант доступен по команде: <code>вопрос [текст]</code>.")

    import re
    tid = 0
    m = re.search(r"t\.me/c/\d+/(\d+)", a)
    if m:
        tid = int(m.group(1))
    elif a.isdigit():
        tid = int(a)
    elif not a:
        tid = getattr(message, "message_thread_id", None) or 0

    if not tid or tid <= 1:
        cur_t = await db.get_setting(message.chat.id, "commands_topic", "0")
        cur_txt = f"ID: {cur_t}" if cur_t != "0" else "не задана"
        return await message.reply(
            f"📌 <b>Тема для вопросов по командам и ИИ-помощи</b>\n\n"
            f"Текущая тема: <b>{cur_txt}</b>\n\n"
            f"👉 <b>Как установить:</b>\n"
            f"• Перейдите в нужную ветку форума (напр. «❓ Вопросы по командам») и напишите: <code>тема команды</code> или <code>+тема команды</code>\n"
            f"• Или укажите ссылку: <code>тема команды https://t.me/c/12345/678</code>\n\n"
            f"❌ Отвязать: <code>тема команды сброс</code> или <code>-тема команды</code>"
        )

    await db.set_setting(message.chat.id, "commands_topic", str(tid))
    await db.set_global_setting("global_commands_chat", str(message.chat.id))
    await db.set_global_setting("global_commands_chat_topic", str(tid))
    await db.set_global_setting("global_commands_topic", str(tid))
    await message.reply(
        f"✅ <b>Тема для вопросов по командам успешно установлена!</b>\n\n"
        f"📌 ID ветки: <code>{tid}</code>\n"
        f"👑 <i>Установлено Администрацией бота.</i>\n\n"
        f"Теперь любой участник может написать свой вопрос прямо в эту ветку (например: «как сделать отн?», «как грабить?», «как завести ребенка?»), "
        f"и ИИ Moxxi сразу ответит с таймером и подробной инструкцией!"
    )


@router.message(Cmd("-тема команды", "-тема команд", "-тема помощь", "-тема вопросов",
                    "выкл тема команды", section=S_COMMUNITY, rank=0, group_only=False,
                    usage="-тема команды", desc="Отвязать тему вопросов по командам"))
async def cmd_unbind_commands_topic(message: Message, bot: Bot, **kw):
    uid = message.from_user.id if message.from_user else 0
    staff_rank = await db.get_bot_staff_rank(uid)
    is_bot_owner_or_admin = config.is_bot_owner(uid) or uid in config.ADMINS or staff_rank >= 3
    if not is_bot_owner_or_admin:
        return  # Молча игнорируем!

    await db.set_setting(message.chat.id, "commands_topic", "0")
    await db.set_global_setting("global_commands_chat_topic", "0")
    await db.set_global_setting("global_commands_topic", "0")
    await message.reply("✅ <b>Привязка темы команд снята.</b>")


# ═══════════════════════════════════════════════════════════════
# 7. ДЕЙСТВИЯ ВЫСШЕЙ АДМИНИСТРАЦИИ НАД СТАФФОМ (ОПРАВДАНИЕ / МУТ / ВАРН)
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("staff_act:"))
async def cb_staff_action(call: CallbackQuery, bot: Bot):
    uid = call.from_user.id
    if not config.is_bot_owner(uid):
        return await call.answer("🔒 Доступно только Высшей Администрации (Владельцам) бота!", show_alert=True)

    parts = call.data.split(":")
    action = parts[1]
    staff_id = int(parts[2])
    ticket_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

    if action == "unwarn":
        new_warns = await db.remove_staff_warn(staff_id)
        try:
            await bot.send_message(
                staff_id,
                "✅ <b>Ваш варн снят!</b>\nВысшая администрация во всём разобралась, извиняемся перед вами за ложное срабатывание."
            )
        except Exception:
            pass
        await call.message.edit_text(
            call.message.html_text + f"\n\n✅ <b>Сотрудник оправдан Высшей Администрацией.</b>\nВарн аннулирован (текущих варнов: {new_warns}/3). Извинения отправлены сотруднику в ЛС."
        )
        return await call.answer("Сотрудник оправдан, варн снят!", show_alert=True)

    if action == "choose":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Выдать варн", callback_data=f"staff_act:warn:{staff_id}:{ticket_id}"),
                InlineKeyboardButton(text="🔇 Мут на 1 час", callback_data=f"staff_act:mute:{staff_id}:{ticket_id}")
            ],
            [
                InlineKeyboardButton(text="🚫 Снять со стаффа", callback_data=f"staff_act:demote:{staff_id}:{ticket_id}"),
                InlineKeyboardButton(text="🟢 Снять мут / Оправдать", callback_data=f"staff_act:unmute:{staff_id}:{ticket_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"staff_act:back:{staff_id}:{ticket_id}")
            ]
        ])
        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer()

    if action == "back":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Оправдать (Снять варн)", callback_data=f"staff_act:unwarn:{staff_id}:{ticket_id}"),
                InlineKeyboardButton(text="⚖️ Выбрать наказание", callback_data=f"staff_act:choose:{staff_id}:{ticket_id}")
            ]
        ])
        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer()

    if action == "warn":
        warns = await db.add_staff_warn(staff_id)
        try:
            await bot.send_message(staff_id, f"⚠️ <b>Высшая Администрация утвердила выговор (варн)!</b>\nВаш текущий баланс варнов: {warns}/3.")
        except Exception:
            pass
        await call.message.edit_text(
            call.message.html_text + f"\n\n⚖️ <b>Высшая Администрация утвердила выговор.</b> Варнов: {warns}/3."
        )
        return await call.answer(f"Варн выдан! Всего: {warns}/3", show_alert=True)

    if action == "mute":
        await db.staff_mute(staff_id, 3600)
        try:
            await bot.send_message(staff_id, "🔇 <b>Высшая Администрация выдала вам мут на 1 час</b> в системе ответов техподдержки.")
        except Exception:
            pass
        await call.message.edit_text(
            call.message.html_text + "\n\n🔇 <b>Сотруднику выдан мут на 1 час</b> в техподдержке."
        )
        return await call.answer("Мут выдан на 1 час", show_alert=True)

    if action == "unmute":
        await db.staff_unmute(staff_id)
        try:
            await bot.send_message(
                staff_id,
                "✅ <b>Ваш мут снят!</b>\nВысшая администрация во всём разобралась, извиняемся перед вами."
            )
        except Exception:
            pass
        await call.message.edit_text(
            call.message.html_text + "\n\n🟢 <b>Мут успешно снят.</b> Извещение с извинениями отправлено сотруднику."
        )
        return await call.answer("Мут снят!", show_alert=True)

    if action == "demote":
        await db.remove_bot_staff(staff_id)
        try:
            await bot.send_message(staff_id, "🚫 <b>Вы были сняты со стаффа бота</b> решением Высшей Администрации.")
        except Exception:
            pass
        await call.message.edit_text(
            call.message.html_text + "\n\n🚫 <b>Сотрудник снят со стаффа бота.</b>"
        )
        return await call.answer("Сотрудник снят со стаффа", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# 8. ПРАВИЛА СООБЩЕСТВА И ЧАТА ОБЩЕНИЯ
# ═══════════════════════════════════════════════════════════════

COMMUNITY_RULES_TEXT = (
    "💜 ✨ <b>ПРАВИЛА СООБЩЕСТВА MOXXI | ЧАТ ОБЩЕНИЯ</b> ✨ 💜\n"
    "✦ ════════ • ⊰ 💖 🔮 🎰 🏢 ⚔️ 🪙 👑 ⊱ • ════════ ✦\n\n"
    "Добро пожаловать в официальный чат <b>MOXXI Community</b>!\n"
    "Для комфортного, дружелюбного и безопасного отдыха в чате действует понятная система правил и чётких санкций:\n\n"
    "⚠️ <b>1. НАРУШЕНИЯ, ЗА КОТОРЫЕ ВЫДАЁТСЯ ВАРН (ПРЕДУПРЕЖДЕНИЕ):</b>\n"
    "• 1.1. <b>Флуд и спам:</b> отправка одинаковых сообщений, стикеров или эмодзи (от 3 подряд) ➔ ⚠️ Варн + удаление;\n"
    "• 1.2. <b>Злоупотребление КАПСОМ:</b> сообщения целиком верхним регистром ➔ ⚠️ Варн + удаление;\n"
    "• 1.3. <b>Команды в общей теме:</b> использование игровых команд и казино в ветке «Общение» вместо ветки «Команды & ИИ» ➔ ⚠️ Варн + перенаправление в тему команд;\n"
    "• 1.4. <b>Провокации:</b> разжигание бессмысленных споров, токсичные подколы и травля ➔ ⚠️ Варн.\n\n"
    "🔇 <b>2. НАРУШЕНИЯ, ЗА КОТОРЫЕ ВЫДАЁТСЯ МУТ (БЛОКИРОВКА ЧАТА):</b>\n"
    "• 2.1. <b>Нецензурная брань:</b> открытый мат в чате, грубые пошлости ➔ 🔇 Мут на 1 час + ⚠️ Варн;\n"
    "• 2.2. <b>Прямые адресные оскорбления:</b> унижение участников, токсичность ➔ 🔇 Мут на 2–6 часов + ⚠️ Варн;\n"
    "• 2.3. <b>Повторный мат / оскорбления:</b> продолжение нарушений после варна ➔ 🔇 Мут на 12–24 часа;\n"
    "• 2.4. <b>Упоминание / оскорбление родных:</b> неуважительные высказывания в адрес близких ➔ 🔇 Мут на 24 часа + ⚠️⚠️ 2 Варна (при включенном бане в настройках чата — Бан 24ч);\n"
    "• 2.5. <b>Политика и межнациональная рознь:</b> политические, религиозные споры и вражда ➔ 🔇 Мут на 12–24 часа + ⚠️ Варн.\n\n"
    "👢 <b>3. НАРУШЕНИЯ, ЗА КОТОРЫЕ ПРИМЕНЯЕТСЯ КИК (ИСКЛЮЧЕНИЕ):</b>\n"
    "• 3.1. <b>Лимит 3/3 варнов:</b> накопление 3 предупреждений (если в настройках чата включен Кик) ➔ 👢 Кик из чата;\n"
    "• 3.2. <b>Обход мута:</b> общение со второго аккаунта (твинка) во время мута ➔ 👢 Кик твинка + продление мута основному аккаунту;\n"
    "• 3.3. <b>Спам-боты:</b> добавление вредоносных ботов или юзерботов ➔ 👢 Немедленный Кик бота.\n\n"
    "⛔️ <b>4. НАРУШЕНИЯ, ЗА КОТОРЫЕ ВЫДАЁТСЯ БАН (БЛОКИРОВКА):</b>\n"
    "• 4.1. <b>Скам и мошенничество:</b> обман игроков, продажа монет/виртов за реальные деньги вне бота ➔ ⛔️ Вечный Бан;\n"
    "• 4.2. <b>Контент 18+ и NSFW:</b> распространение порнографии, интим-фото, расчлененки, шок-контента ➔ ⛔️ Бан навсегда;\n"
    "• 4.3. <b>Несогласованная реклама:</b> спам ссылками на сторонние каналы, чаты, боты и рефералки ➔ ⛔️ Вечный Бан;\n"
    "• 4.4. <b>Деанон:</b> слив личных данных, номеров телефонов, реальных адресов или фото без согласия ➔ ⛔️ Вечный Бан;\n"
    "• 4.5. <b>Рейды и вредительство:</b> участие в рейдах, попытки сломать или закрашить беседу ➔ ⛔️ Вечный Бан.\n\n"
    "⚖️ <b>5. ЛЕСТНИЦА ПРЕДУПРЕЖДЕНИЙ (ВАРНОВ):</b>\n"
    "• 1-й варн: ⚠️ Предупреждение;\n"
    "• 2-й варн: ⚠️⚠️ Второе предупреждение + 🔇 Мут на 2–12 часов;\n"
    "• 3-й варн (лимит): 🚫 Автоматический Кик или Бан (зависит от настроек чата через команду <code>+автоправила</code>).\n\n"
    "✦ ══════════════════════════════════ ✦\n"
    "<i>Администрация и ИИ-надзор Moxxi следят за чатом круглосуточно. Соблюдайте правила и приятного общения!</i>"
)


@router.message(Cmd("правила", "правила общения", "правила чата", "правила сообщества", "rules",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="правила", desc="Правила сообщества и чата общения MOXXI"))
async def cmd_rules(message: Message, bot: Bot, **kw):
    comm_chat = await db.get_global_setting("global_community_chat", "")
    chat_u = getattr(message.chat, "username", "") or ""
    is_comm = (message.chat.type == "private") or (chat_u.lower() == "moxxi_chat") or (comm_chat and str(message.chat.id) == comm_chat)

    if message.chat.type != "private" and not is_comm:
        custom_rules = await db.get_setting(message.chat.id, "rules_text") or await db.get_setting(message.chat.id, "rules")
        if custom_rules:
            from h_chatset import render_rules_card, get_rules_topic
            frame_on = (await db.get_setting(message.chat.id, "rules_card_frame", "1") == "1")
            rtopic = await get_rules_topic(message.chat.id)
            is_forum = bool(getattr(message.chat, "is_forum", False))
            title = message.chat.title or "Беседа"
            if frame_on:
                card, kb_custom = render_rules_card(title, custom_rules, is_forum=is_forum, chat_id=message.chat.id, rules_topic=rtopic)
                return await message.reply(card, reply_markup=kb_custom, disable_web_page_preview=True)
            else:
                return await message.reply(custom_rules, disable_web_page_preview=True)

    me = await bot.me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Задать вопрос ИИ", switch_inline_query_current_chat="ии какие правила?"),
            InlineKeyboardButton(text="🆘 Техподдержка", url=f"https://t.me/{me.username}?start=support")
        ],
        [
            InlineKeyboardButton(text="📖 Меню & Команды", url=f"https://t.me/{me.username}?start=cmds")
        ]
    ])
    await message.reply(COMMUNITY_RULES_TEXT, reply_markup=kb)


@router.callback_query(F.data == "chat_rules_btn")
async def cb_chat_rules(call: CallbackQuery):
    await call.message.reply(COMMUNITY_RULES_TEXT)
    await call.answer()


@router.message(Cmd("+тест приветствие", "приветствие общение", section=S_COMMUNITY, rank=0, group_only=False,
                    desc="Посмотреть приветствие чата общения (только Владелец)"))
async def cmd_test_welcome(message: Message, bot: Bot, **kw):
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid):
        return
    me = await bot.me()
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
    card = (
        f"💜 ✨ <b>ДОБРО ПОЖАЛОВАТЬ В MOXXI COMMUNITY!</b> ✨ 💜\n"
        f"✦ ════════ • ⊰ 💖 🔮 🎰 🏢 ⚔️ 🪙 👑 ⊱ • ════════ ✦\n\n"
        f"👋 Приветствуем тебя в нашем официальном чате, {mention_id(uid, message.from_user.first_name)}!\n"
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
    await message.reply(card, reply_markup=comm_kb)


# ═══════════════════════════════════════════════════════════════
# 9. ОБРАЗЕЦ ОФОРМЛЕНИЯ ТЕМЫ КОМАНД И ОБРАЩЕНИЯ К ИИ (+ОБРАЗЕЦ ИИ)
# ═══════════════════════════════════════════════════════════════

_last_sample_msgs: dict[tuple[int, int], int] = {}

AI_COMMANDS_SAMPLE_TEXT = """🤖 ✨ <b>ОБРАЗЕЦ ОБРАЩЕНИЯ К ИИ И КОМАНД БОТА</b> ✨ 🤖
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
👋 Привет, {user_mention}! Чтобы бот или умный ИИ-помощник сразу вас понял, используйте правильный формат:

🧠 <b>1. Как обратиться к ИИ-помощнику MOXXI:</b>
Начните фразу со слова <code>ии</code>, <code>бот</code> или <code>moxxi</code>:
• <code>ии как работают бизнесы и сбор дохода?</code>
• <code>ии как создать свой клан и пригласить друзей?</code>
• <code>ии какие шансы на победу в казино и рулетке?</code>
• <code>ии объясни правила сообщества и дуэлей</code>
<i>💡 Также можно просто ответить (Reply) на любое сообщение бота своим вопросом!</i>

⚙️ <b>2. Как вводить основные команды:</b>
• <code>меню</code> — интерактивное меню бота со всеми разделами;
• <code>баланс</code> — проверить баланс монет и состояние банка;
• <code>бонус</code> — забрать ежедневную бесплатную награду;
• <code>рулетка</code> — крутить Колесо Фортуны раз в день;
• <code>квесты</code> — список ежедневных заданий с призами;
• <code>казик [ставка]</code> — сыграть в казино (например: <code>казик 1000</code>);
• <code>поддержка [вопрос]</code> — отправить тикет администраторам.

┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
🎯 <i>Отправьте вопрос к ИИ или нужную команду прямо сейчас!</i>"""


async def check_and_send_commands_sample(message: Message, bot: Bot) -> bool:
    """Проверяет сообщение в теме команд и при необходимости отправляет образец."""
    if message.chat.type == "private":
        return False
    if not message.from_user or message.from_user.is_bot:
        return False

    tid = message.message_thread_id or 0
    cid = message.chat.id
    uid = message.from_user.id

    is_owner = config.is_bot_owner(uid)

    # Проверяем, включен ли автообразец для этой темы или чата
    is_topic_on = (await db.get_setting(cid, f"ai_sample_topic_{tid}", "0") == "1")
    is_general_on = (await db.get_setting(cid, "sample_topic_enabled", "0") == "1")
    target_topic = await db.get_setting(cid, "sample_commands_topic", "0")
    if not (is_topic_on or (is_general_on and (target_topic == "0" or target_topic == str(tid)))):
        return False

    text = (message.text or message.caption or "").strip()
    low = text.lower()

    # Если игрок уже обратился к ИИ или вызвал команду, не мешаем ему
    if low.startswith(("ии ", "ии,", "бот ", "moxxi ", "мокси ", "+", "/", "!", ".")):
        return False
    common_cmds = {"меню", "menu", "баланс", "бонус", "рулетка", "квесты", "дейлики", "топ", "профиль", "помощь", "хелп", "help", "инвентарь", "рынок", "бизнесы", "собрать", "казик", "дуэль", "поддержка"}
    if any(low.startswith(c) for c in common_cmds):
        return False

    # Кулдаун: для владельца 3 секунды (для быстрых тестов функционала), для игроков 35 секунд
    cd_secs = 3 if is_owner else 35
    cd_key = f"cmd_sample_{tid}"
    if await db.cooldown_left(uid, cd_key, cd_secs) > 0:
        return False
    await db.set_cooldown(uid, cd_key)

    # Удаляем предыдущий образец в этой теме, если остался
    prev_id = _last_sample_msgs.get((cid, tid))
    if prev_id:
        try:
            await bot.delete_message(cid, prev_id)
        except Exception:
            pass

    card = AI_COMMANDS_SAMPLE_TEXT.format(user_mention=mention_id(uid, message.from_user.first_name))
    me = await bot.me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Задать вопрос ИИ", switch_inline_query_current_chat="ии как играть?"),
            InlineKeyboardButton(text="📖 Меню команд", url=f"https://t.me/{me.username}?start=cmds")
        ]
    ])
    try:
        sent = await message.reply(card, reply_markup=kb)
        _last_sample_msgs[(cid, tid)] = sent.message_id
        return True
    except Exception:
        return False


@router.message(Cmd("+образец ии", "+автообразец", "+образец команд", "+образец темы", "образец ии",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="+образец ии", desc="Включить автообразец обращения к ИИ и команд для темы (только Владелец)"))
async def cmd_sample_topic_on(message: Message, bot: Bot, **kw):
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid):
        return  # Тихий пропуск для обычных игроков и модераторов групп!

    tid = message.message_thread_id or 0
    await db.set_setting(message.chat.id, f"ai_sample_topic_{tid}", "1")
    await db.set_setting(message.chat.id, "sample_topic_enabled", "1")
    await db.set_setting(message.chat.id, "sample_commands_topic", str(tid))

    topic_str = f"в ветке #{tid}" if tid else "в этом чате"
    await message.reply(
        f"✅ <b>Автообразец обращений к ИИ и команд успешно включён {topic_str}!</b>\n\n"
        f"🤖 Теперь при активности игроков бот будет отправлять наглядный образец:\n"
        f"• Как правильно обращаться к ИИ-помощнику (<code>ии [вопрос]</code>);\n"
        f"• Как вводить ключевые игровые команды бота.\n\n"
        f"🔒 <i>Выключить: <code>-образец ии</code></i>"
    )


@router.message(Cmd("-образец ии", "-автообразец", "-образец команд", "-образец темы",
                    section=S_COMMUNITY, rank=0, group_only=False,
                    usage="-образец ии", desc="Выключить автообразец обращения к ИИ и команд (только Владелец)"))
async def cmd_sample_topic_off(message: Message, bot: Bot, **kw):
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid):
        return  # Тихий пропуск для обычных игроков!

    tid = message.message_thread_id or 0
    await db.set_setting(message.chat.id, f"ai_sample_topic_{tid}", "0")
    await db.set_setting(message.chat.id, "sample_topic_enabled", "0")
    await message.reply("✅ <b>Автообразец для темы команд выключен.</b>")



