"""Вспомогательные функции: форматирование, парсинг сумм, уровни, доступ."""
from __future__ import annotations

import html
import re
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, Message, User

from config import ADMINS, CURRENCY, LEVELS, OWNER_ID


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + f" {CURRENCY}"


def mention(user: User) -> str:
    name = html.escape(user.first_name or "user")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def mention_id(user_id: int, name: str | None = None) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name or str(user_id))}</a>'


def level_of(xp: int) -> tuple[int, str, int, int]:
    """-> (номер уровня, название, xp текущего порога, xp следующего порога)"""
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if xp >= need:
            idx = i
    cur_need, title = LEVELS[idx]
    nxt = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else cur_need
    return idx + 1, title, cur_need, nxt


def parse_amount(text: str, balance: int, minimum: int = 1) -> Optional[int]:
    """Понимает: 100, 1k, 2.5кк, 10%, все/всё/all, половина/half."""
    if not text:
        return None
    t = text.strip().lower().replace(" ", "")
    if t in {"все", "всё", "all", "va", "макс", "max"}:
        return balance if balance >= minimum else None
    if t in {"половина", "half", "пол"}:
        return balance // 2
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)%", t)
    if m:
        pct = float(m.group(1).replace(",", "."))
        return int(balance * min(pct, 100) / 100)
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(k|к|kk|кк|m|м|kkk|ккк|b|б)?", t)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    suf = m.group(2) or ""
    mult = {"": 1, "k": 1e3, "к": 1e3, "kk": 1e6, "кк": 1e6, "m": 1e6, "м": 1e6,
            "kkk": 1e9, "ккк": 1e9, "b": 1e9, "б": 1e9}[suf]
    return int(val * mult)


def hms(seconds: int) -> str:
    h, rem = divmod(max(0, seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} ч {m} мин"
    if m:
        return f"{m} мин {s} сек"
    return f"{s} сек"


async def target_user(message: Message) -> Optional[User]:
    """Цель команды: реплай или @упоминание/числовой id в аргументах."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                return ent.user
    return None


def arg_text(message: Message) -> str:
    parts = (message.text or message.caption or "").split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def args_list(message: Message) -> list[str]:
    return (message.text or "").split()[1:]


AUTO_DELETE_DELAY = 300  # 5 минут


async def delayed_delete_message(bot, chat_id: int, message_id: int, delay: int = AUTO_DELETE_DELAY) -> None:
    """Удаляет сообщение через delay секунд (по умолчанию 5 минут) в группах."""
    if not bot or not chat_id or not message_id or chat_id >= 0:
        return
    import asyncio
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


def make_game_replay_kb(game_code: str, bet: int, uid: int, opt: str = "") -> InlineKeyboardMarkup:
    """Инлайн-кнопки повтора и управления ставкой под результатами игр казино."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from config import MAX_BET, MIN_BET

    double_bet = min(MAX_BET, bet * 2)
    half_bet = max(MIN_BET, bet // 2)

    label_repeat = f"🔄 Ещё раз ({money(bet)})"
    if game_code == "slots":
        label_repeat = f"🎰 Крутить ({money(bet)})"
    elif game_code == "cube":
        label_repeat = f"🎲 Бросить ({money(bet)})"
    elif game_code == "darts":
        label_repeat = f"🎯 Бросить ({money(bet)})"
    elif game_code == "coin":
        side_icon = "🦅 Орёл" if opt == "орёл" else "🪙 Решка"
        label_repeat = f"{side_icon} ({money(bet)})"
    elif game_code == "wheel":
        label_repeat = f"🎡 Крутить ({money(bet)})"
    elif game_code == "roulette":
        label_repeat = f"🎡 {opt.capitalize()} ({money(bet)})"
    elif game_code == "bj":
        label_repeat = f"🃏 Раздать карты ({money(bet)})"
    elif game_code == "race":
        h_idx = int(opt) if opt and opt.isdigit() else 1
        h_names = {1: "⚡ Молния", 2: "🛡 Буцефал", 3: "🪽 Пегас", 4: "🌪 Торнадо", 5: "💨 Ветерок"}
        label_repeat = f"🏇 {h_names.get(h_idx, 'Скачки')} ({money(bet)})"

    call_rep = f"grep:{game_code}:{bet}:{uid}:{opt}"
    call_x2 = f"grep:{game_code}:{double_bet}:{uid}:{opt}"
    call_half = f"grep:{game_code}:{half_bet}:{uid}:{opt}"
    call_jackpot = f"grep:jackpot:0:{uid}:{opt}"
    call_close = f"grep:close:0:{uid}:{opt}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label_repeat, callback_data=call_rep)],
        [
            InlineKeyboardButton(text=f"2x ({money(double_bet)})", callback_data=call_x2),
            InlineKeyboardButton(text=f"½ ({money(half_bet)})", callback_data=call_half),
        ],
        [
            InlineKeyboardButton(text="🔥 Джекпот чата", callback_data=call_jackpot),
            InlineKeyboardButton(text="❌ Забрать", callback_data=call_close),
        ]
    ])

