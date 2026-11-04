"""💎 Модуль обмена валют и кристального магазина MOXXI 3.0 REVOLUTION.

Новая твердая валюта:
  💎 Кристаллы Moxxi (Moxxi Crystals).
  Курс: 1 Кристалл = 1 000 000 (1кк) обычных монет (Gram/монет).

Возможности:
- Мгновенный обмен монет на кристаллы и обратно;
- Перевод кристаллов между игроками;
- Эксклюзивный кристальный магазин с мощными бонусами.
"""
from __future__ import annotations

import html
import time
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from utils import mention, money, parse_money

router = Router(name="currency_exchange")
S = 5  # Раздел 5: Экономика и финансы

CRYSTAL_RATE = 1_000_000  # 1 Кристалл = 1,000,000 монет


def _get_exchange_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Купить 1 💎 (1кк)", callback_data="cry:buy:1"),
            InlineKeyboardButton(text="💎 Купить 5 💎 (5кк)", callback_data="cry:buy:5"),
        ],
        [
            InlineKeyboardButton(text="💎 Купить 10 💎 (10кк)", callback_data="cry:buy:10"),
            InlineKeyboardButton(text="🪙 Продать 1 💎 (+1кк)", callback_data="cry:sell:1"),
        ],
        [
            InlineKeyboardButton(text="🛒 Кристальный магазин", callback_data="cry:shop"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="cry:refresh"),
        ]
    ])


@router.message(Cmd("обменник", "курс", "курс кристаллов", "криптообменник", "биржа кристаллов",
                    section=S, rank=0,
                    usage="обменник", desc="💎 Курс и покупка кристаллов Moxxi (1 💎 = 1 000 000 🪙)"))
async def cmd_exchange_menu(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    coins = await db.get_balance(uid)
    crystals = await db.get_crystals(uid)

    text = (
        "💎 ✨ <b>О Б М Е Н Н И К   M O X X I   3.0</b> ✨ 💎\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📊 <b>Официальный курс биржи:</b>\n"
        f"• <b>1 💎 Кристалл</b> = <b>1 000 000 🪙 монет</b> (1кк)\n"
        f"• Резерв биржи: <b>неограничен</b> 🏦\n\n"
        f"👤 <b>Ваш кошелёк:</b>\n"
        f"• Баланс монет: <b>{money(coins)} 🪙</b>\n"
        f"• Баланс кристаллов: <b>{crystals:,} 💎</b>\n\n"
        "⚡️ <b>Быстрые команды обмена:</b>\n"
        "• <code>купить кристаллы [кол-во]</code> — купить нужное число кристаллов\n"
        "• <code>обменять [сумма/все]</code> — обменять монеты на кристаллы\n"
        "• <code>продать кристаллы [кол-во/все]</code> — продать кристаллы за монеты\n"
        "• <code>кристаллы</code> — проверить свой баланс кристаллов\n"
        "• <code>магазин кристаллов</code> — эксклюзивные артефакты и бусты за 💎\n\n"
        "👇 <i>Или используйте интерактивные кнопки ниже:</i>"
    )
    await message.reply(text, reply_markup=_get_exchange_kb())


@router.message(Cmd("кристаллы", "баланс кристаллов", "мои кристаллы",
                    section=S, rank=0,
                    usage="кристаллы", desc="💎 Проверить свой баланс кристаллов Moxxi"))
async def cmd_my_crystals(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    crystals = await db.get_crystals(uid)
    coins = await db.get_balance(uid)

    worth_coins = crystals * CRYSTAL_RATE
    text = (
        f"💎 <b>Кристальный счёт {mention(message.from_user)}:</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"• Баланс: <b>{crystals:,} 💎</b>\n"
        f"• Стоимость в монетах: <b>{money(worth_coins)} 🪙</b>\n"
        f"• Обычный баланс: <b>{money(coins)} 🪙</b>\n\n"
        f"💡 <i>Купить ещё:</i> <code>купить кристаллы [кол-во]</code>\n"
        f"🛒 <i>Потратить:</i> <code>магазин кристаллов</code>"
    )
    await message.reply(text)


@router.message(Cmd("купить кристаллы", "обменять", "купить кристалл",
                    section=S, rank=0,
                    usage="купить кристаллы [кол-во]", desc="💎 Купить кристаллы за монеты (1 💎 = 1 000 000 🪙)"))
async def cmd_buy_crystals(message: Message, bot: Bot, args: str = "", **kw):
    arg = (args or "").strip().lower()
    uid = message.from_user.id
    coins = await db.get_balance(uid)

    if not arg:
        return await message.reply(
            "💎 Укажите количество кристаллов или сумму для покупки!\n"
            "Примеры:\n"
            "• <code>купить кристаллы 5</code> (купить 5 💎 за 5 000 000 🪙)\n"
            "• <code>обменять все</code> (обменять все доступные монеты)"
        )

    if arg in ("все", "всё", "all", "макс"):
        crystals_to_buy = coins // CRYSTAL_RATE
    else:
        # Проверяем, ввел ли пользователь число кристаллов или сумму в монетах (например 5кк)
        parsed = parse_money(arg)
        if parsed is not None and parsed >= CRYSTAL_RATE:
            crystals_to_buy = parsed // CRYSTAL_RATE
        elif parsed is not None and parsed > 0:
            crystals_to_buy = parsed
        else:
            try:
                crystals_to_buy = int(arg)
            except ValueError:
                return await message.reply("⚠️ Не удалось распознать количество кристаллов. Пример: <code>купить кристаллы 5</code>")

    if crystals_to_buy <= 0:
        return await message.reply("⚠️ Минимальная покупка: <b>1 💎</b> (требуется 1 000 000 🪙 монет).")

    total_cost = crystals_to_buy * CRYSTAL_RATE
    if coins < total_cost:
        max_can_buy = coins // CRYSTAL_RATE
        return await message.reply(
            f"❌ <b>Недостаточно монет!</b>\n\n"
            f"Для покупки <b>{crystals_to_buy:,} 💎</b> требуется <b>{money(total_cost)} 🪙</b>.\n"
            f"У вас на балансе: <b>{money(coins)} 🪙</b> (хватает на: <b>{max_can_buy:,} 💎</b>)."
        )

    # Списываем монеты и начисляем кристаллы
    await db.add_balance(uid, -total_cost, action="exchange_buy_crystals", meta=f"count:{crystals_to_buy}")
    new_cry = await db.add_crystals(uid, crystals_to_buy, action="buy", meta=f"cost:{total_cost}")
    new_coins = await db.get_balance(uid)

    await message.reply(
        f"💎 🎉 <b>УСПЕШНЫЙ ОБМЕН ВАЛЮТЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Вы приобрели: <b>+{crystals_to_buy:,} 💎</b>\n"
        f"Списано с баланса: <b>-{money(total_cost)} 🪙</b>\n\n"
        f"👤 <b>Ваш новый баланс:</b>\n"
        f"• Кристаллы: <b>{new_cry:,} 💎</b>\n"
        f"• Монеты: <b>{money(new_coins)} 🪙</b>\n\n"
        f"🛒 <i>Открыть кристальный каталог:</i> <code>магазин кристаллов</code>"
    )


@router.message(Cmd("продать кристаллы", "продать кристалл",
                    section=S, rank=0,
                    usage="продать кристаллы [кол-во]", desc="🪙 Продать кристаллы и получить монеты (1 💎 = 1 000 000 🪙)"))
async def cmd_sell_crystals(message: Message, bot: Bot, args: str = "", **kw):
    arg = (args or "").strip().lower()
    uid = message.from_user.id
    current_cry = await db.get_crystals(uid)

    if not arg:
        return await message.reply(
            "🪙 Укажите количество кристаллов для продажи!\n"
            "Примеры:\n"
            "• <code>продать кристаллы 2</code> (получить +2 000 000 🪙)\n"
            "• <code>продать кристаллы все</code>"
        )

    if arg in ("все", "всё", "all", "макс"):
        cry_to_sell = current_cry
    else:
        try:
            cry_to_sell = int(arg)
        except ValueError:
            return await message.reply("⚠️ Не удалось распознать количество кристаллов. Пример: <code>продать кристаллы 3</code>")

    if cry_to_sell <= 0:
        return await message.reply("⚠️ Минимальная продажа: <b>1 💎</b>.")

    if current_cry < cry_to_sell:
        return await message.reply(
            f"❌ <b>Недостаточно кристаллов!</b>\n\n"
            f"Вы хотите продать <b>{cry_to_sell:,} 💎</b>, но у вас на счету только <b>{current_cry:,} 💎</b>."
        )

    total_coins_gain = cry_to_sell * CRYSTAL_RATE

    # Списываем кристаллы и начисляем монеты
    new_cry = await db.add_crystals(uid, -cry_to_sell, action="sell", meta=f"gain:{total_coins_gain}")
    new_coins = await db.add_balance(uid, total_coins_gain, action="exchange_sell_crystals", meta=f"count:{cry_to_sell}")

    await message.reply(
        f"🪙 ✨ <b>УСПЕШНАЯ ПРОДАЖА КРИСТАЛЛОВ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Продано кристаллов: <b>-{cry_to_sell:,} 💎</b>\n"
        f"Начислено на баланс: <b>+{money(total_coins_gain)} 🪙</b>\n\n"
        f"👤 <b>Ваш новый баланс:</b>\n"
        f"• Кристаллы: <b>{new_cry:,} 💎</b>\n"
        f"• Монеты: <b>{money(new_coins)} 🪙</b>"
    )


@router.message(Cmd("передать кристаллы", "перевести кристаллы",
                    section=S, rank=0,
                    usage="передать кристаллы @юзер [кол-во]", desc="💎 Передать кристаллы другому игроку"))
async def cmd_transfer_crystals(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id
    target = None
    amt_str = ""

    # Проверка ответа реплаем
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
        return await message.reply(
            "💎 <b>Как передать кристаллы другу:</b>\n"
            "• Ответом на сообщение: <code>передать кристаллы [кол-во]</code>\n"
            "• По нику/@username: <code>передать кристаллы @user [кол-во]</code>"
        )

    if target_id == sender_id:
        return await message.reply("😅 Нельзя передавать кристаллы самому себе!")

    try:
        amount = int(amt_str.strip())
    except ValueError:
        return await message.reply("⚠️ Укажите корректное целое число кристаллов. Пример: <code>передать кристаллы @user 5</code>")

    if amount <= 0:
        return await message.reply("⚠️ Минимальная сумма передачи: <b>1 💎</b>.")

    sender_cry = await db.get_crystals(sender_id)
    if sender_cry < amount:
        return await message.reply(
            f"❌ <b>Недостаточно кристаллов!</b>\n"
            f"Вы хотите передать <b>{amount:,} 💎</b>, но у вас есть только <b>{sender_cry:,} 💎</b>."
        )

    # Транзакция без комиссии
    s_new = await db.add_crystals(sender_id, -amount, action="transfer_out", meta=f"to:{target_id}")
    t_new = await db.add_crystals(target_id, amount, action="transfer_in", meta=f"from:{sender_id}")

    target_mention = f'<a href="tg://user?id={target_id}">{html.escape(target_name or str(target_id))}</a>'

    await message.reply(
        f"💎 🎁 <b>КРИСТАЛЛЫ УСПЕШНО ПЕРЕДАНЫ!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Отправитель: {mention(message.from_user)} (остаток: <b>{s_new:,} 💎</b>)\n"
        f"Получатель: {target_mention} (новый счёт: <b>{t_new:,} 💎</b>)\n"
        f"Сумма перевода: <b>{amount:,} 💎</b>\n"
        f"✨ <i>Комиссия перевода: 0%</i>"
    )


# ══════════════════ КРИСТАЛЬНЫЙ МАГАЗИН АРТЕФАКТОВ И БУСТОВ ══════════════════

CRYSTAL_SHOP_ITEMS = {
    1: {
        "id": 1,
        "name": "🛡️ Щит Титана (24 часа)",
        "price": 5,
        "desc": "100% защита от карманников, грабежей и рэкета на 24 часа",
        "action": "shield_24h"
    },
    2: {
        "id": 2,
        "name": "🍀 Амулет Фортуны (12 часов)",
        "price": 10,
        "desc": "+10% шанс победы во всех казино-играх (слоты, кости, рулетка)",
        "action": "fortune_12h"
    },
    3: {
        "id": 3,
        "name": "⚡ Ускоритель Бизнеса x2 (24 часа)",
        "price": 15,
        "desc": "Удваивает пассивный доход со всех купленных предприятий на 24 часа",
        "action": "biz_boost_x2"
    },
    4: {
        "id": 4,
        "name": "🌟 Мгновенное снятие варна",
        "price": 8,
        "desc": "Полное аннулирование 1 предупреждения в текущем чате",
        "action": "clear_warn"
    },
    5: {
        "id": 5,
        "name": "👑 Эксклюзивный кастомный титул",
        "price": 25,
        "desc": "Установка любого персонального титула в профиль на 30 дней",
        "action": "custom_title"
    },
    6: {
        "id": 6,
        "name": "🎨 VIP-Тема оформления «Кибер-Алмаз»",
        "price": 50,
        "desc": "Разблокировка элитной кристалльной темы оформления чата навсегда",
        "action": "vip_theme_diamond"
    }
}


@router.message(Cmd("магазин кристаллов", "кмагаз", "товары за кристаллы", "кристалльный магазин",
                    section=S, rank=0,
                    usage="магазин кристаллов", desc="🛒 Эксклюзивный магазин товаров и бустов за 💎 Кристаллы"))
async def cmd_crystal_shop(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    crystals = await db.get_crystals(uid)

    lines = []
    for num, item in CRYSTAL_SHOP_ITEMS.items():
        lines.append(
            f"<b>{num}. {item['name']}</b> — <b>{item['price']} 💎</b>\n"
            f"   └ <i>{item['desc']}</i>"
        )

    text = (
        "🛒 ✨ <b>К Р И С Т А Л Ь Н Ы Й   М А Г А З И Н</b> ✨ 🛒\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Ваш баланс: <b>{crystals:,} 💎 Кристаллов</b>\n\n"
        + "\n\n".join(lines) + "\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "👇 <b>Для покупки напишите:</b> <code>купить за кристаллы [номер]</code>\n"
        "Например: <code>купить за кристаллы 1</code>"
    )
    await message.reply(text)


@router.message(Cmd("купить за кристаллы", "ккупить", "купить артефакт",
                    section=S, rank=0,
                    usage="купить за кристаллы [номер]", desc="💎 Купить товар в кристальном магазине"))
async def cmd_buy_crystal_item(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    cid = message.chat.id
    arg = (args or "").strip()

    try:
        item_id = int(arg)
    except ValueError:
        return await message.reply("⚠️ Укажите номер товара! Например: <code>купить за кристаллы 1</code> (список: <code>магазин кристаллов</code>)")

    item = CRYSTAL_SHOP_ITEMS.get(item_id)
    if not item:
        return await message.reply("❌ Товар с таким номером не найден. Напишите <code>магазин кристаллов</code> для просмотра каталога.")

    user_cry = await db.get_crystals(uid)
    if user_cry < item["price"]:
        return await message.reply(
            f"❌ <b>Недостаточно кристаллов!</b>\n\n"
            f"Для покупки «{item['name']}» требуется <b>{item['price']} 💎</b>.\n"
            f"У вас на балансе: <b>{user_cry:,} 💎</b>.\n"
            f"💡 <i>Купить кристаллы:</i> <code>купить кристаллы {item['price'] - user_cry}</code>"
        )

    # Применение эффекта
    act = item["action"]
    now = int(time.time())

    if act == "shield_24h":
        until = now + 86400
        await db.execute(
            "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'titan_shield', ?) "
            "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
            (uid, until)
        )
    elif act == "fortune_12h":
        until = now + 43200
        await db.execute(
            "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'fortune_amulet', ?) "
            "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
            (uid, until)
        )
    elif act == "biz_boost_x2":
        until = now + 86400
        await db.execute(
            "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'biz_boost_x2', ?) "
            "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
            (uid, until)
        )
    elif act == "clear_warn":
        warns = await db.get_warns(cid, uid)
        if warns > 0:
            await db.execute("UPDATE warns SET count = MAX(0, count - 1) WHERE chat_id=? AND user_id=?", (cid, uid))
        else:
            return await message.reply("😇 У вас нет активных предупреждений в этом чате! Кристаллы не списаны.")
    elif act == "custom_title":
        # Даем право на команду титул
        until = now + (30 * 86400)
        await db.execute(
            "INSERT INTO cooldowns (user_id, chat_id, cmd, last_ts) VALUES (?, 0, 'vip_title_pass', ?) "
            "ON CONFLICT(user_id, chat_id, cmd) DO UPDATE SET last_ts=excluded.last_ts",
            (uid, until)
        )
    elif act == "vip_theme_diamond":
        # Устанавливаем тему Кибер-Алмаз для чата
        await db.execute(
            "INSERT INTO chat_themes (chat_id, theme, updated_at, updated_by) VALUES (?, 'cyber_diamond', ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET theme='cyber_diamond', updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (cid, now, uid)
        )

    # Списываем кристаллы
    new_cry = await db.add_crystals(uid, -item["price"], action="buy_item", meta=f"item:{item_id}")

    await message.reply(
        f"🎉 <b>ПОКУПКА УСПЕШНО СОВЕРШЕНА!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Приобретено: <b>{item['name']}</b>\n"
        f"Списано: <b>-{item['price']} 💎</b>\n"
        f"Остаток кристаллов: <b>{new_cry:,} 💎</b>\n\n"
        f"✨ <i>Бонус уже активирован и готов к использованию!</i>"
    )


# ── ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ──────────────────────────────────────────

@router.callback_query(F.data.startswith("cry:buy:"))
async def cb_buy_crystals(cq: CallbackQuery, bot: Bot):
    count = int(cq.data.split(":")[2])
    uid = cq.from_user.id
    coins = await db.get_balance(uid)
    cost = count * CRYSTAL_RATE

    if coins < cost:
        return await cq.answer(f"❌ Недостаточно монет! Требуется {money(cost)} 🪙.", show_alert=True)

    await db.add_balance(uid, -cost, action="exchange_cb_buy", meta=f"count:{count}")
    new_cry = await db.add_crystals(uid, count, action="cb_buy", meta=f"cost:{cost}")
    new_coins = await db.get_balance(uid)

    await cq.answer(f"🎉 Вы успешно купили +{count} 💎 за {money(cost)} 🪙!", show_alert=True)
    try:
        text = (
            "💎 ✨ <b>О Б М Е Н Н И К   M O X X I   3.0</b> ✨ 💎\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"📊 <b>Официальный курс биржи:</b>\n"
            f"• <b>1 💎 Кристалл</b> = <b>1 000 000 🪙 монет</b> (1кк)\n\n"
            f"👤 <b>Ваш кошелёк (обновлено):</b>\n"
            f"• Баланс монет: <b>{money(new_coins)} 🪙</b>\n"
            f"• Баланс кристаллов: <b>{new_cry:,} 💎</b>\n\n"
            f"✅ <i>Только что куплено: +{count} 💎</i>"
        )
        await cq.message.edit_text(text, reply_markup=_get_exchange_kb())
    except Exception:
        pass


@router.callback_query(F.data.startswith("cry:sell:"))
async def cb_sell_crystals(cq: CallbackQuery, bot: Bot):
    count = int(cq.data.split(":")[2])
    uid = cq.from_user.id
    current_cry = await db.get_crystals(uid)

    if current_cry < count:
        return await cq.answer("❌ У вас недостаточно кристаллов для продажи!", show_alert=True)

    gain = count * CRYSTAL_RATE
    new_cry = await db.add_crystals(uid, -count, action="cb_sell", meta=f"gain:{gain}")
    new_coins = await db.add_balance(uid, gain, action="exchange_cb_sell", meta=f"count:{count}")

    await cq.answer(f"🪙 Продано {count} 💎. Получено: +{money(gain)} 🪙!", show_alert=True)
    try:
        text = (
            "💎 ✨ <b>О Б М Е Н Н И К   M O X X I   3.0</b> ✨ 💎\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"📊 <b>Официальный курс биржи:</b>\n"
            f"• <b>1 💎 Кристалл</b> = <b>1 000 000 🪙 монет</b> (1кк)\n\n"
            f"👤 <b>Ваш кошелёк (обновлено):</b>\n"
            f"• Баланс монет: <b>{money(new_coins)} 🪙</b>\n"
            f"• Баланс кристаллов: <b>{new_cry:,} 💎</b>\n\n"
            f"✅ <i>Только что продано: -{count} 💎</i>"
        )
        await cq.message.edit_text(text, reply_markup=_get_exchange_kb())
    except Exception:
        pass


@router.callback_query(F.data == "cry:refresh")
async def cb_refresh_exchange(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    coins = await db.get_balance(uid)
    crystals = await db.get_crystals(uid)

    text = (
        "💎 ✨ <b>О Б М Е Н Н И К   M O X X I   3.0</b> ✨ 💎\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📊 <b>Официальный курс биржи:</b>\n"
        f"• <b>1 💎 Кристалл</b> = <b>1 000 000 🪙 монет</b> (1кк)\n\n"
        f"👤 <b>Ваш кошелёк:</b>\n"
        f"• Баланс монет: <b>{money(coins)} 🪙</b>\n"
        f"• Баланс кристаллов: <b>{crystals:,} 💎</b>\n\n"
        "🔄 <i>Данные обновлены в реальном времени.</i>"
    )
    try:
        await cq.message.edit_text(text, reply_markup=_get_exchange_kb())
    except Exception:
        pass
    await cq.answer("🔄 Данные биржи обновлены!")


@router.callback_query(F.data == "cry:shop")
async def cb_open_shop(cq: CallbackQuery, bot: Bot):
    await cq.answer()
    uid = cq.from_user.id
    crystals = await db.get_crystals(uid)
    lines = []
    for num, item in CRYSTAL_SHOP_ITEMS.items():
        lines.append(f"<b>{num}. {item['name']}</b> — <b>{item['price']} 💎</b>\n   └ <i>{item['desc']}</i>")

    text = (
        "🛒 ✨ <b>К Р И С Т А Л Ь Н Ы Й   М А Г А З И Н</b> ✨ 🛒\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Ваш баланс: <b>{crystals:,} 💎 Кристаллов</b>\n\n"
        + "\n\n".join(lines) + "\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "👇 <b>Для покупки напишите:</b> <code>купить за кристаллы [номер]</code>"
    )
    await cq.message.reply(text)
