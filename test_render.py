import asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message, Chat, User
import db, h_userinfo

async def t():
    await db.init()
    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=-1003934033202, type='supergroup')
    msg.from_user = User(id=8412527198, is_bot=False, first_name='Simba')
    bot = AsyncMock()
    
    card = await h_userinfo.render_card(msg, bot, 8412527198, 'Simba')
    p = await h_userinfo._profile(8412527198)
    
    with open('test_card_out.txt', 'w', encoding='utf-8') as f:
        f.write('=== CARD ===\n' + card + '\n=== PROFILE ===\n' + str(dict(p)))
    print('Done!')

asyncio.run(t())
