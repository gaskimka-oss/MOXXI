"""Интерактивные Крестики-Нолики (PVP дуэль) на нативных кнопках в Telegram.

Пошаговый сценарий дуэли:
1. Вызов: создатель кидает команду (например: кн @Simba 100к).
   У противника 2 кнопки: [ ⚔️ Принять вызов ] и [ ❌ Отклонить ].
   При отказе — игра отменяется («Simba отказался от игры»).
2. Выбор фигур: появляются кнопки [ ❌ Крестик ] и [ ⭕️ Нолик ].
   Кто первый выбрал фигуру, второй автоматически получает противоположную!
3. Выбор карты: оба голосуют кнопками [ 3 × 3 ], [ 6 × 6 ], [ 8 × 8 ].
   Если мнения разные — ИИ сам запускает рулетку (гоняет по кругу 3х3 -> 6х6 -> 8х8)
   и останавливается на выпавшей карте!
4. Игровое поле: первым всегда ходит ❌.
   Пока ходит ❌, соперник ⭕️ заблокирован. После хода — передача очереди.
   Победная линия (любое направление: ↔️ ↕️ ↘️ ↙️) подсвечивается 🌟.
5. Финал: кнопки [ 🔄 Сыграть снова ] и [ 🚪 Отказаться / Закрыть ].
"""
from __future__ import annotations

import asyncio
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
    "8x8": {"size": 8, "target": 5, "name": "8 × 8", "desc": "5 в ряд"},
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

        # Состояния: invite -> pick_side -> pick_arena -> playing -> finished
        self.state = "invite"

        # Игроки после распределения фигур
        self.player_x_id = 0
        self.player_x_name = ""
        self.player_o_id = 0
        self.player_o_name = ""

        # Голоса за арену: {user_id: '3x3' | '6x6' | '8x8'}
        self.arena_votes: dict[int, str] = {}
        self.arena_key = "6x6"

        # Игровой процесс
        self.turn = "X"
        self.last_move_ts = 0
        self.board: list[list[str]] = []
        self.winning_cells: list[tuple[int, int]] = []
        self.winner: Optional[str] = None


def _generate_game_id() -> str:
    return hex(int(time.time() * 1000) % 0xFFFFFFF)[2:]


# ══════════════════════════════════════════════════════════════════
# ПРОВЕРКА ПОБЕДЫ (ЛЮБОЕ НАПРАВЛЕНИЕ)
# ══════════════════════════════════════════════════════════════════
def check_winner(board: list[list[str]], target_k: int) -> tuple[Optional[str], list[tuple[int, int]]]:
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
# КЛАВИАТУРЫ ДЛЯ КАЖДОГО ЭТАПА
# ══════════════════════════════════════════════════════════════════

# ЭТАП 1: Принять или Отклонить
def kb_invite(gid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Принять вызов", callback_data=f"xo:inv:accept:{gid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"xo:inv:decline:{gid}")
        ]
    ])


# ЭТАП 2: Выбор фигур (Крестик или Нолик)
def kb_pick_side(gid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Я играю за Крестик", callback_data=f"xo:side:{gid}:X"),
            InlineKeyboardButton(text="⭕️ Я играю за Нолик", callback_data=f"xo:side:{gid}:O"),
        ],
        [
            InlineKeyboardButton(text="🚪 Отказаться от игры", callback_data=f"xo:cancel:{gid}")
        ]
    ])


# ЭТАП 3: Выбор карты (3х3, 6х6, 8х8)
def kb_pick_arena(gid: str, game: GameSession) -> InlineKeyboardMarkup:
    row = []
    for k, a in ARENAS.items():
        row.append(InlineKeyboardButton(text=f"🏟 {a['name']}", callback_data=f"xo:ar_vote:{gid}:{k}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text="🚪 Отказаться от игры", callback_data=f"xo:cancel:{gid}")]
    ])


# Рулетка: индикаторная клавиатура
def kb_roulette(highlight_key: str) -> InlineKeyboardMarkup:
    row = []
    for k, a in ARENAS.items():
        prefix = "🔘" if k == highlight_key else "⚪️"
        row.append(InlineKeyboardButton(text=f"{prefix} {a['name']}", callback_data="xo:noop"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


# ЭТАП 4: Игровое поле
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
            InlineKeyboardButton(text="🔄 Сыграть снова", callback_data=f"xo:rematch:{gid}"),
            InlineKeyboardButton(text="🚪 Отказаться / Закрыть", callback_data=f"xo:close:{gid}")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ══════════════════════════════════════════════════════════════════
# ЭТАП 1: КОМАНДА ВЫЗОВА
# ══════════════════════════════════════════════════════════════════
@router.message(Cmd("кн", "крестики", "крестики нолики", "крестики-нолики", "xo",
                    section=S, rank=0, group_only=True,
                    usage="кн [@юзер] [ставка]",
                    desc="🎮 Дуэль в Крестики-Нолики (с выбором сторон, карт и рулеткой)"))
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

    target_txt = f"⚔️ <b>Противник:</b> {mention_id(target_id, html.escape(target_name))}\n" if target_id else "👥 <b>Вызов:</b> <i>Открытый для любого желающего в чате!</i>\n"
    bet_txt = f"💰 <b>Ставка:</b> <code>{bet:,}</code> 🪙\n" if bet > 0 else "🎮 <b>Режим:</b> <i>Дружеский (без ставки)</i>\n"

    target_question = f"{mention_id(target_id, html.escape(target_name))}, вы принимаете вызов на дуэль?" if target_id else "Кто готов принять вызов на дуэль?"

    text = (
        f"🎮 <b>ВЫЗОВ НА ДУЭЛЬ В КРЕСТИКИ-НОЛИКИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Создатель:</b> {mention_id(uid, html.escape(uname))}\n"
        f"{target_txt}"
        f"{bet_txt}\n"
        f"❓ {target_question}"
    )

    await message.reply(text, reply_markup=kb_invite(gid), disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════════
# ЭТАП 1: ОБРАБОТКА «ПРИНЯТЬ» ИЛИ «ОТКЛОНИТЬ»
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:inv:"))
async def cb_invite_action(call: CallbackQuery):
    parts = call.data.split(":")
    action = parts[2]  # accept | decline
    gid = parts[3]

    game = GAMES.get(gid)
    if not game or game.state != "invite":
        return await call.answer("Вызов уже недействителен или дуэль началась!")

    uid = call.from_user.id
    uname = call.from_user.first_name

    # Создатель не может сам принимать свой вызов
    if uid == game.creator_id:
        return await call.answer("Вы создатель этого вызова! Ожидайте ответа соперника.", show_alert=True)

    # Если вызов был брошен конкретному игроку
    if game.target_id and uid != game.target_id:
        return await call.answer("Этот вызов брошен не вам!", show_alert=True)

    # 1. ОТКЛОНЕНИЕ
    if action == "decline":
        GAMES.pop(gid, None)
        text = f"🛑 <b>{html.escape(uname)} отказался от игры в Крестики-Нолики.</b>"
        await call.message.edit_text(text, reply_markup=None)
        return await call.answer("Вызов отклонен.")

    # 2. ПРИНЯТИЕ
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
    game.state = "pick_side"

    # Переход к ЭТАПУ 2: Выбор фигур
    bet_txt = f"💰 <b>Ставка:</b> <code>{game.bet:,}</code> 🪙\n" if game.bet > 0 else ""
    text = (
        f"🎮 <b>ВЫБОР ФИГУР ДЛЯ ДУЭЛИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Создатель:</b> {mention_id(game.creator_id, html.escape(game.creator_name))}\n"
        f"⚔️ <b>Противник:</b> {mention_id(game.target_id, html.escape(game.target_name))}\n"
        f"{bet_txt}\n"
        f"👉 <b>Кто первый нажмет кнопку — тот выбирает свою фигуру!</b>\n"
        f"Второму игроку автоматически достанется противоположная."
    )
    await call.message.edit_text(text, reply_markup=kb_pick_side(gid), disable_web_page_preview=True)
    await call.answer("Вызов принят! Выберите фигуру.")


# ══════════════════════════════════════════════════════════════════
# ЭТАП 2: ВЫБОР ФИГУРЫ (КРЕСТИК ИЛИ НОЛИК)
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:side:"))
async def cb_pick_side(call: CallbackQuery):
    parts = call.data.split(":")
    gid = parts[2]
    chosen_side = parts[3]  # X | O

    game = GAMES.get(gid)
    if not game or game.state != "pick_side":
        return await call.answer("Выбор фигур уже завершен или недействителен!")

    uid = call.from_user.id
    if uid not in (game.creator_id, game.target_id):
        return await call.answer("Вы не участник этой дуэли!", show_alert=True)

    # Определяем кто нажал
    is_creator = (uid == game.creator_id)
    clicker_name = game.creator_name if is_creator else game.target_name
    other_id = game.target_id if is_creator else game.creator_id
    other_name = game.target_name if is_creator else game.creator_name

    if chosen_side == "X":
        game.player_x_id, game.player_x_name = uid, clicker_name
        game.player_o_id, game.player_o_name = other_id, other_name
    else:
        game.player_o_id, game.player_o_name = uid, clicker_name
        game.player_x_id, game.player_x_name = other_id, other_name

    game.state = "pick_arena"
    game.arena_votes = {}

    bet_txt = f"💰 <b>Банк:</b> <code>{game.bet * 2:,}</code> 🪙\n" if game.bet > 0 else ""

    text = (
        f"🏟 <b>ВЫБОР КАРТЫ ДУЭЛИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
        f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
        f"{bet_txt}\n"
        f"👉 <b>Оба игрока выбирают карту кнопками ниже:</b>\n"
        f"• {html.escape(game.player_x_name)}: <i>⏳ Выбирает...</i>\n"
        f"• {html.escape(game.player_o_name)}: <i>⏳ Выбирает...</i>\n\n"
        f"<i>Если мнения совпадут — играем на ней.\nЕсли будут разные — ИИ запустит рулетку!</i>"
    )

    await call.message.edit_text(text, reply_markup=kb_pick_arena(gid, game), disable_web_page_preview=True)
    await call.answer(f"Вы выбрали {chosen_side}!")


# ══════════════════════════════════════════════════════════════════
# ЭТАП 3: ГОЛОСОВАНИЕ ЗА КАРТУ И РУЛЕТКА ИИ
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("xo:ar_vote:"))
async def cb_arena_vote(call: CallbackQuery):
    parts = call.data.split(":")
    gid = parts[2]
    vote_key = parts[3]  # 3x3 | 6x6 | 8x8

    game = GAMES.get(gid)
    if not game or game.state != "pick_arena":
        return await call.answer("Голосование за карту уже завершено!")

    uid = call.from_user.id
    if uid not in (game.player_x_id, game.player_o_id):
        return await call.answer("Вы не участник этой дуэли!", show_alert=True)

    game.arena_votes[uid] = vote_key
    await call.answer(f"Ваш голос: {ARENAS[vote_key]['name']}")

    x_vote = game.arena_votes.get(game.player_x_id)
    o_vote = game.arena_votes.get(game.player_o_id)

    x_status = f"<b>{ARENAS[x_vote]['name']}</b> ✅" if x_vote else "<i>⏳ Выбирает...</i>"
    o_status = f"<b>{ARENAS[o_vote]['name']}</b> ✅" if o_vote else "<i>⏳ Выбирает...</i>"

    bet_txt = f"💰 <b>Банк:</b> <code>{game.bet * 2:,}</code> 🪙\n" if game.bet > 0 else ""

    # Если еще не оба проголосовали
    if not (x_vote and o_vote):
        text = (
            f"🏟 <b>ВЫБОР КАРТЫ ДУЭЛИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
            f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
            f"{bet_txt}\n"
            f"👉 <b>Голосование за карту:</b>\n"
            f"• {html.escape(game.player_x_name)}: {x_status}\n"
            f"• {html.escape(game.player_o_name)}: {o_status}\n\n"
            f"<i>Если мнения совпадут — играем на ней.\nЕсли будут разные — ИИ запустит рулетку!</i>"
        )
        return await call.message.edit_text(text, reply_markup=kb_pick_arena(gid, game), disable_web_page_preview=True)

    # ══════════════════════════════════════════════════════════════════
    # ОБА ПРОГОЛОСОВАЛИ: СОВПАДЕНИЕ ИЛИ РУЛЕТКА ИИ!
    # ══════════════════════════════════════════════════════════════════
    game.state = "starting"

    # Вариант А: Единогласно
    if x_vote == o_vote:
        game.arena_key = x_vote
        await launch_game(call.message, game, resolve_reason=f"✨ <i>Оба игрока единогласно выбрали арену <b>{ARENAS[x_vote]['name']}</b>!</i>")
        return

    # Вариант Б: Мнения разные -> ИИ ЗАПУСКАЕТ РУЛЕТКУ САМ!
    arena_keys_cycle = ["3x3", "6x6", "8x8"]
    winning_key = random.choice([x_vote, o_vote])  # Выбираем честно между голосами
    game.arena_key = winning_key

    text_base = (
        f"🎲 <b>МНЕНИЯ РАЗДЕЛИЛИСЬ! ИИ ЗАПУСКАЕТ РУЛЕТКУ...</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• {html.escape(game.player_x_name)} выбрал: <b>{ARENAS[x_vote]['name']}</b>\n"
        f"• {html.escape(game.player_o_name)} выбрал: <b>{ARENAS[o_vote]['name']}</b>\n\n"
        f"⚡️ <i>ИИ гоняет рулетку по картам:</i>"
    )

    # Анимация рулетки: делает круг по 3x3 -> 6x6 -> 8x8
    steps = ["3x3", "6x6", "8x8", "3x3", "6x6", "8x8", winning_key]
    for step_key in steps:
        try:
            await call.message.edit_text(text_base, reply_markup=kb_roulette(step_key))
            await asyncio.sleep(0.42)
        except Exception:
            pass

    resolve_note = (
        f"🎯 <i>Рулетка ИИ остановилась на карте <b>{ARENAS[winning_key]['name']}</b>!</i>\n"
        f"({html.escape(game.player_x_name)} голосовал за {ARENAS[x_vote]['name']}, "
        f"{html.escape(game.player_o_name)} за {ARENAS[o_vote]['name']})"
    )

    await launch_game(call.message, game, resolve_reason=resolve_note)


# ══════════════════════════════════════════════════════════════════
# ЭТАП 4: СТАРТ ИГРОВОГО ПОЛЯ
# ══════════════════════════════════════════════════════════════════
async def launch_game(message: Message, game: GameSession, resolve_reason: str):
    ar_info = ARENAS[game.arena_key]
    size = ar_info["size"]
    game.board = [[" " for _ in range(size)] for _ in range(size)]
    game.state = "playing"
    game.turn = "X"  # ПЕРВЫМ ВСЕГДА ХОДИТ КРЕСТИК!
    game.last_move_ts = int(time.time())

    # Списание ставок
    if game.bet > 0:
        await db.add_balance(game.player_x_id, -game.bet, "tictactoe_bet", game.game_id)
        await db.add_balance(game.player_o_id, -game.bet, "tictactoe_bet", game.game_id)

    # Блокировка от других игр
    lock_game(game.player_x_id, "❌ Крестики-Нолики", game.chat_id)
    lock_game(game.player_o_id, "⭕️ Крестики-Нолики", game.chat_id)

    pot = game.bet * 2
    pot_txt = f"💰 <b>Банк игры:</b> <code>{pot:,}</code> 🪙\n" if pot > 0 else ""

    text = (
        f"🎮 <b>КРЕСТИКИ-НОЛИКИ [{ar_info['name']}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Крестик:</b> {mention_id(game.player_x_id, html.escape(game.player_x_name))}\n"
        f"⭕️ <b>Нолик:</b> {mention_id(game.player_o_id, html.escape(game.player_o_name))}\n"
        f"🎯 <b>Цель:</b> <b>{ar_info['desc']}</b> (в любом направлении: ↔️ ↕️ ↘️ ↙️)\n"
        f"{pot_txt}\n"
        f"{resolve_reason}\n\n"
        f"👉 <b>СЕЙЧАС ХОДИТ:</b> ❌ <b>{html.escape(game.player_x_name)}</b>\n"
        f"⏳ <i>Осталось времени на ход: 45 сек</i>"
    )

    await message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════════
# ЭТАП 4: ХОДЫ И БЛОКИРОВКИ
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

    # Строгая блокировка чужого хода
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
        return await call.answer("⚠️ Эта клетка уже занята! Выберите свободную белую клетку.", show_alert=False)

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
        f"🎯 <b>Цель:</b> <b>{ar_info['desc']}</b> (в любом направлении: ↔️ ↕️ ↘️ ↙️)\n"
        f"{pot_txt}\n"
        f"👉 <b>СЕЙЧАС ХОДИТ:</b> {turn_sym} <b>{html.escape(next_name)}</b>\n"
        f"⏳ <i>Осталось времени на ход: 45 сек</i>"
    )
    await call.message.edit_text(text, reply_markup=render_board_kb(game), disable_web_page_preview=True)
    await call.answer()


# ══════════════════════════════════════════════════════════════════
# СДАЧА, ТАЙМ-АУТ, ОТМЕНА, РЕВАНШ
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


@router.callback_query(F.data.startswith("xo:cancel:"))
async def cb_cancel_game(call: CallbackQuery):
    _, _, gid = call.data.split(":")
    game = GAMES.get(gid)
    if not game:
        return await call.answer("Игра уже недействительна")

    uid = call.from_user.id
    if uid not in (game.creator_id, game.target_id):
        return await call.answer("Отказаться могут только участники дуэли!", show_alert=True)

    canceler_name = game.creator_name if uid == game.creator_id else game.target_name
    GAMES.pop(gid, None)
    await call.message.edit_text(f"🛑 <b>{html.escape(canceler_name)} отказался от дуэли.</b>", reply_markup=None)
    await call.answer("Отменено")


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
    GAMES[new_gid] = new_game

    target_name = game.target_name or "Соперник"
    text = (
        f"🔄 <b>РЕВАНШ В КРЕСТИКИ-НОЛИКИ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 {mention_id(game.creator_id, html.escape(game.creator_name))} предлагает реванш!\n"
        f"⚔️ {mention_id(game.target_id, html.escape(target_name))}, принимаете?"
    )
    await call.message.reply(text, reply_markup=kb_invite(new_gid), disable_web_page_preview=True)
    await call.answer("Реванш предложен!")


@router.callback_query(F.data == "xo:noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()
