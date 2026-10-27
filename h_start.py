"""Старт в личке: капча -> Роскошное Главное Меню VIP Moxxi с разделами игр, экономики и рейдов."""
from __future__ import annotations

import asyncio
import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message,
                           PreCheckoutQuery, WebAppInfo)

import db
import config
from config import START_BALANCE
import core_keyboard as kb
from core_registry import Cmd
from h_webapp import DEFAULT_WEBAPP_URL
from utils import mention, mention_id, money

router = Router(name="start")
router.message.filter(F.chat.type == "private")

# --- Капча и Состояния ----------------------------------------------------
EMOJI = ["🍎", "🍌", "🍇", "🍓", "🍒", "🥝", "🍑", "🍍", "🥥", "🍋"]
_captcha: dict[int, dict] = {}
_pending_support_ticket: dict[int, float] = {}


def _captcha_kb(right: str, options: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=o, callback_data=f"cap:{o}") for o in options]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


async def send_captcha(message: Message) -> None:
    right = random.choice(EMOJI)
    others = random.sample([e for e in EMOJI if e != right], 5)
    options = others + [right]
    random.shuffle(options)
    _captcha[message.from_user.id] = {"right": right, "tries": 0, "ts": time.time()}
    await message.answer("🛡 Проверка, что вы человек…", reply_markup=kb.hide())
    await message.answer(
        f"🛡 <b>Проверка, что вы человек</b>\n\n"
        f"Нажмите на этот символ: <b>{right}</b>\n\n"
        f"<i>Это займёт секунду и делается один раз.</i>",
        reply_markup=_captcha_kb(right, options))


@router.callback_query(F.data.startswith("cap:"))
async def cb_captcha(call: CallbackQuery, bot: Bot):
    data = _captcha.get(call.from_user.id)
    if not data:
        await call.message.edit_text("Капча устарела. Отправьте /start ещё раз.")
        return await call.answer()
    choice = call.data.split(":", 1)[1]
    if choice != data["right"]:
        data["tries"] += 1
        if data["tries"] >= 3:
            _captcha.pop(call.from_user.id, None)
            await call.message.edit_text(
                "❌ Слишком много ошибок.\nОтправьте /start, чтобы попробовать снова.")
            return await call.answer("Не угадали", show_alert=True)
        return await call.answer(f"❌ Не то. Попыток осталось: {3 - data['tries']}",
                                 show_alert=True)
    _captcha.pop(call.from_user.id, None)
    await db.get_user(call.from_user.id)
    await db.execute("UPDATE users SET verified=1 WHERE user_id=?", (call.from_user.id,))
    u = await db.get_user(call.from_user.id)
    me = await bot.me()
    await call.message.edit_text(await main_text(call.from_user.first_name, u),
                                 reply_markup=await main_kb(call.from_user.id, me.username))
    await call.answer("✅ Проверка пройдена!")


async def _delayed_delete(msg: Message, delay: float = 1.5) -> None:
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# --- Главное меню ---------------------------------------------------------
async def main_text(name: str | None, u: dict) -> str:
    uid = u["user_id"]
    u_dict = dict(u)
    from h_modules import _rep_title
    rep_val = u_dict.get("rep", 0) or 0
    xp_val = u_dict.get("xp", 0) or 0
    rep_title = _rep_title(rep_val)

    inv_rows = await db.fetchall("SELECT count FROM user_inventory WHERE user_id=? AND count > 0", (uid,))
    inv_count = sum(r["count"] for r in inv_rows)

    is_owner = config.is_bot_owner(uid)
    staff_rank = 4 if is_owner else (await db.get_bot_staff_rank(uid))
    v_lvl, _, v_act = await db.get_vip_info(uid)

    if staff_rank >= 4:
        status_str = "👑 Владелец проекта"
    elif staff_rank == 3:
        status_str = "🥇 Администратор"
    elif staff_rank == 2:
        status_str = "🥈 Модератор"
    elif staff_rank == 1:
        status_str = "🥉 Хелпер"
    elif v_act:
        status_str = "🌟 VIP+ Diamond" if v_lvl >= 2 else "⭐️ VIP"
    else:
        status_str = "🔹 Участник"

    return (
        f"🍸 ✨ <b>MOXXI 2.1 — ГЛАВНОЕ МЕНЮ</b> ✨ 🍸\n"
        f"✦ ══ • ⊰ 💖 🔮 🎰 🏢 ⚔️ 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"👋 Рады видеть, <b>{html.escape(name or 'Боец')}</b>!\n"
        f"🔥 <i>Игровой мир азарта, экономики, рейдов и умного ИИ!</i>\n\n"
        f"┌ 💎 <b>Ваш статус:</b> {status_str}\n"
        f"├ 💰 <b>Баланс:</b> <code>{money(u_dict.get('balance', 0))}</code>\n"
        f"├ ⚡️ <b>Опыт:</b> <code>{xp_val} XP</code>\n"
        f"├ ⭐️ <b>Репутация:</b> <code>{rep_val}</code> <i>({rep_title})</i>\n"
        f"└ 🎒 <b>Инвентарь:</b> <code>{inv_count} предм.</code>\n\n"
        f"✦ ══════════════════════════════ ✦\n"
        f"🚀 <b>Выберите интересующий раздел:</b>"
    )


async def main_kb(uid: int = 0, bot_username: str = "moxxichat_bot") -> InlineKeyboardMarkup:
    rights = ("change_info+delete_messages+restrict_members+invite_users"
              "+pin_messages+manage_chat")
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin={rights}"

    rows = [
        [
            InlineKeyboardButton(text="➕ Добавить бота в беседу", url=add_url)
        ],
        [
            InlineKeyboardButton(text="🎰 Казино и Игры", callback_data="mm:grams"),
            InlineKeyboardButton(text="🏢 Бизнесы и Рынок", callback_data="mm:biz"),
        ],
        [
            InlineKeyboardButton(text="🐉 Рейдовые Боссы", callback_data="mm:boss"),
            InlineKeyboardButton(text="⚔️ PvP-Дуэли", callback_data="mm:duels"),
        ],
        [
            InlineKeyboardButton(text="🛍 Магазин и Кейсы", callback_data="mm:shop_menu"),
            InlineKeyboardButton(text="🎣 Рыбалка и Крафт", callback_data="mm:fish"),
        ],
        [
            InlineKeyboardButton(text="📜 Квесты и Ачивки", callback_data="mm:quests"),
            InlineKeyboardButton(text="🏆 Топ Рейтинги", callback_data="mm:tops"),
        ],
        [
            InlineKeyboardButton(text="🎁 Бонусы", callback_data="mm:bonus"),
            InlineKeyboardButton(text="📖 Все Команды", callback_data="mm:cmds"),
        ],
        [
            InlineKeyboardButton(text="🆘 Написать в техподдержку", callback_data="mm:support")
        ]
    ]

    is_owner = config.is_bot_owner(uid)
    staff_rank = 4 if is_owner else (await db.get_bot_staff_rank(uid))
    if staff_rank >= 1:
        rows.insert(0, [
            InlineKeyboardButton(text="👑 Админ-Панель (Управление)", callback_data="mm:admin_panel")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(extra: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    try:
        await db.track_daily_activity(message.from_user.id, is_start=True)
    except Exception:
        pass
    u = await db.get_user(message.from_user.id)
    if not u["verified"]:
        return await send_captcha(message)
    me = await bot.me()
    try:
        rm = await message.answer("🧹 <i>Обновление интерфейса...</i>", reply_markup=kb.hide())
        asyncio.create_task(_delayed_delete(rm, 1.5))
    except Exception:
        pass
    await message.answer(await main_text(message.from_user.first_name, u),
                         reply_markup=await main_kb(message.from_user.id, me.username))


@router.message(Cmd("меню", "menu", "главное меню", section=32, usage="меню", desc="Главное меню бота"))
async def cmd_menu(message: Message, bot: Bot, **kw):
    u = await db.get_user(message.from_user.id)
    if not u["verified"]:
        return await send_captcha(message)
    me = await bot.me()
    try:
        rm = await message.answer("🧹 <i>Обновление интерфейса...</i>", reply_markup=kb.hide())
        asyncio.create_task(_delayed_delete(rm, 1.5))
    except Exception:
        pass
    await message.answer(await main_text(message.from_user.first_name, u),
                         reply_markup=await main_kb(message.from_user.id, me.username))


# --- Текстовые разделы ---------------------------------------------------

BOSS_MENU_TEXT = """🐉 ✨ <b>РЕЙДОВЫЕ БОССЫ ЧАТА</b> ✨ 🐉
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
В беседах регулярно появляются свирепые Рейдовые Боссы с огромным призовым кушем!

⏰ <b>Расписание спавнов:</b> 08:00, 12:00, 16:00, 20:00 (МСК).
⛔️ <b>Лимит:</b> максимум 4 босса в день на чат.
🎯 <b>Изоляция темы:</b> <code>+тема босс</code> — битвы проходят строго в отдельной ветке!

⚔️ <b>Механика боя:</b>
• Атаки: <code>ударить</code>, <code>выстрел</code>, <code>атака</code> или кнопка «⚔️ НАНЕСТИ УДАР».
• Крит: 22% шанс нанести <b>Критический урон x2.5</b>!
• Контратака босса: босс может отправить бойца в <b>нокаут</b>!
• Лечение упавших: <code>хил @юзер</code>, <code>возродить</code> или <code>аптечка</code>.

🛍 <b>Боевое снаряжение (в магазине):</b>
• 🗡️ Меч (+50% урона), 🔫 Бластер (+120% урона), 🦺 Броня (-65% шанс нокаута)."""

DUELS_MENU_TEXT = """⚔️ ✨ <b>СМЕРТЕЛЬНЫЕ PvP-ДУЭЛИ</b> ✨ ⚔️
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Бросайте вызовы другим участникам и побеждайте в дуэлях на монеты!

🎯 <b>Как вызвать игрока:</b>
• Реплаем: <code>дуэль 1000</code> (на 1 000 монет) или <code>дуэль</code> (без ставки).
• С юзернеймом: <code>дуэль @username 5000</code>.

🔥 <b>Особенности боя:</b>
• Оружие из инвентаря повышает урон и шанс критического выстрела!
• Титановый бронежилет даёт шанс парировать входящую пулю.
• Победитель забирает весь банк ставок и получает опыт.

🏆 Статистика и рейтинг: <code>топ дуэлей</code> · <code>мои дуэли</code>"""

FISH_MENU_TEXT = """🎣 ✨ <b>РЫБАЛКА И ВЕРСТАК КРАФТА</b> ✨ 🎣
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Отправляйтесь на водоем, ловите редкую рыбу и крафтите ценные артефакты!

🎣 <b>Рыбалка:</b>
• Команда: <code>рыбалка</code> (раз в 15 минут, а с Про-Спиннингом — раз в 8 мин).
• 8 видов улова: от <i>Карася</i> до <i>Золотой Рыбки</i> и <i>Древнего Кракена</i>!
• Затонувшие сундуки с монетами, кейсами и ресурсами.
• <code>садок</code> — посмотреть улов · <code>продать рыбу</code> — сдать за монеты.

🛠 <b>Верстак Крафта (<code>крафт</code>):</b>
• Из найденных деталей можно создать 🎣 Про-Спиннинг, 🛡️ Щиты от варна и 🎁 Золотые кейсы!"""

QUESTS_MENU_TEXT = """📜 ✨ <b>КВЕСТЫ И ДОСТИЖЕНИЯ</b> ✨ 📜
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Выполняйте ежедневные задания и открывайте достижения за крутые награды!

📜 <b>Ежедневные квесты (<code>квесты</code>):</b>
• 3 уникальных задания каждый день в 00:00.
• Награды за каждый квест: монеты и опыт!
• 👑 <b>Супер-Бонус:</b> 🎁 <b>Золотой кейс</b> + <b>2 000 монет</b> за закрытие всех 3 квестов!

🏆 <b>Достижения (<code>достижения</code>):</b>
• 11+ достижений по всем направлениям (боссы, дуэли, рыбалка, репутация).
• Дают уникальные звания и денежные выплаты!"""

TOPS_MENU_TEXT = """🏆 ✨ <b>РЕЙТИНГИ И ТОПЫ БОТА</b> ✨ 🏆
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Выберите интересующую таблицу лидеров:"""

SETUP_TEXT = """⚙️ <b>Установка и быстрая настройка бота</b>
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
<b>1. Добавьте бота в чат:</b>
Выдайте права администратора (кнопка сама предложит нужные галочки).

<b>2. Назначьте админов:</b>
• <code>+модер 3 @user</code> — назначить администратора
• <code>кто админ</code> — посмотреть красивый VIP-состав

<b>3. Настройте ветки/темы чата:</b>
• <code>+тема босс</code> — привязать тему для рейдовых боссов
• <code>тема смс</code> — привязать тему для общения и анонсов

<b>4. Полезные команды:</b>
• <code>ночной режим 00:00 08:00</code> — включить тихий час
• <code>анкета обязательна вкл</code> — обязательное описание новичков"""

BONUS_TEXT = """🎁 ✨ <b>ЕЖЕДНЕВНЫЕ БОНУСЫ И НАГРАДЫ</b> ✨ 🎁
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Забирайте бесплатные монеты и прокачивайте свой баланс!

🎁 <b>Ежедневный бонус (<code>бонус</code>):</b>
• Случайная награда: <b>от 1 до 30 000 🌑</b>!
• Базовый кулдаун: раз в 4 часа (для VIP — раз в 2 часа, для VIP+ — раз в 1 час).
• 🌐 <b>Глобальный таймер:</b> бонус един для всех бесед и ЛС (нельзя получить дважды в разных группах).

💼 <b>Заработок на работе (<code>работа</code>):</b>
• Зарабатывайте от 150 до 900 🌑 каждый час.
• 👑 VIP получают <b>+50%</b>, а VIP+ — <b>+100%</b> к зарплате!

🦹 <b>Преступления (<code>крайм</code>):</b>
• Рискованный заработок от 400 до 3 000 🌑 раз в 1.5 часа (шанс 55%)."""

ECONOMY_TEXT = """🏢 ✨ <b>БИЗНЕСЫ И ЭКОНОМИКА</b> ✨ 🏢
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Покупайте предприятия, получайте пассивный доход и развивайте империю!

🏢 <b>Предприятия (<code>бизнесы</code>):</b>
• Покупка: <code>купить [название]</code> (Ферма, Кафе, Автосервис, ТЦ, Нефтяная вышка).
• Сбор прибыли: <code>собрать</code> — накопительный пассивный доход!
• Продажа: <code>продать [название]</code> — возврат 75% стоимости.

📊 <b>Рынок и Торговля (<code>рынок</code>):</b>
• Покупка и продажа ресурсов, снаряжения и кейсов между игроками.
• <code>банк</code> — открытие вклада под 2% в день."""


@router.callback_query(F.data.startswith("mm:"))
async def cb_menu(call: CallbackQuery, bot: Bot):
    what = call.data.split(":", 1)[1]
    uid = call.from_user.id
    me = await bot.me()

    if what == "main":
        u = await db.get_user(uid)
        await call.message.edit_text(await main_text(call.from_user.first_name, u),
                                     reply_markup=await main_kb(uid, me.username))
        return await call.answer()

    if what == "admin_panel":
        rank = 4 if config.is_bot_owner(uid) else (await db.get_bot_staff_rank(uid))
        if rank < 1:
            return await call.answer("🔒 Доступ только для администрации бота!", show_alert=True)
        from h_owner_panel import _owner_panel_kb, STAFF_RANKS_DESC
        stats = await db.get_global_bot_stats()
        rank_name = STAFF_RANKS_DESC.get(rank, f"Ранг {rank}")
        text = (
            f"👑 ✨ <b>ПАНЕЛЬ УПРАВЛЕНИЯ MOXXI BOT</b> ✨ 👑\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>Сотрудник:</b> {mention_id(uid, call.from_user.first_name)} (<code>{uid}</code>)\n"
            f"🔰 <b>Ваш статус:</b> <b>{rank_name}</b>\n\n"
            f"📊 <b>Сводка системы:</b>\n"
            f"• Пользователей в базе: <b>{stats['users_count']}</b>\n"
            f"• Подключенных чатов: <b>{stats['chats_count']}</b>\n"
            f"• Открытых тикетов техподдержки: <b>{stats['open_tickets']} 🆘</b>\n"
            f"• Идей на рассмотрении: <b>{stats['pending_ideas']} 💡</b>\n"
            f"• Всего отзывов: <b>{stats['reviews_count']} ⭐</b>\n"
            f"• Заблокированных групп (ЧС): <b>{stats['blacklisted_chats']} ⛔</b>\n\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👇 <i>Выберите нужный раздел панели ниже:</i>"
        )
        await call.message.edit_text(text, reply_markup=_owner_panel_kb(rank, stats['open_tickets']))
        return await call.answer()

    if what == "boss":
        await call.message.edit_text(BOSS_MENU_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "duels":
        await call.message.edit_text(DUELS_MENU_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "fish":
        await call.message.edit_text(FISH_MENU_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "quests":
        await call.message.edit_text(QUESTS_MENU_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "shop_menu":
        kb = back_kb([
            [
                InlineKeyboardButton(text="💳 Оплата в рублях (СБП / Карты РФ — ВЫГОДНЕЕ 🔥)", callback_data="shop_tab:rub")
            ],
            [
                InlineKeyboardButton(text="⭐️ Оплата Telegram Stars", callback_data="shop_tab:stars")
            ],
            [
                InlineKeyboardButton(text="🪙 Пакеты монет (Рубли & Stars)", callback_data="shop_tab:coins_pack")
            ],
            [
                InlineKeyboardButton(text="📦 Игровой магазин (Оружие & Броня)", callback_data="mm:items_shop"),
                InlineKeyboardButton(text="🎁 Кейсы и лутбоксы", callback_data="mm:cases_shop")
            ]
        ])
        shop_info = (
            "🛍 ✨ <b>МАГАЗИН И КЕЙСЫ MOXXI</b> ✨ 🛍\n"
            "✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
            "Здесь вы можете выбрать удобный способ оплаты и снаряжение:\n\n"
            "💳 <b>Оплата в рублях (ЮKassa / СБП / Карты РФ):</b>\n"
            "🔥 <b>Скидка до 25%!</b> Рублями покупать выгоднее всего:\n"
            "• ⭐️ <b>VIP (30 дн)</b> — <b>39 ₽</b>\n"
            "• 🌟 <b>VIP+ Diamond (30 дн)</b> — <b>79 ₽</b>\n"
            "• 🧠 <b>ИИ-Подписка (30 дн)</b> — <b>29 ₽</b>\n"
            "• 🍬 <b>1 000 000 монет</b> — <b>15 ₽</b>\n"
            "• 🏆 <b>20 000 000 монет</b> — <b>149 ₽</b>\n\n"
            "⭐️ <b>Оплата Telegram Stars:</b>\n"
            "Оплата звёздами прямо в приложении Telegram (VIP — 25 ⭐️, VIP+ — 50 ⭐️).\n\n"
            "🎒 <b>Игровые команды:</b>\n"
            "• <code>магазин</code> — оружие, броня, аптечки и щиты от варна;\n"
            "• <code>кейсы</code> — открытие 4 уровней кейсов от Бронзового до Мифика;\n"
            "• <code>инвентарь</code> — снаряжение и экипировка вашего бойца.\n\n"
            "👇 <b>Выберите желаемый раздел в меню ниже:</b>"
        )
        await call.message.edit_text(shop_info, reply_markup=kb)
        return await call.answer()

    if what == "items_shop":
        txt = (
            "📦 <b>ИГРОВОЙ МАГАЗИН ПРЕДМЕТОВ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "В боте доступно различное боевое снаряжение за внутриигровые монеты (🪙):\n\n"
            "• <code>магазин</code> — полный список оружия, брони, аптечек и щитов;\n"
            "• <code>купить [название/номер]</code> — приобрести предмет;\n"
            "• <code>инвентарь</code> — надеть или использовать экипировку;\n"
            "• <code>щит</code> — проверить статус вашей защиты от варна."
        )
        await call.message.edit_text(txt, reply_markup=back_kb([[InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="mm:shop_menu")]]))
        return await call.answer()

    if what == "cases_shop":
        txt = (
            "🎁 <b>КЕЙСЫ И ЛУТБОКСЫ MOXXI</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Испытайте удачу и выбивайте редчайшие предметы, миллионы монет и VIP!\n\n"
            "• <code>кейсы</code> — посмотреть список доступных кейсов и призы;\n"
            "• <code>открыть кейс [1-4]</code> — открыть кейс;\n"
            "• <code>рулетка</code> — крутить ежедневное Колесо Фортуны бесплатно!\n\n"
            "💡 <i>Владельцы ранга VIP+ получают 1 Алмазный кейс каждую неделю бесплатно!</i>"
        )
        await call.message.edit_text(txt, reply_markup=back_kb([[InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="mm:shop_menu")]]))
        return await call.answer()

    if what == "stars_shop":
        await call.message.edit_text(SHOP_TEXT, reply_markup=shop_kb())
        return await call.answer()

    if what == "setup":
        await call.message.edit_text(SETUP_TEXT, reply_markup=back_kb(), disable_web_page_preview=True)
        return await call.answer()

    if what == "tops":
        kb = back_kb([
            [InlineKeyboardButton(text="💎 Топ богачей", callback_data="mm:toprich"),
             InlineKeyboardButton(text="🏆 Топ активности", callback_data="mm:topday")],
            [InlineKeyboardButton(text="⚔️ Топ дуэлянтов", callback_data="mm:topduels"),
             InlineKeyboardButton(text="🌟 Топ репутации", callback_data="mm:toprep")],
            [InlineKeyboardButton(text="🏰 Топ кланов", callback_data="mm:topclans")]
        ])
        await call.message.edit_text(TOPS_MENU_TEXT, reply_markup=kb)
        return await call.answer()

    if what == "topduels":
        rows = await db.fetchall(
            "SELECT d.user_id, d.wins, d.losses, d.total_earned, u.first_name FROM duels_stats d "
            "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.wins > 0 ORDER BY d.wins DESC LIMIT 10"
        )
        if not rows:
            txt = "⚔️ <b>Топ дуэлянтов</b>\n\nПока пусто."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
            txt = "⚔️ <b>Топ лучших PvP-дуэлянтов</b>\n\n" + "\n".join(
                f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — <b>{r['wins']} побед</b>"
                for i, r in enumerate(rows))
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "toprep":
        rows = await db.fetchall(
            "SELECT user_id, first_name, rep FROM users WHERE rep <> 0 ORDER BY rep DESC LIMIT 10"
        )
        if not rows:
            txt = "🌟 <b>Топ репутации</b>\n\nПока пусто."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
            txt = "🌟 <b>Топ авторитетов по репутации</b>\n\n" + "\n".join(
                f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — ⭐️ <b>{r['rep']}</b>"
                for i, r in enumerate(rows))
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "topclans":
        rows = await db.fetchall(
            "SELECT id, name, balance FROM clans ORDER BY balance DESC LIMIT 10"
        )
        if not rows:
            txt = "🏰 <b>Топ кланов</b>\n\nКланов пока нет."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
            txt = "🏰 <b>Топ сильнейших кланов</b>\n\n" + "\n".join(
                f"{medals[i]} <b>«{html.escape(r['name'])}»</b> — 💰 {money(r['balance'])}"
                for i, r in enumerate(rows))
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "topday":
        day = time.strftime("%Y-%m-%d")
        rows = await db.fetchall(
            "SELECT d.user_id, SUM(d.messages) m, u.first_name FROM daily_stats d "
            "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.day=? "
            "GROUP BY d.user_id ORDER BY m DESC LIMIT 10", (day,))
        if not rows:
            txt = "🏆 <b>Топ дня</b>\n\nСегодня ещё никто не активничал."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
            txt = "🏆 <b>Топ дня по активности</b>\n\n" + "\n".join(
                f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — "
                f"{r['m']} сообщ." for i, r in enumerate(rows))
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "toprich":
        rows = await db.fetchall(
            "SELECT user_id, first_name, username, balance FROM users ORDER BY balance DESC LIMIT 10")
        if not rows:
            txt = "💎 <b>Топ богачей</b>\n\nПока пусто."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
            txt = "💎 <b>Топ богачей по балансу</b>\n\n" + "\n".join(
                f"{medals[i]} {mention_id(r['user_id'], r['first_name'] or r['username'] or str(r['user_id']))} — <b>{money(r['balance'])}</b>"
                for i, r in enumerate(rows))
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "biz":
        from h_start import ECONOMY_TEXT
        await call.message.edit_text(ECONOMY_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "bonus":
        from h_start import BONUS_TEXT
        await call.message.edit_text(BONUS_TEXT, reply_markup=back_kb())
        return await call.answer()

    if what == "grams":
        from h_grams import COIN, c
        bal = await db.get_coins(uid)
        vip_lvl, _, vip_active = await db.get_vip_info(uid)
        cd = 3600 if (vip_active and vip_lvl >= 2) else (7200 if (vip_active and vip_lvl >= 1) else 14400)
        left = await db.cooldown_left(uid, "gram_daily", cd)
        from utils import hms
        status = (f"⏳ Следующий бонус через <b>{hms(left)}</b>" if left
                  else f"🎁 <b>Бонус готов!</b> Нажмите кнопку ниже")
        g_text = (f"🎮 <b>Игры, казино и монеты</b>\n\n"
                  f"💰 Ваш баланс: <b>{c(bal)}</b>\n\n"
                  f"{status}\n\n"
                  f"🎲 Бонус: <b>от 1 до 30 000 🪙</b> (раз в {hms(cd)})\n\n"
                  f"🎰 Игры: <code>казик</code>, <code>мины</code>, <code>дартс</code>, <code>краш</code>, <code>колесо</code>, <code>рулетка</code>, <code>кубик</code>\n"
                  f"🏢 Предприятия: <code>бизнесы</code> · Сбор дохода: <code>собрать</code>")
        kb_rows = []
        if not left:
            kb_rows.append([InlineKeyboardButton(text="🎁 Забрать бонус (1 - 30к 🪙)", callback_data="gbonus")])
        kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")])
        await call.message.edit_text(g_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        return await call.answer()

    if what == "cmds":
        from h_helpmenu import _menu_kb, _menu_text
        await call.message.edit_text(
            _menu_text(), reply_markup=_menu_kb(0),
            disable_web_page_preview=True)
        return await call.answer()

    if what == "reviews":
        stats = await db.get_review_stats()
        reviews = await db.get_reviews(5)
        rev_lines = []
        for r in reviews:
            stars = "⭐" * r["rating"]
            user_tag = html.escape(r["user_name"] or "Игрок")
            rev_lines.append(f"• <b>{user_tag}</b> {stars}\n  «{html.escape(r['text'])}»")
        latest_txt = "\n\n".join(rev_lines) if rev_lines else "<i>Пока нет отзывов. Напишите команду <code>отзыв</code>!</i>"
        txt = (
            f"⭐ ✨ <b>ОТЗЫВЫ О БОТЕ И ПОКУПКАХ</b> ✨ ⭐\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🌟 <b>Рейтинг:</b> <b>{stats['avg_rating']} / 5.0 ⭐</b> (всего: <b>{stats['total']}</b> отзывов)\n\n"
            f"📝 <b>Последние отзывы:</b>\n\n{latest_txt}\n\n"
            f"✍️ <b>Оставить отзыв:</b> отправьте <code>отзыв [текст]</code>"
        )
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "ideas":
        sug_list = await db.get_suggestions(5)
        sug_lines = []
        for s in sug_list:
            sug_lines.append(f"• <b>#{s['id']}</b> (👍 {s['upvotes']} | 👎 {s['downvotes']})\n  «{html.escape(s['text'][:80])}»")
        list_txt = "\n\n".join(sug_lines) if sug_lines else "<i>Пока нет предложений. Будьте первым!</i>"
        txt = (
            f"💡 ✨ <b>БАНК ИДЕЙ И ПРЕДЛОЖЕНИЙ</b> ✨ 💡\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Предлагайте свои идеи для улучшения бота!\n\n"
            f"{list_txt}\n\n"
            f"✍️ <b>Предложить идею:</b> напишите <code>идея [текст]</code>"
        )
        await call.message.edit_text(txt, reply_markup=back_kb())
        return await call.answer()

    if what == "support":
        from utils import hms
        cd_left = await db.cooldown_left(uid, "support_ticket", 1800)
        if cd_left > 0:
            txt = (
                f"⏳ <b>Кулдаун на обращение в техподдержку!</b>\n\n"
                f"Вы уже недавно отправили запрос в техподдержку.\n"
                f"Пожалуйста, подождите ещё <b>{hms(cd_left)}</b>, прежде чем подавать новый тикет.\n\n"
                f"🛡 <i>Защита от спама: не чаще одного обращения в 30 минут. "
                f"Администрация уже получила вашу предыдущую заявку и скоро ответит!</i>"
            )
            await call.message.edit_text(txt, reply_markup=back_kb())
            return await call.answer("⏳ Кулдаун техподдержки", show_alert=False)

        txt = (
            f"🆘 ✨ <b>СЛУЖБА ТЕХПОДДЕРЖКИ MOXXI</b> ✨ 🆘\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Возник вопрос, баг, ошибка при переводе или нужна помощь?\n\n"
            f"Нажмите кнопку <b>«✍️ Написать в техподдержку»</b> ниже и отправьте причину и суть проблемы.\n\n"
            f"⏱ <b>Защита от спама:</b> после отправки запроса действует кулдаун <b>30 минут</b>.\n"
            f"Администратор ответит вам прямо в этот чат!"
        )
        kb_rows = [
            [InlineKeyboardButton(text="✍️ Написать в техподдержку", callback_data="supp:write")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")]
        ]
        await call.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        return await call.answer()

    await call.answer()


@router.callback_query(F.data == "supp:write")
async def cb_supp_write(call: CallbackQuery):
    from utils import hms
    uid = call.from_user.id
    cd_left = await db.cooldown_left(uid, "support_ticket", 1800)
    if cd_left > 0:
        return await call.answer(f"⏳ Кулдаун еще {hms(cd_left)}!", show_alert=True)

    _pending_support_ticket[uid] = time.time()
    txt = (
        f"✍️ <b>По какой причине вы обращаетесь в техподдержку?</b>\n\n"
        f"Отправьте следующим сообщением подробное описание проблемы "
        f"(укажите причину, ник, сумму или подробности ситуации):\n\n"
        f"<i>Пример: «Случайно ошибся ID при переводе монет»</i>"
    )
    await call.message.edit_text(
        txt,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="supp:cancel")
        ]])
    )
    await call.answer()


@router.callback_query(F.data == "supp:cancel")
async def cb_supp_cancel(call: CallbackQuery, bot: Bot):
    _pending_support_ticket.pop(call.from_user.id, None)
    u = await db.get_user(call.from_user.id)
    me = await bot.me()
    await call.message.edit_text(await main_text(call.from_user.first_name, u),
                                 reply_markup=await main_kb(call.from_user.id, me.username))
    await call.answer("Обращение отменено")


def _is_pending_support(m: Message) -> bool:
    if not m.from_user or m.from_user.id not in _pending_support_ticket:
        return False
    # Авто-сброс ожидания через 5 минут
    if time.time() - _pending_support_ticket.get(m.from_user.id, 0) > 300:
        _pending_support_ticket.pop(m.from_user.id, None)
        return False
    txt = (m.text or "").strip()
    if not txt:
        return False
    # Если сообщение начинается со знака команды (+, /, !, .) — НЕ перехватывать как тикет!
    if txt.startswith(("+", "/", "!", ".")):
        _pending_support_ticket.pop(m.from_user.id, None)
        return False
    # Игнорируем навигационные команды
    low = txt.lower()
    if low in ("отмена", "отменить", "меню", "menu", "старт", "start", "помощь", "команды", "баланс", "профиль"):
        _pending_support_ticket.pop(m.from_user.id, None)
        return False
    return True


@router.message(F.text, _is_pending_support)
async def msg_receive_support_ticket(message: Message, bot: Bot):
    uid = message.from_user.id
    from utils import hms
    cd_left = await db.cooldown_left(uid, "support_ticket", 1800)
    if cd_left > 0:
        _pending_support_ticket.pop(uid, None)
        return await message.reply(
            f"⏳ <b>Кулдаун на обращение в техподдержку!</b>\n\n"
            f"Вы уже недавно отправили запрос. Пожалуйста, подождите ещё <b>{hms(cd_left)}</b>.\n"
            f"🛡 <i>Защита от спама: 30 минут.</i>"
        )

    _pending_support_ticket.pop(uid, None)
    txt = (message.text or "").strip()
    if not txt:
        return await message.reply("❌ Сообщение не может быть пустым. Откройте меню и попробуйте снова.")

    # Включаем кулдаун на 30 минут (1800 секунд)
    await db.set_cooldown(uid, "support_ticket")

    from h_community_support import analyze_support_ticket, ticket_admin_kb
    name = message.from_user.first_name or "Пользователь"

    is_valid, reason = await analyze_support_ticket(txt)
    ticket_status = "open" if is_valid else "auto_rejected"
    ticket_id = await db.create_support_ticket(uid, name, txt, status=ticket_status)

    if not is_valid:
        # Автоматический отказ ИИ с разъяснением
        await message.reply(
            f"❌ 🤖 <b>Обращение отклонено ИИ (Тикет #{ticket_id})</b>\n\n"
            f"📝 <b>Ваш текст:</b> «<i>{html.escape(txt)}</i>»\n"
            f"⚠️ <b>Причина отказа ИИ:</b> {html.escape(reason)}\n\n"
            f"💡 <i>Техподдержка принимает только вопросы по работе бота (оплата, звёзды, монеты, баги, команды или жалобы). Бытовой оффтоп и бессмысленные сообщения отклоняются автоматически.</i>\n\n"
            f"👨‍💻 <b>Вторичная проверка:</b> Ваше обращение всё равно отправлено администрации. Если ИИ ошибся, администратор ответит вам лично!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")
            ]])
        )
        admin_notify = (
            f"🆘 🔔 <b>НОВЫЙ ТИКЕТ В ТЕХПОДДЕРЖКУ #{ticket_id}</b>\n"
            f"⚠️ <b>СТАТУС: ❌ ОТКЛОНЁН ИИ</b>\n"
            f"🤖 <b>Причина ИИ:</b> {html.escape(reason)}\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>От:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
            f"📝 <b>Причина / Проблема:</b>\n«{html.escape(txt)}»\n\n"
            f"💡 <i>ИИ посчитал обращение бессмысленным и дал автоотказ. "
            f"Если ИИ ошибся, вы можете ответить пользователю или закрыть тикет:</i>\n\n"
            f"• Свой ответ: <code>+ответ {ticket_id} [текст вашего ответа]</code>\n"
            f"• Быстрый шаблон: <code>автоответ тикет {ticket_id} [1-5]</code>\n"
            f"• Закрыть тикет: <code>закрыть тикет {ticket_id}</code>"
        )
    else:
        # Валидный тикет
        await message.reply(
            f"✅ <b>Ваше обращение принято! (Тикет #{ticket_id})</b>\n\n"
            f"📝 <b>Причина / Описание:</b>\n«<i>{html.escape(txt)}</i>»\n\n"
            f"⏳ <b>Выдан кулдаун: 30 минут</b> на повторные обращения (защита от спама).\n"
            f"👨‍💻 Администрация рассмотрит ваш тикет в ближайшее время и пришлёт ответ прямо сюда в личные сообщения!\n"
            f"🤖 <i>Если администрация не ответит в течение 6 часов, ИИ-Ассистент автоматически поможет решить вопрос.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")
            ]])
        )
        admin_notify = (
            f"🆘 🔔 <b>НОВЫЙ ТИКЕТ В ТЕХПОДДЕРЖКУ #{ticket_id}</b>\n"
            f"✅ <b>СТАТУС: ПРИНЯТ (ПРОВЕРЕН ИИ)</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👤 <b>От:</b> {mention_id(uid, name)} (<code>{uid}</code>)\n"
            f"📝 <b>Причина / Проблема:</b>\n«{html.escape(txt)}»\n\n"
            f"💡 <b>Команды для ответа:</b>\n"
            f"• Свой ответ: <code>+ответ {ticket_id} [текст вашего ответа]</code>\n"
            f"• Быстрый шаблон: <code>автоответ тикет {ticket_id} [1-5]</code>\n"
            f"• Закрыть тикет: <code>закрыть тикет {ticket_id}</code>"
        )

    # Уведомляем владельцев бота и поддержку
    recipients = set(getattr(config, "BOT_OWNERS", {config.OWNER_ID}))
    try:
        staff_rows = await db.get_all_bot_staff()
        for sm in staff_rows:
            if sm.get("rank", 0) >= 1:
                recipients.add(sm["user_id"])
    except Exception:
        pass

    supp_chat = await db.get_global_setting("global_support_chat", "")
    supp_topic = await db.get_global_setting("global_support_chat_topic", "")
    if supp_chat:
        try:
            target_cid = int(supp_chat) if (supp_chat.startswith("-") or supp_chat.isdigit()) else supp_chat
            tid = int(supp_topic) if supp_topic and supp_topic.isdigit() else None
            await bot.send_message(target_cid, admin_notify, reply_markup=ticket_admin_kb(ticket_id), message_thread_id=tid)
        except Exception:
            pass

    for rid in recipients:
        try:
            await bot.send_message(rid, admin_notify, reply_markup=ticket_admin_kb(ticket_id))
        except Exception:
            pass


# --- Магазин за Telegram Stars -------------------------------------------
STARS_PACKS = {
    "vip_30": (25, 0, "⭐️ VIP-статус (30 дней)", "vip", 1, 30),
    "vipplus_30": (50, 0, "🌟 VIP+ Diamond (30 дней)", "vip", 2, 30),
    "ai_pass_30": (15, 0, "🧠 ИИ-Подписка (30 дней)", "ai_pass", 0, 30),
    "coins_1m": (10, 1_000_000, "🍬 1 000 000 монет (1kk)", "coins", 0, 0),
    "coins_3m": (20, 3_000_000, "🎁 3 000 000 монет (3kk)", "coins", 0, 0),
    "coins_7m": (35, 7_000_000, "💎 7 000 000 монет (7kk)", "coins", 0, 0),
    "coins_12m": (55, 12_000_000, "👑 12 000 000 монет (12kk)", "coins", 0, 0),
    "coins_20m": (80, 20_000_000, "🏆 20 000 000 монет (20kk)", "coins", 0, 0),
    # Совместимость со старыми ключами:
    "coins_50k": (5, 50_000, "🍬 50 000 монет", "coins", 0, 0),
    "coins_250k": (7, 250_000, "🎁 250 000 монет", "coins", 0, 0),
    "s": (1, 5_000, "🍬 Горсть монет (5 000)", "coins", 0, 0),
    "m": (5, 30_000, "🍭 Пакет монет (30 000)", "coins", 0, 0),
    "l": (15, 120_000, "🎁 Коробка монет (120 000)", "coins", 0, 0),
    "xl": (50, 500_000, "💎 Сундук монет (500 000)", "coins", 0, 0),
    "vip": (25, 0, "👑 VIP на 30 дней", "vip", 1, 30),
}

SHOP_TEXT = """🛒 <b>Магазин за Telegram Stars</b>
┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
Покупка за ⭐️ <b>Telegram Stars</b> — официальную валюту Telegram прямо в приложении.

⭐ <b>VIP (30 дней)</b> — 25 ⭐️
   +50% к работе, Крит x3.0 по боссам, +50% к бонусу, 5 +реп в день!

🌟 <b>VIP+ Diamond (30 дней)</b> — 50 ⭐️
   +150% к работе, МЕГА-крит x3.5, Безлимитный ИИ, VIP-темы, Кейсы!

🧠 <b>ИИ-Подписка (30 дней)</b> — 15 ⭐️
   Безлимитный ИИ-Ассистент Мокси, свои квизы (+квиз [тема]) и расшифровка ГС!

🍬 1 000 000 🪙 (1kk) — 10 ⭐️
🎁 3 000 000 🪙 (3kk) — 20 ⭐️
💎 7 000 000 🪙 (7kk) — 35 ⭐️
👑 12 000 000 🪙 (12kk) — 55 ⭐️
🏆 20 000 000 🪙 (20kk) — 80 ⭐️"""


def shop_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⭐️ VIP (30 дн) — 25 ⭐️", callback_data="buy:vip_30")],
        [InlineKeyboardButton(text="🌟 VIP+ Diamond (30 дн) — 50 ⭐️", callback_data="buy:vipplus_30")],
        [InlineKeyboardButton(text="🧠 ИИ-Подписка (30 дн) — 15 ⭐️", callback_data="buy:ai_pass_30")],
        [
            InlineKeyboardButton(text="🍬 1kk — 10 ⭐️", callback_data="buy:coins_1m"),
            InlineKeyboardButton(text="🎁 3kk — 20 ⭐️", callback_data="buy:coins_3m"),
        ],
        [
            InlineKeyboardButton(text="💎 7kk — 35 ⭐️", callback_data="buy:coins_7m"),
            InlineKeyboardButton(text="👑 12kk — 55 ⭐️", callback_data="buy:coins_12m"),
        ],
        [
            InlineKeyboardButton(text="🏆 20 000 000 🪙 (20kk) — 80 ⭐️", callback_data="buy:coins_20m"),
        ],
        [InlineKeyboardButton(text="💳 Оплата в рублях (ЮKassa)", callback_data="shop_tab:rub")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="mm:main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery, bot: Bot):
    key = call.data.split(":", 1)[1]
    pack = STARS_PACKS.get(key)
    if not pack:
        return await call.answer("Товар не найден", show_alert=True)

    # Защита от даунгрейда: если уже VIP+ (lvl 2), нельзя купить обычный VIP (lvl 1)
    if key == "vip_30":
        old_lvl, old_until, old_act = await db.get_vip_info(call.from_user.id)
        if old_act and old_lvl >= 2:
            until_str = time.strftime('%d.%m.%Y', time.localtime(old_until))
            return await call.answer(
                f"❌ У вас уже активна наивысшая привилегия — 🌟 VIP+ Diamond (до {until_str})!\n\n"
                f"Вы не можете понизить свой статус до обычного VIP.",
                show_alert=True
            )

    price, amount, title, p_type, lvl, days = pack
    desc = f"Покупка {title} за {price} Stars"
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id, title=title, description=desc,
            payload=f"stars_prod:{key}", currency="XTR",
            prices=[LabeledPrice(label=title, amount=price)])
        await call.answer()
    except Exception as e:
        await call.answer(f"Не удалось открыть оплату: {str(e)[:150]}", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery, bot: Bot):
    raw_key = (q.invoice_payload or "").split(":")[-1]
    if raw_key == "vip_30":
        old_lvl, old_until, old_act = await db.get_vip_info(q.from_user.id)
        if old_act and old_lvl >= 2:
            return await bot.answer_pre_checkout_query(
                q.id, ok=False,
                error_message="У вас уже действует наивысшая привилегия VIP+ Diamond!"
            )
    await bot.answer_pre_checkout_query(q.id, ok=True)


@router.message(F.successful_payment)
async def on_paid(message: Message, bot: Bot):
    sp = message.successful_payment
    raw_key = (sp.invoice_payload or "").split(":")[-1]
    pack = STARS_PACKS.get(raw_key)
    uid = message.from_user.id
    if not pack:
        return await message.answer("Платёж получен, но товар не найден. Напишите владельцу бота.")
    
    price, amount, title, p_type, lvl, days = pack
    now = int(time.time())
    me = await bot.me()
    await db.execute("INSERT INTO purchases (user_id,item,stars,amount,ts) VALUES (?,?,?,?,?)",
                     (uid, raw_key, price, amount, now))

    if p_type == "coins" or amount > 0:
        bal = await db.add_balance(uid, amount, "stars_coins", raw_key)
        await message.answer(
            f"✅ <b>Оплачено!</b>\n\n{title}\n"
            f"Начислено: <b>{money(amount)}</b>\nБаланс: <b>{money(bal)}</b>\n\n"
            f"Спасибо за поддержку проекта! ⭐️", reply_markup=await main_kb(uid, me.username))
    elif p_type == "vip":
        old_lvl, old_until, old_act = await db.get_vip_info(uid)
        if old_act and old_lvl >= 2 and lvl < 2:
            base_ts = old_until if old_until > now else now
            new_until = base_ts + days * 86400
            await db.set_vip(uid, new_until, 2)
            await message.answer(
                f"✅ <b>Оплачено!</b>\n\n💎 Так как у вас уже действовал статус <b>🌟 VIP+ Diamond</b>, он был успешно <b>продлён на {days} дней</b> (до {time.strftime('%d.%m.%Y', time.localtime(new_until))}) без понижения привилегий!",
                reply_markup=await main_kb(uid, me.username))
        elif lvl == 2 and old_act and old_lvl == 1:
            new_until = now + days * 86400
            await db.set_vip(uid, new_until, 2)
            await message.answer(
                f"✅ <b>Оплачено!</b>\n\n🎉 <b>Поздравляем с апгрейдом до 🌟 VIP+ Diamond!</b>\n"
                f"Статус повышен до максимального уровня на <b>{days} дней</b>!\n"
                f"Все суперсилы ранга уже доступны во всех ваших беседах.", reply_markup=await main_kb(uid, me.username))
        else:
            base_ts = old_until if (old_act and old_until > now and old_lvl == lvl) else now
            new_until = base_ts + days * 86400
            await db.set_vip(uid, new_until, lvl)
            lvl_name = "🌟 VIP+ Diamond" if lvl == 2 else "⭐️ VIP"
            await message.answer(
                f"✅ <b>Оплачено!</b>\n\n💎 Статус <b>{lvl_name}</b> активирован на <b>{days} дней</b>!\n"
                f"Все суперсилы ранга уже доступны во всех ваших беседах.", reply_markup=await main_kb(uid, me.username))
    elif p_type == "ai_pass":
        old_until, old_act = await db.get_ai_pass_info(uid)
        base_ts = old_until if (old_act and old_until > now) else now
        new_until = base_ts + days * 86400
        await db.set_ai_pass(uid, new_until)
        await message.answer(
            f"✅ <b>Оплачено!</b>\n\n🧠 <b>ИИ-Подписка</b> активирована на <b>{days} дней</b>!\n"
            f"Вам доступен безлимитный ИИ-Ассистент Мокси и свои квизы.", reply_markup=await main_kb(uid, me.username))

    # Праздничное оповещение во все чаты и личное уведомление владельцам
    try:
        from core_yookassa import broadcast_purchase
        await broadcast_purchase(
            bot=bot,
            user_id=uid,
            item_title=title,
            pay_system="⭐️ Telegram Stars",
            amount_str=f"{price} ⭐️"
        )
    except Exception:
        pass



@router.callback_query(F.data == "gbonus")
async def cb_gram_bonus(call: CallbackQuery):
    import random
    from h_grams import c
    uid = call.from_user.id
    vip_lvl, _, vip_active = await db.get_vip_info(uid)
    cd = 3600 if (vip_active and vip_lvl >= 2) else (7200 if (vip_active and vip_lvl >= 1) else 14400)
    left = await db.cooldown_left(uid, "gram_daily", cd)
    if left:
        from utils import hms
        return await call.answer(f"⏳ Бонус уже получен.\nЖдите {hms(left)}", show_alert=True)
    
    # Сначала фиксируем кулдаун
    await db.set_cooldown(uid, "gram_daily")

    base_bonus = random.randint(1, 30_000)
    vip_mult = 2.0 if (vip_active and vip_lvl >= 2) else (1.5 if (vip_active and vip_lvl >= 1) else 1.0)
    final_bonus = int(base_bonus * vip_mult)
    
    bal = await db.add_balance(uid, final_bonus, "daily_bonus")
    
    vip_tag = ""
    if vip_active and vip_lvl >= 2:
        vip_tag = f"\n🌟 <i>VIP+ бонус x2 (+{final_bonus - base_bonus:,} 🌑)!</i>"
    elif vip_active and vip_lvl >= 1:
        vip_tag = f"\n⭐️ <i>VIP бонус +50% (+{final_bonus - base_bonus:,} 🌑)!</i>"

    from utils import hms
    await call.message.edit_text(
        f"🎉 <b>Бонус получен!</b>\n\n"
        f"🎲 Выпало: <b>+{c(final_bonus)}</b>{vip_tag}\n"
        f"💰 Баланс: <b>{c(bal)}</b>\n\n"
        f"<i>Следующий через {hms(cd)}.</i>",
        reply_markup=back_kb())
    await call.answer(f"🎁 +{final_bonus:,} 🪙!".replace(",", " "))


@router.message(Cmd("добавить", "добавить бота", "добавить в группу", "добавить в беседу",
                    section=1, usage="добавить", desc="➕ Добавить бота в группу / беседу"))
async def cmd_add_to_group(message: Message, bot: Bot, **kw):
    me = await bot.me()
    rights = "change_info+post_messages+edit_messages+delete_messages+restrict_members+invite_users+pin_messages+promote_members+manage_video_chats"
    add_url = f"https://t.me/{me.username}?startgroup&admin={rights}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить Moxxi в беседу", url=add_url)]
    ])
    await message.reply(
        "➕ <b>Добавление Moxxi в вашу группу / беседу</b>\n\n"
        "Нажмите кнопку ниже, чтобы выбрать чат и добавить бота с необходимыми правами администратора:\n\n"
        "✨ <i>Бот автоматически включит защиту чата, экономику, рейды на боссов, дуэли и фильтры!</i>",
        reply_markup=kb,
        disable_web_page_preview=True
    )
