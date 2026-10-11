"""Постоянное меню внизу экрана (reply-клавиатура).

Стильный, эргономичный дизайн по образцу Iris:
- Только 2 кнопки в ряд (удобно нажимать с телефона);
- Верхняя широкая кнопка для Mini App / Казино;
- Без перегруза: только самые важные и частые разделы;
- Все под-игры открываются внутри кнопки «📋 Меню бота».
"""
from __future__ import annotations

from aiogram.types import (KeyboardButton, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)

BTN_ADMIN = "🛡 Админ-панель"
BTN_APP = "📱 Moxxi Mini App • Казино"
BTN_ADD = "➕ Добавить в группу"
BTN_HELP = "📖 Команды"
BTN_BALANCE = "💰 Мой баланс"
BTN_BONUS = "🎁 Бонус"
BTN_CHAT = "💬 Чат сообщества"
BTN_MENU = "📋 Меню бота"
BTN_REVIEWS = "⭐ Оставить отзыв"
BTN_SUPPORT = "🆘 Написать в поддержку"
BTN_VIP = "🌟 Купить VIP"
BTN_COINS = "🪙 Купить монеты"

# Что реально выполняется при нажатии кнопки (маппинг в команду)
ALIASES: dict[str, str] = {
    BTN_ADMIN: "админ",
    "админ": "админ",

    BTN_APP: "апп",
    "📱 Mini App": "апп",
    "mini app": "апп",
    "апп": "апп",
    "казик": "игры",
    "казино": "игры",

    BTN_ADD: "добавить",
    "➕ Добавить в группу": "добавить",
    "добавить в группу": "добавить",
    "добавить бота": "добавить",
    "добавить": "добавить",

    BTN_HELP: "команды",
    "команды": "команды",
    "помощь": "команды",

    BTN_BALANCE: "баланс",
    "💰 Мой баланс": "баланс",
    "🌑 Баланс": "баланс",
    "💰 Баланс": "баланс",
    "баланс": "баланс",
    "профиль": "профиль",

    BTN_BONUS: "бонус",
    "🎁 Бонус": "бонус",
    "бонус": "бонус",

    BTN_CHAT: "чат",
    "💬 Чат бота": "чат",
    "💬 Чат сообщества": "чат",
    "чат": "чат",
    "сообщество": "чат",
    "беседа": "чат",

    BTN_MENU: "меню",
    "📋 Меню": "меню",
    "📋 Меню бота": "меню",
    "меню": "меню",

    BTN_REVIEWS: "отзывы",
    "⭐ Оставить отзыв": "отзывы",
    "⭐ Отзывы": "отзывы",
    "отзывы": "отзывы",
    "отзыв": "отзывы",

    BTN_SUPPORT: "поддержка",
    "🆘 Написать в поддержку": "поддержка",
    "🆘 Поддержка": "поддержка",
    "поддержка": "поддержка",
    "тикет": "поддержка",
    "саппорт": "поддержка",

    BTN_VIP: "купить вип",
    "🌟 Купить VIP": "купить вип",
    "🌟 VIP": "купить вип",
    "купить вип": "купить вип",
    "купить вип+": "купить вип+",
    "купить vip": "купить вип",
    "вип": "вип команды",

    BTN_COINS: "купить монеты",
    "🪙 Купить монеты": "купить монеты",
    "купить монеты": "купить монеты",

    # Совместимость с предыдущими кнопками
    "🛍 Магазин": "магазин",
    "магазин": "магазин",
    "🏢 Бизнесы": "бизнесы",
    "бизнесы": "бизнесы",
    "🎰 Казино": "игры",
    "игры": "игры",
    "🐉 Боссы": "босс",
    "босс": "босс",
    "⚔️ Дуэли": "дуэли",
    "дуэли": "дуэли",
    "🎣 Рыбалка": "рыбалка",
    "рыбалка": "рыбалка",
    "📜 Квесты": "квесты",
    "квесты": "квесты",
    "💡 Идеи": "идеи",
    "идеи": "идеи",
    "📝 Описание": "описание",
    "описание": "описание",
}


def resolve(text: str) -> str | None:
    """Текст нажатой кнопки -> команда. None, если это не кнопка."""
    return ALIASES.get((text or "").strip())


async def main_menu(uid: int = 0) -> ReplyKeyboardMarkup:
    """Аккуратная постоянная клавиатура в стиле Iris."""
    rows = [
        [KeyboardButton(text=BTN_APP)],
        [KeyboardButton(text=BTN_ADD), KeyboardButton(text=BTN_HELP)],
        [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_BONUS)],
        [KeyboardButton(text=BTN_VIP), KeyboardButton(text=BTN_COINS)],
        [KeyboardButton(text=BTN_MENU), KeyboardButton(text=BTN_CHAT)],
        [KeyboardButton(text=BTN_REVIEWS), KeyboardButton(text=BTN_SUPPORT)],
    ]
    if uid:
        try:
            from h_adminpanel import is_staff
            if await is_staff(uid):
                rows.insert(0, [KeyboardButton(text=BTN_ADMIN)])
        except Exception:
            pass
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие или напишите команду")


def hide() -> ReplyKeyboardRemove:
    """Убрать клавиатуру — на время капчи."""
    return ReplyKeyboardRemove()
