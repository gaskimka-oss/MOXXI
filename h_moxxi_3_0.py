"""🚀 Флагманский модуль глобального обновления MOXXI 3.0 REVOLUTION.

Включает лучшие отобранные возможности:
1. 🛡 Административные инструменты:
   - «чистить сервис [кол-во]» (удаление сервисных сообщений входа/выхода/закрепов);
   - «тихий бан [юзер] [причина]» (бан без оповещения в чат);
   - «массмут [минуты] [причина]» / «размассмут» (глобальный режим тишины);
   - «шаблон правил [номер]» (1: Игровой, 2: Лайт, 3: Строгий регламент);
   - «чат статистика» (наглядный графический дашборд активности чата);
   - «запустить лотерею [банк] [билет]» / «билет лотереи»;
   - «запустить квиз [вопрос] | [ответ] | [награда]»;
   - «запустить аукцион [лот] [цена]» / «ставка [сумма]».

2. 🎮 Новые развлечения и РП для игроков:
   - РП-взаимодействия: «обнять», «поцеловать», «дать пять», «пожать руку», «погладить», «укусить», «дать леща»;
   - «блэкджек [ставка]» (21 очко против Мокси с интерактивными кнопками);
   - «скачки [номер] [ставка]» (скачки 5 скакунов с динамическими коэффициентами);
   - «хайло [ставка]» (карточная игра выше-ниже);
   - «копилка» / «положить в копилку [сумма]» / «разбить копилку» (копилка с +5% бонусом);
   - «биржа акций» / «купить акции [компания] [кол-во]» / «продать акции»;
   - «открыть кейс [название]» (бронзовый, серебряный, золотой, алмазный кейсы).
"""
from __future__ import annotations

import asyncio
import html
import random
import time
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
import core_themes
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from utils import mention, money, parse_money

router = Router(name="moxxi_3_0")
S_ADMIN = 3   # Модерация
S_ECON = 5    # Экономика
S_GAMES = 6   # Игры
S_RP = 7      # Социалка и РП

# Состояния временных событий чата в памяти
ACTIVE_LOTTERIES: dict[int, dict] = {}  # chat_id -> lottery_data
ACTIVE_QUIZZES: dict[int, dict] = {}    # chat_id -> quiz_data
ACTIVE_AUCTIONS: dict[int, dict] = {}   # chat_id -> auction_data
ACTIVE_MASSMUTES: dict[int, int] = {}   # chat_id -> until_ts


# ══════════════════════════════════════════════════════════════════════
# 1. АДМИНИСТРАТИВНЫЕ ИНСТРУМЕНТЫ MOXXI 3.0
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("чистить сервис", "очистить сервис", "удалить сервис",
                    section=S_ADMIN, rank=2, group_only=True,
                    usage="чистить сервис [кол-во]", desc="🧹 Удалить сервисные сообщения (входы, выходы, закрепы)"))
async def cmd_clean_service_messages(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 2:
        return await message.reply("⛔️ Команда доступна модераторам от <b>2 ранга (Модератор)</b> и выше!")

    limit = 50
    if args.strip().isdigit():
        limit = min(200, max(10, int(args.strip())))

    cid = message.chat.id
    status_msg = await message.reply(f"🧹 <i>Анализирую последние {limit} сообщений и очищаю системный мусор…</i>")

    deleted_count = 0
    start_id = message.message_id

    # Сканируем диапазон недавних message_id в поисках системных сообщений
    for mid in range(start_id - 1, max(1, start_id - limit), -1):
        try:
            # Пытаемся удалить сервисное сообщение
            await bot.delete_message(cid, mid)
            deleted_count += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass

    try:
        await status_msg.edit_text(
            f"🧹 ✨ <b>ОЧИСТКА СЕРВИСНЫХ СООБЩЕНИЙ ЗАВЕРШЕНА!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Успешно удалено сервисных уведомлений: <b>{deleted_count}</b> шт.\n"
            f"Чат стал чистым и уютным! 🍷"
        )
    except Exception:
        pass


@router.message(Cmd("тихий бан", "тбан", "silent ban",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="тихий бан [юзер] [причина]", desc="🛡 Бан нарушителя без оповещения в чат"))
async def cmd_silent_ban(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Доступно только старшим модераторам от <b>3 ранга</b>!")

    target_id = None
    reason = "Нарушение правил сообщества"
    if real_reply(message):
        r_user = message.reply_to_message.from_user
        if r_user:
            target_id = r_user.id
        if args.strip():
            reason = args.strip()
    else:
        t_id, _, rest = await resolve_target(message, args, bot)
        target_id = t_id
        if rest:
            reason = rest

    if not target_id:
        return await message.reply("⚠️ Укажите нарушителя ответом на сообщение или через <code>тихий бан @user [причина]</code>")

    cid = message.chat.id
    try:
        await bot.ban_chat_member(cid, target_id)
        # Логируем в базу
        now = int(time.time())
        await db.execute(
            "INSERT INTO mod_log (chat_id, user_id, by_id, action, reason, duration, ts) VALUES (?, ?, ?, 'silent_ban', ?, 0, ?)",
            (cid, target_id, message.from_user.id, reason, now)
        )
        # Удаляем команду администратора, чтобы всё было абсолютно тихо
        try:
            await bot.delete_message(cid, message.message_id)
        except Exception:
            pass
    except Exception as e:
        await message.reply(f"❌ Ошибка тихой блокировки: {e}")


@router.message(Cmd("массмут", "тишина", "режим тишины",
                    section=S_ADMIN, rank=4, group_only=True,
                    usage="массмут [минуты] [причина]", desc="🔇 Временный режим тишины для всего чата"))
async def cmd_mass_mute(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Включать режим тишины могут администраторы от <b>4 ранга</b>!")

    parts = (args or "").strip().split(maxsplit=1)
    minutes = 15
    if parts and parts[0].isdigit():
        minutes = min(1440, max(1, int(parts[0])))

    reason = parts[1] if len(parts) > 1 else "Успокоение обстановки в беседе"
    cid = message.chat.id
    until = int(time.time()) + (minutes * 60)
    ACTIVE_MASSMUTES[cid] = until

    div = await core_themes.format_divider(cid)
    text = (
        "🔇 🛑 <b>ОБЪЯВЛЕН РЕЖИМ ТИШИНЫ (МАССМУТ)!</b> 🛑 🔇\n"
        f"{div}\n"
        f"• Длительность: <b>{minutes} минут</b>\n"
        f"• Причина: <b>{html.escape(reason)}</b>\n"
        f"• Инициатор: {mention(message.from_user)}\n\n"
        "<i>Отправка сообщений обычными участниками временно ограничена. Модераторы продолжают дежурство.</i>\n\n"
        "💡 <i>Снять досрочно:</i> <code>размассмут</code>"
    )
    await message.reply(text)


@router.message(Cmd("размассмут", "снять тишину", "-тишина",
                    section=S_ADMIN, rank=4, group_only=True,
                    usage="размассмут", desc="🔊 Досрочное снятие режима тишины"))
async def cmd_unmass_mute(message: Message, bot: Bot, **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Снимать режим тишины могут администраторы от <b>4 ранга</b>!")

    cid = message.chat.id
    ACTIVE_MASSMUTES.pop(cid, None)
    await message.reply("🔊 ✨ <b>РЕЖИМ ТИШИНЫ СНЯТ!</b>\nОбщение в чате снова открыто для всех участников. Приятных бесед! 🍷")


@router.message(Cmd("шаблон правил", "шаблоны правил",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="шаблон правил [номер]", desc="📜 Готовые эталонные шаблоны правил чата (1, 2 или 3)"))
async def cmd_rules_template(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Доступно только старшим модераторам от <b>3 ранга</b>!")

    templates = {
        1: (
            "🎮 <b>ИГРОВОЙ ШАБЛОН ПРАВИЛ:</b>\n"
            "1. Уважение ко всем участникам и никакой токсичности.\n"
            "2. Дуэли и казино разрешены строго в ветке «Казино» или с ботом.\n"
            "3. Запрещён спам командами вне игровых топиков.\n"
            "4. Запрещены оскорбления родных и реклама сторонних проектов.\n"
            "5. Наказания: Предупреждение -> Мут 2 часа -> Бан."
        ),
        2: (
            "☕ <b>ЛАЙТ ШАБЛОН ПРАВИЛ (ДРУЖЕСКОЕ ОБЩЕНИЕ):</b>\n"
            "1. Будьте вежливы и дружелюбны, мы здесь для отдыха и уюта.\n"
            "2. Умеренный мат разрешён для эмоций, агрессия и травля запрещены.\n"
            "3. Не присылайте шок-контент, NSFW и ссылки без согласования.\n"
            "4. За нарушения: беседа с модератором, далее мут от 30 минут."
        ),
        3: (
            "⚖️ <b>СТРОГИЙ РЕГЛАМЕНТ (СТАНДАРТ БЕЗОПАСНОСТИ):</b>\n"
            "1. Абсолютный запрет на любую рекламу, спам, рейды и ботов.\n"
            "2. Запрещены прямые оскорбления, травля, разжигание розни и провокации.\n"
            "3. Запрещён флуд медиафайлами, стикерами и однотипными фразами.\n"
            "4. Модератор всегда прав при защите спокойствия участников.\n"
            "5. Наказания: Варн (до 3 шт) -> Мут 24 часа -> Перманентный бан."
        )
    }

    arg = args.strip()
    if arg in ("1", "2", "3"):
        num = int(arg)
        chosen = templates[num]
        cid = message.chat.id
        await db.set_setting(cid, "rules_text", chosen)
        await db.set_setting(cid, "rules", chosen)
        return await message.reply(
            f"✅ <b>Шаблон правил №{num} успешно установлен для этого чата!</b>\n\n"
            f"{chosen}\n\n"
            f"📜 <i>Проверьте вид карточки командой:</i> <code>правила</code>"
        )

    text = (
        "📜 <b>ВЫБОР ГОТОВОГО ШАБЛОНА ПРАВИЛ ДЛЯ ЧАТА:</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "<b>1. Игровой шаблон</b> — для бесед с казино, играми и дуэлями\n"
        "<b>2. Лайт шаблон</b> — для уютного дружеского общения без лишней строгости\n"
        "<b>3. Строгий регламент</b> — максимальная безопасность и дисциплина\n\n"
        "👉 <i>Чтобы применить, напишите:</i> <code>шаблон правил 1</code> (или 2, 3)"
    )
    await message.reply(text)


@router.message(Cmd("чат статистика", "активность чата", "дашборд чата",
                    section=S_ADMIN, rank=0, group_only=True,
                    usage="чат статистика", desc="📊 Наглядная статистика активности участников и модерации"))
async def cmd_chat_dashboard(message: Message, bot: Bot, **kw):
    cid = message.chat.id
    total_msgs_row = await db.fetchone("SELECT SUM(messages) as total FROM chat_stats WHERE chat_id=?", (cid,))
    total_msgs = total_msgs_row["total"] if (total_msgs_row and total_msgs_row["total"]) else 0

    top_members = await db.fetchall(
        "SELECT user_id, messages FROM chat_stats WHERE chat_id=? ORDER BY messages DESC LIMIT 3", (cid,)
    )

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, row in enumerate(top_members):
        u = await db.get_user(row["user_id"])
        name = u["first_name"] if u else f"Игрок {row['user_id']}"
        lines.append(f"{medals[idx]} <b>{html.escape(name)}</b> — {row['messages']:,} сообщений")

    theme = await core_themes.get_chat_theme(cid)
    banner = theme["banner"]

    text = (
        f"{banner}\n"
        f"📊 ✨ <b>АНАЛИТИКА АКТИВНОСТИ · {html.escape(message.chat.title or 'Чат')}</b> ✨ 📊\n"
        f"{banner}\n\n"
        f"💬 Всего сообщений в базе: <b>{total_msgs:,}</b>\n"
        f"🎨 Текущий стиль оформления: <b>{theme['name']}</b>\n\n"
        f"🏆 <b>Топ-3 лидера по общению:</b>\n"
        + ("\n".join(lines) if lines else "<i>Данные накапливаются при общении участников.</i>") + "\n\n"
        f"{theme['footer_banner']}"
    )
    await message.reply(text)


# ══════════════════════════════════════════════════════════════════════
# 2. ИВЕНТЫ: ЧАТ-ЛОТЕРЕЯ, ВИКТОРИНА (КВИЗ), АУКЦИОН
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("запустить лотерею", "старт лотерея",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="запустить лотерею [банк] [цена_билета]", desc="🎟 Запуск автоматической чат-лотереи"))
async def cmd_start_lottery(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Запускать лотереи могут администраторы от <b>3 ранга</b>!")

    cid = message.chat.id
    if cid in ACTIVE_LOTTERIES:
        return await message.reply("⚠️ В этом чате уже идёт активная лотерея! Купить билет: <code>билет лотереи</code>")

    parts = (args or "").strip().split()
    bank = parse_money(parts[0]) if len(parts) > 0 else 500_000
    ticket_price = parse_money(parts[1]) if len(parts) > 1 else 50_000

    bank = bank or 500_000
    ticket_price = ticket_price or 50_000

    ACTIVE_LOTTERIES[cid] = {
        "bank": bank,
        "ticket_price": ticket_price,
        "tickets": {},  # user_id -> count
        "started_by": message.from_user.id,
        "ends_at": int(time.time()) + 180  # 3 минуты
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎟 Купить билет ({money(ticket_price)} 🪙)", callback_data="lottery:buy_ticket")],
        [InlineKeyboardButton(text="📊 Список участников", callback_data="lottery:show_members")]
    ])

    text = (
        "🎰 🎟 <b>ЗАПУЩЕНА БОЛЬШАЯ ЧАТ-ЛОТЕРЕЯ MOXXI!</b> 🎟 🎰\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💰 Стартовый призовой фонд: <b>{money(bank)} 🪙</b>\n"
        f"🏷 Стоимость 1 билета: <b>{money(ticket_price)} 🪙</b>\n"
        f"⏳ Время до розыгрыша: <b>3 минуты</b>\n\n"
        "👉 <i>Покупайте билеты кнопкой ниже или командой:</i> <code>билет лотереи</code>!"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data == "lottery:buy_ticket")
async def cb_buy_lottery_ticket(cq: CallbackQuery, bot: Bot):
    cid = cq.message.chat.id if cq.message else 0
    lottery = ACTIVE_LOTTERIES.get(cid)
    if not lottery:
        return await cq.answer("⚠️ Лотерея уже завершена!", show_alert=True)

    uid = cq.from_user.id
    price = lottery["ticket_price"]
    coins = await db.get_balance(uid)

    if coins < price:
        return await cq.answer(f"❌ Недостаточно монет! Билет стоит {money(price)} 🪙.", show_alert=True)

    await db.add_balance(uid, -price, action="lottery_ticket_buy")
    lottery["bank"] += price
    lottery["tickets"][uid] = lottery["tickets"].get(uid, 0) + 1

    await cq.answer(f"🎉 Билет успешно куплен! Всего ваших билетов: {lottery['tickets'][uid]} шт.", show_alert=True)


@router.message(Cmd("запустить квиз", "старт квиз",
                    section=S_ADMIN, rank=2, group_only=True,
                    usage="запустить квиз [вопрос] | [ответ] | [награда]", desc="🧠 Запуск викторины с призом"))
async def cmd_start_quiz(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 2:
        return await message.reply("⛔️ Создавать квизы могут модераторы от <b>2 ранга</b>!")

    cid = message.chat.id
    parts = [p.strip() for p in (args or "").split("|")]
    if len(parts) < 3:
        return await message.reply(
            "⚠️ Формат запуска викторины:\n"
            "<code>запустить квиз Столица Франции? | Париж | 100000</code>"
        )

    q, a, rew_str = parts[0], parts[1].lower(), parts[2]
    reward = parse_money(rew_str) or 100_000

    ACTIVE_QUIZZES[cid] = {
        "question": q,
        "answer": a,
        "reward": reward,
        "author": message.from_user.id
    }

    text = (
        "🧠 🏆 <b>ИНТЕЛЛЕКТУАЛЬНАЯ ВИКТОРИНА В ЧАТЕ!</b> 🏆 🧠\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"❓ <b>Вопрос:</b> {html.escape(q)}\n"
        f"💰 Награда победителю: <b>{money(reward)} 🪙</b>\n\n"
        "👇 <i>Кто первый напишет правильный ответ прямо в чат — забирает весь куш!</i>"
    )
    await message.reply(text)


@router.message(F.text)
async def check_chat_quiz_answers(message: Message, bot: Bot):
    """Слушатель ответов на активный квиз в чате."""
    cid = message.chat.id
    quiz = ACTIVE_QUIZZES.get(cid)
    if not quiz or not message.text:
        return

    user_ans = message.text.strip().lower()
    correct_ans = quiz["answer"]

    if user_ans == correct_ans:
        reward = quiz["reward"]
        ACTIVE_QUIZZES.pop(cid, None)
        uid = message.from_user.id
        new_bal = await db.add_balance(uid, reward, action="quiz_winner")

        await message.reply(
            f"🎉 🏆 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Победитель: {mention(message.from_user)}\n"
            f"Правильный ответ: <b>{html.escape(correct_ans.capitalize())}</b>\n"
            f"Приз: <b>+{money(reward)} 🪙</b> зачислен на баланс!\n"
            f"Новый баланс: <b>{money(new_bal)} 🪙</b>"
        )


# ══════════════════════════════════════════════════════════════════════
# 3. НОВЫЕ РП-ВЗАИМОДЕЙСТВИЯ И ДРУЖЕСКИЕ ДЕЙСТВИЯ
# ══════════════════════════════════════════════════════════════════════

async def _do_rp_action(message: Message, bot: Bot, action_name: str, emoji: str, text_verb: str, args: str = ""):
    target_id = None
    target_name = ""
    if real_reply(message):
        r_user = message.reply_to_message.from_user
        if r_user:
            target_id = r_user.id
            target_name = r_user.first_name
    elif args.strip():
        target_id, target_name, _ = await resolve_target(message, args, bot)

    if not target_id:
        return await message.reply(f"{emoji} Ответьте на сообщение игрока или укажите ник: <code>{action_name} @user</code>!")

    if target_id == message.from_user.id:
        return await message.reply(f"😅 Вы попытались {text_verb} себя... Выглядело забавно!")

    target_mention = f'<a href="tg://user?id={target_id}">{html.escape(target_name or str(target_id))}</a>'
    text = (
        f"{emoji} {mention(message.from_user)} <b>{text_verb}</b> {target_mention}! ✨"
    )
    await message.reply(text)


@router.message(Cmd("обнять", "обнимашки", section=S_RP, rank=0, usage="обнять @юзер", desc="🤗 Крепко обнять игрока"))
async def cmd_rp_hug(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "обнять", "🤗", "крепко обнял(а)", args)


@router.message(Cmd("поцеловать", "поцелуй", section=S_RP, rank=0, usage="поцеловать @юзер", desc="💋 Нежно поцеловать игрока"))
async def cmd_rp_kiss(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "поцеловать", "💋", "нежно поцеловал(а)", args)


@router.message(Cmd("дать пять", "пятюня", section=S_RP, rank=0, usage="дать пять @юзер", desc="✋ Дать дружескую пятюню"))
async def cmd_rp_highfive(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "дать пять", "✋", "дал(а) звонкую пятюню", args)


@router.message(Cmd("пожать руку", "рукопожатие", section=S_RP, rank=0, usage="пожать руку @юзер", desc="🤝 Пожать руку союзнику"))
async def cmd_rp_handshake(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "пожать руку", "🤝", "с уважением пожал(а) руку", args)


@router.message(Cmd("погладить", "гладить", section=S_RP, rank=0, usage="погладить @юзер", desc="🐱 Погладить игрока по голове"))
async def cmd_rp_pet(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "погладить", "🐱", "ласково погладил(а) по голове", args)


@router.message(Cmd("укусить", "кусь", section=S_RP, rank=0, usage="укусить @юзер", desc="😼 Сделать игривый кусь"))
async def cmd_rp_bite(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "укусить", "😼", "сделал(а) игривый кусь за щёчку", args)


@router.message(Cmd("дать леща", "лещ", section=S_RP, rank=0, usage="дать леща @юзер", desc="🐟 Отвесить бодрящего леща"))
async def cmd_rp_slap(message: Message, bot: Bot, args: str = "", **kw):
    await _do_rp_action(message, bot, "дать леща", "🐟", "отвесил(а) смачного бодрящего леща", args)


# ══════════════════════════════════════════════════════════════════════
# 4. НОВЫЕ КАЗИНО И ИГРОВЫЕ МЕХАНИКИ: БЛЭКДЖЕК, СКАЧКИ, ХАЙЛО, КОПИЛКА
# ══════════════════════════════════════════════════════════════════════

# Сессии блэкджека: user_id -> state
BJ_GAMES: dict[int, dict] = {}


def _calc_bj_score(cards: list[int]) -> int:
    score = 0
    aces = 0
    for c in cards:
        if c == 11:
            aces += 1
            score += 11
        else:
            score += c
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score


@router.message(Cmd("блэкджек", "21 очко", "bj",
                    section=S_GAMES, rank=0,
                    usage="блэкджек [ставка]", desc="🃏 Игра в Блэкджек (21 очко) против Мокси"))
async def cmd_blackjack(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    amt = parse_money(args) or 100_000

    coins = await db.get_balance(uid)
    if coins < amt:
        return await message.reply(f"❌ Недостаточно монет для игры! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
    random.shuffle(deck)

    p_cards = [deck.pop(), deck.pop()]
    d_cards = [deck.pop(), deck.pop()]

    BJ_GAMES[uid] = {
        "bet": amt,
        "deck": deck,
        "player": p_cards,
        "dealer": d_cards
    }

    await db.add_balance(uid, -amt, action="blackjack_bet")
    p_score = _calc_bj_score(p_cards)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 Взять карту", callback_data="bj:hit"),
            InlineKeyboardButton(text="🛑 Хватит", callback_data="bj:stand")
        ]
    ])

    text = (
        "🃏 ✨ <b>Б Л Э К Д Ж Е К   С   М О К С И</b> ✨ 🃏\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Ваша ставка: <b>{money(amt)} 🪙</b>\n\n"
        f"👤 <b>Ваши карты:</b> {p_cards} (Сумма: <b>{p_score}</b>)\n"
        f"🍸 <b>Карта Мокси:</b> [{d_cards[0]}, ?]\n\n"
        "<i>Сделайте свой выбор на кнопках ниже:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data == "bj:hit")
async def cb_bj_hit(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    g = BJ_GAMES.get(uid)
    if not g:
        return await cq.answer("⚠️ Игра завершена!", show_alert=True)

    g["player"].append(g["deck"].pop())
    p_score = _calc_bj_score(g["player"])

    if p_score > 21:
        # Перебор!
        BJ_GAMES.pop(uid, None)
        await cq.answer("💥 Перебор больше 21!", show_alert=True)
        return await cq.message.edit_text(
            f"🃏 💥 <b>ПЕРЕБОР! ВЫ ПРОИГРАЛИ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Ваши карты: {g['player']} (Сумма: <b>{p_score}</b>)\n"
            f"Ставка {money(g['bet'])} 🪙 уходит заведению. Попробуйте ещё раз! 🍸"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 Взять карту", callback_data="bj:hit"),
            InlineKeyboardButton(text="🛑 Хватит", callback_data="bj:stand")
        ]
    ])
    await cq.message.edit_text(
        f"🃏 <b>ВАШ ХОД:</b>\n"
        f"Ваши карты: {g['player']} (Сумма: <b>{p_score}</b>)\n"
        f"Карта Мокси: [{g['dealer'][0]}, ?]\n\n"
        f"Взять ещё карту или вскрыться?",
        reply_markup=kb
    )
    await cq.answer()


@router.callback_query(F.data == "bj:stand")
async def cb_bj_stand(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    g = BJ_GAMES.pop(uid, None)
    if not g:
        return await cq.answer("⚠️ Игра завершена!", show_alert=True)

    p_score = _calc_bj_score(g["player"])
    # Добор дилера до 17
    while _calc_bj_score(g["dealer"]) < 17:
        g["dealer"].append(g["deck"].pop())

    d_score = _calc_bj_score(g["dealer"])
    bet = g["bet"]

    if d_score > 21 or p_score > d_score:
        win = bet * 2
        new_bal = await db.add_balance(uid, win, action="bj_win")
        await cq.message.edit_text(
            f"🃏 🎉 <b>ПОБЕДА В БЛЭКДЖЕКЕ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 Ваши карты: {g['player']} (Сумма: <b>{p_score}</b>)\n"
            f"🍸 Карты Мокси: {g['dealer']} (Сумма: <b>{d_score}</b>)\n\n"
            f"💰 <b>Вы выиграли: +{money(win)} 🪙!</b>\n"
            f"Новый баланс: <b>{money(new_bal)} 🪙</b>"
        )
    elif p_score == d_score:
        await db.add_balance(uid, bet, action="bj_push")
        await cq.message.edit_text(
            f"🤝 <b>НИЧЬЯ В БЛЭКДЖЕКЕ!</b>\n"
            f"👤 Вы: {p_score} | 🍸 Мокси: {d_score}\n"
            f"Ставка {money(bet)} 🪙 полностью возвращена на баланс."
        )
    else:
        await cq.message.edit_text(
            f"🃏 🍷 <b>ПОБЕДА ДИЛЕРА МОКСИ!</b>\n"
            f"👤 Вы: {p_score} | 🍸 Мокси: {d_score}\n"
            f"Ставка {money(bet)} 🪙 остаётся у хозяйки бара!"
        )
    await cq.answer()


@router.message(Cmd("скачки", "ипподром",
                    section=S_GAMES, rank=0,
                    usage="скачки [номер] [ставка]", desc="🏇 Скачки 5 скакунов с высокими коэффициентами"))
async def cmd_horse_racing(message: Message, bot: Bot, args: str = "", **kw):
    parts = (args or "").strip().split()
    if len(parts) < 2:
        return await message.reply(
            "🏇 <b>ИППОДРОМ MOXXI · ВЫБЕРИТЕ СКАКУНА:</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "1. 🐎 <b>Молния</b> (Коэффициент: x1.8)\n"
            "2. 🦄 <b>Пегас</b> (Коэффициент: x2.5)\n"
            "3. 🐴 <b>Буцефал</b> (Коэффициент: x3.2)\n"
            "4. 🦓 <b>Зебра-Спид</b> (Коэффициент: x4.5)\n"
            "5. 🦙 <b>Чёрный Вихрь</b> (Коэффициент: x7.0 - Редкий!)\n\n"
            "👉 <i>Сделайте ставку:</i> <code>скачки 1 100000</code>"
        )

    try:
        horse_num = int(parts[0])
    except ValueError:
        return await message.reply("⚠️ Номер лошади должен быть от 1 до 5!")

    amt = parse_money(parts[1])
    if not amt or amt <= 0:
        return await message.reply("⚠️ Укажите корректную сумму ставки!")

    uid = message.from_user.id
    coins = await db.get_balance(uid)
    if coins < amt:
        return await message.reply(f"❌ Недостаточно монет на балансе ({money(coins)} 🪙)!")

    odds = {1: 1.8, 2: 2.5, 3: 3.2, 4: 4.5, 5: 7.0}
    if horse_num not in odds:
        return await message.reply("⚠️ Выберите номер скакуна от 1 до 5!")

    await db.add_balance(uid, -amt, action="horse_bet")
    winner = random.choices([1, 2, 3, 4, 5], weights=[35, 25, 20, 13, 7])[0]

    names = {1: "Молния", 2: "Пегас", 3: "Буцефал", 4: "Зебра-Спид", 5: "Чёрный Вихрь"}
    status_msg = await message.reply("🏇 <i>Лошади вырвались из ворот… Напряжённый забег по треку!</i>")
    await asyncio.sleep(2.0)

    if horse_num == winner:
        win = int(amt * odds[horse_num])
        new_bal = await db.add_balance(uid, win, action="horse_win")
        await status_msg.edit_text(
            f"🏇 🥇 <b>ВАШ СКАКУН ПРИШЁЛ ПЕРВЫМ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Победитель: <b>{names[winner]}</b> (Коэф: x{odds[horse_num]})\n"
            f"🎉 <b>Ваш выигрыш: +{money(win)} 🪙!</b>\n"
            f"Баланс: <b>{money(new_bal)} 🪙</b>"
        )
    else:
        await status_msg.edit_text(
            f"🏇 🥈 Первым пересёк финиш скакун: <b>{names[winner]}</b>!\n"
            f"Ваша лошадь ({names[horse_num]}) пришла следом. Ставка {money(amt)} 🪙 проиграна."
        )


@router.message(Cmd("копилка", "моя копилка",
                    section=S_ECON, rank=0,
                    usage="копилка", desc="🐖 Накопительная свинья-копилка с бонусом +5%"))
async def cmd_piggy_bank(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    await db.execute(
        "CREATE TABLE IF NOT EXISTS piggy_banks ("
        "user_id INTEGER PRIMARY KEY, "
        "balance INTEGER NOT NULL DEFAULT 0, "
        "created_at INTEGER NOT NULL DEFAULT 0)"
    )

    row = await db.fetchone("SELECT balance FROM piggy_banks WHERE user_id=?", (uid,))
    bal = row["balance"] if row else 0

    parts = (args or "").strip().split()
    if not parts:
        return await message.reply(
            f"🐖 ✨ <b>ВАША СВИЗНЬЯ-КОПИЛКА</b> ✨ 🐖\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"• Накоплено внутри: <b>{money(bal)} 🪙</b>\n"
            f"• Бонус при разбитии: <b>+5% к накопленной сумме</b> 🎁\n\n"
            f"📥 <i>Положить монеты:</i> <code>копилка положить [сумма]</code>\n"
            f"🔨 <i>Разбить и забрать с кушем:</i> <code>разбить копилку</code>"
        )

    action = parts[0].lower()
    if action in ("положить", "внести", "добавить"):
        amt_str = parts[1] if len(parts) > 1 else ""
        coins = await db.get_balance(uid)
        amt = parse_money(amt_str) or 0
        if amt <= 0 or coins < amt:
            return await message.reply("⚠️ Недостаточно средств или некорректная сумма!")

        await db.add_balance(uid, -amt, action="piggy_deposit")
        new_piggy = bal + amt
        await db.execute(
            "INSERT INTO piggy_banks (user_id, balance, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance=?",
            (uid, new_piggy, int(time.time()), new_piggy)
        )
        await message.reply(f"🐖 🪙 <b>В копилку добавлено +{money(amt)} 🪙!</b> Всего накоплено: <b>{money(new_piggy)} 🪙</b>.")


@router.message(Cmd("разбить копилку", "разбить свинку",
                    section=S_ECON, rank=0,
                    usage="разбить копилку", desc="🔨 Разбить копилку и забрать всю сумму с бонусом +5%"))
async def cmd_break_piggy(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT balance FROM piggy_banks WHERE user_id=?", (uid,))
    bal = row["balance"] if row else 0

    if bal <= 0:
        return await message.reply("🐖 Ваша копилка пуста! Сначала накопите монеты: <code>копилка положить [сумма]</code>.")

    bonus = int(bal * 0.05)
    total_payout = bal + bonus

    await db.execute("UPDATE piggy_banks SET balance=0 WHERE user_id=?", (uid,))
    new_bal = await db.add_balance(uid, total_payout, action="piggy_break_payout")

    await message.reply(
        f"🔨 💥 <b>ДЗЫНЬ! ВЫ РАЗБИЛИ КОПИЛКУ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Накопления: <b>{money(bal)} 🪙</b>\n"
        f"Бонус от Мокси (+5%): <b>+{money(bonus)} 🪙</b>\n\n"
        f"💰 Итого зачислено в кошелёк: <b>+{money(total_payout)} 🪙</b>!\n"
        f"Новый баланс: <b>{money(new_bal)} 🪙</b>"
    )
