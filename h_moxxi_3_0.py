"""🚀 Флагманский модуль глобального обновления MOXXI 3.0 REVOLUTION.

Уникальные новые системы 3.0:
1. 🛡 Административные инструменты:
   - «чистить сервис [кол-во]» (удаление системных смс входов/выходов/закрепов);
   - «тихий бан [юзер] [причина]» (бан без оповещения в чат);
   - «массмут [минуты] [причина]» / «размассмут» (глобальный режим тишины);
   - «шаблон правил [номер]» (1: Игровой, 2: Лайт, 3: Строгий регламент);
   - «чат статистика» (наглядный графический дашборд активности чата);
   - «аудит безопасности» (полная проверка защищенности беседы);
   - «запустить лотерею [банк] [билет]» / «билет лотереи»;
   - «запустить квиз [вопрос] | [ответ] | [награда]»;
   - «запустить аукцион [лот] [цена]» / «ставка [сумма]».

2. 📈 Фондовая Биржа Акций Moxxi (Stock Market):
   - «биржа» / «рынок акций» — котировки 5 компаний;
   - «купить акции [тикер] [кол-во]»;
   - «продать акции [тикер] [кол-во]»;
   - «портфель» / «мои акции» — активы и дивиденды;
   - «дивиденды» — сбор прибыли по акциям.

3. 📦 Секретные Кейсы 3.0 (Лутбоксы):
   - «кейсы 3.0» — просмотр сундуков;
   - «открыть кейс [номер]» — выбивание миллионов монет, кристаллов и VIP-дней.
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

# Состояния временных событий чата в памяти
ACTIVE_LOTTERIES: dict[int, dict] = {}   # chat_id -> lottery_data
ACTIVE_QUIZZES: dict[int, dict] = {}     # chat_id -> quiz_data
ACTIVE_AUCTIONS: dict[int, dict] = {}    # chat_id -> auction_data
ACTIVE_MASSMUTES: dict[int, int] = {}    # chat_id -> until_ts


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

    for mid in range(start_id - 1, max(1, start_id - limit), -1):
        try:
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
        now = int(time.time())
        await db.execute(
            "INSERT INTO mod_log (chat_id, user_id, by_id, action, reason, duration, ts) VALUES (?, ?, ?, 'silent_ban', ?, 0, ?)",
            (cid, target_id, message.from_user.id, reason, now)
        )
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


@router.message(Cmd("аудит безопасности", "безопасность чата",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="аудит безопасности", desc="🛡 Комплексный аудит защиты и модерации беседы"))
async def cmd_security_audit(message: Message, bot: Bot, **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Доступно только старшим модераторам от <b>3 ранга</b>!")

    cid = message.chat.id
    antibot_on = (await db.get_setting(cid, "antibot", "0") == "1")
    nightmode_on = (await db.get_setting(cid, "night_mode", "0") == "1")
    rules_text = await db.get_setting(cid, "rules_text")

    staff_count_row = await db.fetchone("SELECT COUNT(*) as c FROM staff WHERE chat_id=? AND left_chat=0", (cid,))
    staff_count = staff_count_row["c"] if staff_count_row else 0

    text = (
        "🛡️ ✨ <b>АУДИТ БЕЗОПАСНОСТИ БЕСЕДЫ MOXXI 3.0</b> ✨ 🛡️\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Администрация на дежурстве: <b>{staff_count} чел.</b> 👮\n"
        f"• Защита от спам-ботов (Антибот): <b>{'🟢 ВКЛЮЧЕНА' if antibot_on else '🔴 ВЫКЛЮЧЕНА (+антибот)'}</b>\n"
        f"• Ночной режим чата: <b>{'🟢 АКТИВЕН' if nightmode_on else '⚪️ ВЫКЛЮЧЕН (ночной режим)'}</b>\n"
        f"• Правила беседы: <b>{'🟢 НАСТРОЕНЫ' if rules_text else '🟡 СТАНДАРТНЫЕ (шаблон правил 1)'}</b>\n\n"
        "💡 <i>Беседа находится под защитой интеллектуального ядра Moxxi 3.0.</i>"
    )
    await message.reply(text)


# ══════════════════════════════════════════════════════════════════════
# 2. ИВЕНТЫ: ЧАТ-ЛОТЕРЕЯ, ВИКТОРИНА (КВИЗ), ЖИВОЙ АУКЦИОН
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
        "tickets": {},
        "started_by": message.from_user.id,
        "ends_at": int(time.time()) + 180
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


@router.message(Cmd("запустить аукцион", "старт аукцион",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="запустить аукцион [лот] [старт_цена]", desc="🏛 Запуск живого чат-аукциона"))
async def cmd_start_auction(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Запускать аукцион могут администраторы от <b>3 ранга</b>!")

    cid = message.chat.id
    parts = (args or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("⚠️ Пример запуска: <code>запустить аукцион 1000000 Редкий Алмазный Меч</code>")

    start_price = parse_money(parts[0]) or 500_000
    lot_name = parts[1]

    ACTIVE_AUCTIONS[cid] = {
        "lot": lot_name,
        "current_bid": start_price,
        "leader_id": message.from_user.id,
        "leader_name": message.from_user.first_name,
        "ends_at": int(time.time()) + 120
    }

    text = (
        "🏛 🔨 <b>ОТКРЫТЫ ЖИВЫЕ ТОРГИ НА АУКЦИОНЕ MOXXI!</b> 🔨 🏛\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📦 <b>Лот:</b> {html.escape(lot_name)}\n"
        f"💰 Стартовая ставка: <b>{money(start_price)} 🪙</b>\n\n"
        "👇 <i>Чтобы перебить ставку, напишите:</i> <code>ставка [сумма]</code>\n"
        "Торги завершатся через 2 минуты после последней ставки!"
    )
    await message.reply(text)


@router.message(Cmd("ставка", "бид", "перебить",
                    section=S_ECON, rank=0, group_only=True,
                    usage="ставка [сумма]", desc="🔨 Сделать ставку на активном аукционе"))
async def cmd_make_bid(message: Message, bot: Bot, args: str = "", **kw):
    cid = message.chat.id
    auc = ACTIVE_AUCTIONS.get(cid)
    if not auc:
        return await message.reply("🏛 Сейчас в этом чате нет активных торгов.")

    amt = parse_money(args)
    if not amt:
        return await message.reply("⚠️ Укажите сумму ставки: <code>ставка 1500000</code>")

    if amt <= auc["current_bid"]:
        return await message.reply(f"❌ Ставка должна быть выше текущей (минимум: <b>{money(auc['current_bid'] + 50000)} 🪙</b>)!")

    uid = message.from_user.id
    coins = await db.get_balance(uid)
    if coins < amt:
        return await message.reply(f"❌ У вас недостаточно монет на балансе ({money(coins)} 🪙)!")

    auc["current_bid"] = amt
    auc["leader_id"] = uid
    auc["leader_name"] = message.from_user.first_name
    auc["ends_at"] = int(time.time()) + 90

    await message.reply(
        f"🔨 📈 <b>НОВАЯ ЛИДИРУЮЩАЯ СТАВКА!</b>\n"
        f"• Игрок: {mention(message.from_user)}\n"
        f"• Сумма: <b>{money(amt)} 🪙</b>\n"
        f"• Лот: <b>{html.escape(auc['lot'])}</b>\n\n"
        f"⏳ <i>До удара молотка осталось: 90 секунд! Кто больше?</i>"
    )


# ══════════════════════════════════════════════════════════════════════
# 3. ФОНДОВАЯ БИРЖА АКЦИЙ MOXXI 3.0 (STOCK MARKET)
# ══════════════════════════════════════════════════════════════════════

STOCKS = {
    "MOX": {"name": "Moxxi Global Corp", "base": 50_000, "volatility": 0.12},
    "TON": {"name": "The Open Network Coin", "base": 120_000, "volatility": 0.15},
    "CRY": {"name": "Crystal Technologies", "base": 85_000, "volatility": 0.10},
    "NBK": {"name": "Neon Central Bank", "base": 30_000, "volatility": 0.08},
    "ENG": {"name": "Energy Core Systems", "base": 15_000, "volatility": 0.18},
}


def _get_current_stock_price(ticker: str) -> int:
    s = STOCKS.get(ticker.upper())
    if not s:
        return 0
    seed = int(time.time()) // 300
    random.seed(seed + hash(ticker))
    delta = random.uniform(-s["volatility"], s["volatility"])
    price = int(s["base"] * (1.0 + delta))
    return max(1000, price)


async def _ensure_stock_tables():
    await db.execute(
        "CREATE TABLE IF NOT EXISTS user_stocks ("
        "user_id INTEGER NOT NULL, "
        "ticker TEXT NOT NULL, "
        "count INTEGER NOT NULL DEFAULT 0, "
        "buy_price INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (user_id, ticker))"
    )


@router.message(Cmd("биржа", "рынок акций", "акции", "котировки",
                    section=S_ECON, rank=0,
                    usage="биржа", desc="📈 Фондовая биржа акций Moxxi с живыми котировками"))
async def cmd_stock_market(message: Message, bot: Bot, **kw):
    lines = []
    for ticker, data in STOCKS.items():
        price = _get_current_stock_price(ticker)
        diff = price - data["base"]
        sign = "+" if diff >= 0 else ""
        icon = "🟢" if diff >= 0 else "🔴"
        lines.append(f"• <b>{ticker}</b> ({data['name']}): <b>{money(price)} 🪙</b> {icon} <i>({sign}{diff:,} 🪙)</i>")

    text = (
        "📈 ✨ <b>Ф О Н Д О В А Я   Б И Р Ж А   M O X X I</b> ✨ 📈\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Текущие котировки акций компаний (обновление каждые 5 мин):\n\n"
        + "\n".join(lines) + "\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💼 <b>Торговые команды:</b>\n"
        "• <code>купить акции [тикер] [кол-во]</code> (например: <code>купить акции MOX 5</code>)\n"
        "• <code>продать акции [тикер] [кол-во]</code>\n"
        "• <code>портфель</code> — ваш инвестиционный баланс и активы\n"
        "• <code>дивиденды</code> — забрать ежедневные выплаты"
    )
    await message.reply(text)


@router.message(Cmd("купить акции", "купить акцию",
                    section=S_ECON, rank=0,
                    usage="купить акции [тикер] [кол-во]", desc="📈 Покупка акций на фондовой бирже"))
async def cmd_buy_stocks(message: Message, bot: Bot, args: str = "", **kw):
    parts = (args or "").strip().split()
    if len(parts) < 2:
        return await message.reply("⚠️ Пример покупки: <code>купить акции MOX 10</code> (список тикеров: <code>биржа</code>)")

    ticker = parts[0].upper()
    if ticker not in STOCKS:
        return await message.reply("❌ Неизвестный тикер компании! Доступные: MOX, TON, CRY, NBK, ENG.")

    try:
        count = int(parts[1])
    except ValueError:
        return await message.reply("⚠️ Укажите целое количество акций!")

    if count <= 0:
        return await message.reply("⚠️ Минимальное количество для покупки: 1 акция.")

    price = _get_current_stock_price(ticker)
    total_cost = price * count
    uid = message.from_user.id
    coins = await db.get_balance(uid)

    if coins < total_cost:
        return await message.reply(
            f"❌ <b>Недостаточно монет!</b>\n"
            f"Для покупки {count} акций {ticker} требуется <b>{money(total_cost)} 🪙</b>.\n"
            f"Ваш баланс: <b>{money(coins)} 🪙</b>."
        )

    await _ensure_stock_tables()
    await db.add_balance(uid, -total_cost, action="stock_buy", meta=f"{ticker}:{count}")
    await db.execute(
        "INSERT INTO user_stocks (user_id, ticker, count, buy_price) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, ticker) DO UPDATE SET count=count+excluded.count, buy_price=excluded.buy_price",
        (uid, ticker, count, price)
    )

    await message.reply(
        f"📈 🎉 <b>АКЦИИ УСПЕШНО КУПЛЕНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Компания: <b>{STOCKS[ticker]['name']} ({ticker})</b>\n"
        f"Количество: <b>{count} шт.</b> по цене <b>{money(price)} 🪙</b>\n"
        f"Списано с баланса: <b>-{money(total_cost)} 🪙</b>\n\n"
        f"💼 <i>Проверить активы:</i> <code>портфель</code>"
    )


@router.message(Cmd("продать акции", "продать акцию",
                    section=S_ECON, rank=0,
                    usage="продать акции [тикер] [кол-во]", desc="📉 Продажа акций по текущему курсу биржи"))
async def cmd_sell_stocks(message: Message, bot: Bot, args: str = "", **kw):
    parts = (args or "").strip().split()
    if len(parts) < 2:
        return await message.reply("⚠️ Пример продажи: <code>продать акции MOX 5</code>")

    ticker = parts[0].upper()
    if ticker not in STOCKS:
        return await message.reply("❌ Неизвестный тикер компании!")

    uid = message.from_user.id
    await _ensure_stock_tables()
    row = await db.fetchone("SELECT count FROM user_stocks WHERE user_id=? AND ticker=?", (uid, ticker))
    my_count = row["count"] if row else 0

    if my_count <= 0:
        return await message.reply(f"❌ У вас нет акций компании {ticker}!")

    if parts[1].lower() in ("все", "всё", "all"):
        count = my_count
    else:
        try:
            count = int(parts[1])
        except ValueError:
            return await message.reply("⚠️ Укажите целое количество акций!")

    if count > my_count or count <= 0:
        return await message.reply(f"❌ У вас есть только <b>{my_count}</b> акций {ticker}!")

    price = _get_current_stock_price(ticker)
    total_gain = price * count

    new_count = my_count - count
    if new_count > 0:
        await db.execute("UPDATE user_stocks SET count=? WHERE user_id=? AND ticker=?", (new_count, uid, ticker))
    else:
        await db.execute("DELETE FROM user_stocks WHERE user_id=? AND ticker=?", (uid, ticker))

    new_bal = await db.add_balance(uid, total_gain, action="stock_sell", meta=f"{ticker}:{count}")

    await message.reply(
        f"📉 ✨ <b>АКЦИИ УСПЕШНО ПРОДАНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Продано: <b>{count} шт. {ticker}</b>\n"
        f"Начислено в кошелёк: <b>+{money(total_gain)} 🪙</b>\n"
        f"Новый баланс: <b>{money(new_bal)} 🪙</b>"
    )


@router.message(Cmd("портфель", "мои акции",
                    section=S_ECON, rank=0,
                    usage="портфель", desc="💼 Инвестиционный портфель и стоимость ваших акций"))
async def cmd_my_portfolio(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    await _ensure_stock_tables()
    rows = await db.fetchall("SELECT ticker, count, buy_price FROM user_stocks WHERE user_id=? AND count > 0", (uid,))

    if not rows:
        return await message.reply("💼 Ваш инвестиционный портфель пока пуст! Изучите котировки: <code>биржа</code>.")

    total_val = 0
    lines = []
    for r in rows:
        tk = r["ticker"]
        cnt = r["count"]
        cur_p = _get_current_stock_price(tk)
        val = cur_p * cnt
        total_val += val
        lines.append(f"• <b>{tk}</b>: {cnt} шт. — <b>{money(val)} 🪙</b> <i>({money(cur_p)}/шт)</i>")

    text = (
        "💼 ✨ <b>ВАШ ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ</b> ✨ 💼\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines) + "\n\n"
        f"📊 Общая стоимость активов: <b>{money(total_val)} 🪙</b>\n\n"
        "💡 <i>Собрать прибыль:</i> <code>дивиденды</code>"
    )
    await message.reply(text)


@router.message(Cmd("дивиденды", "выплаты",
                    section=S_ECON, rank=0,
                    usage="дивиденды", desc="💰 Ежедневные дивидендные начисления по акциям"))
async def cmd_dividends(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    cd_left = await db.cooldown_left(uid, "stock_dividends", 86400)
    if cd_left > 0:
        h = cd_left // 3600
        return await message.reply(f"⏳ <i>Выплата дивидендов уже получена. Следующая через: <b>{h} часов</b>!</i>")

    await _ensure_stock_tables()
    rows = await db.fetchall("SELECT ticker, count FROM user_stocks WHERE user_id=? AND count > 0", (uid,))
    if not rows:
        return await message.reply("💼 У вас нет акций для получения дивидендов. Купите акции на <code>биржа</code>!")

    total_div = 0
    for r in rows:
        price = _get_current_stock_price(r["ticker"])
        total_div += int(price * r["count"] * 0.03)

    if total_div <= 0:
        total_div = 10_000

    await db.set_cooldown(uid, "stock_dividends")
    new_bal = await db.add_balance(uid, total_div, action="stock_dividends")

    await message.reply(
        f"💰 ✨ <b>ДИВИДЕНДЫ ПО АКЦИЯМ НАЧИСЛЕНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Выплата на ваш счёт: <b>+{money(total_div)} 🪙</b>\n"
        f"Баланс: <b>{money(new_bal)} 🪙</b>\n\n"
        f"🎉 <i>Спасибо за инвестиции в экономику Moxxi!</i>"
    )


# ══════════════════════════════════════════════════════════════════════
# 4. СЕКРЕТНЫЕ КЕЙСЫ 3.0 (ЛУТБОКСЫ С РЕДКИМ ЛУТОМ)
# ══════════════════════════════════════════════════════════════════════

BOXES_3_0 = {
    1: {"name": "📦 Неоновый Кейс", "coins": 250_000, "crystals": 0, "desc": "Шанс выбить до 2 500 000 монет и кристаллы"},
    2: {"name": "💎 Кристальный Ларец", "coins": 0, "crystals": 3, "desc": "Шанс выбить до 15 кристаллов, VIP и 10кк монет"},
    3: {"name": "👑 Императорский Сундук", "coins": 0, "crystals": 10, "desc": "Элитные призы: до 50кк монет, 30 кристаллов и VIP+ статус"}
}


@router.message(Cmd("кейсы 3.0", "лутбоксы", "новые кейсы",
                    section=S_GAMES, rank=0,
                    usage="кейсы 3.0", desc="📦 Новые секретные кейсы 3.0 с миллионами монет и кристаллами"))
async def cmd_boxes_list(message: Message, bot: Bot, **kw):
    lines = []
    for num, b in BOXES_3_0.items():
        cost_txt = f"{money(b['coins'])} 🪙" if b["coins"] else f"{b['crystals']} 💎"
        lines.append(f"<b>{num}. {b['name']}</b> — <b>{cost_txt}</b>\n   └ <i>{b['desc']}</i>")

    text = (
        "📦 ✨ <b>С Е К Р Е Т Н Ы Е   К Е Й С Ы   3.0</b> ✨ 📦\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n\n".join(lines) + "\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "👉 <i>Чтобы открыть, напишите:</i> <code>открыть кейс [номер]</code> (например: <code>открыть кейс 1</code>)"
    )
    await message.reply(text)


@router.message(Cmd("открыть кейс", "открыть сундук", "открыть лутбокс",
                    section=S_GAMES, rank=0,
                    usage="открыть кейс [номер]", desc="📦 Открыть кейс 3.0 и забрать редкий куш"))
async def cmd_open_box(message: Message, bot: Bot, args: str = "", **kw):
    arg = (args or "1").strip()
    try:
        box_id = int(arg)
    except ValueError:
        box_id = 1

    b = BOXES_3_0.get(box_id)
    if not b:
        return await message.reply("❌ Кейс с таким номером не найден! Напишите <code>кейсы 3.0</code>.")

    uid = message.from_user.id
    coins = await db.get_balance(uid)
    crystals = await db.get_crystals(uid)

    if b["coins"] > 0 and coins < b["coins"]:
        return await message.reply(f"❌ Недостаточно монет! Требуется: <b>{money(b['coins'])} 🪙</b>.")
    if b["crystals"] > 0 and crystals < b["crystals"]:
        return await message.reply(f"❌ Недостаточно кристаллов! Требуется: <b>{b['crystals']} 💎</b>.")

    # Списываем стоимость
    if b["coins"] > 0:
        await db.add_balance(uid, -b["coins"], action="box_open")
    if b["crystals"] > 0:
        await db.add_crystals(uid, -b["crystals"], action="box_open")

    status_msg = await message.reply("🎰 <i>Кейс вращается… Замок со щёлканьем открывается…</i>")
    await asyncio.sleep(1.8)

    # Генерация награды
    if box_id == 1:
        win_coins = random.choice([100_000, 300_000, 500_000, 1_000_000, 2_500_000])
        win_cry = 1 if random.random() < 0.25 else 0
        prize_txt = f"+{money(win_coins)} 🪙" + (f" и +{win_cry} 💎" if win_cry else "")
        await db.add_balance(uid, win_coins, action="box_prize")
        if win_cry:
            await db.add_crystals(uid, win_cry, action="box_prize")
    elif box_id == 2:
        win_coins = random.choice([2_000_000, 5_000_000, 10_000_000])
        win_cry = random.randint(2, 8)
        prize_txt = f"+{money(win_coins)} 🪙 и +{win_cry} 💎 Кристаллов"
        await db.add_balance(uid, win_coins, action="box_prize")
        await db.add_crystals(uid, win_cry, action="box_prize")
    else:
        win_coins = random.choice([15_000_000, 30_000_000, 50_000_000])
        win_cry = random.randint(10, 25)
        prize_txt = f"🎉 <b>СУПЕР-КУШ: +{money(win_coins)} 🪙 и +{win_cry} 💎 Кристаллов!</b>"
        await db.add_balance(uid, win_coins, action="box_prize")
        await db.add_crystals(uid, win_cry, action="box_prize")

    await status_msg.edit_text(
        f"📦 🎉 <b>КЕЙС «{b['name']}» УСПЕШНО ОТКРЫТ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Ваш дроп: <b>{prize_txt}</b>\n\n"
        f"Награда моментально зачислена в ваш инвентарь и кошелёк!"
    )
