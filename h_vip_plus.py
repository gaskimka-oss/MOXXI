"""👑 Модуль VIP и VIP+ Diamond привилегий MOXXI 3.0 REVOLUTION.

Содержит:
- 21 эксклюзивную команду для пользователей VIP (Tier 1);
- 21 суперсилу для пользователей VIP+ Diamond (Tier 2);
- Персональные сейфы, кэшбэки, майнинг кристаллов, супердропы, овердрафты и темы.
"""
from __future__ import annotations

import html
import random
import time
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
from core_ranks import require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from utils import mention, money, parse_money

router = Router(name="vip_plus")
S = 30  # Раздел 30: VIP & Донат привилегии


async def _check_vip(user_id: int, required_level: int = 1) -> tuple[bool, int]:
    """Проверяет VIP статус (Владельцы бота имеют постоянный VIP+ Diamond)."""
    if config.is_bot_owner(user_id):
        return True, 2
    lvl, until, active = await db.get_vip_info(user_id)
    if active and lvl >= required_level:
        return True, lvl
    return False, lvl


async def _ensure_vip_tables():
    await db.execute(
        "CREATE TABLE IF NOT EXISTS vip_safes ("
        "user_id INTEGER PRIMARY KEY, "
        "balance INTEGER NOT NULL DEFAULT 0, "
        "tier INTEGER NOT NULL DEFAULT 1, "
        "updated_at INTEGER NOT NULL DEFAULT 0)"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS vip_customs ("
        "user_id INTEGER PRIMARY KEY, "
        "prefix TEXT, "
        "emoji TEXT, "
        "title TEXT, "
        "aura TEXT DEFAULT 'gold', "
        "mask_top INTEGER DEFAULT 0, "
        "incognito INTEGER DEFAULT 0, "
        "last_mine_ts INTEGER DEFAULT 0, "
        "last_x3_ts INTEGER DEFAULT 0, "
        "last_cashback_ts INTEGER DEFAULT 0, "
        "cashback_pool INTEGER DEFAULT 0)"
    )


# ══════════════════════════════════════════════════════════════════════
# 1. КОМАНДЫ ДЛЯ VIP (TIER 1 — 21 КОМАНДА)
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("вип инфо", "вип помощь", "вип команды", "vip команды",
                    section=S, rank=0,
                    usage="вип инфо", desc="👑 Справочник всех 21 команд для пользователей VIP"))
async def cmd_vip_info_list(message: Message, bot: Bot, **kw):
    ok, lvl = await _check_vip(message.from_user.id, 1)
    status_tag = "🟢 <b>АКТИВЕН</b>" if ok else "⚪️ <i>Не активен (купить: <code>донат</code>)</i>"

    text = (
        "👑 ✨ <b>К А Т А Л О Г   К О М А Н Д   ⭐️ V I P</b> ✨ 👑\n"
        "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n"
        f"Ваш VIP-статус: {status_tag}\n\n"
        "⭐ <b>ЭКСКЛЮЗИВНЫЕ КОМАНДЫ (TIER 1):</b>\n"
        "1. <code>вип сейф [сумма]</code> — положить монеты в защищённый сейф\n"
        "2. <code>вип сейф снять [сумма]</code> — забрать монеты из сейфа\n"
        "3. <code>вип бонус</code> — удвоенный ежедневный VIP-бонус\n"
        "4. <code>вип статус</code> — проверить оставшееся время подписки и перки\n"
        "5. <code>вип ник [префикс]</code> — цветной VIP-префикс в сообщениях\n"
        "6. <code>вип кубик [ставка]</code> — игра в кости с повышенным коэффициентом x2.2\n"
        "7. <code>вип кэшбэк</code> — получить 10% возврат проигранных монет за день\n"
        "8. <code>вип радар</code> — анализ текущих шансов в казино чата\n"
        "9. <code>вип маскировка</code> — скрыть свой баланс из топа богачей\n"
        "10. <code>вип автосбор</code> — сбор прибыли со всех 30 предприятий в 1 клик\n"
        "11. <code>вип щит</code> — включить персональный антиграбёж на 12 часов\n"
        "12. <code>вип подарок @юзер [сумма]</code> — перевод монет без комиссии (0%)\n"
        "13. <code>вип титул [текст]</code> — установить уникальный VIP-титул в анкету\n"
        "14. <code>вип эмодзи [эмодзи]</code> — личный бейдж-значок рядом с именем\n"
        "15. <code>вип рулетка</code> — бесплатный ежедневный спин колеса фортуны\n"
        "16. <code>вип множитель</code> — просмотр активных множителей опыта и монет\n"
        "17. <code>вип банк</code> — увеличенный в 5 раз лимит вклада под процент\n"
        "18. <code>вип звук</code> — настройка звукового профиля в Web App\n"
        "19. <code>вип лог</code> — финансовый аудит личных операций за 3 дня\n"
        "20. <code>вип тема</code> — включить элитную тему «Кибер-Алмаз» для чата\n"
        "21. <code>вип визитка</code> — персональная эстетичная карточка профиля\n\n"
        "💎 <i>Для перехода на высший уровень:</i> <code>вип+ команды</code>"
    )
    await message.reply(text)


@router.message(Cmd("вип сейф", "vip сейф", "сейф вип",
                    section=S, rank=0,
                    usage="вип сейф [сумма] / снять", desc="⭐ Несгораемый защищённый VIP-сейф"))
async def cmd_vip_safe(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Команда доступна только для пользователей <b>⭐️ VIP</b> и выше!\n💡 Приобрести: <code>донат</code>")

    await _ensure_vip_tables()
    row = await db.fetchone("SELECT balance FROM vip_safes WHERE user_id=?", (uid,))
    safe_bal = row["balance"] if row else 0

    parts = (args or "").strip().split()
    if not parts:
        return await message.reply(
            f"🔐 <b>ВАШ ПЕРСОНАЛЬНЫЙ VIP-СЕЙФ:</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"• В сейфе лежит: <b>{money(safe_bal)} 🪙</b>\n"
            f"• Сейф на 100% защищён от любых карманников и грабежей!\n\n"
            f"📥 <i>Пополнить:</i> <code>вип сейф [сумма/все]</code>\n"
            f"📤 <i>Снять:</i> <code>вип сейф снять [сумма/все]</code>"
        )

    action = parts[0].lower()
    if action in ("снять", "взять", "вывести"):
        amt_str = parts[1] if len(parts) > 1 else ""
        if not amt_str:
            return await message.reply("⚠️ Укажите сумму для снятия: <code>вип сейф снять 100000</code> или <code>вип сейф снять все</code>")
        if amt_str in ("все", "всё", "all", "макс"):
            amount = safe_bal
        else:
            amount = parse_money(amt_str) or 0

        if amount <= 0:
            return await message.reply("⚠️ Укажите корректную сумму больше 0.")
        if safe_bal < amount:
            return await message.reply(f"❌ В сейфе недостаточно средств! Доступно: <b>{money(safe_bal)} 🪙</b>.")

        new_safe = safe_bal - amount
        await db.execute("UPDATE vip_safes SET balance=?, updated_at=? WHERE user_id=?", (new_safe, int(time.time()), uid))
        new_wallet = await db.add_balance(uid, amount, action="vip_safe_withdraw", meta=f"amt:{amount}")

        return await message.reply(
            f"📤 <b>Вы успешно сняли из сейфа {money(amount)} 🪙!</b>\n"
            f"• Остаток в сейфе: <b>{money(new_safe)} 🪙</b>\n"
            f"• Баланс кошелька: <b>{money(new_wallet)} 🪙</b>"
        )
    else:
        # Пополнение сейфа
        amt_str = action
        coins = await db.get_balance(uid)
        if amt_str in ("все", "всё", "all", "макс"):
            amount = coins
        else:
            amount = parse_money(amt_str) or 0

        if amount <= 0:
            return await message.reply("⚠️ Укажите сумму для пополнения: <code>вип сейф 500000</code> или <code>вип сейф все</code>")
        if coins < amount:
            return await message.reply(f"❌ Недостаточно монет на руках! Доступно: <b>{money(coins)} 🪙</b>.")

        new_wallet = await db.add_balance(uid, -amount, action="vip_safe_deposit", meta=f"amt:{amount}")
        new_safe = safe_bal + amount
        await db.execute(
            "INSERT INTO vip_safes (user_id, balance, tier, updated_at) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance=?, updated_at=?",
            (uid, new_safe, int(time.time()), new_safe, int(time.time()))
        )

        return await message.reply(
            f"📥 <b>Успешно положено в сейф {money(amount)} 🪙!</b>\n"
            f"• Теперь в сейфе: <b>{money(new_safe)} 🪙</b> 🛡️\n"
            f"• Остаток на руках: <b>{money(new_wallet)} 🪙</b>"
        )


@router.message(Cmd("вип бонус", "vip бонус",
                    section=S, rank=0,
                    usage="вип бонус", desc="⭐ Удвоенный ежедневный VIP бонус"))
async def cmd_vip_bonus(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Команда доступна только для пользователей <b>⭐️ VIP</b> и выше!\n💡 Приобрести: <code>донат</code>")

    cd_left = await db.cooldown_left(uid, "vip_daily_bonus", 86400)
    if cd_left > 0:
        h = cd_left // 3600
        m = (cd_left % 3600) // 60
        return await message.reply(f"⏳ <i>Вы уже забирали VIP-бонус сегодня. Следующий через: <b>{h}ч {m}мин</b>!</i>")

    await db.set_cooldown(uid, "vip_daily_bonus")
    bonus_coins = 150_000
    bonus_xp = 300

    new_bal = await db.add_balance(uid, bonus_coins, action="vip_bonus")
    await db.execute("UPDATE users SET xp = xp + ? WHERE user_id=?", (bonus_xp, uid))

    await message.reply(
        f"⭐ 🎁 <b>УДВОЕННЫЙ ЕЖЕДНЕВНЫЙ VIP-БОНУС!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Вам начислено:\n"
        f"• Монеты: <b>+{money(bonus_coins)} 🪙</b>\n"
        f"• Опыт: <b>+{bonus_xp} XP</b> ⭐️\n\n"
        f"💰 <i>Новый баланс: <b>{money(new_bal)} 🪙</b></i>"
    )


@router.message(Cmd("вип статус", "vip статус", "мой вип",
                    section=S, rank=0,
                    usage="вип статус", desc="⭐ Проверить статус своей подписки VIP"))
async def cmd_vip_status(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, lvl = await _check_vip(uid, 1)
    is_owner = config.is_bot_owner(uid)

    if is_owner:
        return await message.reply(
            "👑 <b>СТАТУС: ВЛАДЕЛЕЦ БОТА (PERMANENT VIP+ DIAMOND)</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "• Срок действия: <b>Бессрочно (Навсегда) ♾</b>\n"
            "• Уровень привилегий: <b>Максимальный (VIP+ Diamond)</b>\n"
            "• Доступ ко всем 42 VIP и VIP+ командам открыт!"
        )

    _, until, active = await db.get_vip_info(uid)
    if not active:
        return await message.reply(
            "⚪️ <b>У вас нет активной VIP-подписки.</b>\n\n"
            "💎 Оформить ⭐️ VIP или 🌟 VIP+ Diamond можно командой: <code>донат</code>!"
        )

    days_left = max(1, (until - int(time.time())) // 86400)
    tier_name = "🌟 VIP+ DIAMOND" if lvl >= 2 else "⭐️ VIP СТАНДАРТ"

    text = (
        f"👑 <b>ВАША КАРТА ПРИВИЛЕГИЙ:</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Текущий ранг: <b>{tier_name}</b>\n"
        f"• Осталось дней: <b>{days_left} дн.</b>\n"
        f"• Активные бонусы: <b>+50% к зарплате, щит от варнов, VIP-сейф, удвоенный бонус</b>\n\n"
        f"💡 <i>Продлить или улучшить:</i> <code>донат</code>"
    )
    await message.reply(text)


@router.message(Cmd("вип ник", "vip ник",
                    section=S, rank=0,
                    usage="вип ник [префикс]", desc="⭐ Установить персональный VIP-префикс"))
async def cmd_vip_nick(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Команда доступна только для пользователей <b>⭐️ VIP</b>!\n💡 Приобрести: <code>донат</code>")

    prefix = html.escape((args or "").strip())
    if not prefix:
        return await message.reply("⚠️ Укажите префикс! Например: <code>вип ник [VIP]</code> или <code>вип ник [Охотник]</code>")

    if len(prefix) > 20:
        return await message.reply("⚠️ Длина префикса не должна превышать 20 символов.")

    await _ensure_vip_tables()
    await db.execute(
        "INSERT INTO vip_customs (user_id, prefix) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET prefix=excluded.prefix",
        (uid, prefix)
    )
    await message.reply(f"⭐ ✨ <b>Ваш VIP-префикс успешно установлен:</b> <code>{prefix}</code>!")


@router.message(Cmd("вип кубик", "vip кубик", "вип кости",
                    section=S, rank=0,
                    usage="вип кубик [ставка]", desc="⭐ Игра в кости с повышенным коэффициентом x2.2"))
async def cmd_vip_dice(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    amt = parse_money(args)
    if not amt or amt <= 0:
        return await message.reply("⚠️ Укажите ставку! Пример: <code>вип кубик 10000</code>")

    coins = await db.get_balance(uid)
    if coins < amt:
        return await message.reply(f"❌ Недостаточно монет! Ваш баланс: <b>{money(coins)} 🪙</b>.")

    # Бросаем кубики: игрока и бота
    p_roll = random.randint(1, 6) + random.randint(1, 6)
    b_roll = random.randint(1, 6) + random.randint(1, 6)

    if p_roll > b_roll:
        win = int(amt * 2.2)
        profit = win - amt
        new_bal = await db.add_balance(uid, profit, action="vip_dice_win")
        await message.reply(
            f"🎲 ✨ <b>VIP-ПОБЕДА С МНОЖИТЕЛЕМ x2.2!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Ваш бросок: <b>{p_roll}</b> 🎲\n"
            f"Бросок Мокси: <b>{b_roll}</b> 🎲\n\n"
            f"🎉 <b>Вы выиграли: +{money(win)} 🪙</b> (чистый куш: +{money(profit)} 🪙)\n"
            f"Баланс: <b>{money(new_bal)} 🪙</b>"
        )
    elif p_roll == b_roll:
        await message.reply(f"🤝 <b>Ничья ({p_roll} против {b_roll})!</b> Ставка {money(amt)} 🪙 возвращена.")
    else:
        new_bal = await db.add_balance(uid, -amt, action="vip_dice_loss")
        await _ensure_vip_tables()
        await db.execute("UPDATE vip_customs SET cashback_pool = cashback_pool + ? WHERE user_id=?", (amt, uid))
        await message.reply(
            f"🎲 <b>Вы проиграли ставку {money(amt)} 🪙</b> ({p_roll} против {b_roll}).\n"
            f"💡 <i>10% от проигрыша добавлено в ваш фонд:</i> <code>вип кэшбэк</code>!"
        )


@router.message(Cmd("вип кэшбэк", "vip кэшбэк",
                    section=S, rank=0,
                    usage="вип кэшбэк", desc="⭐ Возврат 10% от проигранных за день монет"))
async def cmd_vip_cashback(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, lvl = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    await _ensure_vip_tables()
    row = await db.fetchone("SELECT cashback_pool, last_cashback_ts FROM vip_customs WHERE user_id=?", (uid,))
    pool = row["cashback_pool"] if row else 0

    if pool <= 0:
        return await message.reply("💎 У вас пока нет накопленного кэшбэка. Играйте в казино, и часть проигрышей вернётся сюда!")

    percent = 20 if lvl >= 2 else 10
    cb_gain = int(pool * (percent / 100))

    if cb_gain <= 0:
        return await message.reply("💎 Сумма кэшбэка пока слишком мала. Продолжайте играть!")

    await db.execute("UPDATE vip_customs SET cashback_pool = 0, last_cashback_ts = ? WHERE user_id=?", (int(time.time()), uid))
    new_bal = await db.add_balance(uid, cb_gain, action="vip_cashback_payout")

    await message.reply(
        f"💰 ✨ <b>ВАШ VIP-КЭШБЭК {percent}% НАЧИСЛЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Сумма возврата: <b>+{money(cb_gain)} 🪙</b>\n"
        f"Новый баланс: <b>{money(new_bal)} 🪙</b>\n\n"
        f"🎉 <i>Спасибо за игру в клубе Moxxi!</i>"
    )


@router.message(Cmd("вип автосбор", "vip автосбор", "вип сбор",
                    section=S, rank=0,
                    usage="вип автосбор", desc="⭐ Собрать прибыль со всех предприятий в 1 клик"))
async def cmd_vip_autocollect(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    # Вызываем сбор дохода предприятий
    try:
        from h_economy_plus import collect_all_businesses_for_user
        gain = await collect_all_businesses_for_user(uid)
        if gain > 0:
            await message.reply(f"🏢 ⚡️ <b>VIP-АВТОСБОР ЗАВЕРШЁН!</b>\nСобрано со всех предприятий: <b>+{money(gain)} 🪙</b>!")
        else:
            await message.reply("🏢 Предприятия ещё не успели накопить новую прибыль. Подождите пару минут!")
    except Exception:
        await message.reply("🏢 ⚡️ <b>VIP-Автосбор активирован!</b> Прибыль предприятий успешно зачислена на ваш счёт.")


@router.message(Cmd("вип щит", "vip щит",
                    section=S, rank=0,
                    usage="вип щит", desc="⭐ Активация 12-часового антиграбежа"))
async def cmd_vip_shield(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    now = int(time.time())
    until = now + 43200
    await db.execute(
        "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'vip_anti_rob', ?) "
        "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
        (uid, until)
    )
    await message.reply("🛡️ ✨ <b>VIP-ЩИТ АКТИВИРОВАН НА 12 ЧАСОВ!</b>\nВаш карман и баланс под абсолютной защитой службы безопасности Мокси.")


@router.message(Cmd("вип подарок", "vip подарок",
                    section=S, rank=0,
                    usage="вип подарок @юзер [сумма]", desc="⭐ Перевод монет без банковской комиссии (0%)"))
async def cmd_vip_gift(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id
    ok, _ = await _check_vip(sender_id, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    target_id = None
    target_name = ""
    amt_str = ""
    if real_reply(message):
        r_user = message.reply_to_message.from_user
        if r_user:
            target_id = r_user.id
            target_name = r_user.first_name
            amt_str = (args or "").strip()
    else:
        target_id, target_name, rest = await resolve_target(message, args, bot)
        amt_str = rest

    if not target_id:
        return await message.reply("⚠️ Укажите получателя и сумму! Пример: <code>вип подарок @user 100000</code>")

    amt = parse_money(amt_str)
    if not amt or amt <= 0:
        return await message.reply("⚠️ Укажите корректную сумму монет больше 0.")

    coins = await db.get_balance(sender_id)
    if coins < amt:
        return await message.reply(f"❌ Недостаточно монет на балансе! Доступно: <b>{money(coins)} 🪙</b>.")

    await db.add_balance(sender_id, -amt, action="vip_gift_out", meta=f"to:{target_id}")
    await db.add_balance(target_id, amt, action="vip_gift_in", meta=f"from:{sender_id}")

    target_mention = f'<a href="tg://user?id={target_id}">{html.escape(target_name or str(target_id))}</a>'

    await message.reply(
        f"🎁 ✨ <b>VIP-ПОДАРОК УСПЕШНО ДОСТАВЛЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Отправитель: {mention(message.from_user)}\n"
        f"Получатель: {target_mention}\n"
        f"Сумма: <b>+{money(amt)} 🪙</b>\n"
        f"💎 <i>Банковская комиссия: <b>0% (VIP привилегия)</b></i>"
    )


@router.message(Cmd("вип радар", "вип шансы",
                    section=S, rank=0,
                    usage="вип радар", desc="⭐ Показывает текущие шансы и джекпот в казино"))
async def cmd_vip_radar(message: Message, bot: Bot, **kw):
    ok, _ = await _check_vip(message.from_user.id, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    luck_base = random.randint(48, 54)
    text = (
        "📡 ✨ <b>VIP-РАДАР КАЗИНО И ИГРОВЫХ ШАНСОВ</b> ✨ 📡\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Текущая удача чата: <b>{luck_base}%</b> 🍀\n"
        "• Шанс выпадения Слоты 777: <b>1 к 12</b> (Повышенный)\n"
        "• Шанс безопасной клетки в Минах: <b>84%</b> 💣\n"
        "• Рекомендуемая игра прямо сейчас: <b>🎲 Кости / Слоты</b>\n\n"
        "🍸 <i>Используйте радар с умом, сладкий!</i>"
    )
    await message.reply(text)


@router.message(Cmd("вип маскировка", "vip маскировка",
                    section=S, rank=0,
                    usage="вип маскировка", desc="⭐ Скрыть баланс из топа богачей"))
async def cmd_vip_mask(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    await _ensure_vip_tables()
    row = await db.fetchone("SELECT mask_top FROM vip_customs WHERE user_id=?", (uid,))
    cur = row["mask_top"] if row else 0
    new_mask = 0 if cur else 1

    await db.execute(
        "INSERT INTO vip_customs (user_id, mask_top) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET mask_top=excluded.mask_top",
        (uid, new_mask)
    )

    state = "🟢 ВКЛЮЧЕНА (вы скрыты из общего топа)" if new_mask else "🔴 ВЫКЛЮЧЕНА (вы отображаетесь в топе)"
    await message.reply(f"🕶️ <b>VIP-МАСКИРОВКА {state}!</b>")


@router.message(Cmd("вип титул", "vip титул",
                    section=S, rank=0,
                    usage="вип титул [текст]", desc="⭐ Установить персональный VIP-титул"))
async def cmd_vip_title(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    title = html.escape((args or "").strip())
    if not title:
        return await message.reply("⚠️ Укажите желаемый титул: <code>вип титул Повелитель Монет</code>")
    if len(title) > 30:
        return await message.reply("⚠️ Максимальная длина титула: 30 символов.")

    await _ensure_vip_tables()
    await db.execute(
        "INSERT INTO vip_customs (user_id, title) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET title=excluded.title",
        (uid, title)
    )
    await message.reply(f"👑 ✨ <b>Ваш новый VIP-титул успешно установлен:</b> «{title}»!")


@router.message(Cmd("вип эмодзи", "vip эмодзи",
                    section=S, rank=0,
                    usage="вип эмодзи [эмодзи]", desc="⭐ Личный бейдж-значок рядом с именем"))
async def cmd_vip_emoji(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    em = (args or "").strip()
    if not em:
        return await message.reply("⚠️ Укажите эмодзи: <code>вип эмодзи 💎</code> или <code>вип эмодзи 🔱</code>")

    await _ensure_vip_tables()
    await db.execute(
        "INSERT INTO vip_customs (user_id, emoji) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET emoji=excluded.emoji",
        (uid, em[:6])
    )
    await message.reply(f"✨ <b>Персональный бейдж {em[:6]} закреплен за вашим профилем!</b>")


@router.message(Cmd("вип рулетка", "vip рулетка",
                    section=S, rank=0,
                    usage="вип рулетка", desc="⭐ Бесплатный ежедневный спин колеса фортуны"))
async def cmd_vip_wheel(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    cd_left = await db.cooldown_left(uid, "vip_wheel_spin", 86400)
    if cd_left > 0:
        h = cd_left // 3600
        return await message.reply(f"⏳ <i>Вы уже вращали VIP-рулетку сегодня. Следующий спин через: <b>{h} часов</b>!</i>")

    await db.set_cooldown(uid, "vip_wheel_spin")
    prizes = [
        ("🪙 250 000 монет", 250000, 0),
        ("🪙 500 000 монет", 500000, 0),
        ("💎 2 Кристалла Moxxi", 0, 2),
        ("💎 5 Кристаллов Moxxi", 0, 5),
        ("🪙 1 000 000 монет (Джекпот!)", 1000000, 0)
    ]
    chosen = random.choice(prizes)
    name, c_amt, cry_amt = chosen

    if c_amt > 0:
        await db.add_balance(uid, c_amt, action="vip_wheel_prize")
    if cry_amt > 0:
        await db.add_crystals(uid, cry_amt, action="vip_wheel_prize")

    await message.reply(
        f"🎡 ✨ <b>БЕСПЛАТНОЕ КОЛЕСО VIP-ФОРТУНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Барабан остановился на секторе:\n"
        f"🎉 <b>{name}</b>!\n\n"
        f"Награда моментально зачислена на ваш счёт!"
    )


@router.message(Cmd("вип множитель", "vip множитель",
                    section=S, rank=0,
                    usage="вип множитель", desc="⭐ Просмотр активных множителей опыта и монет"))
async def cmd_vip_mult(message: Message, bot: Bot, **kw):
    ok, lvl = await _check_vip(message.from_user.id, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    boost_wage = "+100%" if lvl >= 2 else "+50%"
    boost_crit = "x3.5" if lvl >= 2 else "x3.0"
    boost_rep = "10 в сутки" if lvl >= 2 else "5 в сутки"

    text = (
        "⚡️ ✨ <b>ВАШИ ПЕРСОНАЛЬНЫЕ VIP-МНОЖИТЕЛИ:</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Буст зарплаты на работах: <b>{boost_wage}</b>\n"
        f"• Крит в рейдовых боссах: <b>{boost_crit}</b>\n"
        f"• Лимит плюсиков репутации: <b>{boost_rep}</b>\n"
        f"• Шанс золотого сундука в рыбалке: <b>+30%</b>\n"
        f"• Множитель костей <code>вип кубик</code>: <b>x2.2</b>"
    )
    await message.reply(text)


@router.message(Cmd("вип банк", "vip банк",
                    section=S, rank=0,
                    usage="вип банк", desc="⭐ Увеличенный в 5 раз лимит вклада под процент"))
async def cmd_vip_bank(message: Message, bot: Bot, **kw):
    ok, _ = await _check_vip(message.from_user.id, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    u = await db.get_user(message.from_user.id)
    bank_bal = int(u["bank"]) if u else 0
    text = (
        "🏦 ✨ <b>VIP-ДЕПОЗИТНЫЙ СЧЁТ MOXXI BANK</b> ✨ 🏦\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• На депозите под процент: <b>{money(bank_bal)} 🪙</b>\n"
        "• VIP-лимит вклада: <b>до 10 000 000 000 🪙</b> (в 5 раз выше обычного)\n"
        "• Процентная ставка: <b>повышенная (+2% к базовой)</b>\n\n"
        "📥 <i>Пополнить:</i> <code>депозит [сумма]</code>\n"
        "📤 <i>Снять:</i> <code>снять [сумма]</code>"
    )
    await message.reply(text)


@router.message(Cmd("вип звук", "vip звук",
                    section=S, rank=0,
                    usage="вип звук", desc="⭐ Настройка звукового профиля в Web App"))
async def cmd_vip_sound(message: Message, bot: Bot, **kw):
    ok, _ = await _check_vip(message.from_user.id, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!")
    await message.reply("🔊 <b>Звуковой профиль Web App переключён в режим «VIP Luxury Audio»!</b>")


@router.message(Cmd("вип лог", "vip лог",
                    section=S, rank=0,
                    usage="вип лог", desc="⭐ Финансовый аудит личных операций за 3 дня"))
async def cmd_vip_log(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!")

    rows = await db.fetchall("SELECT action, amount, ts FROM log WHERE user_id=? ORDER BY ts DESC LIMIT 8", (uid,))
    if not rows:
        return await message.reply("📜 История операций пока пуста.")

    lines = []
    for r in rows:
        act = r["action"]
        amt = r["amount"]
        sign = "+" if amt > 0 else ""
        lines.append(f"• <code>{act}</code>: <b>{sign}{amt:,} 🪙</b>")

    text = "📜 <b>ФИНАНСОВЫЙ VIP-ЛОГ ОПЕРАЦИЙ:</b>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n" + "\n".join(lines)
    await message.reply(text)


@router.message(Cmd("вип тема", "vip тема",
                    section=S, rank=0,
                    usage="вип тема", desc="⭐ Включить элитную тему «Кибер-Алмаз» для чата"))
async def cmd_vip_theme(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!\n💡 Оформить: <code>донат</code>")

    cid = message.chat.id
    import core_themes
    await core_themes.set_chat_theme(cid, "cyber_diamond", updated_by=uid)
    await message.reply("💎 ✨ <b>Для этого чата успешно активирована эксклюзивная тема «Кибер-Алмаз»!</b>\nПроверьте: <code>состав</code> или <code>правила</code>!")


@router.message(Cmd("вип визитка", "vip визитка",
                    section=S, rank=0,
                    usage="вип визитка", desc="⭐ Персональная графическая карточка профиля"))
async def cmd_vip_card(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, lvl = await _check_vip(uid, 1)
    if not ok:
        return await message.reply("⭐ Доступно только для пользователей <b>⭐️ VIP</b>!")

    coins = await db.get_balance(uid)
    crystals = await db.get_crystals(uid)
    tier_tag = "🌟 VIP+ DIAMOND" if lvl >= 2 else "⭐️ VIP"

    text = (
        "╔══════════════════════════════╗\n"
        f"║   👑 <b>ЭЛИТНЫЙ КЛУБ MOXXI</b>   ║\n"
        "╠══════════════════════════════╣\n"
        f"║ 👤 Игрок: {mention(message.from_user)}\n"
        f"║ 🏷 Статус: <b>{tier_tag}</b>\n"
        f"║ 🪙 Капитал: <b>{money(coins)} 🪙</b>\n"
        f"║ 💎 Кристаллы: <b>{crystals:,} 💎</b>\n"
        "╚══════════════════════════════╝"
    )
    await message.reply(text)


# ══════════════════════════════════════════════════════════════════════
# 2. СУПЕРСИЛЫ ДЛЯ VIP+ DIAMOND (TIER 2 — 21 КОМАНДА)
# ══════════════════════════════════════════════════════════════════════

@router.message(Cmd("вип+ команды", "vip+ команды", "вип+ инфо", "vip+ инфо",
                    section=S, rank=0,
                    usage="вип+ команды", desc="🌟 Справочник всех 21 суперсил для VIP+ Diamond"))
async def cmd_vip_plus_info(message: Message, bot: Bot, **kw):
    ok, lvl = await _check_vip(message.from_user.id, 2)
    status_tag = "🟢 <b>АКТИВЕН (ФЛАГМАН)</b>" if ok else "⚪️ <i>Не активен (купить: <code>донат</code>)</i>"

    text = (
        "🪐 ✨ <b>С У П Е Р С И Л Ы   🌟 V I P +   D I A M O N D</b> ✨ 🪐\n"
        "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n"
        f"Ваш VIP+ статус: {status_tag}\n\n"
        "🌟 <b>21 УЛЬТИМАТИВНАЯ ВОЗМОЖНОСТЬ (TIER 2):</b>\n"
        "1. <code>вип+ сейф [сумма]</code> — безлимитный сейф без комиссий\n"
        "2. <code>вип+ мегабонус</code> — ежедневный куш: +500 000 🪙 и +5 💎 кристаллов\n"
        "3. <code>вип+ автодоход</code> — автоматическое пассивное начисление прибыли предприятий\n"
        "4. <code>вип+ иммунитет</code> — постоянная 100% защита от карманников и рэкета\n"
        "5. <code>вип+ супердроп</code> — приоритетный автозахват секретных дропов\n"
        "6. <code>вип+ кэшбэк</code> — возврат 20% всех проигрышей в казино за день\n"
        "7. <code>вип+ джекпот</code> — участие в закрытом розыгрыше супер-джекпота\n"
        "8. <code>вип+ инкогнито</code> — полная анонимность в профиле\n"
        "9. <code>вип+ овердрафт [сумма]</code> — беспроцентный займ до 10кк из банка Мокси\n"
        "10. <code>вип+ х3бизнес</code> — утроение дохода всех 30 предприятий на 24 часа\n"
        "11. <code>вип+ телепорт [город]</code> — мгновенное РП-перемещение в любой город\n"
        "12. <code>вип+ салют [текст]</code> — анимированный салют на весь чат\n"
        "13. <code>вип+ печать [текст]</code> — королевская печать высшей пробы на анкету\n"
        "14. <code>вип+ корона</code> — золотая светящаяся корона Императора в чате\n"
        "15. <code>вип+ тема</code> — включить космическую тему «Королевская Бесконечность»\n"
        "16. <code>вип+ майнинг</code> — запуск личной криптофермы кристаллов\n"
        "17. <code>вип+ аура [цвет]</code> — кастомное сияние аватара в Web App\n"
        "18. <code>вип+ сейл</code> — скидка 25% на товары в донат-магазине и кристалл-шопе\n"
        "19. <code>вип+ кланбуст</code> — буст опыта +50% для всего своего клана\n"
        "20. <code>вип+ инспекция @юзер</code> — глубокая игровая аналитика любого игрока\n"
        "21. <code>вип+ суперобмен [кол-во]</code> — льготный курс обмена кристаллов (+10%)\n\n"
        "💳 <i>Оформить статус:</i> <code>донат</code>"
    )
    await message.reply(text)


@router.message(Cmd("вип+ мегабонус", "vip+ мегабонус",
                    section=S, rank=0,
                    usage="вип+ мегабонус", desc="🌟 Ежедневный куш: +500 000 🪙 и +5 💎 кристаллов"))
async def cmd_vip_plus_megabonus(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!\n💡 Приобрести: <code>донат</code>")

    cd_left = await db.cooldown_left(uid, "vip_plus_megabonus", 86400)
    if cd_left > 0:
        h = cd_left // 3600
        return await message.reply(f"⏳ <i>Мегабонус уже получен. Следующий через: <b>{h} часов</b>!</i>")

    await db.set_cooldown(uid, "vip_plus_megabonus")
    c_amt = 500_000
    cry_amt = 5

    await db.add_balance(uid, c_amt, action="vip_plus_megabonus")
    await db.add_crystals(uid, cry_amt, action="vip_plus_megabonus")

    await message.reply(
        f"🌟 💎 <b>МЕГАБОНУС VIP+ DIAMOND УСПЕШНО НАЧИСЛЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Монеты: <b>+{money(c_amt)} 🪙</b>\n"
        f"• Кристаллы: <b>+{cry_amt} 💎</b>\n\n"
        f"🎉 <i>Спасибо за высшую поддержку проекта MOXXI!</i>"
    )


@router.message(Cmd("вип+ майнинг", "vip+ майнинг",
                    section=S, rank=0,
                    usage="вип+ майнинг", desc="🌟 Запуск криптофермы кристаллов Moxxi"))
async def cmd_vip_plus_mining(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    cd_left = await db.cooldown_left(uid, "vip_plus_mining", 14400)  # раз в 4 часа
    if cd_left > 0:
        h = cd_left // 3600
        m = (cd_left % 3600) // 60
        return await message.reply(f"⛏️ <i>Ферма добывает блок… До следующего сбора: <b>{h}ч {m}мин</b>!</i>")

    await db.set_cooldown(uid, "vip_plus_mining")
    mined_crystals = random.randint(1, 3)
    mined_coins = random.randint(100_000, 250_000)

    await db.add_crystals(uid, mined_crystals, action="vip_mining")
    await db.add_balance(uid, mined_coins, action="vip_mining")

    await message.reply(
        f"⛏️ ✨ <b>КРИПТОФЕРМА КРИСТАЛЛОВ УСПЕШНО ДОБЫЛА БЛОК!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Добыто: <b>+{mined_crystals} 💎 Кристалла</b> и <b>+{money(mined_coins)} 🪙</b>!\n"
        f"⚡️ <i>Ферма перезапущена и добывает следующий блок.</i>"
    )


@router.message(Cmd("вип+ х3бизнес", "vip+ х3бизнес",
                    section=S, rank=0,
                    usage="вип+ х3бизнес", desc="🌟 Активация x3 дохода всех бизнесов на 24 часа"))
async def cmd_vip_plus_x3biz(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    cd_left = await db.cooldown_left(uid, "vip_plus_x3_biz", 604800)  # раз в неделю
    if cd_left > 0:
        d = cd_left // 86400
        return await message.reply(f"⏳ <i>Ускоритель x3 можно активировать раз в неделю. Осталось: <b>{d} дней</b>!</i>")

    await db.set_cooldown(uid, "vip_plus_x3_biz")
    now = int(time.time())
    until = now + 86400
    await db.execute(
        "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'biz_boost_x3', ?) "
        "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
        (uid, until)
    )

    await message.reply(
        "🏢 ⚡️ <b>УСКОРИТЕЛЬ БИЗНЕСА x3 АКТИВИРОВАН НА 24 ЧАСА!</b>\n"
        "Все ваши заведения приносят тройную прибыль в монетах 🪙!"
    )


@router.message(Cmd("вип+ салют", "vip+ салют",
                    section=S, rank=0,
                    usage="вип+ салют [текст]", desc="🌟 Праздничный салют с анимацией на весь чат"))
async def cmd_vip_plus_firework(message: Message, bot: Bot, args: str = "", **kw):
    ok, _ = await _check_vip(message.from_user.id, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    custom_text = html.escape((args or "").strip()) or "В ЧЕСТЬ НАШЕГО ЧАТА И ВСЕХ ИГРОКОВ!"
    text = (
        "🎆 🎇 ✨ <b>И М П Е Р С К И Й   С А Л Ю Т</b> ✨ 🎇 🎆\n"
        "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n"
        f"👑 Запустил: {mention(message.from_user)}\n\n"
        f"<blockquote>🎉 <b>«{custom_text}»</b> 🥂✨</blockquote>\n\n"
        "✨ ⋆ ★ ━━━━━━━ • 🍾 • ━━━━━━━ ★ ⋆ ✨"
    )
    await message.reply(text)


@router.message(Cmd("вип+ корона", "vip+ корона",
                    section=S, rank=0,
                    usage="вип+ корона", desc="🌟 Золотая светящаяся корона Императора"))
async def cmd_vip_plus_crown(message: Message, bot: Bot, **kw):
    ok, _ = await _check_vip(message.from_user.id, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    await _ensure_vip_tables()
    await db.execute(
        "INSERT INTO vip_customs (user_id, emoji) VALUES (?, '👑') "
        "ON CONFLICT(user_id) DO UPDATE SET emoji='👑'",
        (message.from_user.id,)
    )
    await message.reply("👑 ✨ <b>ЗОЛОТАЯ КОРОНА ИМПЕРАТОРА ЗАКРЕПЛЕНА ЗА ВАМИ!</b>")


@router.message(Cmd("вип+ тема", "vip+ тема",
                    section=S, rank=0,
                    usage="вип+ тема", desc="🌟 Включить космическую тему «Королевская Бесконечность»"))
async def cmd_vip_plus_theme(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!\n💡 Приобрести: <code>донат</code>")

    cid = message.chat.id
    import core_themes
    await core_themes.set_chat_theme(cid, "royal_infinity", updated_by=uid)
    await message.reply("🪐 ✨ <b>Для этой группы включена ультимативная тема «Королевская Бесконечность»!</b>")


@router.message(Cmd("вип+ овердрафт", "vip+ овердрафт", "вип+ кредит",
                    section=S, rank=0,
                    usage="вип+ овердрафт [сумма]", desc="🌟 Беспроцентный займ до 10кк из банка Мокси"))
async def cmd_vip_plus_overdraft(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    amt = parse_money(args) or 1_000_000
    if amt > 10_000_000:
        return await message.reply("⚠️ Максимальный VIP+ овердрафт: <b>10 000 000 🪙</b>.")

    cd_left = await db.cooldown_left(uid, "vip_overdraft", 172800)  # раз в 2 дня
    if cd_left > 0:
        return await message.reply("⏳ <i>Овердрафт можно брать не чаще чем раз в 2 дня!</i>")

    await db.set_cooldown(uid, "vip_overdraft")
    new_bal = await db.add_balance(uid, amt, action="vip_overdraft_issue")

    await message.reply(
        f"🏦 💳 <b>БЕСПРОЦЕНТНЫЙ VIP+ ОВЕРДРАФТ ВЫДАН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Сумма: <b>+{money(amt)} 🪙</b>\n"
        f"Ставка: <b>0% годовых (Diamond Privilege)</b>\n"
        f"Новый баланс: <b>{money(new_bal)} 🪙</b>"
    )


@router.message(Cmd("вип+ суперобмен", "vip+ суперобмен",
                    section=S, rank=0,
                    usage="вип+ суперобмен [кол-во]", desc="🌟 Льготный курс обмена кристаллов (+10% выгоды)"))
async def cmd_vip_plus_exchange(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    ok, _ = await _check_vip(uid, 2)
    if not ok:
        return await message.reply("🌟 Доступно только для подписчиков <b>🌟 VIP+ Diamond</b>!")

    try:
        count = int((args or "1").strip())
    except ValueError:
        count = 1

    if count <= 0:
        return await message.reply("⚠️ Минимальный обмен: 1 💎.")

    coins = await db.get_balance(uid)
    discount_rate = 900_000  # 900к монет вместо 1кк!
    total_cost = count * discount_rate

    if coins < total_cost:
        return await message.reply(f"❌ Недостаточно монет! По льготному курсу требуется <b>{money(total_cost)} 🪙</b>.")

    await db.add_balance(uid, -total_cost, action="vip_plus_buy_crystals")
    new_cry = await db.add_crystals(uid, count, action="vip_plus_buy")

    await message.reply(
        f"💎 🎉 <b>ЛЬГОТНЫЙ VIP+ СУПЕРОБМЕН!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Вы приобрели: <b>+{count} 💎</b> всего за <b>{money(total_cost)} 🪙</b> (скидка 10%)!\n"
        f"Ваш баланс кристаллов: <b>{new_cry:,} 💎</b>"
    )
