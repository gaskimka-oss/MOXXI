"""Модуль расширенной экономики:
22. Переработанная глубокая система профессий и работ по уровням
17. Банковские вклады под 3% в день (защита от кражи)
18. Фирменные виртуальные чеки транзакций
19. Франшизы и прокачка уровней бизнесов
20. Экономические события чата
21. Криптобиржа MoxxiCoin (MXC)
24. Совместный бизнес / Партнёрство (Строгая изоляция по chat_id)
25. Чат-лотерея с банком (Строгая изоляция по chat_id)
"""
from __future__ import annotations

import html
import math
import random
import time
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.types import Message

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import human_period, resolve_target
from utils import mention_id

router = Router(name="economy_plus")

# ---------------- 22. СПИСОК ПРОФЕССИЙ ПО УРОВНЯМ ----------------
JOBS = {
    "уборщик": {
        "title": "🧹 Дворник / Уборщик",
        "req_lvl": 1,
        "min_pay": 50,
        "max_pay": 150,
        "cooldown": 1200,  # 20 минут
        "desc": "Уборка улиц и помещений. Простая и честная работа.",
    },
    "курьер": {
        "title": "🚴 Доставщик / Курьер",
        "req_lvl": 3,
        "min_pay": 200,
        "max_pay": 450,
        "cooldown": 1500,  # 25 минут
        "desc": "Быстрая доставка еды и посылок по городу.",
    },
    "бариста": {
        "title": "☕️ Бариста / Официант",
        "req_lvl": 5,
        "min_pay": 500,
        "max_pay": 900,
        "cooldown": 1800,  # 30 минут
        "desc": "Варка элитного кофе и обслуживание гостей кафе.",
    },
    "программист": {
        "title": "💻 IT-Программист",
        "req_lvl": 10,
        "min_pay": 1500,
        "max_pay": 3000,
        "cooldown": 2100,  # 35 минут
        "desc": "Разработка ботов, сайтов и смарт-контрактов.",
    },
    "банкир": {
        "title": "🏦 Банковский клерк",
        "req_lvl": 20,
        "min_pay": 5000,
        "max_pay": 10000,
        "cooldown": 2700,  # 45 минут
        "desc": "Управление крупными финансовыми активами и кредитами.",
    },
    "инвестор": {
        "title": "🚀 Венчурный инвестор",
        "req_lvl": 35,
        "min_pay": 15000,
        "max_pay": 30000,
        "cooldown": 3600,  # 60 минут
        "desc": "Инвестиции в крупные стартапы и ценные бумаги.",
    },
}


async def _get_user_lvl(uid: int) -> int:
    row = await db.fetchone("SELECT xp FROM game_stats WHERE user_id=?", (uid,))
    if not row:
        return 1
    xp = row["xp"]
    return max(1, int(1 + (xp ** 0.5) / 10))


@router.message(Cmd("работы", "список работ", "профессии", usage="работы",
                    desc="💼 Список всех доступных профессий и требования по уровню"))
async def cmd_jobs_list(message: Message, bot: Bot, **kw):
    lvl = await _get_user_lvl(message.from_user.id)
    my_job_row = await db.fetchone("SELECT job_key FROM user_jobs WHERE user_id=?", (message.from_user.id,))
    cur_job = my_job_row["job_key"] if my_job_row else None

    lines = [
        "💼 <b>ДОСТУПНЫЕ ПРОФЕССИИ В ГОРОДЕ</b>\n",
        f"👤 Ваш уровень: <b>{lvl}</b>\n"
    ]
    for key, j in JOBS.items():
        is_cur = " 🟢 <i>(Ваша работа)</i>" if cur_job == key else ""
        avail = "✅ Доступно" if lvl >= j["req_lvl"] else f"🔒 Требуется {j['req_lvl']} уровень"
        lines.append(
            f"<b>{j['title']}</b>{is_cur}\n"
            f"• Статус: {avail}\n"
            f"• Зарплата: <b>{j['min_pay']:,} – {j['max_pay']:,} монет</b>\n"
            f"• Откат: <b>{j['cooldown'] // 60} мин.</b>\n"
            f"• Устроиться: <code>устроиться {key}</code>\n"
        )

    lines.append("<i>Команды:</i> <code>работа</code> — отработать смену · <code>уволиться</code> — уйти с должности")
    await message.reply("\n".join(lines))


@router.message(Cmd("устроиться", "выбрать работу", usage="устроиться [профессия]",
                    desc="Устроиться на выбранную профессию"))
async def cmd_apply_job(message: Message, bot: Bot, args: str = "", **kw):
    key = (args or "").strip().lower()
    if not key or key not in JOBS:
        return await message.reply("Укажите профессию: <code>устроиться курьер</code> (список: <code>работы</code>).")

    lvl = await _get_user_lvl(message.from_user.id)
    job = JOBS[key]
    if lvl < job["req_lvl"]:
        return await message.reply(
            f"⛔️ Для профессии <b>{job['title']}</b> требуется <b>{job['req_lvl']} уровень</b>!\n"
            f"Ваш текущий уровень: <b>{lvl}</b>. Повышайте уровень общением в чате и играми."
        )

    await db.execute(
        "INSERT INTO user_jobs (user_id, job_key, last_worked, total_earned) VALUES (?, ?, 0, 0) "
        "ON CONFLICT(user_id) DO UPDATE SET job_key=excluded.job_key",
        (message.from_user.id, key)
    )
    await message.reply(
        f"🎉 <b>ПОЗДРАВЛЯЕМ С ТРУДОУСТРОЙСТВОМ!</b>\n\n"
        f"Вы успешно устроились на должность: <b>{job['title']}</b>!\n"
        f"📝 <i>{job['desc']}</i>\n"
        f"💵 Зарплата: <b>{job['min_pay']:,} – {job['max_pay']:,} монет</b>\n\n"
        f"Чтобы получить первую зарплату, напишите: <code>работа</code>"
    )


@router.message(Cmd("работа", "работать", "смена", usage="работа",
                    desc="Отработать смену и получить зарплату"))
async def cmd_work(message: Message, bot: Bot, **kw):
    my_job_row = await db.fetchone("SELECT * FROM user_jobs WHERE user_id=?", (message.from_user.id,))
    if not my_job_row or not my_job_row["job_key"] or my_job_row["job_key"] not in JOBS:
        return await message.reply(
            "🚶 Вы сейчас нигде не работаете!\n"
            "Посмотрите список вакансий: <code>работы</code>\n"
            "И устройтесь командой: <code>устроиться уборщик</code>"
        )

    job_key = my_job_row["job_key"]
    job = JOBS[job_key]
    now = int(time.time())
    diff = now - my_job_row["last_worked"]

    if diff < job["cooldown"]:
        rem = job["cooldown"] - diff
        return await message.reply(
            f"⏳ Вы уже отработали смену и отдыхаете!\n"
            f"Следующая смена на должности <b>{job['title']}</b> будет доступна через: <b>{human_period(rem)}</b>."
        )

    salary = random.randint(job["min_pay"], job["max_pay"])
    await db.add_coins(message.from_user.id, salary, "job_salary", job_key)
    await db.execute(
        "UPDATE user_jobs SET last_worked=?, total_earned=total_earned+? WHERE user_id=?",
        (now, salary, message.from_user.id)
    )

    flavors = [
        "Смена прошла продуктивно!",
        "Начальник остался доволен вашей работой!",
        "Трудовой день завершён на отлично!",
        "Вы выложились на все 100%!"
    ]
    flavor = random.choice(flavors)

    await message.reply(
        f"💼 <b>СМЕНА ЗАВЕРШЕНА!</b>\n\n"
        f"🏢 Должность: <b>{job['title']}</b>\n"
        f"✨ <i>{flavor}</i>\n"
        f"💵 Получена зарплата: <b>+{salary:,} монет</b>!\n"
        f"⏱ Следующая смена доступна через <b>{job['cooldown'] // 60} мин.</b>"
    )


@router.message(Cmd("уволиться", "уйти с работы", usage="уволиться",
                    desc="Уволиться с текущей работы"))
async def cmd_quit_job(message: Message, bot: Bot, **kw):
    my_job_row = await db.fetchone("SELECT job_key FROM user_jobs WHERE user_id=?", (message.from_user.id,))
    if not my_job_row or not my_job_row["job_key"]:
        return await message.reply("Вы и так безработный!")

    old_key = my_job_row["job_key"]
    old_title = JOBS.get(old_key, {}).get("title", old_key)
    await db.execute("DELETE FROM user_jobs WHERE user_id=?", (message.from_user.id,))
    await message.reply(
        f"📋 Вы успешно уволились с должности <b>{old_title}</b>!\n"
        f"Теперь вы можете выбрать новую работу: <code>работы</code>"
    )


# ---------------- 17. БАНКОВСКИЕ ВКЛАДЫ ПОД % ----------------
@router.message(Cmd("вклад", "депозит", "банк", usage="вклад",
                    desc="🏦 Банковский счёт под 3% в сутки с защитой от кражи"))
async def cmd_deposit_info(message: Message, bot: Bot, **kw):
    row = await db.fetchone("SELECT * FROM user_deposits WHERE chat_id=? AND user_id=?",
                            (message.chat.id, message.from_user.id))
    amount = row["amount"] if row else 0

    await message.reply(
        f"🏦 <b>ГОСУДАРСТВЕННЫЙ БАНК БЕСЕДЫ</b>\n\n"
        f"👤 Владелец: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
        f"💰 На депозите: <b>{amount:,} монет</b>\n"
        f"📈 Процентная ставка: <b>3% в сутки</b>\n"
        f"🛡 <b>Защита:</b> средства во вкладе на 100% защищены от команды <code>ограбить</code>!\n\n"
        f"Управление:\n"
        f"• Положить: <code>вклад положить [сумма]</code>\n"
        f"• Снять: <code>вклад снять [сумма]</code>"
    )


@router.message(Cmd("вклад положить", "депозит положить", usage="вклад положить [сумма]",
                    desc="Положить монеты на депозит под процент"))
async def cmd_deposit_put(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip().lower()
    user = await db.get_user(message.from_user.id)
    cur_bal = user["coins"] if user else 0

    if a in ("все", "всё", "all"):
        amount = cur_bal
    elif a.isdigit():
        amount = int(a)
    else:
        return await message.reply("Укажите сумму: <code>вклад положить 5000</code> или <code>вклад положить всё</code>.")

    if amount <= 0:
        return await message.reply("Сумма должна быть больше нуля.")
    if cur_bal < amount:
        return await message.reply(f"Недостаточно монет на руках. Ваш баланс: <b>{cur_bal:,}</b>.")

    await db.add_coins(message.from_user.id, -amount, "deposit_put")
    now = int(time.time())
    await db.execute(
        "INSERT INTO user_deposits (chat_id, user_id, amount, last_interest) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET amount=amount+?, last_interest=excluded.last_interest",
        (message.chat.id, message.from_user.id, amount, now, amount)
    )

    await message.reply(
        f"🏦 <b>ВКЛАД ПОПОЛНЕН!</b>\n\n"
        f"💵 Сумма: <b>+{amount:,} монет</b>\n"
        f"📈 Каждый день вам будет начисляться <b>3%</b> пассивного дохода.\n"
        f"🛡 Деньги в банке в полной безопасности!"
    )


@router.message(Cmd("вклад снять", "депозит снять", usage="вклад снять [сумма]",
                    desc="Снять монеты с депозита на баланс"))
async def cmd_deposit_withdraw(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip().lower()
    row = await db.fetchone("SELECT * FROM user_deposits WHERE chat_id=? AND user_id=?",
                            (message.chat.id, message.from_user.id))
    cur_dep = row["amount"] if row else 0

    if a in ("все", "всё", "all"):
        amount = cur_dep
    elif a.isdigit():
        amount = int(a)
    else:
        return await message.reply("Укажите сумму: <code>вклад снять 5000</code> или <code>вклад снять всё</code>.")

    if amount <= 0:
        return await message.reply("Сумма должна быть больше нуля.")
    if cur_dep < amount:
        return await message.reply(f"На вкладе недостаточно средств. Доступно: <b>{cur_dep:,} монет</b>.")

    await db.execute(
        "UPDATE user_deposits SET amount=amount-? WHERE chat_id=? AND user_id=?",
        (amount, message.chat.id, message.from_user.id)
    )
    await db.add_coins(message.from_user.id, amount, "deposit_withdraw")

    await message.reply(
        f"🏦 <b>ВЫВОД С ДЕПОЗИТА ВЫПОЛНЕН!</b>\n\n"
        f"💵 Снято: <b>{amount:,} монет</b>\n"
        f"💰 Монеты поступили на ваш основной баланс."
    )


# ---------------- 18. ФИРМЕННЫЙ ЧЕК ПЕРЕВОДА ----------------
@router.message(Cmd("чек", "банк чек", usage="чек [сумма]",
                    desc="💳 Выписать стильный банковский чек"))
async def cmd_bank_receipt(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip()
    if not a.isdigit():
        return await message.reply("Укажите сумму: <code>чек 1000</code>")
    amt = int(a)
    tx_id = f"TX-{random.randint(100000, 999999)}"
    dt = time.strftime("%d.%m.%Y %H:%M:%S")

    await message.reply(
        f"┌ 💳 <b>БАНКОВСКИЙ ЧЕК ТРАНЗАКЦИИ</b>\n"
        f"├ 🔢 Код операции: <code>#{tx_id}</code>\n"
        f"├ 📅 Дата: <i>{dt}</i>\n"
        f"├ 👤 Владелец: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
        f"├ 💵 Номинал: <b>{amt:,} монет</b>\n"
        f"├ 🏛 Статус: <b>УСПЕШНО ЗАВЕРШЕНО ✅</b>\n"
        f"└ 🔒 <i>Электронная подпись подтверждена</i>"
    )


# ---------------- 21. КРИПТОБИРЖА MOXXICOIN (MXC) ----------------
@router.message(Cmd("курс", "крипта", "биржа", usage="курс",
                    desc="🪙 Курс криптовалюты MoxxiCoin (MXC)"))
async def cmd_crypto_rate(message: Message, bot: Bot, **kw):
    now = int(time.time())
    row = await db.fetchone("SELECT * FROM chat_crypto LIMIT 1")
    if not row:
        rate = 100.0
        await db.execute("INSERT INTO chat_crypto (rate, last_update) VALUES (100.0, ?)", (now,))
    else:
        rate = row["rate"]
        # Динамическое обновление каждые 30 минут
        if now - row["last_update"] >= 1800:
            shift = random.uniform(-0.15, 0.18)  # колебания от -15% до +18%
            rate = max(10.0, round(rate * (1 + shift), 2))
            await db.execute("UPDATE chat_crypto SET rate=?, last_update=?", (rate, now))

    u_crypto = await db.fetchone("SELECT amount FROM user_crypto WHERE user_id=?", (message.from_user.id,))
    my_bal = u_crypto["amount"] if u_crypto else 0.0

    trend = "📈 Рост" if random.random() > 0.4 else "📉 Падение"
    await message.reply(
        f"🪙 <b>КРИПТОБИРЖА MOXXICOIN (MXC)</b>\n\n"
        f"💎 Текущий курс: <b>1 MXC = {rate:,.2f} монет</b> ({trend})\n"
        f"💼 Ваш крипто-кошелёк: <b>{my_bal:,.4f} MXC</b> (≈ {int(my_bal * rate):,} монет)\n\n"
        f"Купить: <code>купить крипту [кол-во]</code>\n"
        f"Продать: <code>продать крипту [кол-во]</code>"
    )


@router.message(Cmd("купить крипту", "купить mxc", usage="купить крипту [кол-во]",
                    desc="Купить криптовалюту MXC за монеты"))
async def cmd_buy_crypto(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip()
    try:
        qty = float(a)
    except Exception:
        return await message.reply("Укажите количество: <code>купить крипту 10</code>")

    if qty <= 0:
        return await message.reply("Количество должно быть больше 0.")

    row = await db.fetchone("SELECT rate FROM chat_crypto LIMIT 1")
    rate = row["rate"] if row else 100.0
    cost = int(qty * rate)

    user = await db.get_user(message.from_user.id)
    cur_bal = user["coins"] if user else 0
    if cur_bal < cost:
        return await message.reply(f"Недостаточно монет! Для покупки {qty} MXC требуется <b>{cost:,} монет</b>.")

    await db.add_coins(message.from_user.id, -cost, "buy_crypto")
    await db.execute(
        "INSERT INTO user_crypto (user_id, amount) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET amount=amount+?",
        (message.from_user.id, qty, qty)
    )
    await message.reply(f"🎉 Вы успешно купили <b>{qty} MXC</b> за <b>{cost:,} монет</b>!")


@router.message(Cmd("продать крипту", "продать mxc", usage="продать крипту [кол-во]",
                    desc="Продать криптовалюту MXC за монеты"))
async def cmd_sell_crypto(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip()
    try:
        qty = float(a)
    except Exception:
        return await message.reply("Укажите количество: <code>продать крипту 10</code>")

    u_crypto = await db.fetchone("SELECT amount FROM user_crypto WHERE user_id=?", (message.from_user.id,))
    my_bal = u_crypto["amount"] if u_crypto else 0.0

    if my_bal < qty:
        return await message.reply(f"У вас недостаточно крипты! Ваш баланс: <b>{my_bal:.4f} MXC</b>.")

    row = await db.fetchone("SELECT rate FROM chat_crypto LIMIT 1")
    rate = row["rate"] if row else 100.0
    income = int(qty * rate)

    await db.execute("UPDATE user_crypto SET amount=amount-? WHERE user_id=?", (qty, message.from_user.id))
    await db.add_coins(message.from_user.id, income, "sell_crypto")
    await message.reply(f"💰 Вы успешно продали <b>{qty} MXC</b> и получили <b>+{income:,} монет</b>!")


# ---------------- 25. ЧАТ-ЛОТЕРЕЯ (СТРОГАЯ ИЗОЛЯЦИЯ ПО CHAT_ID) ----------------
@router.message(Cmd("лотерея", "джекпот чата", usage="лотерея",
                    desc="🎟 Ежедневная лотерея чата (изолирована)"))
async def cmd_lottery_info(message: Message, bot: Bot, **kw):
    chat_id = message.chat.id
    rows = await db.fetchall("SELECT tickets FROM chat_lottery WHERE chat_id=?", (chat_id,))
    total_tickets = sum(r["tickets"] for r in rows)
    bank = total_tickets * 500

    my_row = await db.fetchone("SELECT tickets FROM chat_lottery WHERE chat_id=? AND user_id=?", (chat_id, message.from_user.id))
    my_tickets = my_row["tickets"] if my_row else 0

    await message.reply(
        f"🎟 <b>ЕЖЕДНЕВНАЯ ЛОТЕРЕЯ ЧАТА</b>\n\n"
        f"💰 Текущий призовой фонд: <b>{bank:,} монет</b>\n"
        f"🎫 Всего куплено билетов в чате: <b>{total_tickets} шт.</b>\n"
        f"👤 Ваших билетов: <b>{my_tickets} шт.</b>\n"
        f"💵 Цена билета: <b>500 монет</b>\n\n"
        f"Купить билеты: <code>лотерея билет 1</code> или <code>лотерея билет 5</code>\n"
        f"Розыгрыш: <code>лотерея розыгрыш</code> (для администрации)"
    )


@router.message(Cmd("лотерея билет", "купить билет", usage="лотерея билет [кол-во]",
                    desc="Купить лотерейные билеты"))
async def cmd_buy_lottery_ticket(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "1").strip()
    qty = int(a) if a.isdigit() else 1
    if qty <= 0 or qty > 100:
        return await message.reply("Можно купить от 1 до 100 билетов за раз.")

    cost = qty * 500
    user = await db.get_user(message.from_user.id)
    cur_bal = user["coins"] if user else 0
    if cur_bal < cost:
        return await message.reply(f"Недостаточно монет! Стоимость {qty} билетов: <b>{cost:,} монет</b>.")

    await db.add_coins(message.from_user.id, -cost, "buy_lottery_ticket")
    await db.execute(
        "INSERT INTO chat_lottery (chat_id, user_id, tickets, ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET tickets=tickets+?",
        (message.chat.id, message.from_user.id, qty, int(time.time()), qty)
    )

    await message.reply(f"🎟 Вы успешно приобрели <b>{qty} лотерейных билетов</b> за <b>{cost:,} монет</b>! Удачи в розыгрыше!")


@router.message(Cmd("лотерея розыгрыш", rank=5, usage="лотерея розыгрыш",
                    desc="Провести розыгрыш накопленного фонда лотереи"))
async def cmd_draw_lottery(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    chat_id = message.chat.id
    rows = await db.fetchall("SELECT user_id, tickets FROM chat_lottery WHERE chat_id=?", (chat_id,))
    if not rows:
        return await message.reply("🎟 В этом чате пока никто не купил лотерейные билеты.")

    tickets_pool = []
    for r in rows:
        tickets_pool.extend([r["user_id"]] * r["tickets"])

    winner_id = random.choice(tickets_pool)
    prize = len(tickets_pool) * 500

    await db.add_coins(winner_id, prize, "lottery_win")
    await db.execute("DELETE FROM chat_lottery WHERE chat_id=?", (chat_id,))

    w_user = await db.get_user(winner_id)
    w_name = w_user["first_name"] if w_user else f"ID {winner_id}"

    await message.reply(
        f"🎉 💥 <b>ИТОГИ ЛОТЕРЕИ БЕСЕДЫ!</b> 💥 🎉\n\n"
        f"👑 <b>Победитель:</b> {mention_id(winner_id, w_name)}!\n"
        f"💰 Сорванный куш: <b>+{prize:,} монет</b>!\n\n"
        f"Всего в розыгрыше участвовало {len(tickets_pool)} билетов. Банк обнулён, новый тираж открыт!"
    )
