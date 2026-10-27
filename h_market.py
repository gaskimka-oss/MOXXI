"""📦 Модуль P2P Рынка и Аукциона между игроками (Moxxi P2P Market).

Позволяет игрокам безопасно торговать любыми предметами из инвентаря
(ресурсы крафта, кейсы, оружие, щиты, снаряжение) за игровые монеты.
"""
from __future__ import annotations

import html
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, mention_id, money

router = Router(name="market")
S = 27  # Раздел 27: Рынок и биржа монет

ITEM_NAME_ALIASES = {
    # Ресурсы
    "дерево": ("craft_wood", "🪵 Редкая древесина"),
    "древесина": ("craft_wood", "🪵 Редкая древесина"),
    "шестеренка": ("craft_gear", "⚙️ Шестеренка"),
    "шестерня": ("craft_gear", "⚙️ Шестеренка"),
    "осколок": ("craft_shard", "💎 Осколок кристалла"),
    "кристалл": ("craft_shard", "💎 Осколок кристалла"),
    "эссенция": ("craft_essence", "🔮 Эссенция бездны"),
    # Кейсы и предметы
    "щит": ("shield_warn", "🛡️ Щит от варна"),
    "золотой кейс": ("case_gold", "🎁 Золотой кейс"),
    "кейс": ("case_gold", "🎁 Золотой кейс"),
    "мифик кейс": ("case_moxxi", "💎 Кейс Moxxi"),
    "мокси кейс": ("case_moxxi", "💎 Кейс Moxxi"),
    "спиннинг": ("item_rod_pro", "🎣 Про-Спиннинг"),
    "удочка": ("item_rod_pro", "🎣 Про-Спиннинг"),
    "меч": ("item_sword", "🗡️ Меч Безумца"),
    "бластер": ("item_blaster", "🔫 Плазменный Бластер"),
    "броня": ("item_armor", "🦺 Титановый Бронежилет"),
    "аптечка": ("item_doc_kit", "💊 Набор медика"),
}


def _market_kb(lots: list[dict], page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    rows = []
    for lot in lots:
        lid = lot["id"]
        title = f"📦 #{lid} {lot['item_name']} x{lot['count']} — {money(lot['price'])}"
        rows.append([InlineKeyboardButton(text=title, callback_data=f"mkt:buy:{lid}")])

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mkt:page:{page - 1}"))
    if page < total_pages - 1:
        nav_btns.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"mkt:page:{page + 1}"))

    if nav_btns:
        rows.append(nav_btns)

    rows.append([
        InlineKeyboardButton(text="💼 Мои лоты", callback_data="mkt:my_lots"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"mkt:page:{page}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("рынок", "биржа", "аукцион", "маркет", "лоты", section=S, rank=0,
                    usage="рынок", desc="📦 P2P Рынок и аукцион предметов между игроками"))
async def cmd_market_show(message: Message, bot: Bot, **kw):
    lots = await db.get_market_lots(limit=8, offset=0)
    total_count = await db.count_market_lots()
    total_pages = max(1, (total_count + 7) // 8)

    if not lots:
        text = (
            "📦 ✨ <b>ТОРГОВЫЙ РЫНОК MOXXI</b> ✨ 📦\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Сейчас на рынке нет активных лотов. Станьте первым торговцем!\n\n"
            "💡 <b>Как выставить предмет на продажу:</b>\n"
            "👉 <code>продать лот [предмет] [цена]</code>\n"
            "👉 <code>продать лот осколок 2 5000</code> (2 осколка за 5 000 🪙)\n"
            "👉 <code>продать лот щит 15000</code>\n"
            "👉 <code>продать лот бластер 45000</code>"
        )
        return await message.reply(text)

    text = (
        f"📦 ✨ <b>ТОРГОВЫЙ РЫНОК И АУКЦИОН (Стр. 1/{total_pages})</b> ✨ 📦\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"Здесь игроки продают ценные ресурсы, оружие и кейсы за монеты.\n"
        f"<i>Нажмите на кнопку лота ниже, чтобы моментально его купить:</i>"
    )
    await message.reply(text, reply_markup=_market_kb(lots, page=0, total_pages=total_pages))


@router.message(Cmd("продать лот", "выставить лот", "продать на рынке", section=S, rank=0,
                    usage="продать лот [предмет] [кол-во] [цена]", desc="📦 Выставить предмет на рынок"))
async def cmd_market_sell(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    if not args:
        if had_prefix or not in_group:
            return await message.reply(
                "⚠️ <b>Формат команды:</b>\n"
                "👉 <code>продать лот [предмет] [кол-во] [цена]</code>\n\n"
                "<b>Примеры:</b>\n"
                "• <code>продать лот осколок 2 5000</code> — продать 2 осколка за 5 000 🪙\n"
                "• <code>продать лот щит 1 12000</code> — продать щит за 12 000 🪙\n"
                "• <code>продать лот бластер 1 40000</code> — продать бластер\n"
                "• <code>продать лот кейс 1 8000</code> — продать золотой кейс"
            )
        return

    parts = args.strip().split()
    if len(parts) < 2:
        if had_prefix or not in_group:
            return await message.reply("⚠️ Укажите предмет и цену! Пример: <code>продать лот дерево 3 1500</code>")
        return

    # Парсим цену (последний аргумент)
    try:
        price = int(parts[-1].replace("k", "000").replace("к", "000").replace("m", "000000"))
    except ValueError:
        if had_prefix or not in_group:
            return await message.reply("❌ Неверная цена! Укажите число в конце команды.")
        return

    if price < 50 or price > 50_000_000:
        return await message.reply("❌ Цена лота должна быть от <b>50</b> до <b>50 000 000 🪙</b>.")

    # Проверяем количество
    count = 1
    item_query = " ".join(parts[:-1]).lower()
    if len(parts) >= 3 and parts[-2].isdigit():
        count = int(parts[-2])
        item_query = " ".join(parts[:-2]).lower()

    if count < 1 or count > 500:
        return await message.reply("❌ Количество должно быть от 1 до 500.")

    # Поиск предмета по алиасам
    item_id = None
    item_name = None
    for alias, (iid, iname) in ITEM_NAME_ALIASES.items():
        if alias in item_query:
            item_id = iid
            item_name = iname
            break

    if not item_id:
        return await message.reply(
            f"❌ Предмет «{html.escape(item_query)}» не найден в каталоге!\n"
            f"Доступно для продажи: <i>дерево, шестеренка, осколок, эссенция, щит, кейс, мифик кейс, спиннинг, меч, бластер, броня, аптечка</i>."
        )

    # Проверяем наличие в инвентаре игрока
    inv_row = await db.fetchone(
        "SELECT count FROM user_inventory WHERE user_id=? AND item_id=?", (uid, item_id)
    )
    has_count = int(inv_row["count"]) if inv_row else 0
    if has_count < count:
        return await message.reply(
            f"❌ <b>У вас нет столько предметов!</b>\n"
            f"В вашем инвентаре: <b>{has_count} шт.</b> (требуется {count} шт.)."
        )

    # Списываем предмет в резерв рынка
    left_count = has_count - count
    if left_count == 0:
        await db.execute("DELETE FROM user_inventory WHERE user_id=? AND item_id=?", (uid, item_id))
    else:
        await db.execute("UPDATE user_inventory SET count=? WHERE user_id=? AND item_id=?", (left_count, uid, item_id))

    seller_name = message.from_user.first_name or "Торговец"
    lot_id = await db.create_market_lot(uid, seller_name, item_id, item_name, count, price)

    await message.reply(
        f"✅ ✨ <b>ЛОТ УСПЕШНО ВЫСТАВЛЕН НА РЫНОК!</b> ✨ ✅\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📦 <b>Лот #{lot_id}:</b> {item_name} x{count}\n"
        f"💰 <b>Цена продажи:</b> <b>{money(price)}</b>\n"
        f"👤 Продавец: {mention(message.from_user)}\n\n"
        f"🏪 <i>Посмотреть все лоты:</i> <code>рынок</code>"
    )


@router.message(Cmd("мои лоты", "мои продажи", section=S, rank=0,
                    usage="мои лоты", desc="📦 Посмотреть свои лоты на рынке"))
async def cmd_my_lots(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    lots = await db.get_user_market_lots(uid)
    if not lots:
        return await message.reply("💼 У вас нет активных лотов на рынке. Выставить: <code>продать лот [предмет] [цена]</code>")

    lines = ["💼 ✨ <b>ВАШИ АКТИВНЫЕ ЛОТЫ НА РЫНКЕ:</b> ✨\n"]
    kb_rows = []
    for lot in lots:
        lid = lot["id"]
        lines.append(f"📦 <b>Лот #{lid}:</b> {lot['item_name']} x{lot['count']} — <b>{money(lot['price'])}</b>")
        kb_rows.append([InlineKeyboardButton(text=f"❌ Снять #{lid} ({lot['item_name']})", callback_data=f"mkt:cancel:{lid}")])

    kb_rows.append([InlineKeyboardButton(text="🏪 Открыть рынок", callback_data="mkt:page:0")])
    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("mkt:"))
async def cb_market_handler(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    action = parts[1]
    uid = call.from_user.id

    if action == "page":
        page = int(parts[2])
        lots = await db.get_market_lots(limit=8, offset=page * 8)
        total_count = await db.count_market_lots()
        total_pages = max(1, (total_count + 7) // 8)

        text = (
            f"📦 ✨ <b>ТОРГОВЫЙ РЫНОК И АУКЦИОН (Стр. {page + 1}/{total_pages})</b> ✨ 📦\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Здесь игроки продают ценные ресурсы, оружие и кейсы за монеты.\n"
            f"<i>Нажмите на кнопку лота ниже, чтобы моментально его купить:</i>"
        )
        try:
            await call.message.edit_text(text, reply_markup=_market_kb(lots, page=page, total_pages=total_pages))
        except Exception:
            pass
        return await call.answer()

    if action == "buy":
        lot_id = int(parts[2])
        lot = await db.get_market_lot_by_id(lot_id)
        if not lot:
            return await call.answer("❌ Этот лот уже продан или снят с продажи!", show_alert=True)

        if lot["seller_id"] == uid:
            return await call.answer("⚠️ Вы не можете купить собственный лот! Чтобы снять его, напишите «мои лоты».", show_alert=True)

        buyer = await db.get_user(uid)
        price = lot["price"]
        if buyer["balance"] < price:
            return await call.answer(f"❌ Недостаточно монет! Требуется {money(price)}.", show_alert=True)

        # Атомарно удаляем лот, чтобы исключить двойную покупку
        cur = await db.conn().execute("DELETE FROM market_lots WHERE id=?", (lot_id,))
        await db.conn().commit()
        if cur.rowcount == 0:
            return await call.answer("❌ Этот лот уже продан или снят с продажи!", show_alert=True)

        # Выполняем безопасную сделку
        await db.add_balance(uid, -price)
        await db.add_balance(lot["seller_id"], price)

        # Начисляем предмет покупателю
        now = int(time.time())
        await db.execute(
            "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + excluded.count",
            (uid, lot["item_id"], lot["item_name"], lot["count"], now)
        )

        await call.answer("🎉 Вы успешно приобрели лот!", show_alert=True)

        # Уведомляем продавца
        try:
            await bot.send_message(
                lot["seller_id"],
                f"💰 ✨ <b>ВАШ ТОВАР КУПИЛИ НА РЫНКЕ!</b> ✨ 💰\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"📦 <b>Лот #{lot_id}:</b> {lot['item_name']} x{lot['count']}\n"
                f"💵 <b>Получено:</b> <b>+{money(price)}</b> на ваш баланс!\n"
                f"👤 Покупатель: <code>{uid}</code>"
            )
        except Exception:
            pass

        # Обновляем сообщение рынка
        lots = await db.get_market_lots(limit=8, offset=0)
        total_count = await db.count_market_lots()
        total_pages = max(1, (total_count + 7) // 8)
        text = (
            f"📦 ✨ <b>ТОРГОВЫЙ РЫНОК И АУКЦИОН</b> ✨ 📦\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🎉 <b>Сделка #{lot_id} завершена!</b> {call.from_user.first_name} купил {lot['item_name']} x{lot['count']}!\n\n"
            f"<i>Доступные лоты:</i>"
        )
        try:
            await call.message.edit_text(text, reply_markup=_market_kb(lots, page=0, total_pages=total_pages))
        except Exception:
            pass

    if action == "cancel":
        lot_id = int(parts[2])
        lot = await db.get_market_lot_by_id(lot_id)
        if not lot:
            return await call.answer("Лот не найден", show_alert=True)

        if lot["seller_id"] != uid:
            return await call.answer("Это не ваш лот!", show_alert=True)

        await db.delete_market_lot(lot_id)
        now = int(time.time())
        await db.execute(
            "INSERT INTO user_inventory (user_id, item_id, item_name, count, ts) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + excluded.count",
            (uid, lot["item_id"], lot["item_name"], lot["count"], now)
        )
        await call.answer("✅ Лот снят с продажи, предметы возвращены в инвентарь!", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass

    if action == "my_lots":
        lots = await db.get_user_market_lots(uid)
        if not lots:
            return await call.answer("У вас нет активных лотов.", show_alert=True)
        lines = ["💼 <b>Ваши активные лоты:</b>\n"]
        kb_rows = []
        for lot in lots:
            lid = lot["id"]
            lines.append(f"📦 #{lid} {lot['item_name']} x{lot['count']} — {money(lot['price'])}")
            kb_rows.append([InlineKeyboardButton(text=f"❌ Снять #{lid}", callback_data=f"mkt:cancel:{lid}")])
        kb_rows.append([InlineKeyboardButton(text="⬅️ Назад в рынок", callback_data="mkt:page:0")])
        await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        return await call.answer()

    await call.answer()
