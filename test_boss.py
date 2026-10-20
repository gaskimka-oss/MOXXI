import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r"c:\Users\eiema\OneDrive\Desktop\бот2.0")

from unittest.mock import AsyncMock
from aiogram.types import Message, Chat, User
import db, h_boss, core_ranks

async def test():
    await db.init()
    msg = AsyncMock(spec=Message)
    msg.text = 'заспавнить босса'
    msg.caption = None
    msg.chat = Chat(id=-1003934033202, type='supergroup', is_forum=True)
    msg.from_user = User(id=8412527198, is_bot=False, first_name='Simba')
    msg.sender_chat = None
    msg.reply_to_message = None
    msg.entities = None
    msg.message_thread_id = 132681  # казик topic
    msg.reply = AsyncMock()

    bot = AsyncMock()

    print('Checking handlers in h_boss.router...')
    matched = False
    for h in h_boss.router.message.handlers:
        for f in h.filters:
            match = await f.callback(msg)
            if match:
                print('Matched handler:', h.callback.__name__, match)
                matched = True
                try:
                    res = await h.callback(msg, bot, **match)
                    print('Callback result:', res)
                    print('msg.reply calls count:', len(msg.reply.call_args_list))
                    for c in msg.reply.call_args_list:
                        print('REPLY TEXT:', c.args[0] if c.args else c.kwargs)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                break
        if matched:
            break
    if not matched:
        print('NO HANDLER MATCHED!')

asyncio.run(test())
