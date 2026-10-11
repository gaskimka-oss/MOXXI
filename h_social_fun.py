"""💖 Социальные развлечения для чата: Пара дня, Гороскоп и Таро, Цитатник, Угощения и Вопрос дня.

Идеальные механики общения, создающие уют, смех и взрывную активность в чате БЕЗ азартных игр.
"""
from __future__ import annotations

import asyncio
import html
import random
import re
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from utils import mention, mention_id

router = Router(name="social_fun")
S_SOCIAL = 45  # Раздел: Душевные развлечения и общение

# ══════════════════════════════════════════════════════════════
# 1. 💖 «ПАРА ДНЯ В ЧАТЕ» / ШИППЕРИНГ
# ══════════════════════════════════════════════════════════════

PAIR_STORIES = [
    "Судьба свела их взгляды в потоке сообщений! Между ними вспыхнула искра в 10 000 вольт! ⚡️",
    "Они подходят друг другу идеально, как утренний кофе и свежий круассан! ☕️🥐",
    "Звёзды сегодня сошлись в идеальном параде планет: этот союз благословлен самой Мокси! 🪐✨",
    "Их совместимость зашкаливает! Чат требует совместную свадьбу и торт! 🎂🥂",
    "Один лайк, один реплай — и началась великая история любви этой беседы! 💕",
    "Они спорили из-за ерунды, но от ненависти до любви оказался всего один шаг! 💋",
    "Гороскопы, карты Таро и нейросети единогласно сошлись: они созданы друг для друга! 🔮",
    "Когда они пишут в чат одновременно, сервер начинает плавиться от романтики! 🔥",
    "Самая гармоничная и милая парочка нашего комьюнити на сегодня! Берегите друг друга! 🕊",
    "Даже бот засмотрелся на эту гармонию. Совет вам да любовь, голубки! 💍✨",
]


@router.message(Cmd("пара дня", "шип", "шипперить", "шипперинг", "любовь дня", section=S_SOCIAL,
                    usage="пара дня", desc="Выбрать случайную пару дня в чате"))
async def cmd_pair_of_day(message: Message, bot: Bot, **kw):
    if message.chat.type not in {"group", "supergroup"}:
        return await message.reply("💖 Команда «Пара дня» работает только в беседах и группах!")

    today = time.strftime("%Y-%m-%d")
    existing = await db.get_pair_of_day(message.chat.id, today)

    if existing:
        u1_link = mention_id(existing["user1_id"], existing["user1_name"])
        u2_link = mention_id(existing["user2_id"], existing["user2_name"])
        pct = existing["compatibility"]
        bar_len = 10
        filled = int((pct / 100) * bar_len)
        bar = "💖" * filled + "🤍" * (bar_len - filled)

        text = (
            f"💖 ✨ <b>ПАРА ДНЯ В НАШЕМ ЧАТЕ</b> ✨ 💖\n"
            f"✦ ══ • ⊰ 💍 👩‍❤️‍👨 🥂 ⊱ • ══ ✦\n\n"
            f"👩‍❤️‍👨 <b>{u1_link}</b>  ➕  <b>{u2_link}</b>\n\n"
            f"📊 <b>Совместимость:</b> <b>{pct}%</b>\n"
            f"<code>[{bar}]</code>\n\n"
            f"💌 <i>{existing['story']}</i>\n\n"
            f"💋 <i>Следующий выбор пары откроется завтра!</i>"
        )
        return await message.reply(text)

    # Ищем участников чата
    rows = await db.fetchall(
        "SELECT user_id FROM chat_members WHERE chat_id=? AND is_member=1 ORDER BY updated_at DESC LIMIT 60",
        (message.chat.id,)
    )
    user_ids = [r["user1_id"] if "user1_id" in r else r["user_id"] for r in rows]
    # Добавляем автора, если его ещё нет
    if message.from_user.id not in user_ids:
        user_ids.append(message.from_user.id)

    if len(user_ids) < 2:
        return await message.reply("В чате пока маловато активности, чтобы звёзды смогли найти двух половинок! Пообщайтесь немного.")

    # Выбираем двух разных людей
    u1_id, u2_id = random.sample(user_ids, 2)
    u1_info = await db.get_user(u1_id)
    u2_info = await db.get_user(u2_id)

    name1 = u1_info["first_name"] if u1_info else f"Участник {u1_id}"
    name2 = u2_info["first_name"] if u2_info else f"Участник {u2_id}"

    # Делаем выбор с интригой
    intro = await message.reply("🔮 <i>Мокси тасует колоду судеб и зажигает звёзды чата...</i>")
    await asyncio.sleep(1.2)

    compat = random.randint(72, 100)
    story = random.choice(PAIR_STORIES)
    await db.set_pair_of_day(message.chat.id, today, u1_id, u2_id, name1, name2, compat, story)

    bar_len = 10
    filled = int((compat / 100) * bar_len)
    bar = "💖" * filled + "🤍" * (bar_len - filled)

    u1_link = mention_id(u1_id, name1)
    u2_link = mention_id(u2_id, name2)

    res_card = (
        f"💖 ✨ <b>ПАРА ДНЯ В НАШЕМ ЧАТЕ!</b> ✨ 💖\n"
        f"✦ ══ • ⊰ 💍 👩‍❤️‍👨 🥂 ⊱ • ══ ✦\n\n"
        f"Сегодня звёзды выбрали этих счастливчиков:\n"
        f"👩‍❤️‍👨 <b>{u1_link}</b>  ➕  <b>{u2_link}</b>\n\n"
        f"📊 <b>Совместимость пары:</b> <b>{compat}%</b>\n"
        f"<code>[{bar}]</code>\n\n"
        f"💌 <i>{story}</i>\n\n"
        f"🥂 <i>Поздравляем новоиспечённую пару дня!</i>"
    )
    try:
        await intro.edit_text(res_card)
    except Exception:
        await message.reply(res_card)


# ══════════════════════════════════════════════════════════════
# 2. 🔮 ГОРОСКОП И КАРТЫ ТАРО ОТ МОКСИ
# ══════════════════════════════════════════════════════════════

ZODIAC_SIGNS = {
    "овен": ("♈️", "Овен"),
    "телец": ("♉️", "Телец"),
    "близнецы": ("♊️", "Близнецы"),
    "рак": ("♋️", "Рак"),
    "лев": ("♌️", "Лев"),
    "дева": ("♍️", "Дева"),
    "весы": ("♎️", "Весы"),
    "скорпион": ("♏️", "Скорпион"),
    "стрелец": ("♐️", "Стрелец"),
    "козерог": ("♑️", "Козерог"),
    "водолей": ("♒️", "Водолей"),
    "рыбы": ("♓️", "Рыбы"),
}

HORO_TEXTS = [
    {
        "love": "Сегодня вам напишет тот, о ком вы думали весь вечер. Держите сердце открытым!",
        "money": "Отличный день для покупок и расширения бизнеса. Интуиция не подведёт!",
        "tip": "Не стесняйтесь флиртовать — ваше обаяние сегодня бьёт без промаха.",
        "lucky": 7
    },
    {
        "love": "В отношениях возможен неожиданный приятный сюрприз или тёплый комплимент.",
        "money": "Звёзды советуют придержать монеты до вечера — возможен выгодный куш!",
        "tip": "Сделайте паузу на чашечку вкусного кофе и никуда не спешите.",
        "lucky": 13
    },
    {
        "love": "Романтическая энергия бьёт ключом. Идеальное время для свиданий и подарков.",
        "money": "Финансовый поток открыт: ваша прибыль будет расти как на дрожжах!",
        "tip": "Если вам предложат авантюру — соглашайтесь, это будет легендарно.",
        "lucky": 21
    },
    {
        "love": "Осторожно с шутками: вторая половинка может принять их слишком близко к сердцу.",
        "money": "Стабильность и уверенный рост. Ваши вложения надежно защищены.",
        "tip": "Окружите себя людьми, которые вас искренне ценят и поддерживают.",
        "lucky": 3
    },
    {
        "love": "Кто-то в этом чате тайно восхищается вами, но пока боится признаться!",
        "money": "Сегодня вам сказочно повезёт: ждите внезапного поступления монет.",
        "tip": "Улыбнитесь новому дню, сегодня вы — главная звезда беседы!",
        "lucky": 77
    },
]

TAROT_DECK = [
    {"name": "0. Шут (Дурак)", "icon": "🃏", "theme": "Новые начинания и спонтанность", "desc": "Время сделать смелый шаг в неизвестность. Не бойтесь рисковать — впереди увлекательное путешествие!"},
    {"name": "I. Маг", "icon": "🪄", "theme": "Сила воли и мастерство", "desc": "У вас в руках есть абсолютно все инструменты для победы. Воплощайте задуманное без колебаний!"},
    {"name": "II. Верховная Жрица", "icon": "🌙", "theme": "Тайны и мощная интуиция", "desc": "Слушайте свой внутренний голос. То, что скрыто от глаз, скоро станет очевидным."},
    {"name": "III. Императрица", "icon": "👑", "theme": "Изобилие, любовь и процветание", "desc": "Вас окружает тёплая энергия плодородия и красоты. Побалуйте себя чем-то особенным!"},
    {"name": "IV. Император", "icon": "🏛", "theme": "Власть, порядок и контроль", "desc": "Время проявить характер лидера. Все процессы под вашим абсолютным контролем."},
    {"name": "VI. Влюблённые", "icon": "💖", "theme": "Сердечный союз и судьбоносный выбор", "desc": "Карта великой любви, страсти и душевной гармонии. Ваше сердце точно знает ответ."},
    {"name": "VII. Колесница", "icon": "🏎", "theme": "Стремительный триумф и прорыв", "desc": "Вы несётесь к цели на полной скорости! Никакие преграды не способны вас остановить."},
    {"name": "VIII. Сила", "icon": "🦁", "theme": "Внутренняя стойкость и уверенность", "desc": "Мягкая сила побеждает любую агрессию. Вы справитесь с любыми вызовами с королевским достоинством."},
    {"name": "X. Колесо Фортуны", "icon": "🎡", "theme": "Поворот судьбы и грандиозная удача", "desc": "Колесо повернулось вашей стороной! Ждите неожиданного подарка судьбы и крупного заноса."},
    {"name": "XI. Справедливость", "icon": "⚖️", "theme": "Честность, баланс и истина", "desc": "Вселенная воздаст вам по заслугам за ваши добрые дела. Баланс будет полностью восстановлен."},
    {"name": "XIV. Умеренность", "icon": "🕊", "theme": "Гармония, спокойствие и исцеление", "desc": "Идеальный душевный штиль. Наслаждайтесь гармонией и приятными беседами."},
    {"name": "XVII. Звезда", "icon": "⭐️", "theme": "Надежда, вдохновение и мечта", "desc": "Ваша заветная мечта ближе, чем кажется. Путеводная звезда освещает ваш путь к успеху."},
    {"name": "XIX. Солнце", "icon": "☀️", "theme": "Абсолютное счастье и триумф", "desc": "Самая светлая карта колоды! Чистая радость, тепло друзей и стопроцентный успех во всём!"},
    {"name": "XXI. Мир", "icon": "🌍", "theme": "Завершение пути и высшая гармония", "desc": "Все пазлы сложились в идеальную картину. Вы на вершине своего величия!"},
]


def _zodiac_kb() -> InlineKeyboardMarkup:
    rows = []
    items = list(ZODIAC_SIGNS.items())
    for i in range(0, len(items), 3):
        row = []
        for k, (e, n) in items[i:i+3]:
            row.append(InlineKeyboardButton(text=f"{e} {n}", callback_data=f"horo:{k}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("гороскоп", "знаки", "зодиак", section=S_SOCIAL,
                    usage="гороскоп [знак]", desc="Ежедневный персональный гороскоп от Мокси"))
async def cmd_horoscope(message: Message, bot: Bot, args: str = "", **kw):
    sign_q = (args or "").strip().lower()
    if not sign_q or sign_q not in ZODIAC_SIGNS:
        # Проверяем, есть ли частичное совпадение
        found_key = None
        for k in ZODIAC_SIGNS:
            if k in sign_q:
                found_key = k
                break
        if not found_key:
            return await message.reply(
                "🔮 ✨ <b>ЕЖЕДНЕВНЫЙ ГОРОСКОП ОТ МОКСИ</b> ✨ 🔮\n\n"
                "Выберите ваш знак зодиака кнопками ниже или напишите: <code>гороскоп лев</code>!",
                reply_markup=_zodiac_kb()
            )
        sign_q = found_key

    e, name = ZODIAC_SIGNS[sign_q]
    # Псевдо-случайный выбор на основе дня и знака, чтобы не менялся каждый клик
    day_hash = int(time.strftime("%Y%m%d")) + sum(ord(c) for c in sign_q)
    h = HORO_TEXTS[day_hash % len(HORO_TEXTS)]

    text = (
        f"🔮 {e} <b>ГОРОСКОП ДЛЯ ЗНАКА: {name.upper()}</b> {e}\n"
        f"✦ ══ • ⊰ ✨ 🪐 💫 ⊱ • ══ ✦\n\n"
        f"❤️ <b>Любовь и чувства:</b>\n{h['love']}\n\n"
        f"🪙 <b>Финансы и бизнес:</b>\n{h['money']}\n\n"
        f"💋 <b>Совет от Мокси:</b>\n<i>«{h['tip']}»</i>\n\n"
        f"🍀 Счастливое число дня: <b>{h['lucky']}</b>"
    )
    await message.reply(text)


@router.callback_query(F.data.startswith("horo:"))
async def cb_horoscope(call: CallbackQuery):
    sign_key = call.data.split(":")[1]
    if sign_key not in ZODIAC_SIGNS:
        return await call.answer()

    e, name = ZODIAC_SIGNS[sign_key]
    day_hash = int(time.strftime("%Y%m%d")) + sum(ord(c) for c in sign_key)
    h = HORO_TEXTS[day_hash % len(HORO_TEXTS)]

    text = (
        f"🔮 {e} <b>ГОРОСКОП ДЛЯ ЗНАКА: {name.upper()}</b> {e}\n"
        f"✦ ══ • ⊰ ✨ 🪐 💫 ⊱ • ══ ✦\n\n"
        f"❤️ <b>Любовь и чувства:</b>\n{h['love']}\n\n"
        f"🪙 <b>Финансы и бизнес:</b>\n{h['money']}\n\n"
        f"💋 <b>Совет от Мокси:</b>\n<i>«{h['tip']}»</i>\n\n"
        f"🍀 Счастливое число дня: <b>{h['lucky']}</b>"
    )
    try:
        await call.message.edit_text(text, reply_markup=_zodiac_kb())
    except Exception:
        pass
    await call.answer(f"Гороскоп для знака {name}")


@router.message(Cmd("таро", "таро дня", "карта таро", "аркан", section=S_SOCIAL,
                    usage="таро дня", desc="Вытянуть персональную Карту Таро дня"))
async def cmd_tarot(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    day_hash = int(time.strftime("%Y%m%d")) + uid * 31
    card = TAROT_DECK[day_hash % len(TAROT_DECK)]

    intro = await message.reply("🃏 <i>Тасуем колоду Старших Арканов... Вытягиваем вашу карту дня...</i>")
    await asyncio.sleep(1.2)

    text = (
        f"🃏 ✨ <b>ВАША КАРТА ТАРО ДНЯ</b> ✨ 🔮\n"
        f"✦ ══ • ⊰ 🌙 🪄 ⭐️ ⊱ • ══ ✦\n\n"
        f"👤 Вопрошающий: {mention(message.from_user)}\n"
        f"🎴 Выпавшая карта: <b>{card['icon']} {card['name']}</b>\n"
        f"🔮 Значение аркана: <b>{card['theme']}</b>\n\n"
        f"📜 <b>Предсказание и наставление:</b>\n"
        f"<i>{card['desc']}</i>\n\n"
        f"💋 <i>Прислушайтесь к мудрости арканов сегодня!</i> ✨"
    )
    try:
        await intro.edit_text(text)
    except Exception:
        await message.reply(text)


# ══════════════════════════════════════════════════════════════
# 3. 📜 ЗОЛОТОЙ ЦИТАТНИК ЧАТА
# ══════════════════════════════════════════════════════════════

@router.message(Cmd("цитата", "в цитатник", "сохранить цитату", section=S_SOCIAL,
                    usage="цитата (ответом на сообщение)", desc="Сохранить фразу участника в цитатник чата"))
async def cmd_add_quote(message: Message, bot: Bot, **kw):
    reply = real_reply(message)
    if not reply or not (reply.text or reply.caption):
        return await message.reply(
            "📜 Чтобы сохранить фразу в Цитатник, ответьте на смешное сообщение участника словом: <code>цитата</code>!"
        )

    q_text = (reply.text or reply.caption or "").strip()
    if len(q_text) < 2:
        return await message.reply("Цитата слишком короткая!")
    if len(q_text) > 800:
        q_text = q_text[:800] + "..."

    author = reply.from_user
    author_name = author.first_name if author else "Аноним"
    adder_name = message.from_user.first_name if message.from_user else "Участник"

    await db.add_chat_quote(message.chat.id, author.id if author else 0, q_text, author_name, adder_name)
    total = await db.get_chat_quotes_count(message.chat.id)

    await message.reply(
        f"📜 ✅ <b>Цитата успешно добавлена в золотой фонд чата!</b>\n\n"
        f"«{html.escape(q_text)}»\n"
        f"<i>— {html.escape(author_name)}</i>\n\n"
        f"📚 Всего цитат в архиве беседы: <b>{total}</b>\n"
        f"💡 Посмотреть случайную: <code>рандом цитата</code>"
    )


@router.message(Cmd("рандом цитата", "случайная цитата", "цитаты", "перл", "перлы", section=S_SOCIAL,
                    usage="рандом цитата", desc="Случайная цитата из архива чата"))
async def cmd_random_quote(message: Message, bot: Bot, **kw):
    q = await db.get_random_chat_quote(message.chat.id)
    if not q:
        return await message.reply(
            "📜 В этом чате пока нет сохраненных цитат!\n\n"
            "Ответьте на любое эпичное сообщение фразой: <code>цитата</code>, чтобы сохранить его в вечность!"
        )

    date_str = time.strftime("%d.%m.%Y", time.localtime(q["created_at"]))
    total = await db.get_chat_quotes_count(message.chat.id)

    res = (
        f"📜 ✨ <b>ЗОЛОТЫЕ ЦИТАТЫ НАШЕГО ЧАТА</b> 💬 ✨\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"«{html.escape(q['quote_text'])}»\n\n"
        f"👤 <b>Автор:</b> {html.escape(q['author_name'])} <i>({date_str})</i>\n"
        f"📌 <b>Сохранил:</b> {html.escape(q['adder_name'])}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📚 <i>Архив беседы: {total} цитат · Ещё: <code>рандом цитата</code></i>"
    )
    await message.reply(res)


# ══════════════════════════════════════════════════════════════
# 4. ☕️ ДРУЖЕСКИЕ УГОЩЕНИЯ И ЗАБОТА
# ══════════════════════════════════════════════════════════════

TREATS = {
    "кофе": ("☕️", "чашечкой ароматного горячего капучино с корицей", "Пусть этот кофе зарядит тебя бодростью и отличным настроением на весь день!"),
    "чай": ("🫖", "кружкой согревающего чая с мятой и лимоном", "Уютного и душевного настроения! Расслабься и почувствуй заботу."),
    "пицца": ("🍕", "большим куском аппетитной сырной пиццы", "Пепперони, тянущийся сыр и море позитива! Приятного аппетита!"),
    "шаурма": ("🌯", "сочнейшей королевской шаурмой с хрустящим лавашом", "Сытно, сочно и от чистого сердца! Теперь сил точно хватит на всё!"),
    "пончик": ("🍩", "сладким пончиком в розовой клубничной глазури", "Сладкой жизни и приятных моментов!"),
    "цветы": ("💐", "роскошным весенним букетом свежих цветов", "Цвети и улыбайся! Твоя улыбка делает этот чат намного светлее!"),
    "шоколад": ("🍫", "плиткой нежнейшего молочного шоколада", "Немного эндорфинов и радости в твой день!"),
    "обнять": ("🤗", "крепкими, тёплыми и искренними объятиями", "Ты замечательный человек! Знай, что здесь тебя всегда поддержат!"),
}


async def _handle_treat(message: Message, bot: Bot, treat_key: str, args: str = ""):
    icon, what, wish = TREATS[treat_key]
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(f"{icon} Укажите, кого вы хотите порадовать (ответом на сообщение или через @ник)!")

    if uid == message.from_user.id:
        return await message.reply(f"{icon} Нельзя угостить самого себя! Порадуйте друга в чате 😊")

    sender = message.from_user
    text = (
        f"{icon} ✨ <b>ТЕПЛО И ЗАБОТА В ЧАТЕ</b> ✨ {icon}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"💖 {mention(sender)} с улыбкой делится {what} с {mention_id(uid, name)}!\n\n"
        f"💌 <b>Пожелание:</b>\n"
        f"<i>«{wish}»</i>\n\n"
        f"💋 <i>Мокси передает лучи добра и уюта!</i> ✨"
    )
    await message.reply(text)


@router.message(Cmd("угостить кофе", "кофе", "чашка кофе", section=S_SOCIAL,
                    usage="угостить кофе @юзер", desc="Угостить друга чашечкой кофе"))
async def cmd_treat_coffee(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "кофе", args)


@router.message(Cmd("угостить чаем", "чай", "чашка чая", section=S_SOCIAL,
                    usage="угостить чаем @юзер", desc="Угостить согревающим чаем"))
async def cmd_treat_tea(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "чай", args)


@router.message(Cmd("подарить пиццу", "пицца", "угостить пиццей", section=S_SOCIAL,
                    usage="пицца @юзер", desc="Угостить вкусной пиццей"))
async def cmd_treat_pizza(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "пицца", args)


@router.message(Cmd("шаурма", "угостить шаурмой", "купить шаурму", section=S_SOCIAL,
                    usage="шаурма @юзер", desc="Угостить сочной шаурмой"))
async def cmd_treat_shawarma(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "шаурма", args)


@router.message(Cmd("пончик", "угостить пончиком", section=S_SOCIAL,
                    usage="пончик @юзер", desc="Подарить сладкий пончик"))
async def cmd_treat_donut(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "пончик", args)


@router.message(Cmd("подарить букет", "букет", "цветы", section=S_SOCIAL,
                    usage="букет @юзер", desc="Подарить красивый букет цветов"))
async def cmd_treat_flowers(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "цветы", args)


@router.message(Cmd("подарить шоколад", "шоколадка", "шоколад", section=S_SOCIAL,
                    usage="шоколад @юзер", desc="Подарить плитку шоколада"))
async def cmd_treat_choco(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "шоколад", args)


@router.message(Cmd("обнять друга", "обнимашки", "обнять по-дружески", section=S_SOCIAL,
                    usage="обнять @юзер", desc="Крепко обнять друга по-дружески"))
async def cmd_treat_hug(message: Message, bot: Bot, args: str = "", **kw):
    await _handle_treat(message, bot, "обнять", args)


# ══════════════════════════════════════════════════════════════
# 5. 🎙 «ВОПРОС ДНЯ ОТ МОКСИ»
# ══════════════════════════════════════════════════════════════

QUESTIONS_BANK = [
    "Если бы вам дали 10 000 000 🪙, но запретили тратить их на себя — кому или куда бы вы их отдали?",
    "Какой самый нелепый или смешной поступок вы совершали из-за лени?",
    "Если бы вы могли стереть память и пересмотреть один фильм или сериал заново, что бы это было?",
    "Какое блюдо вы готовы есть каждый день до конца жизни и оно вам никогда не надоест?",
    "Если бы у вас появилась возможность мгновенно освоить один навык в совершенстве, какой бы выбрали?",
    "О чём вы чаще всего думаете перед тем, как заснуть?",
    "Какой совет вы бы дали самому себе пять лет назад?",
    "Если бы ваша жизнь была фильмом, какой саундтрек играл бы на фоне прямо сейчас?",
    "Что вы выберете: способность читать мысли других людей или способность становиться невидимым?",
    "Какая вещь или привычка моментально поднимает вам настроение даже в самый плохой день?",
    "Если бы вы могли поужинать с любой исторической или знаменитой личностью, кто бы это был?",
    "Какая самая странная фобия или страх у вас есть?",
    "Что для вас важнее: стабильность и покой или риск и яркие приключения?",
    "Какой суперспособностью вы бы наделили своего лучшего друга?",
    "Если бы вам разрешили бесплатно телепортироваться в любую точку планеты на 1 час, куда бы рванули?",
]


@router.message(Cmd("вопрос дня", "тема дня", "тема для общения", "вопрос", section=S_SOCIAL,
                    usage="вопрос дня", desc="Интересный вопрос для обсуждения в чате"))
async def cmd_question_of_day(message: Message, bot: Bot, **kw):
    day_hash = int(time.strftime("%Y%m%d"))
    q = QUESTIONS_BANK[day_hash % len(QUESTIONS_BANK)]

    text = (
        f"🎙 ✨ <b>ВОПРОС ДНЯ ОТ МОКСИ</b> ✨ 💬\n"
        f"✦ ══ • ⊰ 💭 🎙 🗣 ⊱ • ══ ✦\n\n"
        f"🔥 <i>Тема для душевной дискуссии в нашем чате:</i>\n\n"
        f"<b>«{q}»</b>\n\n"
        f"👇 <b>Пишите ваши ответы и мысли прямо в чат! Обсудим вместе!</b> ☕️✨"
    )
    await message.reply(text)


# ══════════════════════════════════════════════════════════════
# 6. ⏰ «УМНАЯ ЧАТ-НАПОМИНАЛКА И ТАЙМЕР МОКСИ»
# ══════════════════════════════════════════════════════════════

async def _remind_job(bot: Bot, chat_id: int, reply_to_id: int, user_id: int, user_name: str, note: str, total_sec: int, dur_str: str):
    await asyncio.sleep(total_sec)
    u_link = mention_id(user_id, user_name)
    text = (
        f"⏰ 🔔 <b>НАПОМИНАНИЕ ОТ МОКСИ!</b> 🔔 ⏰\n"
        f"✦ ══ • ⊰ ⏳ 🛎 📌 ⊱ • ══ ✦\n\n"
        f"👤 {u_link}, вы просили напомнить:\n\n"
        f"📌 <b>«{html.escape(note)}»</b>\n\n"
        f"⏳ <i>Таймер на {dur_str} завершён! Не забудьте!</i> ✨"
    )
    try:
        await bot.send_message(chat_id, text, reply_to_message_id=reply_to_id)
    except Exception:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            pass


@router.message(Cmd("напомни", "напомнить", "таймер", "будильник", section=S_SOCIAL,
                    usage="напомни [время] [текст]", desc="Поставить умный таймер или напоминалку"))
async def cmd_reminder(message: Message, bot: Bot, **kw):
    raw = message.text or ""
    # Ищем шаблон времени: например "через 15 мин сделать чай" или "10м пить воду" или "30 сек"
    m = re.search(r'(?:через\s+)?(\d+)\s*(сек|секунд|секунды|с|мин|минут|минуты|м|ч|час|часа|часов|дн|дней|дня|д)\b\s*(.*)', raw, re.I)
    if not m:
        text = (
            f"⏰ <b>КАК ПОСТАВИТЬ НАПОМИНАЛКУ ИЛИ ТАЙМЕР:</b>\n\n"
            f"• <code>напомни через 15 мин выключить плиту</code>\n"
            f"• <code>таймер 30 сек</code>\n"
            f"• <code>будильник 2 ч пойти спать</code>\n"
            f"• <code>напомни 10 м размять спину</code>\n\n"
            f"🔔 <i>Мокси запомнит заметку и позовёт вас прямо в этот чат!</i>"
        )
        return await message.reply(text)

    num = int(m.group(1))
    unit = m.group(2).lower()
    note = m.group(3).strip() or "Время вышло! Таймер завершён!"

    if unit in ("с", "сек", "секунд", "секунды"):
        total_sec = num
        dur_str = f"{num} сек."
    elif unit in ("м", "мин", "минут", "минуты"):
        total_sec = num * 60
        dur_str = f"{num} мин."
    elif unit in ("ч", "час", "часа", "часов"):
        total_sec = num * 3600
        dur_str = f"{num} ч."
    else:
        total_sec = num * 86400
        dur_str = f"{num} дн."

    if total_sec < 5:
        return await message.reply("⏳ Минимальное время таймера — 5 секунд!")
    if total_sec > 604800:
        return await message.reply("⏳ Максимальное время напоминалки — 7 дней!")

    asyncio.create_task(_remind_job(
        bot=bot,
        chat_id=message.chat.id,
        reply_to_id=message.message_id,
        user_id=message.from_user.id,
        user_name=message.from_user.first_name,
        note=note,
        total_sec=total_sec,
        dur_str=dur_str,
    ))

    text = (
        f"⏰ ✨ <b>ТАЙМЕР УСПЕШНО ЗАПУЩЕН!</b> ✨ ⏰\n"
        f"✦ ══ • ⊰ ⏳ 📝 🔔 ⊱ • ══ ✦\n\n"
        f"⏳ <b>Время ожидания:</b> <b>{dur_str}</b>\n"
        f"📝 <b>Заметка:</b> «<i>{html.escape(note)}</i>»\n\n"
        f"🔔 <i>Мокси обязательно позовёт вас, когда время истечёт!</i>"
    )
    await message.reply(text)


# ══════════════════════════════════════════════════════════════
# 7. 🎵 «МУЗЫКАЛЬНЫЙ ВАЙБ ДНЯ / НАСТРОЕНИЕ ЧАТА»
# ══════════════════════════════════════════════════════════════

VIBES_DATA = {
    "chill": {
        "title": "☕️ Уют & Lo-Fi Чилл",
        "genre": "Lo-Fi Hip Hop / Chillhop",
        "bpm": "74 BPM",
        "track": "Lofi Fruits Music — Sunflower Beats",
        "quote": "Включите спокойный бит, заварите горячий чай и просто наслаждайтесь моментом...",
        "energy": "🟢 25%",
        "vibe": "🟣 96%",
    },
    "drive": {
        "title": "⚡️ Неоновый Драйв & Синтвейв",
        "genre": "Synthwave / Retrowave",
        "bpm": "118 BPM",
        "track": "Kavinsky — Nightcall (Miami Sunset Mix)",
        "quote": "Огни ночного мегаполиса, неоновый свет фар и бесконечная ночная трасса впереди!",
        "energy": "🟡 85%",
        "vibe": "🔵 92%",
    },
    "phonk": {
        "title": "🚀 Ночной Форсаж & Фонк",
        "genre": "Drift Phonk / Hard Bass",
        "bpm": "145 BPM",
        "track": "Kordhell — Murder In My Mind",
        "quote": "Максимальный уровень адреналина, педаль в пол и мощные басы разрывают колонки!",
        "energy": "🔴 99%",
        "vibe": "🔥 98%",
    },
    "cozy": {
        "title": "🍂 Акустический Уют & Инди",
        "genre": "Acoustic Indie Pop",
        "bpm": "82 BPM",
        "track": "Passenger — Let Her Go (Acoustic Sessions)",
        "quote": "Тёплый плед, тихий вечер у окна и мелодии, согревающие самое сердце...",
        "energy": "🟢 35%",
        "vibe": "🧡 94%",
    },
    "melancholy": {
        "title": "💔 Эстетичная Меланхолия",
        "genre": "Dream Pop / Alt Rock",
        "bpm": "85 BPM",
        "track": "The Neighbourhood — Sweater Weather",
        "quote": "Немного приятной светлой грусти, глубоких размышлений и кинематографичной ностальгии...",
        "energy": "🟡 50%",
        "vibe": "🌌 91%",
    },
    "party": {
        "title": "🎉 Праздник & Клубный Хайп",
        "genre": "Dance Pop / Future House",
        "bpm": "126 BPM",
        "track": "Dua Lipa — Levitating (Club Mix)",
        "quote": "Танцуют все! Заряжаем чат космическим позитивом, улыбками и бешеным ритмом!",
        "energy": "🔴 95%",
        "vibe": "⭐️ 97%",
    },
}


def _render_vibe_card(key: str) -> tuple[str, InlineKeyboardMarkup]:
    v = VIBES_DATA.get(key, VIBES_DATA["chill"])
    text = (
        f"🎵 ✨ <b>АТМОСФЕРА И МУЗЫКАЛЬНЫЙ ВАЙБ</b> ✨ 🎧\n"
        f"✦ ══ • ⊰ 🎶 📻 🪐 ⊱ • ══ ✦\n\n"
        f"Текущее настроение чата: <b>{v['title']}</b>\n\n"
        f"📻 <b>Жанр:</b> <code>{v['genre']}</code>\n"
        f"⏱ <b>Темп:</b> <code>{v['bpm']}</code>\n"
        f"🔋 <b>Уровень энергии:</b> {v['energy']}\n"
        f"✨ <b>Индекс вайба:</b> {v['vibe']}\n\n"
        f"🎧 <b>Трек настроения:</b>\n"
        f"🎵 <b>«{v['track']}»</b>\n\n"
        f"💭 <i>«{v['quote']}»</i>\n\n"
        f"👇 <b>Переключите атмосферу чата под ваше настроение:</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☕️ Чилл", callback_data="vibe:chill"),
            InlineKeyboardButton(text="⚡️ Драйв", callback_data="vibe:drive"),
        ],
        [
            InlineKeyboardButton(text="🚀 Фонк", callback_data="vibe:phonk"),
            InlineKeyboardButton(text="🍂 Уют", callback_data="vibe:cozy"),
        ],
        [
            InlineKeyboardButton(text="💔 Меланхолия", callback_data="vibe:melancholy"),
            InlineKeyboardButton(text="🎉 Хайп", callback_data="vibe:party"),
        ],
    ])
    return text, kb


@router.message(Cmd("вайб", "вайб дня", "настроение", "трек дня", "музыка дня", section=S_SOCIAL,
                    usage="вайб", desc="Музыкальный вайб и настроение чата"))
async def cmd_music_vibe(message: Message, bot: Bot, **kw):
    text, kb = _render_vibe_card("chill")
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("vibe:"))
async def cb_vibe(cq: CallbackQuery, bot: Bot):
    key = cq.data.split(":", 1)[1]
    text, kb = _render_vibe_card(key)
    try:
        await cq.message.edit_text(text, reply_markup=kb)
        await cq.answer("🎧 Атмосфера чата переключена!")
    except Exception:
        await cq.answer("🎵 Вайб обновлён!")


# ══════════════════════════════════════════════════════════════
# 8. 💌 «ИСКРЕННИЕ КОМПЛИМЕНТЫ И ТАЙНЫЕ ПОСЛАНИЯ»
# ══════════════════════════════════════════════════════════════

COMPLIMENTS_BANK = [
    "твоя улыбка способна осветить даже самый хмурый понедельник! ✨",
    "рядом с тобой в чате всегда становится теплее и уютнее! ☕️",
    "у тебя потрясающее чувство юмора, твои шутки делают день ярче! 😄",
    "ты один из самых искренних и душевных людей в этом чате! 💎",
    "твоя энергетика заряжает позитивом всех вокруг на 100%! ⚡️",
    "ты невероятно стильно формулируешь мысли — читать твои сообщения одно удовольствие! 📖",
    "мир определённо стал лучше в тот день, когда ты появился в нём! 🌍✨",
    "с тобой безумно приятно общаться на любые темы от космоса до пиццы! 🍕",
    "твоя доброта и отзывчивость вызывают искреннее уважение! 🕊",
    "у тебя прекрасный вкус и удивительная харизма! 🌟",
    "ты сияешь ярче всех созвездий на ночном небе! 🪐💖",
    "любая беседа с твоим участием становится в десять раз интереснее! 🔥",
    "ты вдохновляешь людей вокруг становиться чуточку добрее! 🌸",
    "ты настоящий луч солнца в этом виртуальном пространстве! ☀️",
    "ты потрясающий человек, помни об этом всегда и не сомневайся в себе! 🏆",
]


@router.message(Cmd("комплимент", "похвалить", section=S_SOCIAL,
                    usage="комплимент [@юзер]", desc="Сделать душевный и красивый комплимент"))
async def cmd_compliment(message: Message, bot: Bot, **kw):
    target = await resolve_target(message, bot)
    if not target:
        r = real_reply(message)
        if r and r.from_user:
            target = r.from_user
        else:
            target = message.from_user

    t_link = mention(target)
    comp = random.choice(COMPLIMENTS_BANK)

    text = (
        f"💌 ✨ <b>ДУШЕВНЫЙ КОМПЛИМЕНТ</b> ✨ 💖\n"
        f"✦ ══ • ⊰ 🌸 💌 🕊 ⊱ • ══ ✦\n\n"
        f"Для {t_link}:\n\n"
        f"💖 <b>Знаешь что?</b> <i>{comp}</i>\n\n"
        f"🌟 <i>Пусть твой день будет наполнен радостью и теплом!</i>"
    )
    await message.reply(text)


@router.message(Cmd("признание", "секрет", "тайна", section=S_SOCIAL,
                    usage="признание [@юзер] [текст]", desc="Отправить анонимное послание в чат"))
async def cmd_secret_confession(message: Message, bot: Bot, **kw):
    target = await resolve_target(message, bot)
    if not target:
        r = real_reply(message)
        if r and r.from_user:
            target = r.from_user

    # Извлекаем текст признания
    raw = message.text or ""
    parts = raw.split(maxsplit=2)
    # Если было "признание @юзер привет" -> parts[2]
    # Если реплаем "признание привет как дела" -> parts[1]
    secret_text = ""
    if len(parts) >= 3 and (parts[1].startswith("@") or parts[1].isdigit()):
        secret_text = parts[2]
    elif len(parts) >= 2 and not parts[1].startswith("@"):
        secret_text = raw.split(maxsplit=1)[1]

    if not secret_text or len(secret_text.strip()) < 2:
        return await message.reply(
            "💌 <b>Как отправить тайное послание:</b>\n\n"
            "• <code>признание @юзер Ты мне очень нравишься!</code>\n"
            "• Либо ответом на сообщение: <code>признание Ты лучший друг!</code>\n\n"
            "🤫 <i>Мокси передаст слова, сохранив тайну отправителя!</i>"
        )

    t_name = mention(target) if target else "всему нашему чату"

    # Пытаемся удалить исходное сообщение автора для анонимности
    try:
        await message.delete()
    except Exception:
        pass

    text = (
        f"💌 ✨ <b>ТАЙНОЕ ПОСЛАНИЕ!</b> ✨ 💌\n"
        f"✦ ══ • ⊰ 🤫 💖 🕊 ⊱ • ══ ✦\n\n"
        f"Для: <b>{t_name}</b>\n\n"
        f"💌 <b>Текст послания:</b>\n"
        f"«<i>{html.escape(secret_text.strip())}</i>»\n\n"
        f"🤫 <i>Отправитель пожелал остаться анонимным... Но звёзды знают, что это искренне!</i> ✨"
    )
    await bot.send_message(message.chat.id, text)


# ══════════════════════════════════════════════════════════════
# 9. 💡 «ГЕНЕРАТОР ГЕНИАЛЬНЫХ ОТМАЗОК»
# ══════════════════════════════════════════════════════════════

EXCUSES_BANK = [
    "«Я уже почти вышел, но мой кот лёг мне на колени и уснул. Вы же понимаете, потревожить его — это преступление по законам вселенной!» 🐱💤",
    "«У меня внезапно обновился биоритм до версии 2.0, идёт оптимизация приложений в мозгу, перезагрузка займёт до завтрашнего утра.» 🤖",
    "«Я собирался, но прогноз погоды передал 100% вероятность экзистенциального чилла под пледом с чаем.» ☕️🌧",
    "«Моя внутренняя батарея села на 2%, энергосберегающий режим запрещает покидать горизонтальное положение кровати.» 🛌🔋",
    "«Мне цыганка на вокзале нагадала сегодня не выходить из зоны комфорта во избежание контакта с суетой.» 🔮💅",
    "«Я бы с радостью, но Мокси выдала мне в Таро карту «Отдых и созерцание», а спорить со звёздами себе дороже!» 🃏✨",
    "«Я потерял мотивацию где-то между диваном и кухней. Пока не найду — никуда не сдвинусь!» 🛋🍕",
    "«У меня сегодня плановое совещание с подушкой и одеялом, повестка дня крайне важная, перенести невозможно.» 😴💤",
    "«Космическое излучение сегодня не совпадает с моей чакрой продуктивности. Приходите завтра!» 🪐🛸",
    "«Я не опаздываю и не сливаюсь — я просто создаю интригующее ожидание своего грандиозного появления!» 🕶✨",
]


@router.message(Cmd("отмазка", "отмазаться", "отмазка от работы", "отмазка от встречи", section=S_SOCIAL,
                    usage="отмазка", desc="Гениальная отмазка на любой случай жизни"))
async def cmd_excuse(message: Message, bot: Bot, **kw):
    excuse = random.choice(EXCUSES_BANK)
    text = (
        f"💡 ✨ <b>ГЕНИАЛЬНАЯ ОТМАЗКА ОТ МОКСИ</b> ✨ 🕶\n"
        f"✦ ══ • ⊰ 🧠 🛌 ☕️ ⊱ • ══ ✦\n\n"
        f"{excuse}\n\n"
        f"👌 <i>Пользуйтесь! Работает безотказно в 99.9% случаев!</i>"
    )
    await message.reply(text)

