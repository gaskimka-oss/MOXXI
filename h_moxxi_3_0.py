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


# ══════════════════════════════════════════════════════════════════════
# 5. СИНДИКАТЫ И ВОЙНЫ ЗА РАЙОНЫ (SYNDICATE WARS 3.0)
# ══════════════════════════════════════════════════════════════════════

DISTRICT_NAMES = {
    1: ("Центральный Неон", "🌆", 1_000_000),
    2: ("Финансовый Квартал", "💎", 2_500_000),
    3: ("Портовый Док", "🚢", 800_000),
    4: ("Подземный Бункер", "🚇", 1_500_000),
    5: ("Квартал Казино", "🎰", 3_000_000),
}

async def _init_syndicate_tables():
    await db.execute(
        "CREATE TABLE IF NOT EXISTS syndicates ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT UNIQUE, "
        "tag TEXT, "
        "owner_id INTEGER, "
        "balance INTEGER DEFAULT 0, "
        "rating INTEGER DEFAULT 0, "
        "created_at INTEGER"
        ")"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS syndicate_members ("
        "user_id INTEGER PRIMARY KEY, "
        "syndicate_id INTEGER, "
        "role TEXT DEFAULT 'member', "
        "joined_at INTEGER"
        ")"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS syndicate_districts ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT, "
        "owner_syndicate_id INTEGER DEFAULT 0, "
        "daily_bonus INTEGER DEFAULT 1000000, "
        "updated_at INTEGER DEFAULT 0"
        ")"
    )
    for did, (dname, dicon, dbonus) in DISTRICT_NAMES.items():
        await db.execute(
            "INSERT OR IGNORE INTO syndicate_districts (id, name, owner_syndicate_id, daily_bonus, updated_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (did, f"{dicon} {dname}", dbonus, int(time.time()))
        )


@router.message(Cmd("синдикаты", "топ синдикатов", "районы города", "карта районов",
                    section=S_ECON, rank=0,
                    usage="синдикаты", desc="🏙 Синдикаты, альянсы и контроль над 5 районами города"))
async def cmd_syndicates_list(message: Message, bot: Bot, **kw):
    await _init_syndicate_tables()
    synds = await db.fetchall("SELECT * FROM syndicates ORDER BY rating DESC, balance DESC LIMIT 10")
    districts = await db.fetchall("SELECT * FROM syndicate_districts ORDER BY id ASC")

    # Формируем карту районов
    d_lines = []
    for d in districts:
        owner_str = "<i>Свободен</i>"
        if d["owner_syndicate_id"]:
            s_row = await db.fetchone("SELECT name, tag FROM syndicates WHERE id=?", (d["owner_syndicate_id"],))
            if s_row:
                owner_str = f"<b>[{s_row['tag']}] {s_row['name']}</b>"
        d_lines.append(f"• <b>Район {d['id']}:</b> {d['name']} — {owner_str} (+{money(d['daily_bonus'])} 🪙/день)")

    s_lines = []
    if synds:
        for idx, s in enumerate(synds, 1):
            count_row = await db.fetchone("SELECT COUNT(*) as c FROM syndicate_members WHERE syndicate_id=?", (s["id"],))
            m_count = count_row["c"] if count_row else 1
            s_lines.append(f"<b>{idx}. [{s['tag']}] {s['name']}</b> • 👥 {m_count} чел. • 🏆 {s['rating']} PTS • 💰 {money(s['balance'])} 🪙")
    else:
        s_lines.append("<i>Пока не создано ни одного синдиката. Создайте свой первым!</i>")

    text = (
        "🏙 ⚔️ <b>СИНДИКАТЫ И КАРТА ГОРОДА MOXXI 3.0</b> ⚔️ 🏙\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "<b>Контроль городских районов:</b>\n"
        + "\n".join(d_lines) + "\n\n"
        "🏆 <b>Топ сильнейших синдикатов:</b>\n"
        + "\n".join(s_lines) + "\n\n"
        "💡 <b>Команды синдикатов:</b>\n"
        "• <code>создать синдикат [название] | [ТЕГ]</code> (цена: 10кк)\n"
        "• <code>мой синдикат</code> — ваш клан, казна и бойцы\n"
        "• <code>захват района [номер 1-5]</code> — объявить войну за район\n"
        "• <code>синдикат казна положить [сумма]</code> — пополнить казну"
    )
    await message.reply(text)


@router.message(Cmd("создать синдикат", "новый синдикат",
                    section=S_ECON, rank=0,
                    usage="создать синдикат [название] | [ТЕГ]", desc="🏙 Основать свой собственный синдикат за 10 000 000 🪙"))
async def cmd_create_syndicate(message: Message, bot: Bot, args: str = "", **kw):
    await _init_syndicate_tables()
    uid = message.from_user.id
    existing = await db.fetchone("SELECT * FROM syndicate_members WHERE user_id=?", (uid,))
    if existing:
        return await message.reply("❌ Вы уже состоите в синдикате! Чтобы создать новый, сначала напишите <code>покинуть синдикат</code>.")

    cost = 10_000_000
    coins = await db.get_balance(uid)
    if coins < cost:
        return await message.reply(f"❌ Для создания синдиката требуется <b>{money(cost)} 🪙</b>! У вас: {money(coins)} 🪙.")

    parts = [p.strip() for p in args.split("|") if p.strip()]
    if len(parts) < 2:
        return await message.reply("Укажите название и тег синдиката через черту:\n<code>создать синдикат Ночные Волки | WOLVES</code>")

    s_name = parts[0][:32]
    s_tag = parts[1][:6].upper()

    check_name = await db.fetchone("SELECT id FROM syndicates WHERE lower(name)=lower(?) OR lower(tag)=lower(?)", (s_name, s_tag))
    if check_name:
        return await message.reply("❌ Синдикат с таким названием или тегом уже существует!")

    await db.add_balance(uid, -cost, action="create_syndicate")
    now = int(time.time())
    res = await db.execute(
        "INSERT INTO syndicates (name, tag, owner_id, balance, rating, created_at) VALUES (?, ?, ?, 0, 100, ?)",
        (s_name, s_tag, uid, now)
    )
    synd_id = res.lastrowid
    await db.execute(
        "INSERT INTO syndicate_members (user_id, syndicate_id, role, joined_at) VALUES (?, ?, 'leader', ?)",
        (uid, synd_id, now)
    )

    await message.reply(
        f"🏙 🎉 <b>СИНДИКАТ [{s_tag}] «{s_name}» УСПЕШНО ОСНОВАН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👑 Лидер: <b>{message.from_user.first_name}</b>\n"
        f"🏆 Стартовый рейтинг: <b>100 PTS</b>\n"
        f"💵 Списано на регистрацию: <b>-{money(cost)} 🪙</b>\n\n"
        f"💡 Набирайте бойцов и захватывайте районы города: <code>захват района [1-5]</code>!"
    )


@router.message(Cmd("мой синдикат", "инфо синдиката",
                    section=S_ECON, rank=0,
                    usage="мой синдикат", desc="🏙 Просмотр информации о вашем синдикате"))
async def cmd_my_syndicate(message: Message, bot: Bot, **kw):
    await _init_syndicate_tables()
    uid = message.from_user.id
    mem = await db.fetchone("SELECT * FROM syndicate_members WHERE user_id=?", (uid,))
    if not mem:
        return await message.reply("❌ Вы не состоите ни в одном синдикате! Вступите по приглашению или создайте свой: <code>создать синдикат [имя] | [ТЕГ]</code>.")

    synd = await db.fetchone("SELECT * FROM syndicates WHERE id=?", (mem["syndicate_id"],))
    members_count = await db.fetchone("SELECT COUNT(*) as c FROM syndicate_members WHERE syndicate_id=?", (synd["id"],))
    controlled = await db.fetchall("SELECT name FROM syndicate_districts WHERE owner_syndicate_id=?", (synd["id"],))

    dist_str = ", ".join([c["name"] for c in controlled]) if controlled else "<i>Пока нет районов под контролем</i>"
    await message.reply(
        f"🏙 🛡 <b>СИНДИКАТ [{synd['tag']}] «{synd['name']}»</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 Состав: <b>{members_count['c']} бойцов</b>\n"
        f"🏆 Боевой рейтинг: <b>{synd['rating']} PTS</b>\n"
        f"💰 Казна синдиката: <b>{money(synd['balance'])} 🪙</b>\n"
        f"🌆 Подконтрольные районы: {dist_str}\n\n"
        f"📌 Ваша должность: <b>{'👑 Лидер' if mem['role'] == 'leader' else '⚔️ Боец'}</b>"
    )


@router.message(Cmd("захват района", "атаковать район", "захватить район",
                    section=S_ECON, rank=0,
                    usage="захват района [номер 1-5]", desc="⚔️ Война за городской район между синдикатами"))
async def cmd_capture_district(message: Message, bot: Bot, args: str = "", **kw):
    await _init_syndicate_tables()
    uid = message.from_user.id
    mem = await db.fetchone("SELECT * FROM syndicate_members WHERE user_id=?", (uid,))
    if not mem:
        return await message.reply("❌ Захватывать районы могут только члены синдикатов!")

    synd = await db.fetchone("SELECT * FROM syndicates WHERE id=?", (mem["syndicate_id"],))
    if not args.strip().isdigit() or not (1 <= int(args.strip()) <= 5):
        return await message.reply("Укажите номер района от 1 до 5: <code>захват района 1</code>.")

    did = int(args.strip())
    dist = await db.fetchone("SELECT * FROM syndicate_districts WHERE id=?", (did,))
    if dist["owner_syndicate_id"] == synd["id"]:
        return await message.reply("✅ Этот район уже находится под полным контролем вашего синдиката!")

    # Проверка КД
    now = int(time.time())
    if now - dist["updated_at"] < 3600:
        left_m = int((3600 - (now - dist["updated_at"])) / 60)
        return await message.reply(f"⏳ Район укреплён и находится под защитой перемирия ещё <b>{left_m} мин.</b>!")

    # Боевой расчет победы
    roll_attacker = random.randint(1, 100)
    roll_defender = random.randint(1, 80) if dist["owner_syndicate_id"] else 30

    status_msg = await message.reply(f"⚔️ <i>Синдикат [{synd['tag']}] начинает штурм района «{dist['name']}»…</i>")
    await asyncio.sleep(2.0)

    if roll_attacker >= roll_defender:
        await db.execute(
            "UPDATE syndicate_districts SET owner_syndicate_id=?, updated_at=? WHERE id=?",
            (synd["id"], now, did)
        )
        bonus_pts = random.randint(25, 50)
        await db.execute("UPDATE syndicates SET rating=rating+?, balance=balance+? WHERE id=?",
                         (bonus_pts, dist["daily_bonus"], synd["id"]))
        await status_msg.edit_text(
            f"🎉 ⚔️ <b>РАЙОН «{dist['name']}» УСПЕШНО ЗАХВАЧЕН!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Победу одержал синдикат: <b>[{synd['tag']}] {synd['name']}</b>!\n"
            f"🏆 Рейтинг синдиката: <b>+{bonus_pts} PTS</b>\n"
            f"💰 Трофей в казну: <b>+{money(dist['daily_bonus'])} 🪙</b>\n\n"
            f"Каждые 24 часа район будет приносить пассивный доход в казну синдиката!"
        )
    else:
        await status_msg.edit_text(
            f"💀 <b>ШТУРМ ОТБИТ!</b>\n"
            f"Оборона района оказалась сильнее атаки. Перегруппируйте силы и попробуйте снова!"
        )


# ══════════════════════════════════════════════════════════════════════
# 6. ЭМОДЗИ-ИГРЫ КАЗИНО TELEGRAM (DICE API С РЕАЛЬНОЙ ФИЗИКОЙ)
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("дартс", "дартс кометы", "дартс монеты",
                    section=S_GAMES, rank=0,
                    usage="дартс [ставка]", desc="🎯 Настоящий бросок дротика в Telegram (х1.5 - х3.5)"))
async def cmd_tg_darts(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    bet = parse_money(args) if args else 500
    if not bet or bet < 100:
        return await message.reply("Минимальная ставка в Дартс: <b>100 🪙</b>. Пример: <code>дартс 1000</code>")

    coins = await db.get_balance(uid)
    if coins < bet:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    await db.add_balance(uid, -bet, action="darts_bet")
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎯", reply_to_message_id=message.message_id)
    score = dice_msg.dice.value
    await asyncio.sleep(2.5)

    if score == 6:
        win = int(bet * 3.5)
        await db.add_balance(uid, win, action="darts_win")
        await message.reply(f"🎯 💥 <b>В ЯБЛОЧКО! Точнейший бросок в центр!</b>\nВыигрыш (х3.5): <b>+{money(win)} 🪙</b>")
    elif score == 5:
        win = int(bet * 2.0)
        await db.add_balance(uid, win, action="darts_win")
        await message.reply(f"🎯 ✨ <b>Красное кольцо!</b> Выигрыш (х2.0): <b>+{money(win)} 🪙</b>")
    elif score == 4:
        win = int(bet * 1.5)
        await db.add_balance(uid, win, action="darts_win")
        await message.reply(f"🎯 Белое кольцо! Выигрыш (х1.5): <b>+{money(win)} 🪙</b>")
    else:
        await message.reply(f"🎯 Мимо мишени… Вы потеряли <b>-{money(bet)} 🪙</b>.")


@router.message(Cmd("баскетбол", "баскет",
                    section=S_GAMES, rank=0,
                    usage="баскетбол [ставка]", desc="🏀 Бросок мяча в баскетбольную корзину (х2.5)"))
async def cmd_tg_basketball(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    bet = parse_money(args) if args else 500
    if not bet or bet < 100:
        return await message.reply("Минимальная ставка: <b>100 🪙</b>. Пример: <code>баскетбол 1000</code>")

    coins = await db.get_balance(uid)
    if coins < bet:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    await db.add_balance(uid, -bet, action="basket_bet")
    dice_msg = await bot.send_dice(message.chat.id, emoji="🏀", reply_to_message_id=message.message_id)
    score = dice_msg.dice.value
    await asyncio.sleep(3.0)

    # В баскетболе 4 и 5 - попадания
    if score >= 4:
        mult = 2.5 if score == 5 else 2.0
        win = int(bet * mult)
        await db.add_balance(uid, win, action="basket_win")
        await message.reply(f"🏀 💥 <b>ГОООЛ! Точный бросок прямо в кольцо!</b>\nВыигрыш (х{mult}): <b>+{money(win)} 🪙</b>")
    else:
        await message.reply(f"🏀 Мяч отскочил от щита! Проигрыш <b>-{money(bet)} 🪙</b>.")


@router.message(Cmd("боулинг",
                    section=S_GAMES, rank=0,
                    usage="боулинг [ставка]", desc="🎳 Бросок шара в боулинге: страйк x4.0, полустрайк x2.0"))
async def cmd_tg_bowling(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    bet = parse_money(args) if args else 500
    if not bet or bet < 100:
        return await message.reply("Минимальная ставка: <b>100 🪙</b>. Пример: <code>боулинг 1000</code>")

    coins = await db.get_balance(uid)
    if coins < bet:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    await db.add_balance(uid, -bet, action="bowling_bet")
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎳", reply_to_message_id=message.message_id)
    score = dice_msg.dice.value
    await asyncio.sleep(2.8)

    if score == 6:
        win = int(bet * 4.0)
        await db.add_balance(uid, win, action="bowling_win")
        await message.reply(f"🎳 💥 <b>СТРАЙК! Все кегли разлетелись в щепки!</b>\nВыигрыш (х4.0): <b>+{money(win)} 🪙</b>")
    elif score >= 4:
        win = int(bet * 2.0)
        await db.add_balance(uid, win, action="bowling_win")
        await message.reply(f"🎳 ✨ <b>Сбито большинство кеглей!</b> Выигрыш (х2.0): <b>+{money(win)} 🪙</b>")
    else:
        await message.reply(f"🎳 Шар ушёл в желоб… Проигрыш <b>-{money(bet)} 🪙</b>.")


@router.message(Cmd("футбол", "пенальти",
                    section=S_GAMES, rank=0,
                    usage="футбол [ставка]", desc="⚽️ Пробитие пенальти по воротам (х2.0 - х2.5)"))
async def cmd_tg_football(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    bet = parse_money(args) if args else 500
    if not bet or bet < 100:
        return await message.reply("Минимальная ставка: <b>100 🪙</b>. Пример: <code>футбол 1000</code>")

    coins = await db.get_balance(uid)
    if coins < bet:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    await db.add_balance(uid, -bet, action="football_bet")
    dice_msg = await bot.send_dice(message.chat.id, emoji="⚽️", reply_to_message_id=message.message_id)
    score = dice_msg.dice.value
    await asyncio.sleep(2.8)

    # 3, 4, 5 — голы
    if score >= 3:
        mult = 2.5 if score == 5 else 2.0
        win = int(bet * mult)
        await db.add_balance(uid, win, action="football_win")
        await message.reply(f"⚽️ 💥 <b>ГОООООЛ! Мяч вонзается в сетку ворот!</b>\nВыигрыш (х{mult}): <b>+{money(win)} 🪙</b>")
    else:
        await message.reply(f"⚽️ Вратарь парирует удар! Проигрыш <b>-{money(bet)} 🪙</b>.")


# ══════════════════════════════════════════════════════════════════════
# 7. АДМИН-КАРАНТИН НОВИЧКОВ И АНТИ-РЕЙД ЩИТ 3.0
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("карантин", "песочница новичков",
                    section=S_ADMIN, rank=4, group_only=True,
                    usage="карантин [минуты/выкл]", desc="🛡 Режим карантина для новичков (ограничение ссылок и медиа)"))
async def cmd_admin_quarantine(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Команда доступна администраторам от <b>4 ранга (Старший админ)</b>.")

    cid = message.chat.id
    raw = args.strip().lower()
    if raw in {"выкл", "0", "off", "disable"}:
        await db.set_setting(cid, "quarantine_min", "0")
        return await message.reply("✅ <b>Карантин новичков выключен.</b> Новые участники сразу получают полный доступ.")

    if not raw.isdigit() or int(raw) < 1 or int(raw) > 1440:
        cur = await db.get_setting(cid, "quarantine_min", "0")
        return await message.reply(
            f"🛡 <b>Карантин новичков:</b> {'активен (' + cur + ' мин.)' if cur != '0' else 'выключен'}\n\n"
            f"Укажите время в минутах: <code>карантин 15</code> (или <code>карантин выкл</code>)."
        )

    mins = int(raw)
    await db.set_setting(cid, "quarantine_min", str(mins))
    await message.reply(
        f"🛡 ✅ <b>КАРАНТИН НОВИЧКОВ ВКЛЮЧЕН НА {mins} МИНУТ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Все вступившие в группу участники в течение первых <b>{mins} мин.</b> не смогут отправлять ссылки и пересылать сообщения, защищая чат от спам-волн!"
    )


@router.message(Cmd("лог модерации", "журнал действий", "стафф лог",
                    section=S_ADMIN, rank=2, group_only=True,
                    usage="лог модерации [кол-во=10]", desc="📋 Детальный дашборд последних действий модераторов чата"))
async def cmd_mod_action_log(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 2:
        return await message.reply("⛔️ Доступно модераторам от <b>2 ранга</b>.")

    limit = min(25, max(5, int(args.strip()) if args.strip().isdigit() else 10))
    cid = message.chat.id
    rows = await db.fetchall(
        "SELECT * FROM rank_log WHERE chat_id=? ORDER BY ts DESC LIMIT ?",
        (cid, limit)
    )

    if not rows:
        return await message.reply("📋 <i>В журнале пока нет записанных действий модерации для этой беседы.</i>")

    lines = []
    for r in rows:
        t_str = time.strftime("%d.%m %H:%M", time.localtime(r["ts"]))
        by_user = await db.get_user(r["by_id"]) if r["by_id"] else None
        target_user = await db.get_user(r["user_id"])
        by_name = by_user["first_name"] if by_user else "Система/Владелец"
        tgt_name = target_user["first_name"] if target_user else f"ID {r['user_id']}"
        lines.append(f"• <code>[{t_str}]</code> <b>{by_name}</b> ➔ <b>{tgt_name}</b> (Ранг: <b>{r['rank']}</b>)")

    await message.reply(
        f"📋 🛡 <b>ПОСЛЕДНИЕ ДЕЙСТВИЯ СТАФФА ({len(lines)} зап.)</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines)
    )



# ══════════════════════════════════════════════════════════════════════
# 6. КАЗИНО ЕВРОПЕЙСКАЯ РУЛЕТКА (ROULETTE X36)
# ══════════════════════════════════════════════════════════════════════

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

@router.message(Cmd("рулетка", "рулетка казино", "крутить рулетку",
                    section=S_GAMES, rank=0,
                    usage="рулетка [ставка] [красное|черное|зеро|чет|нечет|0..36]",
                    desc="🎰 Европейская рулетка: угадайте сектор или цвет (выигрыш до x36!)"))
async def cmd_casino_roulette(message: Message, bot: Bot, args: str = "", **kw):
    parts = args.strip().split()
    if len(parts) < 2:
        return await message.reply(
            "🎰 <b>Европейская Рулетка MOXXI:</b>\n\n"
            "• На цвет: <code>рулетка 1000 красное</code> (x2)\n"
            "• На цвет: <code>рулетка 1000 черное</code> (x2)\n"
            "• На четность: <code>рулетка 1000 чет</code> / <code>нечет</code> (x2)\n"
            "• На зеро: <code>рулетка 1000 зеро</code> (x36)\n"
            "• На точное число: <code>рулетка 1000 17</code> (x36) [0–36]"
        )

    bet_raw, choice_raw = parts[0], parts[1].lower()
    bet = parse_money(bet_raw)
    if not bet or bet <= 0:
        return await message.reply("❌ Укажите корректную сумму ставки!")

    uid = message.from_user.id
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < bet:
        return await message.reply(f"❌ Недостаточно средств! Ваш баланс: <b>{money(bal)}</b> монет.")

    valid_choices = {"красное", "красный", "red", "черное", "чёрное", "черный", "black", "зеро", "zero", "чет", "четное", "нечет", "нечетное"}
    is_num = choice_raw.isdigit() and (0 <= int(choice_raw) <= 36)
    if not is_num and choice_raw not in valid_choices:
        return await message.reply("❌ Неверный выбор! Выберите: <code>красное</code>, <code>черное</code>, <code>зеро</code>, <code>чет</code>, <code>нечет</code> или число <code>0–36</code>.")

    await db.add_money(uid, -bet)

    spin_msg = await message.reply(f"🎡 <i>Шарик запущен по колесу рулетки… Ставка: {money(bet)} монет!</i> ⚪️")
    await asyncio.sleep(1.8)

    winning_num = random.randint(0, 36)
    if winning_num == 0:
        win_color = "зеленое 🟢"
        color_tag = "зеро"
    elif winning_num in ROULETTE_RED:
        win_color = "красное 🔴"
        color_tag = "красное"
    else:
        win_color = "черное ⚫️"
        color_tag = "черное"

    is_even = (winning_num > 0) and (winning_num % 2 == 0)

    # Проверка выигрыша
    won = False
    multiplier = 0.0

    if is_num and int(choice_raw) == winning_num:
        won = True
        multiplier = 36.0
    elif choice_raw in {"зеро", "zero"} and winning_num == 0:
        won = True
        multiplier = 36.0
    elif choice_raw in {"красное", "красный", "red"} and color_tag == "красное":
        won = True
        multiplier = 2.0
    elif choice_raw in {"черное", "чёрное", "черный", "black"} and color_tag == "черное":
        won = True
        multiplier = 2.0
    elif choice_raw in {"чет", "четное"} and is_even:
        won = True
        multiplier = 2.0
    elif choice_raw in {"нечет", "нечетное"} and (winning_num > 0 and not is_even):
        won = True
        multiplier = 2.0

    payout = int(bet * multiplier)
    if won:
        await db.add_money(uid, payout)
        net_profit = payout - bet
        res_text = (
            f"🎰 🎯 <b>ПОБЕДА В РУЛЕТКЕ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Выпало: <b>{winning_num}</b> ({win_color})\n"
            f"Множитель: <b>x{multiplier:.1f}</b>\n"
            f"💰 Выигрыш: <b>+{money(payout)}</b> монет (+{money(net_profit)} чистыми)!\n"
            f"Баланс: <b>{money(bal - bet + payout)}</b> монет."
        )
    else:
        res_text = (
            f"🎰 💨 <b>ВЫ ПРОИГРАЛИ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Выпало: <b>{winning_num}</b> ({win_color})\n"
            f"Ваш выбор: <code>{choice_raw}</code>\n"
            f"💸 Потеряно: <b>-{money(bet)}</b> монет.\n"
            f"Баланс: <b>{money(bal - bet)}</b> монет."
        )

    try:
        await spin_msg.edit_text(res_text)
    except Exception:
        await message.reply(res_text)


# ══════════════════════════════════════════════════════════════════════
# 7. АДМИН-ОБЪЯВЛЕНИЕ И АНТИРЕЙД КАПЧА
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("объявление", "объявить", "важное",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="объявление [текст]", desc="📢 Опубликовать стильное объявление от администрации с закрепом"))
async def cmd_admin_announcement(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Команда доступна модераторам от <b>3 ранга (Администратор)</b>.")

    text = args.strip()
    if not text:
        return await message.reply("📢 Укажите текст объявления: <code>объявление Сегодня в 20:00 клановый турнир!</code>")

    admin_name = message.from_user.first_name if message.from_user else "Администрация"
    cid = message.chat.id

    banner = (
        f"📢 ⚡️ <b>ОФИЦИАЛЬНОЕ ОБЪЯВЛЕНИЕ АДМИНИСТРАЦИИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{html.escape(text)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✍️ Опубликовал: <b>{html.escape(admin_name)}</b>\n"
        f"🔔 Просьба ознакомиться всем участникам беседы!"
    )

    try:
        sent = await message.reply(banner)
        try:
            await bot.pin_chat_message(cid, sent.message_id, disable_notification=False)
        except Exception:
            pass
    except Exception as e:
        await message.reply(f"❌ Ошибка публикации: {e}")


@router.message(Cmd("капча", "антирейд капча", "вход капча",
                    section=S_ADMIN, rank=4, group_only=True,
                    usage="капча [вкл|выкл]", desc="🛡 Анти-бот капча при вступлении новых участников"))
async def cmd_admin_captcha_toggle(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Команда доступна администраторам от <b>4 ранга</b>.")

    cid = message.chat.id
    raw = args.strip().lower()

    if raw in {"вкл", "1", "on", "enable"}:
        await db.set_setting(cid, "captcha_join", "1")
        return await message.reply(
            "🛡 🤖 <b>АНТИ-СПАМ КАПЧА ВКЛЮЧЕНА!</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Каждый новый участник чата обязан пройти проверку кнопкой «Я человек» в течение 60 секунд. "
            "Спам-боты и рейдеры будут автоматически изолированы!"
        )
    elif raw in {"выкл", "0", "off", "disable"}:
        await db.set_setting(cid, "captcha_join", "0")
        return await message.reply("🛡 <b>Капча для новичков выключена.</b>")
    else:
        cur = await db.get_setting(cid, "captcha_join", "0")
        state_str = "🟢 включена" if cur == "1" else "🔴 выключена"
        await message.reply(
            f"🛡 <b>Защита чата капчей:</b> {state_str}\n\n"
            f"Используйте: <code>капча вкл</code> или <code>капча выкл</code>."
        )


# ══════════════════════════════════════════════════════════════════════
# 8. МИНИ-ИГРА «КРАШ / РАКЕТА» (CRASH GAME X1.0 - X35.0)
# ══════════════════════════════════════════════════════════════════════

ACTIVE_CRASH_GAMES: dict[str, dict] = {}

@router.message(Cmd("ракета", "краш", "crash",
                    section=S_GAMES, rank=0,
                    usage="ракета [ставка]",
                    desc="🚀 Космическая ракета: успейте забрать куш до взрыва ракеты!"))
async def cmd_crash_game(message: Message, bot: Bot, args: str = "", **kw):
    bet = parse_money(args)
    if not bet or bet <= 0:
        return await message.reply("🚀 <b>Игра «Краш / Ракета»:</b>\n\nУкажите сумму ставки: <code>ракета 1000</code>\nРакета набирает высоту, множитель растёт до x35! Успейте нажать кнопку «Забрать», пока ракета не взорвалась.")

    uid = message.from_user.id
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < bet:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(bal)}</b> монет.")

    game_id = f"{message.chat.id}_{message.message_id}_{uid}"
    if game_id in ACTIVE_CRASH_GAMES:
        return await message.reply("⏳ У вас уже есть активный запуск ракеты!")

    await db.add_money(uid, -bet)

    # Определяем точку взрыва (взвешенная случайность)
    r = random.random()
    if r < 0.35:
        crash_multiplier = round(random.uniform(1.10, 1.65), 2)
    elif r < 0.70:
        crash_multiplier = round(random.uniform(1.70, 3.20), 2)
    elif r < 0.90:
        crash_multiplier = round(random.uniform(3.30, 7.50), 2)
    else:
        crash_multiplier = round(random.uniform(8.00, 32.00), 2)

    game_data = {
        "user_id": uid,
        "bet": bet,
        "crash_at": crash_multiplier,
        "current": 1.00,
        "cashed_out": False,
        "chat_id": message.chat.id
    }
    ACTIVE_CRASH_GAMES[game_id] = game_data

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💰 ЗАБРАТЬ ВЫИГРЫШ (x1.00)", callback_data=f"crash_cashout:{game_id}")
    ]])

    flight_msg = await message.reply(
        f"🚀 ✨ <b>РАКЕТА MOXXI ЗАПУЩЕНА!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Ставка: <b>{money(bet)}</b> монет\n"
        f"Текущий множитель: <b>x1.00</b> 📈\n"
        f"Успейте нажать кнопку ниже до взрыва!",
        reply_markup=kb
    )

    async def run_flight():
        cur = 1.00
        steps = [1.15, 1.30, 1.50, 1.75, 2.10, 2.60, 3.20, 4.00, 5.20, 7.00, 9.50, 13.00, 18.00, 25.00, 35.00]
        for step in steps:
            await asyncio.sleep(1.2)
            if game_id not in ACTIVE_CRASH_GAMES or ACTIVE_CRASH_GAMES[game_id]["cashed_out"]:
                return

            if step >= crash_multiplier:
                # Взрыв ракеты
                ACTIVE_CRASH_GAMES.pop(game_id, None)
                try:
                    await flight_msg.edit_text(
                        f"💥 💨 <b>РАКЕТА ВЗОРВАЛАСЬ НА ОТМЕТКЕ x{crash_multiplier:.2f}!</b>\n"
                        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                        f"Игрок: <b>{html.escape(message.from_user.first_name)}</b>\n"
                        f"💸 Потеряно: <b>-{money(bet)}</b> монет.\n"
                        f"В следующий раз обязательно повезёт!"
                    )
                except Exception:
                    pass
                return

            cur = step
            ACTIVE_CRASH_GAMES[game_id]["current"] = cur
            cur_payout = int(bet * cur)
            new_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"💰 ЗАБРАТЬ +{money(cur_payout)} (x{cur:.2f})", callback_data=f"crash_cashout:{game_id}")
            ]])
            try:
                await flight_msg.edit_text(
                    f"🚀 🔥 <b>РАКЕТА НАБИРАЕТ ВЫСОТУ!</b>\n"
                    f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    f"Ставка: <b>{money(bet)}</b> монет\n"
                    f"Текущий множитель: <b>x{cur:.2f}</b> 📈\n"
                    f"💰 Возможный куш: <b>+{money(cur_payout)}</b> монет",
                    reply_markup=new_kb
                )
            except Exception:
                pass

    asyncio.create_task(run_flight())


@router.callback_query(F.data.startswith("crash_cashout:"))
async def on_crash_cashout(call: CallbackQuery):
    game_id = call.data.split(":", 1)[1]
    game = ACTIVE_CRASH_GAMES.get(game_id)
    if not game:
        return await call.answer("❌ Ракета уже завершила полет!", show_alert=True)

    if call.from_user.id != game["user_id"]:
        return await call.answer("⛔️ Это не ваш запуск ракеты!", show_alert=True)

    if game["cashed_out"]:
        return await call.answer("Вы уже забрали выигрыш!", show_alert=True)

    game["cashed_out"] = True
    ACTIVE_CRASH_GAMES.pop(game_id, None)

    mult = game["current"]
    bet = game["bet"]
    win = int(bet * mult)
    profit = win - bet

    await db.add_money(call.from_user.id, win)
    await call.answer(f"🎉 Вы забрали +{money(win)} монет (x{mult:.2f})!", show_alert=True)

    try:
        await call.message.edit_text(
            f"🎉 🚀 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Игрок: <b>{html.escape(call.from_user.first_name)}</b>\n"
            f"Зафиксированный множитель: <b>x{mult:.2f}</b> 🏆\n"
            f"💰 Выигрыш: <b>+{money(win)}</b> монет (+{money(profit)} чистыми)!"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# 9. СИСТЕМА КОРПОРАЦИЙ И БИЗНЕС-ИМПЕРИЙ (MEGA CORPORATIONS)
# ══════════════════════════════════════════════════════════════════════

BRANCH_CATALOG = {
    1: {"name": "Сеть кофеен Moxxi Coffee", "cost": 250_000, "income": 18_000, "icon": "☕️"},
    2: {"name": "IT-Холдинг и Финтех", "cost": 1_000_000, "income": 85_000, "icon": "💻"},
    3: {"name": "Логистический Порт", "cost": 4_500_000, "income": 420_000, "icon": "🚢"},
    4: {"name": "Нефтедобывающий Комплекс", "cost": 18_000_000, "income": 1_900_000, "icon": "🛢"},
    5: {"name": "Квантовый Дата-Центр", "cost": 75_000_000, "income": 8_500_000, "icon": "🔮"},
    6: {"name": "Орбитальный Космодром", "cost": 280_000_000, "income": 38_000_000, "icon": "🛰"}
}

@router.message(Cmd("создать корпорацию", "новая корпорация",
                    section=S_ECON, rank=0,
                    usage="создать корпорацию [название]",
                    desc="🏢 Основать собственную корпорацию и бизнес-сеть (от 500k)"))
async def cmd_create_corporation(message: Message, bot: Bot, args: str = "", **kw):
    name = args.strip()
    if not name or len(name) < 3:
        return await message.reply("🏢 Укажите название корпорации: <code>создать корпорацию CyberTech</code> (от 3 до 24 символов).")

    uid = message.from_user.id
    row = await db.fetchone("SELECT id FROM moxxi_corporations WHERE owner_id=?", (uid,))
    if row:
        return await message.reply("❌ Вы уже владеете корпорацией! Используйте <code>моя корпорация</code>.")

    cost = 500_000
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < cost:
        return await message.reply(f"❌ Для основания корпорации требуется <b>{money(cost)}</b> монет! Ваш баланс: {money(bal)}.")

    await db.add_money(uid, -cost)
    now = int(time.time())
    import json
    await db.execute(
        "INSERT INTO moxxi_corporations (owner_id, name, balance, level, branches, last_collect, created_ts) VALUES (?,?,?,?,?,?,?)",
        (uid, name[:24], 0, 1, json.dumps([]), now, now)
    )

    await message.reply(
        f"🏢 🥂 <b>ПОЗДРАВЛЯЕМ С ОСНОВАНИЕМ КОРПОРАЦИИ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Название: <b>«{html.escape(name[:24])}»</b>\n"
        f"Генеральный директор: <b>{html.escape(message.from_user.first_name)}</b>\n"
        f"💡 Теперь покупайте филиалы: <code>купить филиал [1-6]</code> и собирайте пассивную прибыль!"
    )


@router.message(Cmd("моя корпорация", "корпорация", "корпорация инфо",
                    section=S_ECON, rank=0,
                    desc="🏢 Просмотр состояния корпорации, казны и открытых филиалов"))
async def cmd_my_corporation(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    corp = await db.fetchone("SELECT * FROM moxxi_corporations WHERE owner_id=?", (uid,))
    if not corp:
        return await message.reply(
            "🏢 <b>У вас пока нет корпорации!</b>\n\n"
            "Основать бизнес-империю: <code>создать корпорацию [название]</code> (500,000 монет)."
        )

    import json
    branches = json.loads(corp["branches"]) if corp["branches"] else []
    
    total_hourly = sum(BRANCH_CATALOG[b]["income"] for b in branches if b in BRANCH_CATALOG)
    now = int(time.time())
    hours_passed = max(0, (now - int(corp["last_collect"])) / 3600.0)
    unclaimed = int(total_hourly * hours_passed)

    branch_lines = []
    for bid, binfo in BRANCH_CATALOG.items():
        status = "✅ Открыт" if bid in branches else f"🔒 <code>купить филиал {bid}</code>"
        branch_lines.append(f"{binfo['icon']} {binfo['name']}: {status} (+{money(binfo['income'])}/ч)")

    await message.reply(
        f"🏢 👔 <b>КОРПОРАЦИЯ «{html.escape(corp['name'])}»</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💰 Казна корпорации: <b>{money(int(corp['balance']))}</b> монет\n"
        f"📈 Пассивная выручка: <b>+{money(total_hourly)}</b> монет/час\n"
        f"📦 Несобранный доход: <b>+{money(unclaimed)}</b> монет (<code>собрать прибыль</code>)\n\n"
        f"🏭 <b>Филиалы корпорации ({len(branches)}/6):</b>\n"
        + "\n".join(branch_lines) + "\n\n"
        f"💡 Команды: <code>собрать прибыль</code>, <code>снять из корпорации [сумма]</code>"
    )


@router.message(Cmd("купить филиал", "открыть филиал",
                    section=S_ECON, rank=0,
                    usage="купить филиал [1-6]",
                    desc="🏭 Приобрести филиал для корпорации (пассивный доход)"))
async def cmd_buy_branch(message: Message, bot: Bot, args: str = "", **kw):
    if not args.strip().isdigit() or int(args.strip()) not in BRANCH_CATALOG:
        return await message.reply("🏭 Укажите номер филиала от 1 до 6: <code>купить филиал 1</code> (список доступен в <code>моя корпорация</code>).")

    bid = int(args.strip())
    binfo = BRANCH_CATALOG[bid]

    uid = message.from_user.id
    corp = await db.fetchone("SELECT * FROM moxxi_corporations WHERE owner_id=?", (uid,))
    if not corp:
        return await message.reply("❌ Сначала создайте корпорацию: <code>создать корпорацию [название]</code>!")

    import json
    branches = json.loads(corp["branches"]) if corp["branches"] else []
    if bid in branches:
        return await message.reply(f"❌ У вас уже открыт филиал <b>{binfo['name']}</b>!")

    cost = binfo["cost"]
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < cost:
        return await message.reply(f"❌ Недостаточно средств! Стоимость филиала: <b>{money(cost)}</b> монет (ваш баланс: {money(bal)}).")

    await db.add_money(uid, -cost)
    branches.append(bid)
    await db.execute("UPDATE moxxi_corporations SET branches=? WHERE id=?", (json.dumps(branches), corp["id"]))

    await message.reply(
        f"🏭 ✨ <b>ФИЛИАЛ УСПЕШНО ПРИОБРЕТЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Открыт: <b>{binfo['icon']} {binfo['name']}</b>\n"
        f"Прибавка к доходу: <b>+{money(binfo['income'])} монет/час</b>! 📈"
    )


@router.message(Cmd("собрать прибыль", "собрать доход",
                    section=S_ECON, rank=0,
                    desc="💰 Собрать накопленную прибыль филиалов в казну корпорации"))
async def cmd_collect_corp_profit(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    corp = await db.fetchone("SELECT * FROM moxxi_corporations WHERE owner_id=?", (uid,))
    if not corp:
        return await message.reply("❌ У вас нет корпорации!")

    import json
    branches = json.loads(corp["branches"]) if corp["branches"] else []
    total_hourly = sum(BRANCH_CATALOG[b]["income"] for b in branches if b in BRANCH_CATALOG)

    if total_hourly <= 0:
        return await message.reply("❌ У вас еще нет работающих филиалов! Откройте филиал: <code>купить филиал 1</code>.")

    now = int(time.time())
    hours_passed = max(0, (now - int(corp["last_collect"])) / 3600.0)
    profit = int(total_hourly * hours_passed)

    if profit < 1000:
        return await message.reply("⏳ Прибыль пока слишком мала. Подождите еще немного!")

    new_bal = int(corp["balance"]) + profit
    await db.execute("UPDATE moxxi_corporations SET balance=?, last_collect=? WHERE id=?", (new_bal, now, corp["id"]))

    await message.reply(
        f"💰 ✨ <b>ПРИБЫЛЬ УСПЕШНО СОБРАНА!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"В казну корпорации поступило: <b>+{money(profit)}</b> монет!\n"
        f"Баланс казны: <b>{money(new_bal)}</b> монет.\n"
        f"Вывести средства основателю: <code>снять из корпорации [сумма]</code>"
    )


@router.message(Cmd("снять из корпорации", "вывод из корпорации",
                    section=S_ECON, rank=0,
                    usage="снять из корпорации [сумма]",
                    desc="💳 Вывести накопленные монеты из казны корпорации на личный баланс"))
async def cmd_withdraw_corp(message: Message, bot: Bot, args: str = "", **kw):
    amount = parse_money(args)
    if not amount or amount <= 0:
        return await message.reply("💳 Укажите сумму: <code>снять из корпорации 50000</code>.")

    uid = message.from_user.id
    corp = await db.fetchone("SELECT * FROM moxxi_corporations WHERE owner_id=?", (uid,))
    if not corp:
        return await message.reply("❌ У вас нет корпорации!")

    corp_bal = int(corp["balance"])
    if corp_bal < amount:
        return await message.reply(f"❌ В казне корпорации только <b>{money(corp_bal)}</b> монет!")

    await db.execute("UPDATE moxxi_corporations SET balance=balance-? WHERE id=?", (amount, corp["id"]))
    await db.add_money(uid, amount)

    await message.reply(
        f"💳 ✅ <b>ВЫВОД ИЗ КОРПОРАЦИИ ВЫПОЛНЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Сумма: <b>+{money(amount)}</b> монет зачислена на ваш баланс!\n"
        f"Остаток в казне: <b>{money(corp_bal - amount)}</b> монет."
    )


# ══════════════════════════════════════════════════════════════════════
# 10. АРТЕФАКТЫ И РЕЛИКВИИ МОКСИ (ANCIENT ARTIFACTS)
# ══════════════════════════════════════════════════════════════════════

ARTIFACTS_CATALOG = {
    1: {"name": "Око Бури", "cost": 500_000, "desc": "⚡️ +15% к выигрышам в казино и рулетке", "icon": "⚡️"},
    2: {"name": "Щит Титана", "cost": 750_000, "desc": "🛡 50% шанс отразить карманника/ограбление", "icon": "🛡"},
    3: {"name": "Кристалл Изобилия", "cost": 1_500_000, "desc": "💎 +25% к ежедневному бонусу и дивидендам", "icon": "💎"},
    4: {"name": "Хроно-Сфера", "cost": 3_500_000, "desc": "⏳ Сокращает перезарядку всех игр в 2 раза", "icon": "⏳"},
    5: {"name": "Венец Императора", "cost": 10_000_000, "desc": "👑 Эксклюзивный статус и уважение в чате", "icon": "👑"},
    6: {"name": "Печать Дракона", "cost": 25_000_000, "desc": "🐉 Двойной урон по мировым рейд-боссам", "icon": "🐉"}
}

@router.message(Cmd("артефакты", "витрина артефактов",
                    section=S_GAMES, rank=0,
                    desc="🔮 Каталог древних магических артефактов Мокси"))
async def cmd_artifacts_catalog(message: Message, bot: Bot, args: str = "", **kw):
    lines = []
    for aid, a in ARTIFACTS_CATALOG.items():
        lines.append(f"<b>{aid}. {a['icon']} {a['name']}</b> — {money(a['cost'])} монет\n   └ {a['desc']}")

    await message.reply(
        "🔮 ⚡️ <b>МАГИЧЕСКИЕ АРТЕФАКТЫ MOXXI 3.0</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines) + "\n\n"
        "Купить артефакт: <code>купить артефакт [номер]</code>\n"
        "Ваши реликвии: <code>мои артефакты</code>"
    )


@router.message(Cmd("купить артефакт",
                    section=S_GAMES, rank=0,
                    usage="купить артефакт [номер]",
                    desc="🔮 Приобрести магический артефакт в свою коллекцию"))
async def cmd_buy_artifact(message: Message, bot: Bot, args: str = "", **kw):
    if not args.strip().isdigit() or int(args.strip()) not in ARTIFACTS_CATALOG:
        return await message.reply("🔮 Укажите номер артефакта от 1 до 6: <code>купить артефакт 1</code>.")

    aid = int(args.strip())
    art = ARTIFACTS_CATALOG[aid]
    uid = message.from_user.id

    owned = await db.fetchone("SELECT * FROM moxxi_artifacts WHERE user_id=? AND artifact_id=?", (uid, aid))
    if owned:
        return await message.reply(f"❌ У вас уже есть артефакт <b>{art['icon']} {art['name']}</b>!")

    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < art["cost"]:
        return await message.reply(f"❌ Недостаточно средств! Стоимость: <b>{money(art['cost'])}</b> монет (ваш баланс: {money(bal)}).")

    await db.add_money(uid, -art["cost"])
    now = int(time.time())
    await db.execute("INSERT INTO moxxi_artifacts (user_id, artifact_id, level, acquired_ts) VALUES (?,?,?,?)",
                     (uid, aid, 1, now))

    await message.reply(
        f"🔮 ✨ <b>АРТЕФАКТ УСПЕШНО АКТИВИРОВАН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Получен: <b>{art['icon']} {art['name']}</b>\n"
        f"Эффект: <b>{art['desc']}</b>\n"
        f"Артефакт навсегда закреплен за вашим профилем!"
    )


@router.message(Cmd("мои артефакты",
                    section=S_GAMES, rank=0,
                    desc="🔮 Список активированных артефактов в вашем профиле"))
async def cmd_my_artifacts(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    rows = await db.fetchall("SELECT * FROM moxxi_artifacts WHERE user_id=?", (uid,))
    if not rows:
        return await message.reply("🔮 У вас пока нет ни одного артефакта! Посмотреть список: <code>артефакты</code>.")

    lines = []
    for r in rows:
        aid = int(r["artifact_id"])
        if aid in ARTIFACTS_CATALOG:
            a = ARTIFACTS_CATALOG[aid]
            lines.append(f"• {a['icon']} <b>{a['name']}</b> (Ур. {r['level']}) — {a['desc']}")

    await message.reply(
        f"🔮 👑 <b>ВАШИ МАГИЧЕСКИЕ АРТЕФАКТЫ ({len(lines)} шт.):</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines)
    )


# ══════════════════════════════════════════════════════════════════════
# 11. МИРОВЫЕ РЕЙД-БОССЫ 3.0 (WORLD RAID BOSSES)
# ══════════════════════════════════════════════════════════════════════

BOSS_CATALOG = {
    1: {"name": "Кибер-Левиафан", "max_hp": 10_000_000, "reward": 20_000_000, "icon": "👾"},
    2: {"name": "Теневой Владыка", "max_hp": 25_000_000, "reward": 60_000_000, "icon": "🦇"},
    3: {"name": "Древний Дракон Бездны", "max_hp": 60_000_000, "reward": 180_000_000, "icon": "🐲"}
}

ACTIVE_WORLD_BOSS: dict[str, dict] = {}   # "boss" -> boss_data

@router.message(Cmd("призвать босса", "вызвать босса",
                    section=S_GAMES, rank=2, group_only=True,
                    usage="призвать босса [1-3]",
                    desc="🐲 Призвать мирового босса в беседу (доступно от 2 ранга)"))
async def cmd_summon_boss(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 2:
        return await message.reply("⛔️ Призывать боссов могут модераторы от <b>2 ранга</b>.")

    if "current" in ACTIVE_WORLD_BOSS:
        b = ACTIVE_WORLD_BOSS["current"]
        return await message.reply(f"❌ В чате уже бушует босс: <b>{b['icon']} {b['name']}</b> (HP: {money(b['hp'])}/{money(b['max_hp'])})! Атакуйте его: <code>ударить босса</code>.")

    bid = int(args.strip()) if args.strip().isdigit() and int(args.strip()) in BOSS_CATALOG else 1
    binfo = BOSS_CATALOG[bid]

    ACTIVE_WORLD_BOSS["current"] = {
        "id": bid,
        "name": binfo["name"],
        "icon": binfo["icon"],
        "max_hp": binfo["max_hp"],
        "hp": binfo["max_hp"],
        "reward": binfo["reward"],
        "attackers": {}   # user_id -> total_dmg
    }

    await message.reply(
        f"🐲 ⚡️ <b>ПРИЗВАН МИРОВОЙ БОСС: {binfo['icon']} {binfo['name']}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❤️ Запас здоровья: <b>{money(binfo['max_hp'])} HP</b>\n"
        f"💰 Призовой фонд: <b>{money(binfo['reward'])} монет</b>\n\n"
        f"⚔️ <b>Объединяйте силы всей беседы!</b>\n"
        f"Нанесите удар командой: <code>ударить босса</code>\n"
        f"Награда разделится между всеми бойцами пропорционально урону!"
    )


@router.message(Cmd("ударить босса", "атаковать босса", "удар по боссу",
                    section=S_GAMES, rank=0, group_only=True,
                    desc="⚔️ Нанести мощный удар по мировому рейд-боссу"))
async def cmd_attack_boss(message: Message, bot: Bot, args: str = "", **kw):
    if "current" not in ACTIVE_WORLD_BOSS:
        return await message.reply("💤 В чате сейчас нет боссов. Модераторы могут призвать босса: <code>призвать босса [1-3]</code>.")

    boss = ACTIVE_WORLD_BOSS["current"]
    uid = message.from_user.id

    # Базовый урон
    base_dmg = random.randint(75_000, 250_000)
    crit = False

    # Проверяем артефакт "Печать Дракона" (id=6)
    has_dragon_art = await db.fetchone("SELECT 1 FROM moxxi_artifacts WHERE user_id=? AND artifact_id=6", (uid,))
    if has_dragon_art:
        base_dmg *= 2
        crit = True

    # 15% шанс критического удара
    if random.random() < 0.15:
        base_dmg = int(base_dmg * 2.5)
        crit = True

    boss["hp"] = max(0, boss["hp"] - base_dmg)
    boss["attackers"][uid] = boss["attackers"].get(uid, 0) + base_dmg

    crit_tag = " 💥 <b>КРИТИЧЕСКИЙ УДАР!</b>" if crit else ""

    if boss["hp"] <= 0:
        # Босс повержен!
        total_dmg = sum(boss["attackers"].values())
        reward_pool = boss["reward"]

        lines = []
        for att_id, dmg in sorted(boss["attackers"].items(), key=lambda x: x[1], reverse=True)[:5]:
            share_pct = (dmg / total_dmg) if total_dmg else 0
            user_reward = int(reward_pool * share_pct)
            await db.add_money(att_id, user_reward)
            u = await db.get_user(att_id)
            name = u["first_name"] if u else f"ID {att_id}"
            lines.append(f"• <b>{name}</b>: {money(dmg)} урона ➔ <b>+{money(user_reward)} монет</b>!")

        boss_name = boss["name"]
        boss_icon = boss["icon"]
        ACTIVE_WORLD_BOSS.pop("current", None)

        return await message.reply(
            f"🏆 🐲 <b>РЕЙД-БОСС {boss_icon} {boss_name} УСПЕШНО ПОВЕРЖЕН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Герои беседы сокрушили чудовище! Призовой фонд разделен:\n\n"
            + "\n".join(lines) + "\n\n"
            f"🎉 Поздравляем всех участников эпического рейда!"
        )

    # Прогресс-бар здоровья
    pct = max(0, min(100, int((boss["hp"] / boss["max_hp"]) * 100)))
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    await message.reply(
        f"⚔️ <b>{html.escape(message.from_user.first_name)}</b> наносит <b>-{money(base_dmg)}</b> урона!{crit_tag}\n"
        f"{boss['icon']} <b>{boss['name']}:</b> [{bar}] {pct}% ({money(boss['hp'])} HP осталось)"
    )


# ══════════════════════════════════════════════════════════════════════
# 12. БАНКОВСКИЕ ДЕПОЗИТЫ И ЗАЙМЫ (CENTRAL BANK 3.0)
# ══════════════════════════════════════════════════════════════════════

DEPOSIT_RATES = {
    1: 0.05,   # 1 день = +5%
    3: 0.18,   # 3 дня = +18%
    7: 0.50    # 7 дней = +50%
}

@router.message(Cmd("депозиты", "вклады",
                    section=S_ECON, rank=0,
                    desc="🏦 Линейка процентных депозитов Центрального Банка Moxxi"))
async def cmd_bank_deposits_list(message: Message, bot: Bot, args: str = "", **kw):
    await message.reply(
        "🏦 📈 <b>ДЕПОЗИТНЫЕ СЧЕТА MOXXI CENTRAL BANK</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Размещайте свободные монеты под высокий фиксированный процент:\n\n"
        "• <b>1 день:</b> +5% доходности (<code>вклад открыть [сумма] 1</code>)\n"
        "• <b>3 дня:</b> +18% доходности (<code>вклад открыть [сумма] 3</code>)\n"
        "• <b>7 дней:</b> +50% доходности (<code>вклад открыть [сумма] 7</code>)\n\n"
        "💡 Забрать вклад по окончании срока: <code>вклад забрать</code>"
    )


@router.message(Cmd("вклад открыть", "депозит открыть",
                    section=S_ECON, rank=0,
                    usage="вклад открыть [сумма] [1|3|7]",
                    desc="🏦 Открыть доходный депозит на 1, 3 или 7 дней"))
async def cmd_open_deposit(message: Message, bot: Bot, args: str = "", **kw):
    parts = args.strip().split()
    if len(parts) < 2:
        return await message.reply("🏦 Используйте: <code>вклад открыть [сумма] [1|3|7]</code> (например: <code>вклад открыть 100000 3</code>).")

    amount = parse_money(parts[0])
    days_str = parts[1]
    if not amount or amount < 10_000:
        return await message.reply("❌ Минимальная сумма депозита: <b>10,000</b> монет!")

    if not days_str.isdigit() or int(days_str) not in DEPOSIT_RATES:
        return await message.reply("❌ Выберите срок: <code>1</code>, <code>3</code> или <code>7</code> дней!")

    days = int(days_str)
    rate = DEPOSIT_RATES[days]
    uid = message.from_user.id

    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < amount:
        return await message.reply(f"❌ Недостаточно средств! Ваш баланс: {money(bal)} монет.")

    await db.add_money(uid, -amount)
    now = int(time.time())
    expire = now + (days * 86400)

    await db.execute(
        "INSERT INTO moxxi_deposits (user_id, amount, term_days, yield_pct, open_ts, expire_ts, claimed) VALUES (?,?,?,?,?,?,0)",
        (uid, amount, days, rate, now, expire)
    )

    profit = int(amount * rate)
    await message.reply(
        f"🏦 🔒 <b>ДЕПОЗИТ УСПЕШНО ОТКРЫТ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Сумма вклада: <b>{money(amount)}</b> монет\n"
        f"Срок: <b>{days} дн.</b> (+{int(rate*100)}% доходности)\n"
        f"💰 Ожидаемая выплата: <b>{money(amount + profit)}</b> монет (+{money(profit)} чистыми)\n"
        f"Дата выплаты: через {days} дн. (<code>вклад забрать</code>)"
    )


@router.message(Cmd("мой вклад", "вклад забрать", "депозит забрать",
                    section=S_ECON, rank=0,
                    desc="🏦 Проверить состояние вклада и забрать выплату с процентами"))
async def cmd_claim_deposit(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT * FROM moxxi_deposits WHERE user_id=? AND claimed=0 ORDER BY expire_ts ASC LIMIT 1", (uid,))
    if not row:
        return await message.reply("🏦 У вас нет активных депозитов! Открыть: <code>депозиты</code>.")

    now = int(time.time())
    expire = int(row["expire_ts"])
    amount = int(row["amount"])
    rate = float(row["yield_pct"])
    total_payout = int(amount * (1.0 + rate))

    if now < expire:
        rem_sec = expire - now
        hours = rem_sec // 3600
        mins = (rem_sec % 3600) // 60
        return await message.reply(
            f"🏦 ⏳ <b>ДЕПОЗИТ ЕЩЕ В РАБОТЕ!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Сумма вклада: <b>{money(amount)}</b> монет\n"
            f"Ожидаемый доход: <b>+{money(total_payout - amount)}</b> монет\n"
            f"Осталось ждать: <b>{hours} ч. {mins} мин.</b>"
        )

    await db.execute("UPDATE moxxi_deposits SET claimed=1 WHERE id=?", (row["id"],))
    await db.add_money(uid, total_payout)

    await message.reply(
        f"🏦 💰 <b>ВЫПЛАТА ПО ДЕПОЗИТУ ЗАЧИСЛЕНА!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Возврат тела вклада: <b>{money(amount)}</b>\n"
        f"Чистая прибыль (+{int(rate*100)}%): <b>+{money(total_payout - amount)}</b> монет\n"
        f"Итого зачислено: <b>+{money(total_payout)}</b> монет на ваш баланс!"
    )


# ══════════════════════════════════════════════════════════════════════
# 13. БОЕВОЙ ПРОПУСК «НЕОНОВЫЙ РАССВЕТ» (BATTLE PASS)
# ══════════════════════════════════════════════════════════════════════

BP_REWARDS = {
    1: {"free": 25_000, "prem": 100_000, "name": "Стартовый кейс"},
    2: {"free": 50_000, "prem": 250_000, "name": "Неоновый значок"},
    3: {"free": 100_000, "prem": 500_000, "name": "Кристаллы x10"},
    4: {"free": 150_000, "prem": 1_000_000, "name": "Титул «Неоновый Воин»"},
    5: {"free": 300_000, "prem": 2_500_000, "name": "VIP-статус на 7 дней"},
    6: {"free": 500_000, "prem": 5_000_000, "name": "Секретный лутбокс 3.0"},
    7: {"free": 1_000_000, "prem": 10_000_000, "name": "Артефакт Око Бури"},
    8: {"free": 2_000_000, "prem": 25_000_000, "name": "Платиновый сундук"},
    9: {"free": 5_000_000, "prem": 50_000_000, "name": "Золотой статус Императора"},
    10: {"free": 10_000_000, "prem": 100_000_000, "name": "Легендарный кубок Сезона 1"}
}

@router.message(Cmd("боевой пропуск", "бп", "battle pass",
                    section=S_GAMES, rank=0,
                    desc="🏆 Сезонный Боевой Пропуск: уровни, испытания и крутые награды"))
async def cmd_battle_pass(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT * FROM moxxi_battle_pass WHERE user_id=?", (uid,))
    if not row:
        await db.execute("INSERT INTO moxxi_battle_pass (user_id, points, level, has_premium, claimed_levels) VALUES (?,?,?,?,?)",
                         (uid, 50, 1, 0, "[]"))
        row = {"user_id": uid, "points": 50, "level": 1, "has_premium": 0, "claimed_levels": "[]"}

    pts = int(row["points"])
    lvl = min(10, max(1, (pts // 100) + 1))
    has_prem = bool(row["has_premium"])

    import json
    claimed = json.loads(row["claimed_levels"]) if row["claimed_levels"] else []

    status_tag = "👑 PREMIUM PASS" if has_prem else "⚪️ БЕСПЛАТНЫЙ PASS"

    lines = []
    for l, r in BP_REWARDS.items():
        state = "✅ Забран" if l in claimed else ("🎁 Доступен" if lvl >= l else "🔒 Заблокирован")
        prem_mark = f" [+{money(r['prem'])}]" if has_prem else ""
        lines.append(f"Ур. {l}: <b>{r['name']}</b> ➔ {money(r['free'])}{prem_mark} ({state})")

    await message.reply(
        f"🏆 ⚡️ <b>БОЕВОЙ ПРОПУСК: СЕЗОН 1 «НЕОНОВЫЙ РАССВЕТ»</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Статус: <b>{status_tag}</b>\n"
        f"Ваш уровень: <b>{lvl}/10</b> (Очков: {pts % 100}/100)\n\n"
        + "\n".join(lines[:6]) + "\n…\n\n"
        f"💡 Забрать открытые награды: <code>забрать бп</code>\n"
        f"Купить Premium (+x10 наград): <code>купить бп</code> (1,000,000 монет)"
    )


@router.message(Cmd("купить бп", "купить премиум бп",
                    section=S_GAMES, rank=0,
                    desc="🏆 Активировать Premium Battle Pass (+x10 к наградам сезона)"))
async def cmd_buy_premium_bp(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT * FROM moxxi_battle_pass WHERE user_id=?", (uid,))
    if row and row["has_premium"]:
        return await message.reply("❌ У вас уже активирован Premium Battle Pass!")

    cost = 1_000_000
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < cost:
        return await message.reply(f"❌ Недостаточно средств! Стоимость Premium BP: <b>{money(cost)}</b> монет.")

    await db.add_money(uid, -cost)
    await db.execute(
        "INSERT INTO moxxi_battle_pass (user_id, points, level, has_premium, claimed_levels) VALUES (?,50,1,1,'[]') "
        "ON CONFLICT(user_id) DO UPDATE SET has_premium=1",
        (uid,)
    )

    await message.reply(
        "🏆 👑 <b>PREMIUM BATTLE PASS УСПЕШНО АКТИВИРОВАН!</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Теперь на каждом уровне вы получаете увеличенные в 10 раз награды, уникальные титулы и кристаллы! 🌟"
    )


@router.message(Cmd("забрать бп", "награды бп",
                    section=S_GAMES, rank=0,
                    desc="🎁 Забрать все открытые награды уровней Боевого Пропуска"))
async def cmd_claim_bp_rewards(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    row = await db.fetchone("SELECT * FROM moxxi_battle_pass WHERE user_id=?", (uid,))
    if not row:
        return await message.reply("❌ Сначала откройте боевой пропуск командой: <code>бп</code>.")

    pts = int(row["points"])
    current_lvl = min(10, max(1, (pts // 100) + 1))
    has_prem = bool(row["has_premium"])

    import json
    claimed = set(json.loads(row["claimed_levels"]) if row["claimed_levels"] else [])

    total_reward = 0
    new_claimed = []

    for l in range(1, current_lvl + 1):
        if l not in claimed and l in BP_REWARDS:
            r = BP_REWARDS[l]
            rew = r["free"] + (r["prem"] if has_prem else 0)
            total_reward += rew
            claimed.add(l)
            new_claimed.append(l)

    if total_reward <= 0:
        return await message.reply("⏳ Нет доступных наград! Повышайте уровень БП активностью в чате.")

    await db.execute("UPDATE moxxi_battle_pass SET claimed_levels=? WHERE user_id=?",
                     (json.dumps(list(claimed)), uid))
    await db.add_money(uid, total_reward)

    await message.reply(
        f"🎁 🏆 <b>НАГРАДЫ БОЕВОГО ПРОПУСКА ПОЛУЧЕНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Забраны уровни: <b>{', '.join(map(str, new_claimed))}</b>\n"
        f"💰 Зачислено: <b>+{money(total_reward)}</b> монет на ваш баланс!"
    )


# ══════════════════════════════════════════════════════════════════════
# 14. СИСТЕМА РОСКОШНЫХ ПОДАРКОВ (LUXURY GIFTS)
# ══════════════════════════════════════════════════════════════════════

GIFTS_SHOP = {
    1: {"name": "Букет алых роз", "cost": 50_000, "icon": "🌹"},
    2: {"name": "Кольцо с сапфиром", "cost": 250_000, "icon": "💍"},
    3: {"name": "Спорткар Cyber-GT", "cost": 1_200_000, "icon": "🏎"},
    4: {"name": "Неоновый Особняк", "cost": 6_000_000, "icon": "🏰"},
    5: {"name": "Корона Монарха", "cost": 25_000_000, "icon": "👑"}
}

@router.message(Cmd("подарки магазин", "каталог подарков",
                    section=S_GAMES, rank=0,
                    desc="🎁 Магазин роскошных подарков для друзей и участников"))
async def cmd_gifts_shop(message: Message, bot: Bot, args: str = "", **kw):
    lines = []
    for gid, g in GIFTS_SHOP.items():
        lines.append(f"<b>{gid}. {g['icon']} {g['name']}</b> — {money(g['cost'])} монет")

    await message.reply(
        "🎁 ✨ <b>МАГАЗИН РОСКОШНЫХ ПОДАРКОВ MOXXI</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines) + "\n\n"
        "Отправить подарок: <code>подарить [номер] @юзер [сообщение]</code>\n"
        "Посмотреть подарки: <code>подарки @юзер</code>"
    )


@router.message(Cmd("подарить", "сделать подарок",
                    section=S_GAMES, rank=0, group_only=True,
                    usage="подарить [номер] @юзер [текст]",
                    desc="🎁 Отправить подарок другу или участнику беседы"))
async def cmd_send_gift(message: Message, bot: Bot, args: str = "", **kw):
    parts = args.strip().split(maxsplit=2)
    if not parts or not parts[0].isdigit():
        return await message.reply("🎁 Укажите: <code>подарить [номер] @юзер [сообщение]</code> (каталог: <code>подарки магазин</code>).")

    gid = int(parts[0])
    if gid not in GIFTS_SHOP:
        return await message.reply("❌ Неверный номер подарка! Выберите от 1 до 5.")

    gift = GIFTS_SHOP[gid]
    target_arg = parts[1] if len(parts) > 1 else ""
    user_msg = parts[2] if len(parts) > 2 else "От всего сердца!"

    target_uid = await resolve_target(message, bot, target_arg)
    if not target_uid:
        return await message.reply("❌ Укажите получателя подарка: ответным сообщением или @юзернеймом!")

    if target_uid == message.from_user.id:
        return await message.reply("❌ Нельзя дарить подарки самому себе!")

    uid = message.from_user.id
    u = await db.get_user(uid)
    bal = int(u["balance"])
    if bal < gift["cost"]:
        return await message.reply(f"❌ Недостаточно монет! Стоимость: <b>{money(gift['cost'])}</b> монет (ваш баланс: {money(bal)}).")

    await db.add_money(uid, -gift["cost"])
    now = int(time.time())
    await db.execute(
        "INSERT INTO moxxi_gifts (from_id, to_id, gift_id, gift_name, message, ts) VALUES (?,?,?,?,?,?)",
        (uid, target_uid, gid, gift["name"], user_msg[:100], now)
    )

    tgt_user = await db.get_user(target_uid)
    tgt_name = tgt_user["first_name"] if tgt_user else "Участник"

    await message.reply(
        f"🎁 💖 <b>ПОДАРОК УСПЕШНО ВРУЧЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"От кого: <b>{html.escape(message.from_user.first_name)}</b>\n"
        f"Кому: <b>{html.escape(tgt_name)}</b>\n"
        f"Подарок: <b>{gift['icon']} {gift['name']}</b>\n"
        f"💌 Сообщение: <i>«{html.escape(user_msg[:100])}»</i>"
    )


@router.message(Cmd("подарки", "мои подарки",
                    section=S_GAMES, rank=0,
                    desc="🎁 Посмотреть витрину подарков в профиле пользователя"))
async def cmd_view_gifts(message: Message, bot: Bot, args: str = "", **kw):
    target_uid = await resolve_target(message, bot, args) or message.from_user.id
    rows = await db.fetchall("SELECT * FROM moxxi_gifts WHERE to_id=? ORDER BY ts DESC LIMIT 10", (target_uid,))
    
    tgt_user = await db.get_user(target_uid)
    tgt_name = tgt_user["first_name"] if tgt_user else "Участник"

    if not rows:
        return await message.reply(f"🎁 У <b>{html.escape(tgt_name)}</b> пока нет подарков. Сделайте приятное: <code>подарить [1-5] @юзер</code>!")

    lines = []
    for r in rows:
        from_user = await db.get_user(r["from_id"])
        sender_name = from_user["first_name"] if from_user else "Тайный поклонник"
        gid = r["gift_id"]
        icon = GIFTS_SHOP[gid]["icon"] if gid in GIFTS_SHOP else "🎁"
        lines.append(f"{icon} <b>{r['gift_name']}</b> от <i>{html.escape(sender_name)}</i>: «{html.escape(r['message'])}»")

    await message.reply(
        f"🎁 🌟 <b>ВИТРИНА ПОДАРКОВ: {html.escape(tgt_name)}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines)
    )


# ══════════════════════════════════════════════════════════════════════
# 15. СУПЕР-ИНСТРУМЕНТЫ АДМИНИСТРАЦИИ (SLOWMODE, НЕАКТИВ, ШТРАФНИКИ)
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("медленный режим", "слоумод", "slowmode",
                    section=S_ADMIN, rank=3, group_only=True,
                    usage="медленный режим [10|30|60|300|выкл]",
                    desc="⏳ Включить официальный медленный режим Telegram в группе"))
async def cmd_slowmode(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 3:
        return await message.reply("⛔️ Команда доступна администраторам от <b>3 ранга</b>.")

    raw = args.strip().lower()
    cid = message.chat.id

    if raw in {"выкл", "0", "off", "disable"}:
        try:
            await bot.set_chat_slow_mode_delay(cid, 0)
            return await message.reply("⏳ 🟢 <b>Медленный режим выключен!</b> Участники могут писать без задержек.")
        except Exception as e:
            return await message.reply(f"❌ Ошибка настройки медленного режима: {e}")

    valid_delays = {10, 30, 60, 300, 900, 3600}
    if not raw.isdigit() or int(raw) not in valid_delays:
        return await message.reply(
            "⏳ <b>Настройка медленного режима группы:</b>\n\n"
            "Доступные задержки: <code>10</code>, <code>30</code>, <code>60</code>, <code>300</code> сек.\n"
            "Пример: <code>медленный режим 30</code> или <code>медленный режим выкл</code>."
        )

    delay = int(raw)
    try:
        await bot.set_chat_slow_mode_delay(cid, delay)
        await message.reply(
            f"⏳ 🛡 <b>МЕДЛЕННЫЙ РЕЖИМ ВКЛЮЧЕН НА {delay} СЕК!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Теперь каждый участник может отправлять одно сообщение не чаще, чем раз в <b>{delay} секунд</b>.\n"
            f"Флуд и спам-атаки остановлены! Выключить: <code>медленный режим выкл</code>."
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось изменить режим (проверьте права бота на управление чатом): {e}")


@router.message(Cmd("вайп неактива", "чистка неактива", "неактив",
                    section=S_ADMIN, rank=4, group_only=True,
                    usage="вайп неактива [дни=30]",
                    desc="🧹 Аналитический отчёт об участниках без активности в чате"))
async def cmd_inactive_wipe(message: Message, bot: Bot, args: str = "", **kw):
    me = await effective_rank(message, bot)
    if me < 4:
        return await message.reply("⛔️ Команда доступна старшим администраторам от <b>4 ранга</b>.")

    days = int(args.strip()) if args.strip().isdigit() and 1 <= int(args.strip()) <= 365 else 30
    cutoff = int(time.time()) - (days * 86400)
    cid = message.chat.id

    rows = await db.fetchall(
        "SELECT user_id, updated_at FROM chat_members WHERE chat_id=? AND updated_at < ? LIMIT 20",
        (cid, cutoff)
    )

    if not rows:
        return await message.reply(f"🧹 <b>Неактивных участников не найдено!</b>\nВсе активны за последние {days} дней.")

    lines = []
    for r in rows:
        u = await db.get_user(r["user_id"])
        name = u["first_name"] if u else f"ID {r['user_id']}"
        lines.append(f"• <b>{name}</b> (ID: <code>{r['user_id']}</code>)")

    await message.reply(
        f"🧹 📊 <b>ОТЧЕТ ПО НЕАКТИВУ (более {days} дн.):</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Обнаружено неактивных участников: <b>{len(rows)}</b> чел.\n\n"
        + "\n".join(lines[:12]) + "\n\n"
        f"💡 Администрация может удалить их из группы вручную или воспользоваться киком."
    )


@router.message(Cmd("топ нарушителей", "штрафники", "антитоп",
                    section=S_ADMIN, rank=2, group_only=True,
                    desc="📋 Топ участников с наибольшим количеством наказаний в беседе"))
async def cmd_top_violators(message: Message, bot: Bot, args: str = "", **kw):
    cid = message.chat.id
    rows = await db.fetchall(
        "SELECT user_id, COUNT(*) as cnt FROM punishments WHERE chat_id=? GROUP BY user_id ORDER BY cnt DESC LIMIT 10",
        (cid,)
    )

    if not rows:
        return await message.reply("😇 <b>В этой беседе царит идеальный порядок!</b> Нарушений не зафиксировано.")

    lines = []
    for i, r in enumerate(rows, 1):
        u = await db.get_user(r["user_id"])
        name = u["first_name"] if u else f"ID {r['user_id']}"
        lines.append(f"{i}. <b>{html.escape(name)}</b> ➔ <b>{r['cnt']}</b> нарушений")

    await message.reply(
        f"📋 🚨 <b>ТОП НАРУШИТЕЛЕЙ БЕСЕДЫ ({len(rows)} чел.)</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines)
    )


# ══════════════════════════════════════════════════════════════════════
# 16. ОФИЦИАЛЬНЫЙ СПИСОК ОБНОВЛЕНИЯ MOXXI 3.0 REVOLUTION
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("обновление 3.0", "обнова 3.0", "релиз 3.0", "обновление", "обнова", "что нового", "патчноут",
                    section=S_ADMIN, rank=0,
                    desc="🚀 Официальный манифест и полный список глобального обновления MOXXI 3.0"))
async def cmd_global_update_3_0_manifest(message: Message, bot: Bot, args: str = "", **kw):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎮 Открыть Web App 3.0", web_app={"url": config.WEBAPP_URL} if hasattr(config, "WEBAPP_URL") and config.WEBAPP_URL else None) if hasattr(config, "WEBAPP_URL") and config.WEBAPP_URL else InlineKeyboardButton(text="🎮 Игры и Казино", callback_data="nav_games"),
            InlineKeyboardButton(text="🏢 Корпорации", callback_data="nav_corp")
        ],
        [
            InlineKeyboardButton(text="🛡 Защита и Карантин", callback_data="nav_shield"),
            InlineKeyboardButton(text="🏆 Боевой Пропуск", callback_data="nav_bp")
        ]
    ])

    text = (
        "🚀 🌟 <b>ГЛОБАЛЬНОЕ ОБНОВЛЕНИЕ MOXXI 3.0 REVOLUTION!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Встречайте масштабнейший релиз в истории бота! Добавлены десятки новых механик, "
        "игры, масштабная экономика корпораций и непробиваемая защита бесед:\n\n"
        "🎮 <b>РАЗВЛЕЧЕНИЯ И КАЗИНО 3.0:</b>\n"
        "• <b>Европейская Рулетка:</b> ставки на цвет, четность, зеро и точные числа до x36! (<code>рулетка 1000 красное</code>)\n"
        "• <b>Мини-игра «Краш / Ракета»:</b> космический взлёт множителя до x35 с живой кнопкой кэшаута! (<code>ракета [ставка]</code>)\n"
        "• <b>Telegram Dice Казино:</b> <code>дартс</code>, <code>баскетбол</code>, <code>футбол</code>, <code>боулинг</code> с реальными ставками!\n"
        "• <b>Moxxi Mini App 3.0:</b> обновленный каталог с 15 предприятиями, выбором бомб в Минах и синхронизацией КД.\n\n"
        "🏢 <b>БИЗНЕС-ИМПЕРИИ И КОРПОРАЦИИ:</b>\n"
        "• <b>Мега-Корпорации:</b> основание корпораций от 500k монет (<code>создать корпорацию [название]</code>).\n"
        "• <b>6 уровней филиалов:</b> от кофейни до квантового дата-центра и космодрома (<code>купить филиал [1-6]</code>).\n"
        "• <b>Сбор и вывод казны:</b> <code>собрать прибыль</code> и <code>снять из корпорации</code>.\n\n"
        "🏙 <b>СИНДИКАТЫ И ВОЙНЫ ЗА РАЙОНЫ:</b>\n"
        "• <b>Битва за 5 районов города:</b> Центр, Казино, Доки, Финансы, Бункер (<code>синдикаты</code>).\n"
        "• <b>Ежедневная дань:</b> миллионные отчисления прямо в казну сильнейших (<code>захват района [1-5]</code>).\n\n"
        "🔮 <b>АРТЕФАКТЫ И РЕЙД-БОССЫ:</b>\n"
        "• <b>6 древних артефактов:</b> Око Бури, Щит Титана, Кристалл Изобилия, Хроно-Сфера, Венец, Печать Дракона (<code>артефакты</code>).\n"
        "• <b>Мировые рейд-боссы:</b> Кибер-Левиафан, Теневой Владыка, Дракон Бездны (<code>призвать босса</code> / <code>ударить босса</code>).\n\n"
        "🏦 <b>БАНК, ДЕПОЗИТЫ И БОЕВОЙ ПРОПУСК:</b>\n"
        "• <b>Фиксированные депозиты:</b> до +50% доходности за 7 дней (<code>депозиты</code>, <code>вклад открыть</code>).\n"
        "• <b>Боевой Пропуск Сезон 1:</b> 10 уровней с ценными наградами и Free/Premium Pass (<code>боевой пропуск</code>).\n"
        "• <b>Магазин роскошных подарков:</b> розы, спорткары, особняки с витриной в профиле (<code>подарки магазин</code>).\n\n"
        "🛡 <b>АДМИНИСТРАЦИЯ И ЗАЩИТА:</b>\n"
        "• <b>Умные подсказки ДК:</b> при нехватке прав бот выводит готовую команду разблокировки в 1 клик.\n"
        "• <b>Карантин новичков:</b> авто-ограничение ссылок и медиа при входе (<code>карантин [минуты/выкл]</code>).\n"
        "• <b>Антирейд капча:</b> обязательная кнопка подтверждения человека (<code>капча [вкл/выкл]</code>).\n"
        "• <b>Официальные объявления:</b> публикация баннеров с автозакрепом (<code>объявление [текст]</code>).\n"
        "• <b>Медленный режим:</b> официальный Slowmode от 10 до 3600 сек (<code>медленный режим [сек]</code>).\n"
        "• <b>Чистка сервисных смс:</b> удаление оповещений входов и выходов (<code>чистить сервис [кол-во]</code>).\n\n"
        "🎙 <b>МУЛЬТИМОДАЛЬНЫЙ ИИ И STT:</b>\n"
        "• <b>Мгновенная расшифровка кружочков и ГС:</b> авто-перевод видео-заметок и аудио в текст на лету!\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>MOXXI 3.0 REVOLUTION — мощь, комфорт и безопасность вашей беседы!</i>"
    )

    await message.reply(text, reply_markup=kb)
