import asyncio
from aiogram import Bot
import db, h_userinfo
from config import BOT_TOKEN

async def test():
    await db.init()
    bot = Bot(token=BOT_TOKEN)
    with open("test_counts_output.txt", "w", encoding="utf-8") as f:
        for cid in [-1003934033202, -1004434155942]:
            real_count, known = await h_userinfo._get_chat_active_uids(cid, bot)
            f.write(f"Chat {cid}: real_count={real_count}, known_uids={len(known)}\n")
            
            nick_txt, _ = await h_userinfo._render_nick_list_page(cid, bot, 1)
            first_lines_n = [l for l in nick_txt.split('\n') if l.strip()][:3]
            f.write(f"Chat {cid} NICK LIST header:\n  " + "\n  ".join(first_lines_n) + "\n\n")
            
            desc_txt, _ = await h_userinfo._render_desc_list_page(cid, bot, 1)
            first_lines_d = [l for l in desc_txt.split('\n') if l.strip()][:5]
            f.write(f"Chat {cid} DESC LIST header:\n  " + "\n  ".join(first_lines_d) + "\n\n")
    await bot.session.close()

asyncio.run(test())
