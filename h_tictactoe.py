"""Интерактивные Крестики-Нолики (PVP дуэль) на нативных кнопках в Telegram.

Поддержка режимов (Арены):
- 3 × 3 (собрать 3 в ряд)
- 6 × 6 (собрать 4 в ряд)
- 7 × 7 (собрать 5 в ряд)

Проверка линий в любом направлении (горизонталь, вертикаль, обе диагонали).
Выбор стороны: Рандом или вручную (❌ / ⭕️) с честным разрешением жребием.
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

# Хранилище активных сессий: {game_id: GameSession}
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
        arena_key: str = "6x6",
    ):
        self.game_id = game_id
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.target_id = target_id
        self.target_name = target_name
        self.bet = bet
        self.arena_key = arena_key
        self.state = "lobby"  # lobby | playing | finished

        # Настройки выбора фигур в лобби: "random" | "X" | "O"
        self.creator_choice = "random"
        self.target_choice = "random"

        # Игроки после старта:
        self.player_x_id = 0
        self.player_x_name = ""
        self.player_o_id = 0
        self.player_o_name = ""

        # Текущий ход: "X" (всегда первый) или "O"
        self.turn = "X"
        self.last_move_ts = 0

        # Поле: список строк
        size = ARENAS[arena_key]["size"]
        self.board = [[" " for _ in range(size)] for _ in range(size)]
        self.winning_cells: list[tuple[int, int]] = []
        self.winner: Optional[str] = None  # "X", "O", "draw"


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

    # Проверка на ничью (нет пустых клеток)
    for row in board:
        if " " in row:
            return None, []
    return "draw", []


# ══════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ И ОТРИСОВКА
# ══════════════════════════════════════════════════════════════════
def render_lobby_kb(game: GameSession) -> InlineKeyboardMarkup:
    gid = game.game_id
    rows = []

    # 1. Выбор Арены
    arena_row = []
    for k, a in ARENAS.items():
        is_sel = (k == game.arena_key)
        prefix = "🔘" if is_sel else "⚪️"
        arena_row.append(
            InlineKeyboardButton(
                text=f"{prefix} {a['name']}",
                callback_data=f"xo:arena:{gid}:{k}"
            )
        )
    rows.append(arena_row)

    # 2. Выбор стороны для создателя
    c_side = game.creator_choice
    rows.append([
        InlineKeyboardButton(
            text=f"{'🔘' if c_side == 'random' else '⚪️'} 🎲 Рандом",
            callback_data=f"xo:side:{gid}:creator:random"
        ),
        InlineKeyboardButton(
            text=f"{'🔘' if c_side == 'X' else '⚪️'} ❌ Хочу X",
            callback_data=f"xo:side:{gid}:creator:X"
        ),
        InlineKeyboardButton(
            text=f"{'🔘' if c_side == 'O' else '⚪️'} ⭕️ Хочу O",
            callback_data=f"xo:side:{gid}:creator:O"
        ),
    ])

    # 3. Кнопки принятия вызова соперником (с выбором стороны)
    rows.append([
        InlineKeyboardButton(text="⚔️ Принять (🎲)", callback_data=f"xo:accept:{gid}:random"),
        InlineKeyboardButton(text="⚔️ За ❌", callback_data=f"xo:accept:{gid}:X"),
        InlineKeyboardButton(text="⚔️ За ⭕️", callback_data=f"xo:accept:{gid}:O"),
    ])

    # 4. Отмена
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

    # Вспомогательные кнопки внизу
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
    ar_info = ARENAS[game.arena_key]
    target_txt = f"⚔️ <b>Противник:</b> {mention_id(game.target_id, html.escape(game.target_name))}\n" if game.target_id else "👥 <b>Вызов:</b> <i>Открытый для любого желающего в чате!</i>\n"
    bet_txt = f"💰 <b>Ставка:</b> <code>{game.bet:,}</code> 🪙\n" if game.bet > 0 else "🎮 <b>Режим:</b> <i>Дружеский (без ставки)</i>\n"

    c_choice_map = {"random": "🎲 Рандом", "X": "❌ Крестик", "O": "⭕️ Нолик"}
    c_choice_txt = c_choice_map.get(game.creator_choice, "🎲 Рандом")

    return (
        f"🎮 <b>ДУЭЛЬ В КРЕСТИКИ-НОЛИКИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Создатель:</b> {mention_id(game.creator_id, html.escape(game.creator_name))}\n"
        f"{target_txt}"
        f"{bet_txt}"
        f"🏟 <b>Арена:</b> <b>{ar_info['name']}</b> ({ar_info['desc']})\n"
        f"🎯 <b>Желание создателя:</b> <b>{c_choice_txt}</b>\n\n"
        f"👉 <i>Создатель настраивает арену и свой выбор выше.\n"
        f"Соперник жмёт одну из кнопок «Принять» ниже:</i>"
    )


# ══════════════════════════════════════════════════════════════════
# КОМАНДА ЗАПУСКА И ВЫЗОВА
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
        arena_key="6x6",  # По умолчанию выбран 6x6 (4 в ряд)
    )
    GAMES[gid] = game

    text = _render_lobby_text(game)
    await message.reply(text, reply_markup=render_lobby_kb(game), disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════════
# ОБРАБОТКА ДЕЙСТВИЙ В ЛОББИ
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:arena:"))
async def cb_select_arena(call: CallbackQuery):
    _, _, gid, arena_key = call.data.split(":")
    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Игра уже началась или недействительна", show_alert=True)

    uid = call.from_user.id
    if uid != game.creator_id and (game.target_id and uid != game.target_id):
        return await call.answer("Настраивать параметры могут только участники дуэли!", show_alert=True)

    if arena_key in ARENAS:
        game.arena_key = arena_key
        size = ARENAS[arena_key]["size"]
        game.board = [[" " for _ in range(size)] for _ in range(size)]

    text = _render_lobby_text(game)
    await call.message.edit_text(text, reply_markup=render_lobby_kb(game), disable_web_page_preview=True)
    await call.answer(f"Выбрана арена {ARENAS[game.arena_key]['name']}")


@router.callback_query(F.data.startswith("xo:side:"))
async def cb_select_side(call: CallbackQuery):
    _, _, gid, role, choice = call.data.split(":")
    game = GAMES.get(gid)
    if not game or game.state != "lobby":
        return await call.answer("Лобби недоступно", show_alert=True)

    uid = call.from_user.id
    if uid == game.creator_id:
        game.creator_choice = choice
        choice_name = "🎲 Рандом" if choice == "random" else ("❌ Крестик" if choice == "X" else "⭕️ Нолик")
        await call.answer(f"Ваш выбор: {choice_name}")
    elif uid == game.target_id:
        game.target_choice = choice
        choice_name = "🎲 Рандом" if choice == "random" else ("❌ Крестик" if choice == "X" else "⭕️ Нолик")
        await call.answer(f"Ваш выбор: {choice_name}")
    else:
        return await call.answer("Выбирать сторону могут только участники дуэли!", show_alert=True)

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
# ПРИНЯТИЕ ДУЭЛИ И СТАРТ
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

    # ══════════════════════════════════════════════════════════════════
    # РАСПРЕДЕЛЕНИЕ ФИГУР ПО ПРАВИЛАМ
    # ══════════════════════════════════════════════════════════════════
    c_want = game.creator_choice
    t_want = game.target_choice
    c_name = game.creator_name
    t_name = game.target_name

    resolve_note = ""

    # 1. Если выбрали разные фигуры (один X, второй O) -> каждый получает своё
    if c_want in ("X", "O") and t_want in ("X", "O") and c_want != t_want:
        if c_want == "X":
            game.player_x_id, game.player_x_name = game.creator_id, c_name
            game.player_o_id, game.player_o_name = game.target_id, t_name
        else:
            game.player_o_id, game.player_o_name = game.creator_id, c_name
            game.player_x_id, game.player_x_name = game.target_id, t_name
        resolve_note = "✨ <i>Игроки выбрали разные стороны — каждый получил свою фигуру!</i>"

    # 2. Создатель выбрал фигуру, а соперник нажал «Рандом»
    elif c_want in ("X", "O") and t_want == "random":
        flip = random.choice([True, False])
        if (flip and c_want == "X") or (not flip and c_want == "O"):
            game.player_x_id, game.player_x_name = game.creator_id, c_name
            game.player_o_id, game.player_o_name = game.target_id, t_name
            resolve_note = f"🎲 <i>Создатель выбрал {c_want}, соперник — рандом. Жребий отдал выбор создателю!</i>"
        else:
            game.player_o_id, game.player_o_name = game.creator_id, c_name
            game.player_x_id, game.player_x_name = game.target_id, t_name
            resolve_note = f"🎲 <i>Создатель выбрал {c_want}, соперник — рандом. Жребий перевернул стороны!</i>"

    # 3. Соперник выбрал фигуру, а создатель нажал «Рандом»
    elif c_want == "random" and t_want in ("X", "O"):
        flip = random.choice([True, False])
        if (flip and t_want == "X") or (not flip and t_want == "O"):
            game.player_x_id, game.player_x_name = game.target_id, t_name
            game.player_o_id, game.player_o_name = game.creator_id, c_name
            resolve_note = f"🎲 <i>Соперник выбрал {t_want}, создатель — рандом. Жребий отдал выбор сопернику!</i>"
        else:
            game.player_o_id, game.player_o_name = game.target_id, t_name
            game.player_x_id, game.player_x_name = game.creator_id, c_name
            resolve_note = f"🎲 <i>Соперник выбрал {t_want}, создатель — рандом. Жребий перевернул стороны!</i>"

    # 4. Оба выбрали одну и ту же фигуру (конфликт) -> жребий 50/50
    elif c_want in ("X", "O") and c_want == t_want:
        flip = random.choice([True, False])
        if flip:
            game.player_x_id, game.player_x_name = game.creator_id, c_name
            game.player_o_id, game.player_o_name = game.target_id, t_name
        else:
            game.player_x_id, game.player_x_name = game.target_id, t_name
            game.player_o_id, game.player_o_name = game.creator_id, c_name
        resolve_note = f"⚔️ <i>Оба участника хотели играть за {c_want} — жребий 50/50 разрешил спор!</i>"

    # 5. Оба нажали «Рандом» -> чистый жребий
    else:
        flip = random.choice([True, False])
        if flip:
            game.player_x_id, game.player_x_name = game.creator_id, c_name
            game.player_o_id, game.player_o_name = game.target_id, t_name
        else:
            game.player_x_id, game.player_x_name = game.target_id, t_name
            game.player_o_id, game.player_o_name = game.creator_id, c_name
        resolve_note = "🎲 <i>Оба участника выбрали рандом — стороны определил жребий!</i>"

    # Списание ставок
    if game.bet > 0:
        await db.add_balance(game.creator_id, -game.bet, "tictactoe_bet", gid)
        await db.add_balance(game.target_id, -game.bet, "tictactoe_bet", gid)

    # Блокировка игроков от других азартных игр
    lock_game(game.player_x_id, "❌ Крестики-Нолики", game.chat_id)
    lock_game(game.player_o_id, "⭕️ Крестики-Нолики", game.chat_id)

    game.state = "playing"
    game.turn = "X"  # Первым ВСЕГДА ходит Крестик!
    game.last_move_ts = int(time.time())

    ar_info = ARENAS[game.arena_key]
    pot = game.bet * 2
    pot_txt = f"💰 <b>Банк игры:</b> <code>{pot:,}</code> 🪙\n" if pot > 0 else ""

    text = (
        f"🎮 <b>КРЕСТИКИ-НОЛИКИ [{ar_info['name']}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
        f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
        f"🎯 <b>Цель:</b> <b>{ar_info['desc']}</b> (в любом направлении!)\n"
        f"{pot_txt}\n"
        f"{resolve_note}\n\n"
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

    # 1. Защита от посторонних
    if uid not in (game.player_x_id, game.player_o_id):
        return await call.answer("⛔️ Это чужая дуэль! Начните свою: кн [ставка]", show_alert=True)

    # 2. Строгая проверка очередности хода
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

    # 3. Проверка занятости клетки
    if game.board[r][c] != " ":
        return await call.answer("⚠️ Эта клетка уже занята! Выберите свободную.", show_alert=False)

    # Совершаем ход
    game.board[r][c] = current_sym
    game.last_move_ts = int(time.time())

    # Проверяем результат (победа в любом направлении: - | \ /)
    target_k = ARENAS[game.arena_key]["target"]
    winner, win_line = check_winner(game.board, target_k)

    ar_info = ARENAS[game.arena_key]

    if winner in ("X", "O"):
        game.state = "finished"
        game.winner = winner
        game.winning_cells = win_line

        # Разблокируем игроков
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

        # Возврат ставок при ничьей
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

    # Игра продолжается: переключаем ход
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

    # Игрок, чей сейчас ход, затянул время -> техническое поражение
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
        arena_key=game.arena_key,
    )
    GAMES[new_gid] = new_game

    text = _render_lobby_text(new_game)
    await call.message.reply(text, reply_markup=render_lobby_kb(new_game), disable_web_page_preview=True)
    await call.answer("Реванш предложен!")
