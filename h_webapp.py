"""📱 Модуль Telegram Mini App (Web App интерфейс Казино и Игр).

Предоставляет:
- Полноэкранный WebApp с Колесом Фортуны, Слотами, Минами, Крашем, Инвентарем и Терминалом Команд;
- Двустороннюю связь: отправку команд и действий из WebApp прямо в Telegram чат.
"""
from __future__ import annotations

import os
from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message, WebAppInfo)

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, money

router = Router(name="webapp")
S = 32  # Раздел 32: Инфо, справка и Mini App

# URL для Telegram WebApp (постоянный GitHub Pages хостинг с поддержкой HTTPS)
DEFAULT_WEBAPP_URL = os.getenv("WEBAPP_URL", "https://gaskimka-oss.github.io/MOXXI/").strip()


def _get_webapp_kb(url: str | None = None) -> InlineKeyboardMarkup:
    target_url = url or DEFAULT_WEBAPP_URL
    # Если URL не начинается с https://, используем постоянный GitHub Pages хостинг
    if not target_url.startswith("https://"):
        target_url = "https://gaskimka-oss.github.io/MOXXI/"

    if "t.me/" in target_url:
        top_btn = InlineKeyboardButton(text="📱 Открыть Moxxi Mini App (Казино & Игры)", url=target_url)
    else:
        top_btn = InlineKeyboardButton(text="📱 Открыть Moxxi Mini App (Казино & Игры)", web_app=WebAppInfo(url=target_url))

    return InlineKeyboardMarkup(inline_keyboard=[
        [top_btn],
        [
            InlineKeyboardButton(text="🎰 Слоты в чате", callback_data="jp:play_slots"),
            InlineKeyboardButton(text="💎 Джекпот", callback_data="jp:refresh:0")
        ]
    ])


@router.message(Cmd("апп", "webapp", "казик апп", "игры апп", "приложение", "мини апп", "хаб", "меню апп", section=S, rank=0,
                    usage="апп", desc="📱 Открыть интерактивный Telegram Mini App (Казино и Игры)"))
async def cmd_open_webapp(message: Message, bot: Bot, **kw):
    text = (
        "📱 ✨ <b>ИНТЕРАКТИВНЫЙ TELEGRAM MINI APP</b> ✨ 📱\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Добро пожаловать в визуальный игровой хаб Мокси!\n\n"
        "🎮 <b>Что доступно внутри приложения:</b>\n"
        "• 🎡 <b>Колесо Фортуны</b> — крутите пальцем с плавной физикой и выигрывайте джекпот!\n"
        "• 🎰 <b>Неоновые Слоты 777</b> — анимированные барабаны с виброоткликом;\n"
        "• 💣 <b>Игра «Мины»</b> — интерактивная сетка кристаллов и бомб;\n"
        "• 🚀 <b>Краш Ракета</b> — живой график роста множителя до x50.0;\n"
        "• 🎒 <b>Визуальный Инвентарь</b> — карточки оружия, брони и ресурсов;\n"
        "• ⌨️ <b>Терминал Команд</b> — быстрый запуск любых действий в чате в 1 клик!\n\n"
        "👇 <i>Нажмите кнопку ниже, чтобы запустить приложение:</i>"
    )
    await message.reply(text, reply_markup=_get_webapp_kb())


@router.message(F.web_app_data)
async def on_webapp_data_received(message: Message, bot: Bot):
    """Обрабатывает команды и действия, отправленные из WebApp."""
    raw_data = message.web_app_data.data.strip()
    if not raw_data:
        return

    # Эмулируем отправку команды от пользователя
    await message.reply(
        f"📱 <b>[Moxxi WebApp] Получено действие:</b> <code>{raw_data}</code>\n"
        f"⚡️ <i>Выполняю команду на арене...</i>"
    )

    # Запускаем обработку команды
    copy_msg = message.model_copy(update={"text": raw_data})
    dp = bot.__dict__.get("_dp")
    # Команда будет обработана стандартным диспетчером
