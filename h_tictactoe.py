"""Интерактивные Крестики-Нолики (PVP дуэль) на нативных кнопках в Telegram.

Поддержка режимов (Арены):
- 3 × 3 (собрать 3 в ряд)
- 6 × 6 (собрать 4 в ряд)
- 7 × 7 (собрать 5 в ряд)

Выбор карты И фигуры ОБОИМИ игроками:
- Игрок 1 выбирает свою желанную арену и фигуру.
- Игрок 2 выбирает свою желанную арену и фигуру.
- При несовпадении честный жребий 50/50 разрешает спор и по карте, и по фигурам!
Строгая очередность: первым всегда ходит ❌, во время чужого хода кнопки блокируются всплывающим окном.
"""
from __future__ import annotations

import html
import random
import time
from typing import Any, Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_game_lock import is_in_game, lock_game, unlock_game
from core_registry import Cmd
from core_resolve import resolve_target
from utils import mention_id

router = Router(name="tictactoe")
S = 5  # Раздел «Игры и казино»

ARENAS = {
    "3x3": {"size": 3, "target": 3, "name": "3 × 3", "desc": "3 в ряд"},
    "6x6": {"size": 6, "target": 4, "name": "6 × 6", "desc": "4 в ряд"},
    "7x7": {"size": 7, "target": 5, "name": "7 × 7", "desc": "5 в ряд"},
}

GAMES: dict[str, GameSession] = {}


class GameSession:
    def __init__(
        self,
        game_id: str,
        chat_id: int,
        creator_id: int,
        creator_name: str,
        target_id: Optional[int],
        target_name: Optional[str],
        bet: int,
    ):
        self.game_id = game_id
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.target_id = target_id
        self.target_name = target_name
        self.bet = bet
        self.state = "lobby"  # lobby | playing | finished

        # Выбор карты ОБОИМИ игроками:
        self.creator_arena = "6x6"
        self.target_arena = "6x6"

        # Выбор фигуры ОБОИМИ игроками: "random" | "X" | "O"
        self.creator_choice = "X"
        self.target_choice = "random"

        # Итоговая выбранная арена (после жребия):
        self.arena_key = "6x6"

        # Игроки после старта:
        self.player_x_id = 0
        self.player_x_name = ""
        self.player_o_id = 0
        self.player_o_name = ""

        # Ход: ❌ всегда начинает первым!
        self.turn = "X"
        self.last_move_ts = 0

        # Поле инициализируется при старте
        self.board: list[list[str]] = []
        self.winning_cells: list[tuple[int, int]] = []
        self.winner: Optional[str] = None


def _generate_game_id() -> str:
    return hex(int(time.time() * 1000) % 0xFFFFFFF)[2:]


# ══════════════════════════════════════════════════════════════════
# ПРОВЕРКА ПОБЕДНЫХ ЛИНИЙ (ГОРИЗОНТАЛЬ, ВЕРТИКАЛЬ, ОБЕ ДИАГОНАЛИ)
# ══════════════════════════════════════════════════════════════════
def check_winner(board: list[list[str]], target_k: int) -> tuple[Optional[str], list[tuple[int, int]]]:
    """Проверяет непрерывную линию длины target_k во всех 4 направлениях."""
    n = len(board)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

    for r in range(n):
        for c in range(n):
            sym = board[r][c]
            if sym not in ("X", "O"):
                continue

            for dr, dc in directions:
                line = []
                for step in range(target_k):
                    nr, nc = r + dr * step, c + dc * step
                    if 0 <= nr < n and 0 <= nc < n and board[nr][nc] == sym:
                        line.append((nr, nc))
                    else:
                        break
                if len(line) == target_k:
                    return sym, line

    for row in board:
        if " " in row:
            return None, []
    return "draw", []


# ══════════════════════════════════════════════════════════════════
# РАЗРЕШЕНИЕ ВЫБОРА АРЕНЫ И ФИГУР МЕЖДУ 2 ИГРОКАМИ
# ══════════════════════════════════════════════════════════════════
def resolve_arena(c_ar: str, t_ar: str) -> tuple[str, str]:
    if c_ar == t_ar:
        return c_ar, f"🏟 <i>Оба игрока выбрали арену <b>{ARENAS[c_ar]['name']}</b>!</i>"
    
    # Спор: жребий 50/50 решает чья карта
    flip = random.choice([True, False])
    if flip:
        return c_ar, f"🎲 <i>Спор по карте ({ARENAS[c_ar]['name']} vs {ARENAS[t_ar]['name']}): жребий 50/50 выбрал карту создателя (<b>{ARENAS[c_ar]['name']}</b>)!</i>"
    else:
        return t_ar, f"🎲 <i>Спор по карте ({ARENAS[c_ar]['name']} vs {ARENAS[t_ar]['name']}): жребий 50/50 выбрал карту соперника (<b>{ARENAS[t_ar]['name']}</b>)!</i>"


def resolve_sides(creator_id: int, creator_name: str, c_side: str,
                  target_id: int, target_name: str, t_side: str) -> tuple[int, str, int, str, str]:
    # 1. Выбрали разные конкретные фигуры
    if c_side in ("X", "O") and t_side in ("X", "O") and c_side != t_side:
        if c_side == "X":
            return creator_id, creator_name, target_id, target_name, "✨ <i>Игроки выбрали разные стороны — каждый получил свою фигуру!</i>"
        else:
            return target_id, target_name, creator_id, creator_name, "✨ <i>Игроки выбрали разные стороны — каждый получил свою фигуру!</i>"

    # 2. Создатель выбрал фигуру, соперник — рандом
    elif c_side in ("X", "O") and t_side == "random":
        flip = random.choice([True, False])
        if (flip and c_side == "X") or (not flip and c_side == "O"):
            return creator_id, creator_name, target_id, target_name, f"🎲 <i>Создатель выбрал {c_side}, соперник — рандом. Жребий отдал выбор создателю!</i>"
        else:
            return target_id, target_name, creator_id, creator_name, f"🎲 <i>Создатель выбрал {c_side}, соперник — рандом. Жребий перевернул стороны!</i>"

    # 3. Соперник выбрал фигуру, создатель — рандом
    elif c_side == "random" and t_side in ("X", "O"):
        flip = random.choice([True, False])
        if (flip and t_side == "X") or (not flip and t_side == "O"):
            return target_id, target_name, creator_id, creator_name, f"🎲 <i>Соперник выбрал {t_side}, создатель — рандом. Жребий отдал выбор сопернику!</i>"
        else:
            return creator_id, creator_name, target_id, target_name, f"🎲 <i>Соперник выбрал {t_side}, создатель — рандом. Жребий перевернул стороны!</i>"

    # 4. Оба выбрали одну и ту же фигуру
    elif c_side in ("X", "O") and c_side == t_side:
        flip = random.choice([True, False])
        if flip:
            return creator_id, creator_name, target_id, target_name, f"⚔️ <i>Оба хотели играть за {c_side} — жребий 50/50 решил спор!</i>"
        else:
            return target_id, target_name, creator_id, creator_name, f"⚔️ <i>Оба хотели играть за {c_side} — жребий 50/50 решил спор!</i>"

    # 5. Оба выбрали рандом
    else:
        flip = random.choice([True, False])
        if flip:
            return creator_id, creator_name, target_id, target_name, "🎲 <i>Оба участника выбрали рандом — стороны определил жребий!</i>"
        else:
            return target_id, target_name, creator_id, creator_name, "🎲 <i>Оба участника выбрали рандом — стороны определил жребий!</i>"


# ══════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ И ТЕКСТ ЛОББИ
# ══════════════════════════════════════════════════════════════════
def render_lobby_kb(game: GameSession) -> InlineKeyboardMarkup:
    gid = game.game_id
    rows = []

    # 1. Выбор карты создателя (Ряд 1)
    c_ar_btns = []
    for k, a in ARENAS.items():
        is_sel = (k == game.creator_arena)
        prefix = "🔘" if is_sel else "⚪️"
        c_ar_btns.append(InlineKeyboardButton(text=f"{prefix} 👑 {a['name']}", callback_data=f"xo:ar:c:{gid}:{k}"))
    rows.append(c_ar_btns)

    # 2. Выбор карты соперника (Ряд 2)
    t_ar_btns = []
    for k, a in ARENAS.items():
        is_sel = (k == game.target_arena)
        prefix = "🔘" if is_sel else "⚪️"
        t_ar_btns.append(InlineKeyboardButton(text=f"{prefix} ⚔️ {a['name']}", callback_data=f"xo:ar:t:{gid}:{k}"))
    rows.append(t_ar_btns)

    # 3. Выбор стороны создателя (Ряд 3)
    c_side = game.creator_choice
    rows.append([
        InlineKeyboardButton(text=f"{'🔘' if c_side == 'random' else '⚪️'} 👑 🎲 Рандом", callback_data=f"xo:sd:c:{gid}:random"),
        InlineKeyboardButton(text=f"{'🔘' if c_side == 'X' else '⚪️'} 👑 ❌ Хочу X", callback_data=f"xo:sd:c:{gid}:X"),
        InlineKeyboardButton(text=f"{'🔘' if c_side == 'O' else '⚪️'} 👑 ⭕️ Хочу O", callback_data=f"xo:sd:c:{gid}:O"),
    ])

    # 4. Выбор стороны соперника и принятие (Ряд 4)
    rows.append([
        InlineKeyboardButton(text="⚔️ Принять (🎲)", callback_data=f"xo:accept:{gid}:random"),
        InlineKeyboardButton(text="⚔️ За ❌", callback_data=f"xo:accept:{gid}:X"),
        InlineKeyboardButton(text="⚔️ За ⭕️", callback_data=f"xo:accept:{gid}:O"),
    ])

    # 5. Отмена
    rows.append([
        InlineKeyboardButton(text="❌ Отменить вызов", callback_data=f"xo:cancel:{gid}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_board_kb(game: GameSession) -> InlineKeyboardMarkup:
    gid = game.game_id
    board = game.board
    size = len(board)
    rows = []

    win_set = set(game.winning_cells)

    for r in range(size):
        btn_row = []
        for c in range(size):
            cell = board[r][c]
            is_win = (r, c) in win_set

            if cell == "X":
                txt = "🌟" if is_win else "❌"
            elif cell == "O":
                txt = "🌟" if is_win else "⭕️"
            else:
                txt = "⬜️"

            btn_row.append(
                InlineKeyboardButton(
                    text=txt,
                    callback_data=f"xo:move:{gid}:{r}:{c}"
                )
            )
        rows.append(btn_row)

    if game.state == "playing":
        rows.append([
            InlineKeyboardButton(text="🏳️ Сдаться", callback_data=f"xo:surrender:{gid}"),
            InlineKeyboardButton(text="⏰ Тайм-аут (45с)", callback_data=f"xo:timeout:{gid}")
        ])
    elif game.state == "finished":
        rows.append([
            InlineKeyboardButton(text="🔄 Играть снова", callback_data=f"xo:rematch:{gid}"),
            InlineKeyboardButton(text="🚪 Закрыть", callback_data=f"xo:close:{gid}")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_lobby_text(game: GameSession) -> str:
    target_txt = f"⚔️ <b>Противник:</b> {mention_id(game.target_id, html.escape(game.target_name))}\n" if game.target_id else "👥 <b>Вызов:</b> <i>Открытый для любого желающего в чате!</i>\n"
    bet_txt = f"💰 <b>Ставка:</b> <code>{game.bet:,}</code> 🪙\n" if game.bet > 0 else "🎮 <b>Режим:</b> <i>Дружеский (без ставки)</i>\n"

    c_choice_map = {"random": "🎲 Рандом", "X": "❌ Крестик", "O": "⭕️ Нолик"}
    c_choice_txt = c_choice_map.get(game.creator_choice, "🎲 Рандом")
    t_choice_txt = c_choice_map.get(game.target_choice, "🎲 Рандом")

    c_ar_txt = ARENAS.get(game.creator_arena, {}).get("name", "6 × 6")
    t_ar_txt = ARENAS.get(game.target_arena, {}).get("name", "6 × 6")

    return (
        f"🎮 <b>ДУЭЛЬ В КРЕСТИКИ-НОЛИКИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Создатель:</b> {mention_id(game.creator_id, html.escape(game.creator_name))}\n"
        f"   • Карта: <b>{c_ar_txt}</b> | Фигура: <b>{c_choice_txt}</b>\n"
        f"{target_txt}"
        f"   • Карта: <b>{t_ar_txt}</b> | Фигура: <b>{t_choice_txt}</b>\n"
        f"{bet_txt}\n"
        f"👉 <i>Оба игрока выбирают карту и фигуру кнопками ниже.\n"
        f"Если карты или стороны не совпадут — решит честный жребий 50/50!</i>"
    )


# ══════════════════════════════════════════════════════════════════
# КОМАНДА ЗАПУСКА
# ══════════════════════════════════════════════════════════════════
@router.message(Cmd("кн", "крестики", "крестики нолики", "крестики-нолики", "xo",
                    section=S, rank=0, group_only=True,
                    usage="кн [@юзер] [ставка]",
                    desc="🎮 Дуэль в Крестики-Нолики на нативных кнопках (3х3, 6х6, 7х7)"))
async def cmd_tictactoe(message: Message, bot: Bot, args: str = "", **kw):
    cid = message.chat.id
    uid = message.from_user.id
    uname = message.from_user.first_name

    target_id, target_name, rem_args = await resolve_target(message, args, bot)
    bet = 0

    tokens = (rem_args or "").split()
    for tok in tokens:
        clean = tok.replace("k", "000").replace("к", "000").replace("m", "000000").replace("м", "000000")
        if clean.isdigit():
            bet = int(clean)
            break

    if target_id == uid:
        return await message.reply("🤔 Нельзя бросить вызов самому себе!")

    me = await bot.me()
    if target_id == me.id:
        return await message.reply("🤖 Сыграйте дуэль с другим участником чата: <code>кн @юзер [ставка]</code>!")

    if bet > 0:
        u_data = await db.get_user(uid)
        u_bal = int(u_data.get("balance", 0) or 0)
        if u_bal < bet:
            return await message.reply(
                f"💰 <b>Недостаточно средств для ставки!</b>\n\n"
                f"Ваш баланс: <b>{u_bal:,}</b> 🪙\n"
                f"Требуется: <b>{bet:,}</b> 🪙"
            )

    cur_g = is_in_game(uid)
    if cur_g:
        return await message.reply(f"⚠️ Вы уже находитесь в игре: <b>{cur_g}</b>!")

    gid = _generate_game_id()
    game = GameSession(
        game_id=gid,
        chat_id=cid,
        creator_id=uid,
        creator_name=uname,
        target_id=target_id,
        target_name=target_name,
        bet=bet,
    )
    GAMES[gid] = game

    text = _render_lobby_text(game)
    await message.reply(text, reply_markup=render_lobby_kb(game), disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════════
# ДЕЙСТВИЯ В ЛОББИ: ВЫБОР КАРТЫ ДЛЯ 1-ГО И 2-ГО ИГРОКА
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:ar:"))
async def cb_select_arena(call: CallbackQuery):
    parts = call.data.split(":")
    who = parts[2]  # 'c' (creator) | 't' (target)
    gid = parts[3]
    arena_key = parts[4]

    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Игра уже началась или недействительна", show_alert=True)

    uid = call.from_user.id

    if who == "c":
        if uid != game.creator_id:
            return await call.answer("⚠️ Это строка выбора карты для создателя дуэли!", show_alert=True)
        game.creator_arena = arena_key
        await call.answer(f"Создатель выбрал карту {ARENAS[arena_key]['name']}")
    else:
        if uid == game.creator_id:
            return await call.answer("⚠️ Это строка выбора карты для соперника!", show_alert=True)
        if game.target_id and uid != game.target_id:
            return await call.answer("Этот вызов брошен конкретному игроку!", show_alert=True)

        # Фиксируем соперника если был открытый вызов
        if not game.target_id:
            game.target_id = uid
            game.target_name = call.from_user.first_name

        game.target_arena = arena_key
        await call.answer(f"Соперник выбрал карту {ARENAS[arena_key]['name']}")

    text = _render_lobby_text(game)
    await call.message.edit_text(text, reply_markup=render_lobby_kb(game), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("xo:sd:"))
async def cb_select_side(call: CallbackQuery):
    parts = call.data.split(":")
    who = parts[2]  # 'c' (creator)
    gid = parts[3]
    choice = parts[4]

    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Лобби недоступно", show_alert=True)

    uid = call.from_user.id
    if uid != game.creator_id:
        return await call.answer("⚠️ Выбирать фигуру создателя может только создатель!", show_alert=True)

    game.creator_choice = choice
    choice_name = "🎲 Рандом" if choice == "random" else ("❌ Крестик" if choice == "X" else "⭕️ Нолик")
    await call.answer(f"Ваш выбор фигуры: {choice_name}")

    text = _render_lobby_text(game)
    await call.message.edit_text(text, reply_markup=render_lobby_kb(game), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("xo:cancel:"))
async def cb_cancel_game(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Игра уже началась или недействительна")

    uid = call.from_user.id
    if uid != game.creator_id:
        return await call.answer("Отменить дуэль может только создатель!", show_alert=True)

    GAMES.pop(gid, None)
    await call.message.edit_text("🛑 <b>Дуэль в Крестики-Нолики отменена создателем.</b>")
    await call.answer("Отменено")


# ══════════════════════════════════════════════════════════════════
# ПРИНЯТИЕ И ЗАПУСК
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:accept:"))
async def cb_accept_game(call: CallbackQuery):
    parts = call.data.split(":")
    gid = parts[2]
    side_pref = parts[3] if len(parts) > 3 else "random"

    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Игра уже началась или устарела!", show_alert=True)

    uid = call.from_user.id
    uname = call.from_user.first_name

    if uid == game.creator_id:
        return await call.answer("Вы создатель этой дуэли! Ожидайте второго игрока.", show_alert=True)

    if game.target_id and uid != game.target_id:
        return await call.answer("Этот вызов брошен конкретному игроку!", show_alert=True)

    # Проверка баланса
    if game.bet > 0:
        c_data = await db.get_user(game.creator_id)
        if int(c_data.get("balance", 0) or 0) < game.bet:
            GAMES.pop(gid, None)
            return await call.message.edit_text("❌ У создателя дуэли недостаточно монет для подтверждения ставки.")

        u_data = await db.get_user(uid)
        if int(u_data.get("balance", 0) or 0) < game.bet:
            return await call.answer("У вас недостаточно монет для принятия этой ставки!", show_alert=True)

    if is_in_game(uid):
        return await call.answer("Вы уже находитесь в другой активной игре!", show_alert=True)

    game.target_id = uid
    game.target_name = uname
    game.target_choice = side_pref

    # 1. Разрешаем Арену (Карту)
    resolved_ar, ar_note = resolve_arena(game.creator_arena, game.target_arena)
    game.arena_key = resolved_ar
    ar_info = ARENAS[resolved_ar]

    # 2. Разрешаем Фигуры (Стороны)
    px_id, px_name, po_id, po_name, side_note = resolve_sides(
        game.creator_id, game.creator_name, game.creator_choice,
        game.target_id, game.target_name, game.target_choice
    )
    game.player_x_id, game.player_x_name = px_id, px_name
    game.player_o_id, game.player_o_name = po_id, po_name

    # Создаем поле под выбранную арену
    size = ar_info["size"]
    game.board = [[" " for _ in range(size)] for _ in range(size)]

    # Списание ставок
    if game.bet > 0:
        await db.add_balance(game.creator_id, -game.bet, "tictactoe_bet", gid)
        await db.add_balance(game.target_id, -game.bet, "tictactoe_bet", gid)

    # Блокировка игроков
    lock_game(game.player_x_id, "❌ Крестики-Нолики", game.chat_id)
    lock_game(game.player_o_id, "⭕️ Крестики-Нолики", game.chat_id)

    game.state = "playing"
    game.turn = "X"  # Первым ВСЕГДА ходит Крестик!
    game.last_move_ts = int(time.time())

    pot = game.bet * 2
    pot_txt = f"💰 <b>Банк игры:</b> <code>{pot:,}</code> 🪙\n" if pot > 0 else ""

    text = (
        f"🎮 <b>КРЕСТИКИ-НОЛИКИ [{ar_info['name']}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
        f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
        f"🎯 <b>Цель:</b> <b>{ar_info['desc']}</b> (в любом направлении!)\n"
        f"{pot_txt}\n"
        f"{ar_note}\n"
        f"{side_note}\n\n"
        f"👉 <b>СЕЙЧАС ХОДИТ:</b> ❌ <b>{html.escape(game.player_x_name)}</b>\n"
        f"⏳ <i>Осталось времени на ход: 45 сек</i>"
    )

    await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
    await call.answer("Дуэль началась! Первый ход делает Крестик.")


# ══════════════════════════════════════════════════════════════════
# ИГРОВОЙ ХОД И ПРОВЕРКА ОЧЕРЕДНОСТИ
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:move:"))
async def cb_make_move(call: CallbackQuery):
    _, _, gid, s_r, s_c = call.data.split(":")
    r, c = int(s_r), int(s_c)

    game = GAMES.get(gid)
    if not game or game.state != "playing":
        return await call.answer("Игра завершена или не найдена!")

    uid = call.from_user.id

    if uid not in (game.player_x_id, game.player_o_id):
        return await call.answer("⛔️ Это чужая дуэль! Начните свою: кн [ставка]", show_alert=True)

    if game.turn == "X":
        if uid != game.player_x_id:
            return await call.answer(
                f"⏳ Сейчас ход Крестика ({game.player_x_name})!\nВы заблокированы до завершения его хода.",
                show_alert=True
            )
        current_sym = "X"
        next_turn = "O"
        next_name = game.player_o_name
    else:
        if uid != game.player_o_id:
            return await call.answer(
                f"⏳ Сейчас ход Нолика ({game.player_o_name})!\nВы заблокированы до завершения его хода.",
                show_alert=True
            )
        current_sym = "O"
        next_turn = "X"
        next_name = game.player_x_name

    if game.board[r][c] != " ":
        return await call.answer("⚠️ Эта клетка уже занята! Выберите свободную.", show_alert=False)

    game.board[r][c] = current_sym
    game.last_move_ts = int(time.time())

    target_k = ARENAS[game.arena_key]["target"]
    winner, win_line = check_winner(game.board, target_k)
    ar_info = ARENAS[game.arena_key]

    if winner in ("X", "O"):
        game.state = "finished"
        game.winner = winner
        game.winning_cells = win_line

        unlock_game(game.player_x_id)
        unlock_game(game.player_o_id)

        winner_id = game.player_x_id if winner == "X" else game.player_o_id
        winner_name = game.player_x_name if winner == "X" else game.player_o_name
        loser_id = game.player_o_id if winner == "X" else game.player_x_id
        loser_name = game.player_o_name if winner == "X" else game.player_x_name
        sym_win = "❌" if winner == "X" else "⭕️"

        pot = game.bet * 2
        reward_txt = ""
        if pot > 0:
            await db.add_balance(winner_id, pot, "tictactoe_win", gid)
            await db.add_xp(winner_id, 80)
            await db.add_xp(loser_id, 20)
            reward_txt = f"\n💰 <b>Выигрыш:</b> <code>+{pot:,}</code> 🪙 зачислены победителю!"

        text = (
            f"🏆 <b>ПОБЕДА В КРЕСТИКИ-НОЛИКИ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{sym_win} <b>Победитель:</b> {mention_id(winner_id, html.escape(winner_name))}\n"
            f"🎯 Собрана победная линия из <b>{target_k}</b> в ряд (🌟)!"
            f"{reward_txt}\n\n"
            f"👏 Поздравляем победителя дуэли!"
        )
        await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
        return await call.answer("Победа!")

    elif winner == "draw":
        game.state = "finished"
        game.winner = "draw"

        unlock_game(game.player_x_id)
        unlock_game(game.player_o_id)

        if game.bet > 0:
            await db.add_balance(game.player_x_id, game.bet, "tictactoe_refund", gid)
            await db.add_balance(game.player_o_id, game.bet, "tictactoe_refund", gid)

        text = (
            f"🤝 <b>БОЕВАЯ НИЧЬЯ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Все клетки арены <b>{ar_info['name']}</b> заполнены!\n"
            f"Ни один игрок не уступил позиции.\n"
            f"💰 Ставки возвращены участникам в полном объеме."
        )
        await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
        return await call.answer("Ничья!")

    game.turn = next_turn
    turn_sym = "❌" if next_turn == "X" else "⭕️"
    pot = game.bet * 2
    pot_txt = f"💰 <b>Банк игры:</b> <code>{pot:,}</code> 🪙\n" if pot > 0 else ""

    text = (
        f"🎮 <b>КРЕСТИКИ-НОЛИКИ [{ar_info['name']}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
        f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
        f"🎯 <b>Цель:</b> <b>{ar_info['desc']}</b> (в любом направлении!)\n"
        f"{pot_txt}\n"
        f"👉 <b>СЕЙЧАС ХОДИТ:</b> {turn_sym} <b>{html.escape(next_name)}</b>\n"
        f"⏳ <i>Осталось времени на ход: 45 сек</i>"
    )
    await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
    await call.answer()


# ══════════════════════════════════════════════════════════════════
# СДАЧА И ТАЙМ-АУТ
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:surrender:"))
async def cb_surrender(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    game = GAMES.get(gid)
    if not game or game.state != "playing":
        return await call.answer("Игра неактивна")

    uid = call.from_user.id
    if uid not in (game.player_x_id, game.player_o_id):
        return await call.answer("Вы не участник этой игры!", show_alert=True)

    winner_id = game.player_o_id if uid == game.player_x_id else game.player_x_id
    winner_name = game.player_o_name if uid == game.player_x_id else game.player_x_name
    loser_name = game.player_x_name if uid == game.player_x_id else game.player_o_name

    game.state = "finished"
    unlock_game(game.player_x_id)
    unlock_game(game.player_o_id)

    pot = game.bet * 2
    if pot > 0:
        await db.add_balance(winner_id, pot, "tictactoe_surrender", gid)

    text = (
        f"🏳️ <b>ИГРОК СДАЛСЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{html.escape(loser_name)}</b> признал поражение.\n"
        f"🏆 Победитель: {mention_id(winner_id, html.escape(winner_name))}!\n"
        + (f"💰 Выигрыш: <code>+{pot:,}</code> 🪙" if pot > 0 else "")
    )
    await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
    await call.answer("Вы сдались")


@router.callback_query(F.data.startswith("xo:timeout:"))
async def cb_timeout_check(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    game = GAMES.get(gid)
    if not game or game.state != "playing":
        return await call.answer("Игра неактивна")

    uid = call.from_user.id
    if uid not in (game.player_x_id, game.player_o_id):
        return await call.answer("Вы не участник этой игры!")

    now = int(time.time())
    diff = now - game.last_move_ts
    if diff < 45:
        return await call.answer(f"Тайм-аут ещё не истёк! Осталось {45 - diff} сек ожидания.", show_alert=True)

    if game.turn == "X":
        winner_id, winner_name = game.player_o_id, game.player_o_name
        loser_name = game.player_x_name
    else:
        winner_id, winner_name = game.player_x_id, game.player_x_name
        loser_name = game.player_o_name

    game.state = "finished"
    unlock_game(game.player_x_id)
    unlock_game(game.player_o_id)

    pot = game.bet * 2
    if pot > 0:
        await db.add_balance(winner_id, pot, "tictactoe_timeout", gid)

    text = (
        f"⏰ <b>ТЕХНИЧЕСКОЕ ПОРАЖЕНИЕ (ТАЙМ-АУТ)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Игрок <b>{html.escape(loser_name)}</b> превысил лимит времени на ход (45 сек).\n"
        f"🏆 Победа присуждена: {mention_id(winner_id, html.escape(winner_name))}!\n"
        + (f"💰 Выигрыш: <code>+{pot:,}</code> 🪙" if pot > 0 else "")
    )
    await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
    await call.answer("Тайм-аут зафиксирован")


@router.callback_query(F.data.startswith("xo:close:"))
async def cb_close_game(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    GAMES.pop(gid, None)
    await call.message.delete()
    await call.answer()


@router.callback_query(F.data.startswith("xo:rematch:"))
async def cb_rematch(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    game = GAMES.get(gid)
    if not game:
        return await call.answer("Игра устарела. Напишите: кн [ставка]")

    new_gid = _generate_game_id()
    new_game = GameSession(
        game_id=new_gid,
        chat_id=game.chat_id,
        creator_id=game.creator_id,
        creator_name=game.creator_name,
        target_id=game.target_id,
        target_name=game.target_name,
        bet=game.bet,
    )
    new_game.creator_arena = game.creator_arena
    new_game.target_arena = game.target_arena
    new_game.creator_choice = game.creator_choice
    new_game.target_choice = game.target_choice
    GAMES[new_gid] = new_game

    text = _render_lobby_text(new_game)
    await call.message.reply(text, reply_markup=render_lobby_kb(new_game), disable_web_page_preview=True)
    await call.answer("Реванш предложен!")
