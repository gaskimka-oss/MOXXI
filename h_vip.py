"""Модуль рангов VIP, VIP+ и ИИ-Подписки (Moxxi Premium System).

Включает:
- Уровни: ⭐️ VIP (1) и 🌟 VIP+ Diamond (2)
- 🧠 ИИ-Подписка (AI Pass)
- Покупка за монеты (🪙), рубли (💳 ЮKassa / СБП / Карты) и ⭐️ Telegram Stars
- Меню выбора неоновых тем оформления («вип меню»)
- Интерактивный магазин и моментальная авто-выдача
"""
from __future__ import annotations

import html
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message)

import db
from core_ranks import require
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from core_yookassa import PRODUCTS, create_rub_payment, fulfill_payment, get_payment_status
from utils import mention, mention_id, money

router = Router(name="vip")
S_VIP = 41  # Раздел 41: VIP-статусы и подписки

# Стоимость покупки за монеты на 30 дней
VIP_PRICE = 5000
VIPPLUS_PRICE = 10000

# Темы оформления для VIP пользователей
VIP_THEMES = {
    "default": ("⚪️ Классический", "Классический чистый стиль"),
    "purple": ("🟣 Неоновый фиолетовый", "Стильный фиолетовый акцент"),
    "blue": ("🔵 Лазурный сапфир", "Глубокий синий оттенок"),
    "green": ("🟢 Изумрудный", "Яркий зелёный стиль"),
    "gold": ("🟡 Золотой рассвет", "Роскошное золотое оформление"),
    "ruby": ("🔴 Рубиновый закат", "Пылкий красный стиль"),
    "sakura": ("🌸 Нежная сакура", "Розовый весенний акцент"),
}


def vip_badge_str(level: int) -> str:
    if level >= 2:
        return "🌟 VIP+ Diamond"
    if level >= 1:
        return "⭐️ VIP"
    return "Отсутствует"


def vip_theme_keyboard(current_theme: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, (name, _) in VIP_THEMES.items():
        check = " ✅" if key == current_theme else ""
        buttons.append([InlineKeyboardButton(text=f"{name}{check}", callback_data=f"vip_set_theme:{key}")])
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="vip_close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплата в рублях (ЮKassa / СБП)", callback_data="shop_tab:rub"),
        ],
        [
            InlineKeyboardButton(text="⭐️ Оплата Telegram Stars", callback_data="shop_tab:stars"),
        ],
        [
            InlineKeyboardButton(text="🪙 Купить пакеты игровых монет", callback_data="shop_tab:coins_pack"),
        ],
        [
            InlineKeyboardButton(text="📖 Подробное сравнение VIP и VIP+", callback_data="shop_compare"),
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть", callback_data="vip_close")
        ]
    ])


def rub_shop_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⭐️ VIP (30 дн) — 99 ₽", callback_data="buy_rub:vip_30")],
        [InlineKeyboardButton(text="🌟 VIP+ Diamond (30 дн) — 199 ₽", callback_data="buy_rub:vipplus_30")],
        [InlineKeyboardButton(text="🧠 ИИ-Подписка (30 дн) — 69 ₽", callback_data="buy_rub:ai_pass_30")],
        [
            InlineKeyboardButton(text="🍬 1kk — 49 ₽", callback_data="buy_rub:coins_1m"),
            InlineKeyboardButton(text="🎁 3kk — 99 ₽", callback_data="buy_rub:coins_3m"),
        ],
        [
            InlineKeyboardButton(text="💎 7kk — 169 ₽", callback_data="buy_rub:coins_7m"),
            InlineKeyboardButton(text="👑 12kk — 269 ₽", callback_data="buy_rub:coins_12m"),
        ],
        [
            InlineKeyboardButton(text="🏆 20 000 000 🪙 (20kk) — 399 ₽", callback_data="buy_rub:coins_20m"),
        ],
        [InlineKeyboardButton(text="📖 Описание всех суперсил VIP и VIP+", callback_data="shop_compare")],
        [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="buy_vip_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stars_shop_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⭐️ VIP (30 дн) — 25 ⭐️", callback_data="buy_stars:vip_30")],
        [InlineKeyboardButton(text="🌟 VIP+ Diamond (30 дн) — 50 ⭐️", callback_data="buy_stars:vipplus_30")],
        [InlineKeyboardButton(text="🧠 ИИ-Подписка (30 дн) — 15 ⭐️", callback_data="buy_stars:ai_pass_30")],
        [
            InlineKeyboardButton(text="🍬 1kk — 10 ⭐️", callback_data="buy_stars:coins_1m"),
            InlineKeyboardButton(text="🎁 3kk — 20 ⭐️", callback_data="buy_stars:coins_3m"),
        ],
        [
            InlineKeyboardButton(text="💎 7kk — 35 ⭐️", callback_data="buy_stars:coins_7m"),
            InlineKeyboardButton(text="👑 12kk — 55 ⭐️", callback_data="buy_stars:coins_12m"),
        ],
        [
            InlineKeyboardButton(text="🏆 20 000 000 🪙 (20kk) — 80 ⭐️", callback_data="buy_stars:coins_20m"),
        ],
        [InlineKeyboardButton(text="📖 Описание всех суперсил VIP и VIP+", callback_data="shop_compare")],
        [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="buy_vip_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def coins_pack_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍬 1 000 000 🪙 (49 ₽)", callback_data="buy_rub:coins_1m"),
            InlineKeyboardButton(text="10 ⭐️ Stars", callback_data="buy_stars:coins_1m"),
        ],
        [
            InlineKeyboardButton(text="🎁 3 000 000 🪙 (99 ₽)", callback_data="buy_rub:coins_3m"),
            InlineKeyboardButton(text="20 ⭐️ Stars", callback_data="buy_stars:coins_3m"),
        ],
        [
            InlineKeyboardButton(text="💎 7 000 000 🪙 (169 ₽)", callback_data="buy_rub:coins_7m"),
            InlineKeyboardButton(text="35 ⭐️ Stars", callback_data="buy_stars:coins_7m"),
        ],
        [
            InlineKeyboardButton(text="👑 12 000 000 🪙 (269 ₽)", callback_data="buy_rub:coins_12m"),
            InlineKeyboardButton(text="55 ⭐️ Stars", callback_data="buy_stars:coins_12m"),
        ],
        [
            InlineKeyboardButton(text="🏆 20 000 000 🪙 (399 ₽)", callback_data="buy_rub:coins_20m"),
            InlineKeyboardButton(text="80 ⭐️ Stars", callback_data="buy_stars:coins_20m"),
        ],
        [
            InlineKeyboardButton(text="👑 Магазин статусов VIP / VIP+", callback_data="buy_vip_menu"),
        ]
    ])


def shop_compare_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐️ Оформить VIP", callback_data="shop_select:1"),
            InlineKeyboardButton(text="🌟 Оформить VIP+", callback_data="shop_select:2"),
        ],
        [
            InlineKeyboardButton(text="🪙 Купить пакеты монет", callback_data="shop_tab:coins_pack"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="buy_vip_menu")
        ]
    ])


def shop_select_keyboard(lvl: int) -> InlineKeyboardMarkup:
    if lvl == 2:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 199 ₽ через ЮKassa (СБП / Карты)", callback_data="buy_rub:vipplus_30")],
            [InlineKeyboardButton(text="⭐️ Оплатить 50 ⭐️ через Telegram Stars", callback_data="buy_stars:vipplus_30")],
            [InlineKeyboardButton(text="⬅️ Назад к сравнению", callback_data="shop_compare")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить 99 ₽ через ЮKassa (СБП / Карты)", callback_data="buy_rub:vip_30")],
        [InlineKeyboardButton(text="⭐️ Оплатить 25 ⭐️ через Telegram Stars", callback_data="buy_stars:vip_30")],
        [InlineKeyboardButton(text="⬅️ Назад к сравнению", callback_data="shop_compare")]
    ])


# ================== КОМАНДЫ VIP ==================

@router.message(Cmd("вип команды", "вип инфо", "vip команды", "вип", "vip", section=S_VIP,
                    usage="вип команды", desc="Команды и суперсилы ранга VIP"))
async def cmd_vip_info(message: Message, bot: Bot, **kw):
    me_id = message.from_user.id
    lvl, until, active = await db.get_vip_info(me_id)
    theme = await db.get_vip_theme(me_id)
    theme_name = VIP_THEMES.get(theme, VIP_THEMES["default"])[0]

    if active:
        left = int(until - time.time())
        status_line = f"🟢 <b>Ваш статус:</b> {vip_badge_str(lvl)} (ещё {human_period(left)})\n🎨 <b>Текущая тема:</b> {theme_name}"
    else:
        status_line = "⚪️ <b>Ваш статус:</b> Отсутствует"

    text = (
        f"⭐ <b>Команды и привилегии ранга VIP</b>\n"
        f"✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        f"{status_line}\n\n"
        f"👑 <b>Суперсилы статуса VIP:</b>\n"
        f"• 💰 <b>Работа:</b> <b>+50% к зарплате</b> на команде <code>работа</code>\n"
        f"• 🐉 <b>Рейды на Боссов:</b> шанс нанести <b>Крит x3.0</b> (вместо x2.5) + <b>-30% шанс нокаута</b>\n"
        f"• ⚔️ <b>PvP-Дуэли:</b> увеличенный лимит ставок + золотая анимация выстрела\n"
        f"• 🎣 <b>Рыбалка:</b> <b>+30% шанс</b> поймать редкую рыбу и сундук с сокровищами\n"
        f"• 🎁 <b>Бонус:</b> <b>+50% монет и опыта</b> на команде <code>бонус</code>\n"
        f"• ⭐️ <b>Репутация:</b> <b>5 плюсиков</b> (<code>+реп</code>) в сутки вместо 3\n"
        f"• 🛡 <b>Защита:</b> 1 бесплатный Щит от варна каждый месяц\n"
        f"• 🏷 <b>Профиль:</b> статусная плашка ⭐️ VIP в анкетах и профилях\n\n"
        f"💡 <b>Команды:</b>\n"
        f"• <code>вип+ команды</code> — возможности улучшенного ранга VIP+\n"
        f"• <code>купить вип</code> — открыть магазин покупки за рубли, звёзды и монеты"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛍 Открыть Магазин VIP", callback_data="buy_vip_menu")
        ]
    ])
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(Cmd("вип+ команды", "вип+ инфо", "вип плюс команды", "vip+ команды",
                    "вип+", "vip+", "вип плюс", section=S_VIP,
                    usage="вип+ команды", desc="Команды и возможности ранга VIP+ Diamond"))
async def cmd_vipplus_info(message: Message, bot: Bot, **kw):
    me_id = message.from_user.id
    lvl, until, active = await db.get_vip_info(me_id)
    theme = await db.get_vip_theme(me_id)
    theme_name = VIP_THEMES.get(theme, VIP_THEMES["default"])[0]

    if active:
        left = int(until - time.time())
        status_line = f"🟢 <b>Ваш статус:</b> {vip_badge_str(lvl)} (ещё {human_period(left)})\n🎨 <b>Текущая тема:</b> {theme_name}"
    else:
        status_line = "⚪️ <b>Ваш статус:</b> Отсутствует"

    text = (
        f"🌟 <b>Команды и привилегии ранга VIP+ Diamond</b>\n"
        f"✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        f"{status_line}\n\n"
        f"👑 <b>Максимальные суперсилы VIP+:</b>\n"
        f"• 💰 <b>Работа:</b> <b>+150% к зарплате</b> (в 2.5 раза больше монет!)\n"
        f"• 🐉 <b>Рейды на Боссов:</b> <b>МЕГА-крит x3.5</b> + <b>-60% шанс нокаута</b> + <b>+30% к кушу</b>\n"
        f"• ⚔️ <b>PvP-Дуэли:</b> иммунитет к карманным кражам + шанс парировать пулю титановым щитом\n"
        f"• 🎣 <b>Рыбалка:</b> кулдаун в 2 раза быстрее + шанс поймать Золотую Рыбку (x2 монеты)\n"
        f"• 🎁 <b>Бонус:</b> <b>ДВОЙНОЙ бонус (x2)</b> + <b>1 Алмазный Кейс</b> каждую неделю!\n"
        f"• ⭐️ <b>Репутация:</b> <b>10 плюсиков</b> (<code>+реп</code>) в сутки + титул «🌟 VIP-Авторитет»\n"
        f"• 🎨 <b>VIP Меню:</b> выбор неоновых стилей и тем сообщений (<code>вип меню</code>)\n"
        f"• 🤖 <b>Безлимитный ИИ:</b> полный доступ к ИИ-Ассистенту и созданию своих квизов\n"
        f"• 👑 <b>Профиль:</b> сияющая плашка 🌟 VIP+ во всех топах и анкетах\n\n"
        f"💡 <b>Команды:</b>\n"
        f"• <code>вип меню</code> — открыть палитру неоновых стилей\n"
        f"• <code>купить вип+</code> — приобрести статус на 30 дней"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 VIP Меню (Темы)", callback_data="vip_open_menu"),
            InlineKeyboardButton(text="🛍 Купить VIP+", callback_data="buy_vip_menu")
        ]
    ])
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(Cmd("ии подписка", "ии команды", "ии пасс", "ai pass", section=S_VIP,
                    usage="ии подписка", desc="Суперсилы ИИ-подписки (AI Pass)"))
async def cmd_ai_pass_info(message: Message, **kw):
    until, active = await db.get_ai_pass_info(message.from_user.id)
    if active:
        left = int(until - time.time())
        status_line = f"🟢 <b>Ваш статус:</b> 🧠 AI Master (ещё {human_period(left)})"
    else:
        status_line = "⚪️ <b>Ваш статус:</b> Отсутствует"

    text = (
        f"🧠 <b>ИИ-Подписка (AI Pass) — Суперсилы Нейросети</b>\n"
        f"✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        f"{status_line}\n\n"
        f"🔥 <b>Что даёт подписка:</b>\n"
        f"• ⚡️ <b>Безлимитный ИИ-Ассистент:</b> общение с Мокси без кулдаунов и задержек (<code>ии [вопрос]</code>)\n"
        f"• 🏆 <b>Свои викторины в чате:</b> запуск квизов на ЛЮБУЮ тему (<code>+квиз [тема]</code>)\n"
        f"• 🎙 <b>Безлимитная расшифровка:</b> перевод любых голосовых и видео-кружков в текст\n"
        f"• 🔮 <b>ИИ-Гороскопы и Таро дня:</b> персональные предсказания с баффом к удаче\n"
        f"• 🎤 <b>ИИ-Панчи:</b> генератор рифм и подколов для дуэлей (<code>панч @user</code>)\n"
        f"• 💎 Значок 🧠 AI Master в профиле!\n\n"
        f"<i>💡 Подписка включена бесплатно во флагманский ранг 🌟 VIP+!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛍 Приобрести ИИ-Подписку (69 ₽)", callback_data="buy_rub:ai_pass_30")
        ]
    ])
    await message.reply(text, reply_markup=kb, disable_web_page_preview=True)


# ================== ПОКУПКА VIP И МАГАЗИН ==================

SHOP_HUB_TEXT = (
    "🛍 ✨ <b>МАГАЗИН ПРИВИЛЕГИЙ И ВАЛЮТЫ MOXXI</b> ✨ 🛍\n"
    "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
    "👑 <b>Что могут статусы:</b>\n\n"
    "⭐️ <b>Ранг ⭐️ VIP:</b>\n"
    "• 💰 <b>Работа:</b> <b>+50%</b> к зарплате каждый час\n"
    "• 🐉 <b>Рейды на Боссов:</b> Крит <b>x3.0</b> урона + <b>-30% шанс нокаута</b>\n"
    "• 🎁 <b>Бонус:</b> <b>+50%</b> монет и опыта каждые 2 часа\n"
    "• 🎣 <b>Рыбалка:</b> <b>+30%</b> шанс редкого улова и сундуков\n"
    "• ⭐️ <b>Репутация:</b> <b>5 плюсиков</b> (+реп) в сутки + 1 щит от варна\n"
    "• 🏷 <b>Профиль:</b> статусная плашка ⭐️ VIP во всех беседах\n\n"
    "🌟 <b>Ранг 🌟 VIP+ Diamond (Максимум возможностей):</b>\n"
    "• 🧠 <b>Нейросеть Moxxi AI:</b> <b>Включена бесплатно!</b> Безлимитный ИИ, свои квизы, расшифровка голосовых\n"
    "• 💰 <b>Работа:</b> <b>+100%</b> к зарплате (удвоение дохода!)\n"
    "• 🐉 <b>Рейды на Боссов:</b> МЕГА-Крит <b>x3.5</b> урона + <b>-60% шанс нокаута</b>\n"
    "• 🎁 <b>Бонус:</b> Удвоение <b>x2.0</b> раз в 1 час (до 60 000 🪙!)\n"
    "• 🎨 <b>Темы:</b> Неоновые цветные стили в <code>вип меню</code>\n"
    "• ⭐️ <b>Репутация:</b> <b>10 плюсиков</b> (+реп) в сутки\n"
    "• 📦 <b>Подарки:</b> Бесплатный секретный кейс каждую неделю\n"
    "• 🏷 <b>Профиль:</b> роскошный значок 🌟 VIP+ во всех чатах\n\n"
    "✦ ══════════════════════════════ ✦\n"
    "👇 <i>Выберите способ оплаты или откройте сравнение:</i>"
)


BUY_COINS_TEXT = (
    "🪙 ✨ <b>ПОКУПКА ИГРОВЫХ МОНЕТ (ВАЛЮТЫ MOXXI)</b> ✨ 🪙\n"
    "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
    "Пополните свой баланс монет для ставок в казино, дуэлей, открытия кейсов, рыбалки и покупки снаряжения!\n\n"
    "📦 <b>Доступные пакеты монет:</b>\n"
    "• 🍬 <b>1 000 000 🪙 (1kk)</b> — <b>49 ₽</b> <i>(или 10 ⭐️)</i>\n"
    "• 🎁 <b>3 000 000 🪙 (3kk)</b> — <b>99 ₽</b> <i>(или 20 ⭐️)</i>\n"
    "• 💎 <b>7 000 000 🪙 (7kk)</b> — <b>169 ₽</b> <i>(или 35 ⭐️)</i>\n"
    "• 👑 <b>12 000 000 🪙 (12kk)</b> — <b>269 ₽</b> <i>(или 55 ⭐️)</i>\n"
    "• 🏆 <b>20 000 000 🪙 (20kk)</b> — <b>399 ₽</b> <i>(или 80 ⭐️)</i> 🔥\n\n"
    "💳 <i>Официальная оплата через ЮKassa (СБП, Карты РФ, Mir Pay, Т-Банк, Сбер) или Telegram Stars. Начисление моментальное!</i>"
)


@router.message(Cmd("купить вип", "купить вип+", "купить vip", "купить vip+", "магазин вип", "донат", "шоп",
                    section=S_VIP, usage="купить вип", desc="Купить VIP или VIP+ за рубли/Stars"))
async def cmd_buy_vip_dialog(message: Message, **kw):
    await message.reply(SHOP_HUB_TEXT, reply_markup=shop_hub_keyboard(), disable_web_page_preview=True)


@router.message(Cmd("купить монеты", "купить валюту", "магазин монет", "монеты купить", "монеты",
                    section=S_VIP, usage="купить монеты", desc="Купить пакеты игровых монет за рубли/Stars"))
async def cmd_buy_coins_dialog(message: Message, **kw):
    await message.reply(BUY_COINS_TEXT, reply_markup=coins_pack_keyboard(), disable_web_page_preview=True)


@router.callback_query(F.data == "buy_vip_menu")
async def cb_buy_vip_menu(call: CallbackQuery):
    await call.message.edit_text(SHOP_HUB_TEXT, reply_markup=shop_hub_keyboard(), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data == "shop_compare")
async def cb_shop_compare(call: CallbackQuery):
    txt = (
        "👑 ✨ <b>СРАВНЕНИЕ ВОЗМОЖНОСТЕЙ: VIP vs VIP+ DIAMOND</b> ✨ 👑\n"
        "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        "⭐ <b>1. ВОЗМОЖНОСТИ ⭐️ VIP:</b>\n"
        "• 💼 <b>Работа:</b> <b>+50%</b> к зарплате каждый час (до 1 350 🪙)\n"
        "• 🐉 <b>Боссы:</b> Крит <b>x3.0</b> урона (вместо x2.5) + <b>-30% шанс нокаута</b>\n"
        "• 🎁 <b>Бонус:</b> <b>+50%</b> монет и опыта каждые 2 часа (до 45 000 🪙)\n"
        "• 🎣 <b>Рыбалка:</b> <b>+30%</b> шанс редкой рыбы и сундука с сокровищами\n"
        "• ⭐️ <b>Репутация:</b> <b>5 плюсиков</b> (<code>+реп</code>) в сутки вместо 3\n"
        "• 🛡 <b>Защита:</b> 1 бесплатный щит от варна каждый месяц\n"
        "• 🏷 <b>Профиль:</b> статусная плашка ⭐️ VIP во всех анкетах и беседах\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🌟 <b>2. СУПЕРСИЛЫ 🌟 VIP+ DIAMOND (ФЛАГМАН):</b>\n"
        "• 🧠 <b>Нейросеть Moxxi AI:</b> <b>Включена бесплатно!</b> Безлимитный ИИ, свои квизы (<code>+квиз [тема]</code>), расшифровка голосовых и кружков\n"
        "• 💼 <b>Работа:</b> <b>+100%</b> к зарплате (удвоение дохода, до 1 800 🪙/час)\n"
        "• 🐉 <b>Боссы:</b> МЕГА-Крит <b>x3.5</b> урона + <b>-60% шанс нокаута</b>\n"
        "• 🎁 <b>Бонус:</b> Удвоенный бонус <b>x2.0</b> (до 60 000 🪙) каждые <b>1 час</b>!\n"
        "• 🎨 <b>Неоновые темы:</b> выбор эксклюзивных стилей оформления в <code>вип меню</code>\n"
        "• ⭐️ <b>Репутация:</b> <b>10 плюсиков</b> (<code>+реп</code>) в сутки\n"
        "• 📦 <b>Подарки:</b> бесплатный кейс со снаряжением каждую неделю\n"
        "• 🏷 <b>Профиль:</b> роскошный значок 🌟 VIP+ Diamond во всех беседах\n\n"
        "✦ ══════════════════════════════ ✦\n"
        "💡 <i>Любой выбранный статус действует во всех ваших группах и в ЛС!</i>"
    )
    await call.message.edit_text(txt, reply_markup=shop_compare_keyboard(), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("shop_select:"))
async def cb_shop_select(call: CallbackQuery):
    lvl = int(call.data.split(":")[1])
    if lvl == 2:
        txt = (
            "🌟 ✨ <b>ОФОРМЛЕНИЕ СТАТУСА VIP+ DIAMOND (30 ДНЕЙ)</b> ✨ 🌟\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "💎 <b>Что входит в статус:</b>\n"
            "• 🧠 <b>Безлимитный ИИ Moxxi:</b> диалоги без задержек, свои квизы (<code>+квиз</code>), расшифровка ГС\n"
            "• 💰 <b>Работа:</b> <b>+100%</b> к зарплате (удвоение прибыли каждый час)\n"
            "• 🐉 <b>Боссы:</b> МЕГА-Крит <b>x3.5</b> урона + <b>-60% шанс нокаута</b>\n"
            "• 🎁 <b>Бонус:</b> Удвоение <b>x2.0</b> каждый <b>1 час</b> (до 60 000 🪙)\n"
            "• 🎨 <b>Темы:</b> Неоновые цветные темы профиля в <code>вип меню</code>\n"
            "• ⭐️ <b>Репутация:</b> <b>10 плюсиков</b> (+реп) в сутки\n"
            "• 📦 <b>Подарки:</b> Бесплатный секретный кейс каждую неделю\n\n"
            "👇 <i>Выберите удобный способ оплаты:</i>"
        )
    else:
        txt = (
            "⭐️ ✨ <b>ОФОРМЛЕНИЕ СТАТУСА VIP (30 ДНЕЙ)</b> ✨ ⭐️\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "💎 <b>Что входит в статус:</b>\n"
            "• 💰 <b>Работа:</b> <b>+50%</b> к зарплате каждый час (до 1 350 🪙)\n"
            "• 🐉 <b>Боссы:</b> Крит <b>x3.0</b> урона + <b>-30% шанс нокаута</b>\n"
            "• 🎁 <b>Бонус:</b> <b>+50%</b> монет и опыта каждые 2 часа (до 45 000 🪙)\n"
            "• 🎣 <b>Рыбалка:</b> <b>+30%</b> шанс редкой рыбы и сокровищ\n"
            "• ⭐️ <b>Репутация:</b> <b>5 плюсиков</b> (+реп) в сутки\n"
            "• 🛡 <b>Защита:</b> 1 бесплатный щит от варна каждый месяц\n\n"
            "👇 <i>Выберите удобный способ оплаты:</i>"
        )
    await call.message.edit_text(txt, reply_markup=shop_select_keyboard(lvl), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("shop_tab:"))
async def cb_shop_tab(call: CallbackQuery):
    tab = call.data.split(":", 1)[1]
    if tab == "rub":
        txt = (
            "💳 <b>Оплата в рублях через ЮKassa (СБП / Карты РФ / Mir Pay)</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Официальная оплата с моментальным автоматическим начислением:\n\n"
            "• ⭐ <b>VIP (30 дн) — 99 ₽</b>\n"
            "  └ <i>+50% к работе, Крит x3.0 по боссам, +50% бонус, +30% рыбалка, 5 +реп</i>\n\n"
            "• 🌟 <b>VIP+ Diamond (30 дн) — 199 ₽</b>\n"
            "  └ <i>Все суперсилы VIP + безлимитный ИИ Moxxi + удвоение работы (+100%) + МЕГА-Крит x3.5 + цветные темы + еженедельный кейс</i>\n\n"
            "• 🧠 <b>ИИ-Подписка (30 дн) — 69 ₽</b>\n"
            "  └ <i>Безлимитный ИИ, свои квизы, расшифровка голосовых и Таро</i>\n\n"
            "• 🍬 <b>1 000 000 монет (1kk) — 49 ₽</b>\n"
            "• 🎁 <b>3 000 000 монет (3kk) — 99 ₽</b>\n"
            "• 💎 <b>7 000 000 монет (7kk) — 169 ₽</b>\n"
            "• 👑 <b>12 000 000 монет (12kk) — 269 ₽</b>\n"
            "• 🏆 <b>20 000 000 монет (20kk) — 399 ₽</b> 🔥\n\n"
            "Выберите товар для покупки:"
        )
        await call.message.edit_text(txt, reply_markup=rub_shop_keyboard(), disable_web_page_preview=True)
        return await call.answer()

    if tab == "stars":
        txt = (
            "⭐️ <b>Оплата за Telegram Stars</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Оплата в 1 клик с баланса Telegram (активно во всех группах):\n\n"
            "• ⭐ <b>VIP (30 дн) — 25 ⭐️</b>\n"
            "  └ <i>+50% к работе, Крит x3.0 по боссам, +50% бонус, +30% рыбалка, 5 +реп</i>\n\n"
            "• 🌟 <b>VIP+ Diamond (30 дн) — 50 ⭐️</b>\n"
            "  └ <i>Все суперсилы VIP + безлимитный ИИ Moxxi + удвоение работы (+100%) + МЕГА-Крит x3.5 + цветные темы + еженедельный кейс</i>\n\n"
            "• 🧠 <b>ИИ-Подписка (30 дн) — 15 ⭐️</b>\n"
            "  └ <i>Безлимитный ИИ, свои квизы, расшифровка голосовых и Таро</i>\n\n"
            "• 🍬 <b>1 000 000 монет (1kk) — 10 ⭐️</b>\n"
            "• 🎁 <b>3 000 000 монет (3kk) — 20 ⭐️</b>\n"
            "• 💎 <b>7 000 000 монет (7kk) — 35 ⭐️</b>\n"
            "• 👑 <b>12 000 000 монет (12kk) — 55 ⭐️</b>\n"
            "• 🏆 <b>20 000 000 монет (20kk) — 80 ⭐️</b> 🔥\n\n"
            "Выберите товар для покупки:"
        )
        await call.message.edit_text(txt, reply_markup=stars_shop_keyboard(), disable_web_page_preview=True)
        return await call.answer()

    if tab in ("coins", "coins_pack"):
        txt = (
            "🪙 <b>Покупка пакетов игровых монет (валюты Moxxi)</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Пополните свой баланс монет для ставок в казино, дуэлей, открытия кейсов, рыбалки и снаряжения!\n\n"
            "• 🍬 <b>1 000 000 🪙 (1kk)</b> — <b>49 ₽</b> <i>(или 10 ⭐️)</i>\n"
            "• 🎁 <b>3 000 000 🪙 (3kk)</b> — <b>99 ₽</b> <i>(или 20 ⭐️)</i>\n"
            "• 💎 <b>7 000 000 🪙 (7kk)</b> — <b>169 ₽</b> <i>(или 35 ⭐️)</i>\n"
            "• 👑 <b>12 000 000 🪙 (12kk)</b> — <b>269 ₽</b> <i>(или 55 ⭐️)</i>\n"
            "• 🏆 <b>20 000 000 🪙 (20kk)</b> — <b>399 ₽</b> <i>(или 80 ⭐️)</i> 🔥\n\n"
            "💳 <i>Официальная оплата через ЮKassa (СБП, Карты РФ, Mir Pay, Т-Банк, Сбер) или Telegram Stars. Начисление монет моментальное!</i>"
        )
        await call.message.edit_text(txt, reply_markup=coins_pack_keyboard(), disable_web_page_preview=True)
        return await call.answer()

    await call.answer()


# ── Оплата в рублях через ЮKassa ──
@router.callback_query(F.data.startswith("buy_rub:"))
async def cb_buy_rub(call: CallbackQuery, bot: Bot):
    item_key = call.data.split(":", 1)[1]
    prod = PRODUCTS.get(item_key)
    if not prod:
        return await call.answer("Товар не найден", show_alert=True)

    # Защита от даунгрейда: если уже есть VIP+ (lvl 2), нельзя купить обычный VIP (lvl 1)
    if item_key == "vip_30":
        old_lvl, old_until, old_act = await db.get_vip_info(call.from_user.id)
        if old_act and old_lvl >= 2:
            until_str = time.strftime('%d.%m.%Y', time.localtime(old_until))
            return await call.answer(
                f"❌ У вас уже активна наивысшая привилегия — 🌟 VIP+ Diamond (до {until_str})!\n\n"
                f"Вы не можете понизить свой статус до обычного VIP.",
                show_alert=True
            )

    me = await bot.me()
    pay_url, payment_id = await create_rub_payment(call.from_user.id, item_key, me.username)

    if not pay_url or not payment_id:
        return await call.answer(
            "⚠️ Не удалось сформировать счёт ЮKassa. Попробуйте оплату через Telegram Stars или обратитесь к создателю.",
            show_alert=True
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Перейти к оплате в ЮKassa", url=pay_url)
        ],
        [
            InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_yoo:{payment_id}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="shop_tab:rub")
        ]
    ])

    text = (
        f"🧾 <b>Счёт на оплату через ЮKassa сформирован!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📦 <b>Товар:</b> {prod['title']}\n"
        f"💵 <b>Сумма к оплате:</b> <b>{prod['price_rub']:.2f} ₽</b>\n\n"
        f"💳 <b>Способы оплаты:</b> СБП (без комиссии), Карты РФ, Mir Pay, Т-Банк, Сбер.\n\n"
        f"👉 <i>Нажмите кнопку ниже, чтобы перейти на защищенную страницу оплаты ЮKassa. После оплаты статус/монеты начислятся автоматически в течение 10 секунд!</i>"
    )
    await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("check_yoo:"))
async def cb_check_yoo(call: CallbackQuery, bot: Bot):
    payment_id = call.data.split(":", 1)[1]
    st = await get_payment_status(payment_id)

    if st == "succeeded":
        ok = await fulfill_payment(bot, payment_id)
        if ok:
            await call.answer("🎉 Оплата успешно подтверждена! Товар начислен!", show_alert=True)
            return await cb_buy_vip_menu(call)
        else:
            return await call.answer("✅ Этот платёж уже был успешно активирован ранее.", show_alert=True)

    if st == "pending":
        return await call.answer("⏳ Платёж ещё в процессе обработки банком. Завершите оплату и нажмите проверку снова!", show_alert=True)

    if st in ("canceled", "cancelled"):
        return await call.answer("❌ Платёж был отменён. Вы можете создать новый счёт в магазине.", show_alert=True)

    await call.answer(f"Статус платежа: {st or 'ожидание'}", show_alert=True)


# ── Оплата за Telegram Stars ──
@router.callback_query(F.data.startswith("buy_stars:"))
async def cb_buy_stars(call: CallbackQuery, bot: Bot):
    item_key = call.data.split(":", 1)[1]
    prod = PRODUCTS.get(item_key)
    if not prod:
        return await call.answer("Товар не найден", show_alert=True)

    # Защита от даунгрейда: если уже есть VIP+ (lvl 2), нельзя купить обычный VIP (lvl 1)
    if item_key == "vip_30":
        old_lvl, old_until, old_act = await db.get_vip_info(call.from_user.id)
        if old_act and old_lvl >= 2:
            until_str = time.strftime('%d.%m.%Y', time.localtime(old_until))
            return await call.answer(
                f"❌ У вас уже активна наивысшая привилегия — 🌟 VIP+ Diamond (до {until_str})!\n\n"
                f"Вы не можете понизить свой статус до обычного VIP.",
                show_alert=True
            )

    price_stars = prod["price_stars"]
    title = prod["title"]
    desc = prod["desc"]

    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=title,
            description=desc,
            payload=f"stars_prod:{item_key}",
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=price_stars)]
        )
        await call.answer("⭐️ Окно оплаты Telegram Stars открыто!")
    except Exception as e:
        await call.answer(f"Ошибка открытия Stars: {str(e)[:120]}", show_alert=True)


# ── Покупка VIP за виртуальные монеты отключена (VIP/VIP+ только за рубли и Stars) ──
@router.callback_query(F.data.startswith("buy_vip_do:"))
async def cb_buy_vip_do(call: CallbackQuery):
    await call.answer(
        "❌ Статусы VIP и VIP+ — это премиальные привилегии, доступные только за рубли (ЮKassa / СБП) или Telegram Stars.\n\n"
        "За игровые монеты вы можете открывать кейсы и покупать снаряжение в игре!",
        show_alert=True
    )


# ================== VIP МЕНЮ (ТЕМЫ) ==================

@router.message(Cmd("вип меню", "vip menu", "вип темы", section=S_VIP,
                    usage="вип меню", desc="Выбор цвета и темы оформления VIP+"))
async def cmd_vip_menu(message: Message, **kw):
    me_id = message.from_user.id
    lvl, until, active = await db.get_vip_info(me_id)
    if not active or lvl < 2:
        return await message.reply(
            "🔒 <b>VIP-меню и выбор тем оформления доступны только для пользователей с активным статусом 🌟 VIP+!</b>\n\n"
            "Приобрести статус: напишите <code>купить вип+</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🛍 Купить VIP+", callback_data="buy_vip_menu")
            ]]))

    theme = await db.get_vip_theme(me_id)
    text = (
        f"🎨 <b>VIP Меню — Выбор темы оформления</b>\n\n"
        f"Ваш статус: <b>{vip_badge_str(lvl)}</b>\n"
        f"Выберите желаемый цветовой стиль сообщений и акцентов:"
    )
    await message.reply(text, reply_markup=vip_theme_keyboard(theme))


@router.callback_query(F.data == "vip_open_menu")
async def cb_vip_open_menu(call: CallbackQuery):
    lvl, until, active = await db.get_vip_info(call.from_user.id)
    if not active or lvl < 2:
        return await call.answer("🔒 Выбор тем доступен только владельцам статуса 🌟 VIP+!\nПриобретите статус: «купить вип+»", show_alert=True)

    theme = await db.get_vip_theme(call.from_user.id)
    text = (
        f"🎨 <b>VIP Меню — Выбор темы оформления</b>\n\n"
        f"Ваш статус: <b>{vip_badge_str(lvl)}</b>\n"
        f"Выберите желаемый цветовой стиль сообщений и акцентов:"
    )
    await call.message.edit_text(text, reply_markup=vip_theme_keyboard(theme))
    await call.answer()


@router.callback_query(F.data.startswith("vip_set_theme:"))
async def cb_vip_set_theme(call: CallbackQuery):
    theme_key = call.data.split(":")[1]
    lvl, until, active = await db.get_vip_info(call.from_user.id)
    if not active or lvl < 2:
        return await call.answer("🔒 Темы оформления доступны только для пользователей со статусом 🌟 VIP+!", show_alert=True)

    if theme_key not in VIP_THEMES:
        return await call.answer()

    await db.set_vip_theme(call.from_user.id, theme_key)
    theme_name = VIP_THEMES[theme_key][0]
    await call.message.edit_reply_markup(reply_markup=vip_theme_keyboard(theme_key))
    await call.answer(f"✅ Установлена тема: {theme_name}", show_alert=True)


@router.callback_query(F.data == "vip_close")
async def cb_vip_close(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


# ---------- Административные команды управления VIP ----------

@router.message(Cmd("выдать вип", "дать вип", "выдать vip", "дать vip",
                    "выдать вип+", "дать вип+", "выдать vip+", "дать vip+",
                    "+вип", "+vip", "+вип+", "+vip+",
                    section=S_VIP, rank=0,
                    usage="выдать вип {ссылка} [срок] [1|2]", desc="Выдать VIP / VIP+ (только создатель)"))
async def cmd_give_vip(message: Message, bot: Bot, args: str = "", **kw):
    import config
    is_bot_owner = bool(message.from_user and message.from_user.id == config.OWNER_ID)
    if not is_bot_owner:
        return await message.reply(
            "🔒 <b>Выдача VIP доступна исключительно Создателю бота!</b>\n\n"
            "Приобрести статус: напишите <code>купить вип</code> или <code>купить вип+</code>!"
        )

    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply(
            "Укажите пользователя: <code>выдать вип @user [срок]</code> или <code>выдать вип+ @user [срок]</code>")

    msg_cmd = (message.text or "").split()[0].lower() if message.text else ""
    default_lvl = 2 if ("+" in msg_cmd or "vip+" in msg_cmd or "вип+" in msg_cmd) else 1

    level = default_lvl
    parts = rest.split()
    clean_parts = []
    for p in parts:
        p_low = p.lower()
        if p_low in ("1", "vip", "вип"):
            level = 1
        elif p_low in ("2", "vip+", "вип+", "плюс", "plus"):
            level = 2
        else:
            clean_parts.append(p)

    period_str = " ".join(clean_parts)
    secs, _ = parse_period(period_str)
    secs = secs or 30 * 86400

    until = int(time.time()) + secs
    await db.set_vip(uid, until, level)

    lvl_name = "🌟 VIP+ Diamond" if level == 2 else "⭐️ VIP"
    await message.reply(
        f"💎 {mention_id(uid, name)} получил статус <b>{lvl_name}</b> на <b>{human_period(secs)}</b>!\n"
        f"До: {time.strftime('%d.%m.%Y %H:%M', time.localtime(until))}")


@router.message(Cmd("снять вип", "забрать вип", "снять vip", "забрать vip",
                    "снять вип+", "забрать вип+", "снять vip+", "забрать vip+",
                    "-вип", "-vip", "-вип+", "-vip+",
                    section=S_VIP, rank=8, hidden=True,
                    usage="снять вип {ссылка}", desc="Снять статус VIP / VIP+ (только создатель)"))
async def cmd_remove_vip(message: Message, bot: Bot, args: str = "", **kw):
    import config
    is_bot_owner = bool(message.from_user and message.from_user.id == config.OWNER_ID)
    if not is_bot_owner:
        return await message.reply("🔒 <b>Снимать статус VIP может только создатель бота!</b>")

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: <code>снять вип @user</code>")

    await db.remove_vip(uid)
    await message.reply(f"⚪️ Статус VIP снят с {mention_id(uid, name)}.")
