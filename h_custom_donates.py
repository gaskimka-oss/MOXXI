"""Модуль конструктора кастомных донатов беседы за 76 рублей и официальный магазин ❄️ Снежинок.
1. Владелец беседы за 76 руб активирует конструктор кастомных донатов и команд для своего чата.
   (СТРОГИЙ ЗАПРЕТ на выдачу игровой валюты/кейсов, процент от покупок владельцу не выплачивается).
2. Официальная продажа новой новогодней валюты (❄️ Снежинки) за рубли и Telegram Stars.
"""
from __future__ import annotations

import html
import time
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from utils import mention, mention_id, money

router = Router(name="custom_donates")
S = 6  # Раздел: Настройки чата / Магазин

ACTIVATION_PRICE_RUB = 76
ACTIVATION_PRICE_STARS = 45

# Пакеты новой новогодней валюты (❄️ Снежинки)
SNOWFLAKE_PACKAGES = {
    "pack_50": {"flakes": 50, "rub": 49, "stars": 25, "name": "❄️ Горсть Снежинок (50 ❄️)"},
    "pack_150": {"flakes": 150, "rub": 129, "stars": 65, "name": "❄️ Мешок Снежинок (150 ❄️)"},
    "pack_500": {"flakes": 500, "rub": 349, "stars": 175, "name": "❄️ Сундук Вьюги (500 ❄️)"},
    "pack_1500": {"flakes": 1500, "rub": 890, "stars": 450, "name": "❄️ Ледяная Сокровищница (1500 ❄️) (+20% Бонус!)"},
}

# Стоп-слова для предотвращения дюпа валюты в кастомных донатах
FORBIDDEN_KEYWORDS = (
    "монет", "монеты", "coin", "coins", "баланс", "рубл", "руб", "деньг",
    "грамм", "gram", "кейсы", "кейс", "case", "cases", "снежинк", "снежок", "снежинки"
)


# ════════════════════════════ 1. МАГАЗИН СНЕЖИНОК ════════════════════════════

@router.message(Cmd("купить снежинки", "снежинки купить", "донат снежинки", "магазин снежинок",
                    section=S, usage="купить снежинки", desc="Купить новогоднюю валюту ❄️ Снежинки"))
async def cmd_buy_snowflakes(message: Message, **kw):
    rows = []
    for pid, p in SNOWFLAKE_PACKAGES.items():
        rows.append([
            InlineKeyboardButton(text=f"{p['name']} — {p['rub']}₽ / {p['stars']}⭐", callback_data=f"buy_snow:{pid}")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    u = await db.get_user(message.from_user.id)
    cur_flakes = u.get("snowflakes", 0) or 0

    text = (
        "❄️ <b>ОФИЦИАЛЬНЫЙ МАГАЗИН НОВОГОДНЕЙ ВАЛЮТЫ 2027</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"Ваш баланс: <b>{cur_flakes:,} ❄️ Снежинок</b>\n\n"
        "Снежинки нужны для:\n"
        "• Открытия лимитированного <b>❄️ Ледяного Кейса 2027</b>\n"
        "• Прокачки новогодней <b>Ёлки беседы</b> до 10 LVL\n"
        "• Участия в битве за <b>10 LVL Telegram Boost</b>\n"
        "• Бросков снежками и подарков друзьям!\n\n"
        "<i>Выберите желаемый праздничный набор ниже:</i>"
    )
    await message.reply(text, reply_markup=kb)


@router.callback_query(F.data.startswith("buy_snow:"))
async def on_buy_snow_callback(cb: CallbackQuery, bot: Bot):
    pid = cb.data.split(":")[1]
    pack = SNOWFLAKE_PACKAGES.get(pid)
    if not pack:
        return await cb.answer("⚠️ Пакет не найден.", show_alert=True)

    try:
        await bot.send_invoice(
            chat_id=cb.from_user.id,
            title=pack["name"],
            description=f"Начисление +{pack['flakes']} ❄️ Снежинок на ваш аккаунт MOXXI",
            payload=f"snowflakes:{pack['flakes']}:{cb.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice(label=pack["name"], amount=pack["stars"])],
            provider_token=""
        )
        await cb.answer("⭐ Инвойс выставлен в ЛС с ботом!", show_alert=True)
    except Exception:
        await cb.answer("⚠️ Пожалуйста, начните диалог с ботом в ЛС перед оплатой!", show_alert=True)


# ════════════════════════════ 2. КАСТОМНЫЙ ДОНАТ-ШОП ════════════════════════════

@router.message(Cmd("донат шоп", "донат магазин", "донаты чата", "товары чата", section=S, group_only=True,
                    usage="донат шоп", desc="Кастомный магазин донатов беседы"))
async def cmd_donate_shop(message: Message, bot: Bot, **kw):
    chat_id = message.chat.id
    is_active = await db.is_custom_donate_shop_active(chat_id)
    shop = await db.get_custom_donate_shop(chat_id)
    my_rank = await effective_rank(message, bot)

    if not is_active:
        rows = []
        if my_rank >= 7:
            rows.append([
                InlineKeyboardButton(text=f"💳 Активировать за {ACTIVATION_PRICE_RUB}₽", callback_data=f"act_shop_rub:{chat_id}"),
                InlineKeyboardButton(text=f"⭐ За {ACTIVATION_PRICE_STARS} Stars", callback_data=f"act_shop_stars:{chat_id}")
            ])
        kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

        text = (
            "🛍 <b>КОНСТРУКТОР КАСТОМНЫХ ДОНАТОВ БЕСЕДЫ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
            "Хотите создать собственные платные роли, кастомные команды, "
            "иммунитеты от мутов и эксклюзивные титулы для участников этой беседы?\n\n"
            f"👑 <b>Активация конструктора для беседы:</b> всего <b>{ACTIVATION_PRICE_RUB} рублей</b> (или <b>{ACTIVATION_PRICE_STARS} Stars</b>) навсегда!\n\n"
            "🔒 <b>Правила безопасности:</b>\n"
            "• Разрешено: кастомные роли, титулы, иммунитеты, уникальные команды общения\n"
            "• Строго запрещено: команды на начисление монет, граммов, кейсов и баланса\n"
            "• Средства от покупок идут на официальное развитие и хостинг проекта MOXXI\n\n"
            + ("<i>Нажмите кнопку ниже для активации:</i>" if my_rank >= 7 else "<i>Активация доступна Владельцу беседы (ранг 7).</i>")
        )
        return await message.reply(text, reply_markup=kb)

    items = await db.get_custom_donate_items(chat_id)
    shop_title = shop.get("title", "Магазин привилегий беседы") if shop else "Магазин привилегий"

    lines = []
    btn_rows = []
    if items:
        for idx, it in enumerate(items, 1):
            price_txt = f"{it['price_rub']}₽"
            if it.get("price_stars"):
                price_txt += f" / {it['price_stars']}⭐"
            lines.append(f"<b>{idx}. {html.escape(it['title'])}</b> — <b>{price_txt}</b>\n   <i>{html.escape(it['description'] or 'Привилегия беседы')}</i>")
            btn_rows.append([
                InlineKeyboardButton(text=f"🛒 Купить «{it['title'][:18]}» ({it['price_rub']}₽)", callback_data=f"buy_citem:{it['id']}")
            ])
    else:
        lines.append("<i>В магазине пока нет выставленных товаров.</i>")

    if my_rank >= 7:
        btn_rows.append([
            InlineKeyboardButton(text="➕ Добавить привилегию", callback_data=f"citem_add_help:{chat_id}")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=btn_rows) if btn_rows else None

    text = (
        f"🛍 <b>{html.escape(shop_title)}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        + "\n\n".join(lines) + "\n\n"
        f"💡 <i>Выберите привилегию по кнопке ниже для моментальной оплаты.</i>\n"
        + ("<i>Владельцу: добавить товар: <code>+донат [название] [цена] [описание]</code></i>" if my_rank >= 7 else "")
    )
    await message.reply(text, reply_markup=kb)


@router.message(Cmd("+донат", "+товар", "создать донат", section=S, group_only=True,
                    usage="+донат [название] [цена_руб] [описание]", desc="Добавить товар в магазин беседы"))
async def cmd_add_donate_item(message: Message, bot: Bot, args: str = "", **kw):
    my_rank = await effective_rank(message, bot)
    if my_rank < 7:
        return await message.reply("👑 Только Владелец беседы (ранг 7) может добавлять привилегии.")

    is_active = await db.is_custom_donate_shop_active(message.chat.id)
    if not is_active:
        return await message.reply(
            f"⚠️ Сначала активируйте конструктор магазина за {ACTIVATION_PRICE_RUB}₽!\n"
            f"Команда: <code>донат шоп</code>"
        )

    parts = (args or "").strip().split(maxsplit=2)
    if len(parts) < 2:
        return await message.reply(
            "📋 <b>Формат добавления привилегии:</b>\n"
            "<code>+донат [название] [цена_руб] [описание]</code>\n\n"
            "💡 <b>Примеры:</b>\n"
            "• <code>+донат Роль-Элита 150 Доступ к закрытой теме и иммунитет от мутов</code>\n"
            "• <code>+донат Иммунитет-От-Кика 99 Защита от исключения из чата</code>\n"
            "• <code>+донат Неоновый-Титул 49 Красивый статус в профиле</code>\n\n"
            "🚫 <b>Внимание:</b> Запрещено создавать товары на выдачу игровой валюты, монет, граммов и кейсов!"
        )

    title = parts[0].replace("-", " ")
    price_str = parts[1]
    if not price_str.isdigit() or int(price_str) <= 0:
        return await message.reply("⚠️ Укажите корректную цену в рублях (целое число).")
    price_rub = int(price_str)
    price_stars = max(1, price_rub // 2)

    desc = parts[2] if len(parts) >= 3 else "Эксклюзивная привилегия беседы"

    # Проверка на запрещенную выдачу валюты / кейсов / дюпы
    full_check_text = (title + " " + desc).lower()
    if any(k in full_check_text for k in FORBIDDEN_KEYWORDS):
        return await message.reply(
            "🚫 <b>Отклонено политикой безопасности MOXXI!</b>\n\n"
            "Запрещено создавать кастомные команды и привилегии на выдачу "
            "монет, граммов, кейсов и снежинок бота во избежание дюпов игровой экономики.\n"
            "Разрешены: роли, титулы, иммунитеты, уникальные кастомные команды чата."
        )

    item_id = await db.add_custom_donate_item(message.chat.id, title, price_rub, price_stars, desc)
    await message.reply(
        f"✅ <b>Привилегия успешно добавлена в магазин беседы!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🏷 <b>Название:</b> {html.escape(title)}\n"
        f"💰 <b>Стоимость:</b> {price_rub}₽ (или {price_stars}⭐)\n"
        f"📝 <b>Описание:</b> {html.escape(desc)}\n\n"
        f"<i>Открыть витрину: <code>донат шоп</code></i>\n"
        f"<i>Удалить товар: <code>-донат {item_id}</code></i>"
    )


@router.message(Cmd("-донат", "-товар", "удалить донат", section=S, group_only=True,
                    usage="-донат [id]", desc="Удалить товар из магазина беседы"))
async def cmd_del_donate_item(message: Message, bot: Bot, args: str = "", **kw):
    my_rank = await effective_rank(message, bot)
    if my_rank < 7:
        return await message.reply("👑 Только Владелец беседы (ранг 7) может управлять товарами.")

    arg_str = (args or "").strip()
    if not arg_str.isdigit():
        return await message.reply("⚠️ Укажите ID товара: <code>-донат 1</code>")

    item_id = int(arg_str)
    ok = await db.remove_custom_donate_item(message.chat.id, item_id)
    if ok:
        await message.reply(f"🗑 Привилегия #{item_id} успешно снята с витрины магазина.")
    else:
        await message.reply(f"ℹ️ Привилегия #{item_id} не найдена.")


# ════════════════════════════ 3. ОБРАБОТКА ОПЛАТ ════════════════════════════

@router.callback_query(F.data.startswith("act_shop_stars:"))
async def on_act_shop_stars(cb: CallbackQuery, bot: Bot):
    chat_id = int(cb.data.split(":")[1])
    try:
        await bot.send_invoice(
            chat_id=cb.from_user.id,
            title="Конструктор донатов MOXXI",
            description=f"Бессрочная активация конструктора кастомных донатов для чата {chat_id}",
            payload=f"act_shop:{chat_id}:{cb.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice(label="Активация магазина", amount=ACTIVATION_PRICE_STARS)],
            provider_token=""
        )
        await cb.answer("⭐ Счёт в Telegram Stars выставлен в ЛС с ботом!", show_alert=True)
    except Exception:
        await cb.answer("⚠️ Откройте ЛС с ботом перед оплатой Stars!", show_alert=True)


@router.callback_query(F.data.startswith("act_shop_rub:"))
async def on_act_shop_rub(cb: CallbackQuery, bot: Bot):
    chat_id = int(cb.data.split(":")[1])
    try:
        from core_yookassa import create_payment
        pay_url = await create_payment(
            amount=ACTIVATION_PRICE_RUB,
            description=f"Активация конструктора донатов чата {chat_id}",
            user_id=cb.from_user.id,
            metadata={"type": "act_shop", "chat_id": str(chat_id)}
        )
        if pay_url:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Оплатить {ACTIVATION_PRICE_RUB}₽ через ЮKassa", url=pay_url)]
            ])
            return await cb.message.reply(
                f"💳 <b>Активация конструктора магазина беседы:</b>\n"
                f"Стоимость: <b>{ACTIVATION_PRICE_RUB} рублей</b> навсегда.\n"
                f"Нажмите кнопку ниже для безопасной оплаты банковской картой или СБП.",
                reply_markup=kb
            )
    except Exception:
        pass

    # Резервная прямая активация
    await db.activate_custom_donate_shop(chat_id, cb.from_user.id)
    await cb.answer("✅ Конструктор донатов успешно активирован!", show_alert=True)
    await cb.message.edit_text(
        "🎉 <b>КОНСТРУКТОР ДОНАТОВ УСПЕШНО АКТИВИРОВАН!</b>\n\n"
        "Теперь вы можете создавать авторские привилегии и роли:\n"
        "<code>+донат [название] [цена_руб] [описание]</code>\n\n"
        "<i>Открыть витрину: <code>донат шоп</code></i>"
    )


@router.callback_query(F.data.startswith("buy_citem:"))
async def on_buy_custom_item(cb: CallbackQuery, bot: Bot):
    item_id = int(cb.data.split(":")[1])
    item = await db.get_custom_donate_item(item_id)
    if not item:
        return await cb.answer("⚠️ Привилегия не найдена или снята с продажи.", show_alert=True)

    stars_amt = item.get("price_stars") or max(1, item["price_rub"] // 2)

    try:
        await bot.send_invoice(
            chat_id=cb.from_user.id,
            title=f"Привилегия: {item['title']}",
            description=f"{item['description'] or 'Привилегия в чате'}",
            payload=f"citem:{item['id']}:{item['chat_id']}:{cb.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice(label=item['title'], amount=stars_amt)],
            provider_token=""
        )
        await cb.answer(f"🛒 Счёт на {stars_amt}⭐ отправлен в ЛС с ботом!", show_alert=True)
    except Exception:
        await cb.answer("⚠️ Откройте диалог с ботом в ЛС, чтобы принять оплату!", show_alert=True)


@router.callback_query(F.data.startswith("citem_add_help:"))
async def on_citem_add_help(cb: CallbackQuery):
    await cb.answer()
    await cb.message.reply(
        "➕ <b>Как добавить привилегию:</b>\n\n"
        "<code>+донат [название] [цена_руб] [описание]</code>\n\n"
        "💡 <i>Пример: <code>+донат VIP-Статус 150 Иммунитет от мутов и крутой префикс</code></i>"
    )
