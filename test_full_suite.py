import asyncio
import os
import re
import sys

sys.path.insert(0, r"c:\Users\eiema\OneDrive\Desktop\бот2.0")

from aiogram.types import Message, Chat, User
import core_registry
import core_access
from core_game_lock import is_in_game, lock_game, unlock_game
import h_fun
import h_grams
import h_botinfo
import h_ai_features
import h_chatset

def make_msg(text, is_group=True):
    return Message.model_construct(
        message_id=1,
        date=12345,
        chat=Chat(id=-1001234567890 if is_group else 12345, type="supergroup" if is_group else "private"),
        from_user=User(id=999, is_bot=False, first_name="Дима"),
        text=text
    )

async def test_suite():
    print("--- 1. Testing Anti-Trigger & Conversational Filtering ---")
    # 1. Бытовые фразы не должны триггерить бот
    for phrase in ["А як", "А где госпожа Елизавета 😅?", "а ты кто такой?", "а як справы", "А что тут происходит"]:
        m = make_msg(phrase)
        matched = []
        for c in core_registry.REGISTRY:
            f = core_registry.Cmd(*c.names, rank=c.rank, section=c.section, group_only=c.group_only)
            res = await f(m)
            if res:
                matched.append((c.key, res))
        print(f"Phrase '{phrase}' matches: {matched}")
        assert len(matched) == 0, f"Expected 0 matches for '{phrase}', got {matched}"

    # 2. Команды должны матчиться через Cmd
    expected_matches = [
        ("ии анализ", "ии итоги"),
        ("автонастройка", "автонастройка"),
        ("игры", "игры"),
        ("анонс обновлений", "обновление"),
        ("анонс обновления", "обновление"),
        ("рулетка 1000 на 7-8", "рулетка"),
        ("рулетка красное 500", "рулетка"),
        ("рулетка 23000000 11 12 14 13 15", "рулетка"),
    ]

    for cmd_text, expected_key in expected_matches:
        m = make_msg(cmd_text)
        matched = []
        for c in core_registry.REGISTRY:
            f = core_registry.Cmd(*c.names, rank=c.rank, section=c.section, group_only=c.group_only)
            res = await f(m)
            if res:
                matched.append(c.key)
        print(f"Command '{cmd_text}' matched keys: {matched}")
        assert expected_key in matched, f"Expected '{expected_key}' in matches for '{cmd_text}', got {matched}"

    # 3. Проверка прямого ввода ставок без слова 'рулетка'
    direct_pattern = re.compile(r"^(?:([\d\s]+)\s+на\s+(\d+[-–—]\d+|красн\w*|ч[её]рн\w*|зеро|0|[1-9]\d*)|(\d{3,})\s+((?:\b(?:[0-9]|[12][0-9]|3[0-6])\b\s*){2,}))\s*$", re.IGNORECASE)
    assert direct_pattern.match("1 111 111 на 7-8"), "Should match '1 111 111 на 7-8'"
    assert direct_pattern.match("1000 на красное"), "Should match '1000 на красное'"
    assert direct_pattern.match("23000000 11 12 14 13 15 10 9 8 7 6 5 4 3 2 1 0 17"), "Should match multi-bet line"
    assert not direct_pattern.match("Привет 2026"), "Should NOT match normal chat"
    assert not direct_pattern.match("А как дела"), "Should NOT match normal chat"
    print("Direct roulette regex pattern verified!")

    print("\n--- 2. Testing Game Lock Mechanism ---")
    test_uid = 777888999
    unlock_game(test_uid)
    assert is_in_game(test_uid) is None, "User should initially not be in game"

    locked1 = lock_game(test_uid, "slots", -100123)
    assert locked1 is True, "First lock_game must succeed"
    assert is_in_game(test_uid) == "🎰 Слоты / Казино", f"Current game should be slots, got {is_in_game(test_uid)}"

    # Попытка начать вторую игру во время слотов
    locked2 = lock_game(test_uid, "cube", -100123)
    assert locked2 is False, "Second lock_game must be blocked while first is active"

    # Разблокировка после завершения
    unlock_game(test_uid)
    assert is_in_game(test_uid) is None, "User should be free after unlock"

    locked3 = lock_game(test_uid, "cube", -100123)
    assert locked3 is True, "Can start new game after previous game finished"
    unlock_game(test_uid)

    print("Game lock passed successfully!")

    print("\n--- 3. Testing Auction Business Wealth Selection ---")
    # Проверяем логику выбора бизнеса при низком балансе игроков (chat_id = -999999, где нет богачей)
    chosen_biz, chosen_tier = await h_grams._select_auction_business(chat_id=-999999999999)
    info = h_grams.BUSINESS_TYPES[chosen_biz]
    print(f"Selected business for empty/beginner chat: {info['name']} (ID: {info['id']}, Tier: {chosen_tier})")
    assert 1 <= info["id"] <= 6, f"Expected business ID 1..6 for low-wealth chat, got {info['id']}"

    print("\n--- 4. Testing GAMES_TEXT Content ---")
    for game_keyword in ["СЛОТЫ", "ОРЁЛ И РЕШКА", "МИНЫ", "ДАРТС", "КРАШ", "КОЛЕСО", "КУБИК", "САПЁР", "РУЛЕТКА", "БЛЭКДЖЕК", "СКАЧКИ", "БОУЛИНГ", "ФУТБОЛ", "БАСКЕТБОЛ", "ДУЭЛЬ", "РЕЙД-БОСС", "РЫБАЛКА", "ВИКТОРИНА"]:
        assert game_keyword in h_grams.GAMES_TEXT, f"Missing {game_keyword} in GAMES_TEXT"
    print("All 18 games present in GAMES_TEXT!")

    print("\n--- 5. Testing UPDATE_PART_1 Content ---")
    assert "SMART FILTER" in h_botinfo.UPDATE_PART_1
    assert "GAME LOCK" in h_botinfo.UPDATE_PART_1
    assert "РУЛЕТКА 2.0" in h_botinfo.UPDATE_PART_1
    assert "УМНЫЙ АУКЦИОН ПРЕДПРИЯТИЙ" in h_botinfo.UPDATE_PART_1
    assert "GEMINI 3 FLASH" in h_botinfo.UPDATE_PART_1
    print("UPDATE_PART_1 contains all newly added updates!")

    print("\n===============================")
    print(">>> ALL VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
    print("===============================")

if __name__ == "__main__":
    asyncio.run(test_suite())
