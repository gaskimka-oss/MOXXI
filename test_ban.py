import asyncio
from unittest.mock import AsyncMock
from aiogram import Bot
from aiogram.types import Message, Chat, User
import h_mod_bans
import db

async def test():
    await db.init()
    msg = AsyncMock(spec=Message)
    msg.text = 'бан'
    msg.caption = None
    msg.chat = Chat(id=-1001234567890, type='supergroup')
    msg.from_user = User(id=8036974481, is_bot=False, first_name='Фанат')
    msg.sender_chat = None
    msg.reply_to_message = None
    msg.entities = None
    msg.reply = AsyncMock()

    bot = AsyncMock(spec=Bot)
    
    for h in h_mod_bans.router.message.handlers:
        f = h.filters[0].callback
        match = await f(msg)
        if match:
            print('Matched handler:', h.callback.__name__, match)
            try:
                res = await h.callback(msg, bot, **match)
                print('Callback result:', res)
                print('msg.reply calls:', [c.args[0] for c in msg.reply.call_args_list])
            except Exception as e:
                import traceback
                traceback.print_exc()
            break

asyncio.run(test())
