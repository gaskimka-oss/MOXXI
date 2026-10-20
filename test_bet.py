import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from unittest.mock import AsyncMock
from aiogram.types import Message, Chat, User
import db, h_grams

async def test():
    await db.init()
    uid = 8412527198
    # Установим баланс для теста 5_000_000
    await db.set_balance(uid, 5_000_000)
    
    # 1. Тест: ставка 50_000_000 (больше баланса) в группе без префикса
    msg1 = AsyncMock(spec=Message)
    msg1.chat = Chat(id=-1003934033202, type="supergroup")
    msg1.message_thread_id = 132681
    msg1.from_user = User(id=uid, is_bot=False, first_name="Simba")
    msg1.reply = AsyncMock()
    
    res1 = await h_grams.take_bet(msg1, "50000000", had_prefix=False)
    print(f"Test 1 (50kk > 5kk): bet = {res1}")
    print(f"Test 1 reply text:\n{msg1.reply.call_args[0][0]}\n")
    assert res1 is None
    assert "Недостаточно монет" in msg1.reply.call_args[0][0]

    # 2. Тест: пустая ставка 'краш'
    msg2 = AsyncMock(spec=Message)
    msg2.chat = Chat(id=-1003934033202, type="supergroup")
    msg2.message_thread_id = 132681
    msg2.from_user = User(id=uid, is_bot=False, first_name="Simba")
    msg2.reply = AsyncMock()
    
    res2 = await h_grams.take_bet(msg2, "", had_prefix=False)
    print(f"Test 2 (empty): bet = {res2}")
    print(f"Test 2 reply text:\n{msg2.reply.call_args[0][0]}\n")
    assert res2 is None
    assert "Укажите ставку" in msg2.reply.call_args[0][0]

    # 3. Тест: ставка 1000 (успешная)
    msg3 = AsyncMock(spec=Message)
    msg3.chat = Chat(id=-1003934033202, type="supergroup")
    msg3.message_thread_id = 132681
    msg3.from_user = User(id=uid, is_bot=False, first_name="Simba")
    msg3.reply = AsyncMock()
    
    res3 = await h_grams.take_bet(msg3, "1000", had_prefix=False)
    print(f"Test 3 (1000): bet = {res3}")
    assert res3 == 1000

    print("ALL BET TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test())
