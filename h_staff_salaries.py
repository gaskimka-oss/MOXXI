"""Модуль реальных зарплат администрации чата от Владельца.
Владелец группы настраивает зарплатную сетку рангов (+зп ранг интервал сумма валюта).
При получении админом ЗП средства списываются с ЛИЧНОГО баланса ВЛАДЕЛЬЦА беседы,
а бот удерживает фиксированную комиссию 3% с владельца.
"""
from __future__ import annotations

import html
import re
import time
from typing import Optional

from aiogram import Bot, Router
from aiogram.types import Message

import db
from core_ranks import effective_rank, rank_name, require
from core_registry import Cmd
from utils import mention, mention_id, money, parse_amount

router = Router(name="staff_salaries")
S = 6  # Раздел: Настройки чата / Управление персоналом

COMMISSION_RATE = 0.03  # 3% комиссия бота с владельца


def parse_salary_interval(text: str) -> Optional[int]:
    """Парсит интервал выплаты: 10м, 1ч, 12ч, 1д, 7д."""
    if not text:
        return None
    raw = text.strip().lower()
    m = re.match(r"^(\d+)\s*(м|мин|минут[ыа]?|m|min)$", raw)
    if m:
        return int(m.group(1)) * 60
    m = re.match(r"^(\d+)\s*(ч|час|часа|часов|h|hr)$", raw)
    if m:
        return int(m.group(1)) * 3600
    m = re.match(r"^(\d+)\s*(д|день|дня|дней|d|day|days)$", raw)
    if m:
        return int(m.group(1)) * 86400
    if raw.isdigit():
        val = int(raw)
        return val if val >= 60 else 60
    return None


def format_interval(seconds: int) -> str:
    """Форматирует секунды в читаемый вид."""
    if seconds < 3600:
        return f"{seconds // 60} мин."
    if seconds < 86400:
        return f"{seconds // 3600} ч."
    days = seconds // 86400
    return f"{days} дн."


def currency_title(cur: str, amount: int) -> str:
    """Форматирует сумму с валютой."""
    if cur == "grams":
        return f"{amount:,} г. монет".replace(",", " ")
    if cur == "snowflakes":
        return f"{amount:,} ❄️ Снежинок".replace(",", " ")
    return money(amount)


async def find_chat_owner(bot: Bot, chat_id: int) -> tuple[int, str]:
    """Ищет ID и имя создателя/владельца беседы (ранг 7 или creator в Telegram)."""
    # 1. Поиск в таблице ranks по рангу 7 (Владелец)
    row = await db.fetchone(
        "SELECT user_id FROM ranks WHERE chat_id = ? AND rank >= 7 ORDER BY rank DESC LIMIT 1",
        (chat_id,)
    )
    if row:
        u = await db.get_user(row["user_id"])
        return row["user_id"], u.get("first_name", "Владелец")

    # 2. Поиск через администраторов Telegram
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.status == "creator" and a.user and not a.user.is_bot:
                return a.user.id, a.user.first_name
    except Exception:
        pass
    return 0, ""


# ════════════════════════════ КОМАНДЫ ════════════════════════════

@router.message(Cmd("+зп", "+зарплата", "установить зп", section=S, group_only=True,
                    usage="+зп [ранг 1-6] [интервал: 1д/12ч/1ч] [сумма] [монеты/грамм/снежинки]",
                    desc="Настроить зарплату рангу от баланса владельца"))
async def cmd_set_salary(message: Message, bot: Bot, args: str = "", **kw):
    # Команда доступна только создателю/владельцу чата (ранг 7)
    my_rank = await effective_rank(message, bot)
    if my_rank < 7:
        return await message.reply("👑 <b>Эта команда доступна только Владельцу беседы (ранг 7)!</b>")

    parts = (args or "").strip().split()
    if len(parts) < 3:
        return await message.reply(
            "📋 <b>Формат настройки зарплаты:</b>\n"
            "<code>+зп [ранг 1-6] [время] [сумма] [валюта]</code>\n\n"
            "💡 <b>Примеры:</b>\n"
            "• <code>+зп 2 1д 50000 монеты</code> — Младший модер получает 50к раз в день\n"
            "• <code>+зп 3 12ч 100000 монеты</code> — Старший модер получает 100к каждые 12ч\n"
            "• <code>+зп 1 1ч 500 грамм</code> — Стажёр получает 500 грамм каждый час\n"
            "• <code>+зп 4 1д 25 снежинки</code> — Главный модер получает 25 ❄️ раз в день\n\n"
            "⚠️ <i>Зарплата списывается с вашего личного баланса при каждом взятии админом (+3% комиссии бота).</i>"
        )

    # 1. Ранг
    rank_str = parts[0]
    if not rank_str.isdigit() or not (1 <= int(rank_str) <= 6):
        return await message.reply("⚠️ Укажите ранг от <b>1</b> до <b>6</b> (1=Стажёр, 2=Мл.модер, 3=Ст.модер, 4=Гл.модер, 5=Мл.админ, 6=Ст.админ).")
    target_rank = int(rank_str)

    # 2. Интервал
    interval_str = parts[1]
    parsed_sec = parse_salary_interval(interval_str)
    if not parsed_sec:
        return await message.reply("⚠️ Неверный интервал времени! Примеры: <code>10м</code>, <code>1ч</code>, <code>6ч</code>, <code>12ч</code>, <code>1д</code>.")

    # 3. Сумма
    amount = parse_amount(parts[2])
    if amount <= 0:
        return await message.reply("⚠️ Сумма зарплаты должна быть больше нуля.")

    # 4. Валюта
    currency = "coins"
    if len(parts) >= 4:
        c_raw = parts[3].lower()
        if any(w in c_raw for w in ("грамм", "gram", "г")):
            currency = "grams"
        elif any(w in c_raw for w in ("снеж", "flake", "❄")):
            currency = "snowflakes"

    await db.set_staff_salary(message.chat.id, target_rank, amount, currency, parsed_sec)

    r_name = rank_name(target_rank)
    fee_preview = max(1, int(amount * COMMISSION_RATE))
    total_owner = amount + fee_preview

    await message.reply(
        f"✅ <b>Зарплата для ранга «{r_name}» успешно настроена!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👮 <b>Должность:</b> Ранг {target_rank} — {r_name}\n"
        f"💰 <b>Выплата админу:</b> <b>{currency_title(currency, amount)}</b>\n"
        f"⏱ <b>Интервал:</b> каждые <b>{format_interval(parsed_sec)}</b>\n"
        f"🏦 <b>Списание с вашего баланса:</b> <b>{currency_title(currency, total_owner)}</b> (включая 3% комиссии бота: {currency_title(currency, fee_preview)})\n\n"
        f"<i>Посмотреть всю сетку: <code>зарплаты</code></i>\n"
        f"<i>Удалить ставку: <code>-зп {target_rank}</code></i>"
    )


@router.message(Cmd("-зп", "-зарплата", "удалить зп", section=S, group_only=True,
                    usage="-зп [ранг 1-6]", desc="Удалить зарплату ранга"))
async def cmd_del_salary(message: Message, bot: Bot, args: str = "", **kw):
    my_rank = await effective_rank(message, bot)
    if my_rank < 7:
        return await message.reply("👑 <b>Эта команда доступна только Владельцу беседы (ранг 7)!</b>")

    r_str = (args or "").strip()
    if not r_str.isdigit():
        return await message.reply("⚠️ Укажите номер ранга для удаления: <code>-зп 2</code>")
    target_rank = int(r_str)

    ok = await db.remove_staff_salary(message.chat.id, target_rank)
    if ok:
        await message.reply(f"🗑 Зарплата для ранга {target_rank} ({rank_name(target_rank)}) удалена.")
    else:
        await message.reply(f"ℹ️ Для ранга {target_rank} зарплата не была установлена.")


@router.message(Cmd("зарплаты", "зп сетка", "зп список", "ставки зп", section=S, group_only=True,
                    usage="зарплаты", desc="Зарплатная ведомость беседы"))
async def cmd_salary_list(message: Message, bot: Bot, **kw):
    salaries = await db.get_chat_salaries(message.chat.id)
    owner_id, owner_name = await find_chat_owner(bot, message.chat.id)

    owner_mention = mention_id(owner_id, owner_name) if owner_id else "Не назначен"

    if not salaries:
        return await message.reply(
            f"💼 <b>Зарплатная ведомость беседы</b>\n"
            f"👑 <b>Спонсор выплат (Владелец):</b> {owner_mention}\n\n"
            f"<i>Зарплаты пока не настроены.</i>\n"
            f"Владелец может задать зарплату: <code>+зп 2 1д 50000 монеты</code>"
        )

    lines = []
    for s in salaries:
        r = s["rank"]
        r_n = rank_name(r)
        cur = s["currency"]
        amt = s["amount"]
        inter = format_interval(s["interval_seconds"])
        lines.append(f"• <b>Ранг {r} ({r_n}):</b> {currency_title(cur, amt)} / каждые {inter}")

    await message.reply(
        f"💼 <b>Зарплатная ведомость беседы</b>\n"
        f"👑 <b>Спонсор выплат:</b> {owner_mention}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        + "\n".join(lines) + "\n\n"
        f"💡 <i>Администраторы могут получить зарплату по кнопке или команде <code>зп</code>.</i>\n"
        f"<i>При каждой выплате бот удерживает 3% комиссии со счета спонсора.</i>"
    )


@router.message(Cmd("зп", "получить зп", "забрать зп", "моя зп", section=S, group_only=True,
                    usage="зп", desc="Получить зарплату администратора"))
async def cmd_claim_salary(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    my_rank = await effective_rank(message, bot)

    if my_rank < 1:
        return await message.reply("👮 <b>Зарплата доступна только модераторам и администраторам беседы (ранг 1+)!</b>")
    if my_rank >= 7:
        return await message.reply("👑 Вы являетесь Владельцем беседы и сами спонсируете зарплаты своей команде!")

    # Ищем ставку для ранга
    salary_rule = await db.get_staff_salary(message.chat.id, my_rank)
    if not salary_rule:
        return await message.reply(
            f"ℹ️ Для вашего ранга (<b>Ранг {my_rank} — {rank_name(my_rank)}</b>) зарплата в этой беседе ещё не назначена.\n"
            f"Попросите владельца установить её: <code>+зп {my_rank} 1д 50000</code>"
        )

    amount = salary_rule["amount"]
    currency = salary_rule["currency"]
    interval = salary_rule["interval_seconds"]

    # Проверка кулдауна
    claim_info = await db.get_staff_salary_claim(message.chat.id, uid)
    now = int(time.time())
    if claim_info:
        elapsed = now - claim_info["last_claim_ts"]
        if elapsed < interval:
            left_sec = interval - elapsed
            left_str = format_interval(left_sec) if left_sec >= 60 else f"{left_sec} сек."
            return await message.reply(
                f"⏳ <b>Вы уже получали зарплату недавно!</b>\n\n"
                f"Следующая выплата будет доступна через: <b>{left_str}</b>."
            )

    # Ищем Владельца беседы
    owner_id, owner_name = await find_chat_owner(bot, message.chat.id)
    if not owner_id:
        return await message.reply("⚠️ Не удалось определить создателя беседы для списания зарплаты.")

    owner_user = await db.get_user(owner_id)
    fee = max(1, int(amount * COMMISSION_RATE))
    total_deduct = amount + fee

    # Проверяем баланс Владельца
    if currency == "coins":
        owner_bal = owner_user.get("balance", 0) or 0
        if owner_bal < total_deduct:
            return await message.reply(
                f"⚠️ <b>В казне владельца беседы недостаточно средств для выплаты!</b>\n\n"
                f"👑 Владелец: {mention_id(owner_id, owner_name)}\n"
                f"Требуется: <b>{money(total_deduct)}</b> (включая 3% комиссии)\n"
                f"На балансе владельца: <b>{money(owner_bal)}</b>.\n\n"
                f"<i>Владельцу необходимо пополнить личный баланс для возобновления выплат.</i>"
            )
        # Списываем у владельца сумму + 3% комиссии
        await db.add_balance(owner_id, -total_deduct, "staff_salary_paid")
        # Начисляем админу чистую сумму
        await db.add_balance(uid, amount, "staff_salary_received")

    elif currency == "grams":
        from h_grams import get_grams, add_grams
        owner_grams = await get_grams(owner_id)
        if owner_grams < total_deduct:
            return await message.reply(
                f"⚠️ <b>У владельца беседы недостаточно грамм монет для выплаты!</b>\n"
                f"Нужно: {total_deduct} г., у владельца: {owner_grams} г."
            )
        await add_grams(owner_id, -total_deduct)
        await add_grams(uid, amount)

    elif currency == "snowflakes":
        owner_flakes = owner_user.get("snowflakes", 0) or 0
        if owner_flakes < total_deduct:
            return await message.reply(
                f"⚠️ <b>У владельца беседы недостаточно ❄️ Снежинок для выплаты!</b>\n"
                f"Нужно: {total_deduct} ❄️, у владельца: {owner_flakes} ❄️."
            )
        await db.add_user_snowflakes(owner_id, -total_deduct)
        await db.add_user_snowflakes(uid, amount)

    # Фиксируем выплату
    await db.record_staff_salary_claim(message.chat.id, uid, amount)

    # Чек об успешной выплате
    await message.reply(
        f"💵 <b>ЗАРПЛАТА АДМИНИСТРАТОРА ВЫПЛАЧЕНА!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👮 <b>Сотрудник:</b> {mention(message.from_user)} (Ранг {my_rank} — {rank_name(my_rank)})\n"
        f"💰 <b>Получено на руки:</b> <b>+{currency_title(currency, amount)}</b>\n"
        f"👑 <b>Спонсор выплаты:</b> {mention_id(owner_id, owner_name)}\n"
        f"📉 <b>Списано у спонсора:</b> <b>{currency_title(currency, total_deduct)}</b>\n"
        f"🏦 <b>Комиссия системы (3%):</b> {currency_title(currency, fee)}\n\n"
        f"⏳ <i>Следующая выплата через: {format_interval(interval)}</i>"
    )

    # Уведомление владельцу в ЛС бота (если открыт диалог)
    try:
        await bot.send_message(
            owner_id,
            f"💼 <b>Выплата зарплаты в беседе «{message.chat.title}»:</b>\n"
            f"Сотрудник: <b>{message.from_user.first_name}</b> (Ранг {my_rank})\n"
            f"С вашего баланса списано: <b>{currency_title(currency, total_deduct)}</b> (включая 3% комиссии)."
        )
    except Exception:
        pass
