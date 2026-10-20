import sys
sys.path.insert(0, r"c:\Users\eiema\OneDrive\Desktop\бот2.0")
import asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message, Chat, User
import db
import h_userinfo
import h_mod_bans
import h_mod_ranks
import h_staff_plus
import h_grams

async def run_tests():
    print("Initializing DB...")
    await db.init()
    print("DB initialized.")
    bot = AsyncMock()
    chat = Chat(id=-1003934033202, type='supergroup')
    user_kaktys = User(id=8297844640, is_bot=False, first_name='Kaktys6390')
    user_simba = User(id=8412527198, is_bot=False, first_name='Simba')

    print("--- 1. Testing 'кто я' ---")
    msg1 = AsyncMock(spec=Message)
    msg1.chat = chat
    msg1.from_user = user_kaktys
    msg1.sender_chat = None
    msg1.reply = AsyncMock()
    await h_userinfo.cmd_who_am_i(msg1, bot)
    print("SUCCESS 'кто я':", msg1.reply.call_args[0][0][:60].strip())

    print("\n--- 2. Testing 'чек щас' ---")
    msg2 = AsyncMock(spec=Message)
    msg2.chat = chat
    msg2.from_user = user_simba
    msg2.sender_chat = None
    msg2.reply_to_message = None
    msg2.reply = AsyncMock()
    await h_mod_bans.cmd_dossier(msg2, bot, args="щас", had_prefix=False)
    print("'чек щас' replies:", len(msg2.reply.call_args_list))
    assert len(msg2.reply.call_args_list) == 0

    print("\n--- 3. Testing 'снять выговор' guard in cmd_remove_rank ---")
    msg3 = AsyncMock(spec=Message)
    msg3.chat = chat
    msg3.from_user = user_kaktys
    msg3.sender_chat = None
    msg3.reply_to_message = None
    msg3.reply = AsyncMock()
    await h_mod_ranks.cmd_remove_rank(msg3, bot, args="выговор Simba", had_prefix=False)
    print("cmd_remove_rank replies:", len(msg3.reply.call_args_list))
    assert len(msg3.reply.call_args_list) == 0

    print("\n--- 4. Testing 'снять выговор' in cmd_remove_reprimand ---")
    msg3_rep = AsyncMock(spec=Message)
    msg3_rep.chat = chat
    msg3_rep.from_user = user_kaktys
    msg3_rep.sender_chat = None
    msg3_rep.reply_to_message = None
    msg3_rep.reply = AsyncMock()
    # Put dummy reprimand
    await db.execute(
        "INSERT INTO warns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
        (-1003934033202, 8412527198, 8297844640, "[ВЫГОВОР] Тест", 123456)
    )
    await h_staff_plus.cmd_remove_reprimand(msg3_rep, bot, args="8412527198", had_prefix=False)
    print("cmd_remove_reprimand reply:", msg3_rep.reply.call_args[0][0][:60].strip())

    print("\n--- 5. Testing self-reprimand ---")
    msg4 = AsyncMock(spec=Message)
    msg4.chat = chat
    msg4.from_user = user_kaktys
    msg4.sender_chat = None
    msg4.reply = AsyncMock()
    await h_staff_plus.cmd_give_reprimand(msg4, bot, args="8297844640 Нарушение")
    print("self-reprimand reply:", msg4.reply.call_args[0][0].strip())
    assert "Нельзя выдать выговор самому себе" in msg4.reply.call_args[0][0]

    print("\n--- 6. Testing duplicate business buy ---")
    msg5 = AsyncMock(spec=Message)
    msg5.chat = chat
    msg5.from_user = user_simba
    msg5.sender_chat = None
    msg5.message_thread_id = 132681
    msg5.reply = AsyncMock()
    await h_grams.cmd_buy_business(msg5, args="кофейня 1", had_prefix=False)
    print("duplicate buy reply:", msg5.reply.call_args[0][0].strip())
    assert "Вы уже владеете" in msg5.reply.call_args[0][0]

    print("\n--- 7. Testing self coin giving ---")
    msg6 = AsyncMock(spec=Message)
    msg6.chat = chat
    msg6.from_user = user_kaktys
    msg6.sender_chat = None
    msg6.reply = AsyncMock()
    await h_grams.cmd_give_admin(msg6, bot, args="8297844640 90000", had_prefix=False)
    print("self coin reply:", msg6.reply.call_args[0][0].strip())
    assert "Запрещено выдавать монеты самому себе" in msg6.reply.call_args[0][0]

    print("\nALL 7 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
