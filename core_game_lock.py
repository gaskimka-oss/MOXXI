"""Управление блокировкой активных игр: защита от спама ставками и параллельных игр.

Игрок (включая админов и создателей) не может начать новую игру,
пока не завершилась предыдущая (слоты, кости, дартс, краш, мины, блэкджек, рулетка, скачки и т.д.).
"""
from __future__ import annotations

import time
from typing import Optional

# uid -> {"game": str, "started_at": float, "chat_id": int}
_ACTIVE_GAMES: dict[int, dict] = {}
GAME_TIMEOUT_SEC = 50  # Авто-сброс зависшей игры через 50 секунд

GAME_NAMES_RU = {
    "slots": "🎰 Слоты / Казино",
    "cube": "🎲 Кости / Кубик",
    "dice": "🎲 Кости / Кубик",
    "darts": "🎯 Дартс",
    "coin": "🪙 Орёл и Решка",
    "mines": "💣 Мины",
    "crash": "💥 Краш",
    "wheel": "🎡 Колесо фортуны",
    "sapper": "💣 Сапёр",
    "roulette": "🎡 Рулетка",
    "bj": "🃏 Блэкджек (21 очко)",
    "race": "🏇 Скачки",
    "duel": "⚔️ Дуэль",
    "bowling": "🎳 Боулинг",
    "football": "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
}


def is_in_game(uid: int) -> Optional[str]:
    """Если игрок в игре — возвращает понятное название текущей игры, иначе None."""
    info = _ACTIVE_GAMES.get(uid)
    if not info:
        return None
    now = time.time()
    if now - info.get("started_at", 0) > GAME_TIMEOUT_SEC:
        _ACTIVE_GAMES.pop(uid, None)
        return None
    code = info.get("game", "игра")
    return GAME_NAMES_RU.get(code, code)


def lock_game(uid: int, game_code: str, chat_id: int = 0) -> bool:
    """Пытается заблокировать игрока под игру. True — успешно заблокирован, False — уже играет."""
    current = is_in_game(uid)
    if current:
        return False
    _ACTIVE_GAMES[uid] = {
        "game": game_code,
        "started_at": time.time(),
        "chat_id": chat_id,
    }
    return True


def unlock_game(uid: int) -> None:
    """Освобождает игрока после выдачи результата."""
    _ACTIVE_GAMES.pop(uid, None)
