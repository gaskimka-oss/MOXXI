"""🎲 Модуль Командных Пати-Игр («Крокодил / Угадай Слово»).

Быстрые внутричатовые игры на реакцию и эрудицию с автоматической
проверкой ответов в потоке сообщений и мгновенными денежными призами.
"""
from __future__ import annotations

import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
import core_ai as ai
from core_ranks import require
from core_registry import Cmd
from utils import mention, money

router = Router(name="party_games")
S = 43  # Раздел 43: Пати-игры и викторины

WORDS_BANK = [
    {"word": "дракон", "hint": "Огнедышащее чешуйчатое мифическое существо, охраняющее сокровищницы."},
    {"word": "пирамида", "hint": "Грандиозное древнее каменное сооружение в Египте."},
    {"word": "телескоп", "hint": "Оптический прибор для наблюдения за далёкими звёздами и планетами."},
    {"word": "вертолёт", "hint": "Летательный аппарат с несущим вращающимся винтом."},
    {"word": "водопад", "hint": "Стремительное падение потока реки с высокой скалы."},
    {"word": "аквариум", "hint": "Стеклянный резервуар с водой для содержания рыбок."},
    {"word": "джойстик", "hint": "Игровой манипулятор или геймпад для управления на консоли."},
    {"word": "капучино", "hint": "Популярный кофейный напиток с нежной молочной пенкой."},
    {"word": "микроскоп", "hint": "Прибор для рассматривания крошечных бактерий и клеток."},
    {"word": "шампанское", "hint": "Игристое вино, которое открывают с хлопком на Новый год."},
    {"word": "парашют", "hint": "Купол из ткани, замедляющий падение человека с самолёта."},
    {"word": "лабиринт", "hint": "Запутанная сеть коридоров и ходов с множеством тупиков."},
    {"word": "банкомат", "hint": "Уличное устройство для выдачи и внесения наличных денег."},
    {"word": "саксофон", "hint": "Золотистый духовой музыкальный инструмент, символ джаза."},
    {"word": "скафандр", "hint": "Герметичный костюм космонавта для выхода в открытый космос."},
    {"word": "астероид", "hint": "Каменная глыба, летящая в космическом пространстве."},
    {"word": "маяк", "hint": "Башня со световым сигналом на берегу для кораблей."},
    {"word": "динамит", "hint": "Взрывчатое вещество на основе нитроглицерина."},
    {"word": "гитара", "hint": "Струнный музыкальный инструмент с деревянным корпусом."},
    {"word": "айсберг", "hint": "Огромная плавающая ледяная гора в океане."},
]


def _make_mask(word: str) -> str:
    """Делает красивую маску: Д _ _ _ _ Н."""
    if len(word) <= 3:
        return "_ " * len(word)
    # Открываем первую и последнюю букву
    first = word[0].upper()
    last = word[-1].upper()
    middle = " _" * (len(word) - 2)
    return f"{first}{middle} {last}"


@router.message(Cmd("крокодил", "угадай слово", "игра слово", "викторина слово", section=S, rank=0,
                    usage="крокодил", desc="🎲 Запустить быструю игру «Угадай слово» в чате"))
async def cmd_start_word_game(message: Message, bot: Bot, **kw):
    cid = message.chat.id
    if message.chat.type == "private":
        return await message.reply("🎲 Игра «Угадай слово» запускается в группах для всех участников!")

    # Проверяем активную игру
    active = await db.get_active_word_game(cid)
    now = int(time.time())
    if active and (now - active["created_at"]) < 90:
        return await message.reply("⏳ В чате уже идёт игра! Угадайте текущее слово выше.")

    entry = random.choice(WORDS_BANK)
    word = entry["word"].lower().strip()
    hint = entry["hint"]
    mask = _make_mask(word)

    reward_coins = random.randint(250, 500)
    reward_xp = 35

    await db.set_word_game(cid, word, hint, reward_coins, reward_xp)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💡 Первая подсказка", callback_data=f"word_hint:{cid}"),
            InlineKeyboardButton(text="❌ Сдаться", callback_data=f"word_giveup:{cid}")
        ]
    ])

    text = (
        f"🎲 ✨ <b>ИГРА «УГАДАЙ СЛОВО» ОТ МОКСИ!</b> ✨ 🎲\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🧩 <b>Подсказка:</b> <i>«{hint}»</i>\n\n"
        f"🔤 <b>Слово:</b> <code>{mask}</code> ({len(word)} букв)\n\n"
        f"💰 Приз первому угадавшему: <b>+{money(reward_coins)}</b> · <b>+{reward_xp} XP</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👉 <i>Просто напишите ваш вариант слова прямо в этот чат!</i>"
    )
    await message.reply(text, reply_markup=kb)


async def _has_active_game(message: Message) -> bool:
    if message.chat.type == "private" or not message.text:
        return False
    t = message.text.strip()
    if t.startswith(("/", "!", ".")):
        return False
    active = await db.get_active_word_game(message.chat.id)
    return bool(active)


@router.message(_has_active_game)
async def word_game_listener(message: Message, bot: Bot):
    """Слушает текстовые сообщения в чате и проверяет ответ на слово."""
    text = message.text.strip().lower()
    cid = message.chat.id
    active = await db.get_active_word_game(cid)
    if not active:
        return

    correct_word = active["word"].lower().strip()

    # Проверяем совпадение
    if text == correct_word:
        await db.finish_word_game(cid)

        uid = message.from_user.id
        coins = active.get("reward_coins", 300)
        xp = active.get("reward_xp", 35)

        await db.add_balance(uid, coins)
        await db.add_xp(cid, uid, xp)

        win_msg = (
            f"🎉 ✨ <b>СЛОВО УГАДАНО!</b> ✨ 🎉\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"👑 <b>Победитель:</b> {mention(message.from_user)}!\n"
            f"🔤 Загаданное слово: <b>{correct_word.upper()}</b>\n\n"
            f"💰 <b>Выигрыш:</b> <b>+{money(coins)}</b> · <b>+{xp} XP</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🎲 <i>Следующий раунд: напишите <code>крокодил</code></i>"
        )
        return await message.reply(win_msg)


# ================== CALLBACKS ==================

@router.callback_query(F.data.startswith("word_hint:"))
async def cb_word_hint(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[1])
    active = await db.get_active_word_game(cid)
    if not active:
        return await call.answer("Игра уже завершена!", show_alert=True)

    w = active["word"]
    await call.answer(f"💡 Количество букв: {len(w)}. Первая буква: {w[0].upper()}, последняя: {w[-1].upper()}.", show_alert=True)


@router.callback_query(F.data.startswith("word_giveup:"))
async def cb_word_giveup(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split(":")[1])
    active = await db.get_active_word_game(cid)
    if not active:
        return await call.answer("Игра уже завершена!", show_alert=True)

    await db.finish_word_game(cid)
    w = active["word"]
    await call.message.edit_text(
        f"🏳️ <b>Раунд завершен!</b>\n\nНикто не смог угадать слово: <b>{w.upper()}</b>!\n"
        f"Запустить новый раунд: <code>крокодил</code>"
    )
    await call.answer("Раунд сброшен.")
