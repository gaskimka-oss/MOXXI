import asyncio
from unittest.mock import AsyncMock
from aiogram import Bot, Dispatcher
from aiogram.types import Message, Chat, User
import bot as main_bot

async def run_check():
    # Build list of all routers as in bot.main
    routers = [
        main_bot.nav.router, main_bot.adminpanel.router, main_bot.owner_panel.router,
        main_bot.clan_sync.router, main_bot.start.router, main_bot.helpmenu.router,
        main_bot.dk.router, main_bot.chatlock.router, main_bot.callall.router,
        main_bot.mod_ranks.router, main_bot.mod_bans.router, main_bot.security_plus.router,
        main_bot.staff_plus.router, main_bot.economy_plus.router, main_bot.social_plus.router,
        main_bot.veteran.router, main_bot.automod.router, main_bot.nightmode.router,
        main_bot.ai_features.router, main_bot.boss.router, main_bot.items.router,
        main_bot.duels.router, main_bot.clan_wars.router, main_bot.fishing_craft.router,
        main_bot.achievements.router, main_bot.quests.router, main_bot.pets.router,
        main_bot.market.router, main_bot.dungeon.router, main_bot.jackpot.router,
        main_bot.titles.router, main_bot.party_games.router, main_bot.webapp.router,
        main_bot.community_support.router, main_bot.chatset.router, main_bot.fun.router,
        main_bot.social_fun.router, main_bot.relations.router, main_bot.vip.router,
        main_bot.modules.router, main_bot.grams.router, main_bot.tournament.router,
        main_bot.rp.router, main_bot.botinfo.router, main_bot.userinfo.router,
        main_bot.passive.router
    ]

    test_words = ['бот', 'ии привет', 'команды', 'профиль', 'никлист']

    for text in test_words:
        msg = AsyncMock(spec=Message)
        msg.text = text
        msg.caption = None
        msg.chat = Chat(id=-1003934033202, type='supergroup')
        msg.from_user = User(id=8412527198, is_bot=False, first_name='Simba')
        msg.sender_chat = None
        msg.reply_to_message = AsyncMock(spec=Message) # in logs it was reply=True!
        msg.reply_to_message.from_user = User(id=8545937596, is_bot=True, first_name='MOXXI')
        msg.entities = None
        
        found = False
        print(f"--- Checking '{text}' ---", flush=True)
        for r in routers:
            for h in r.message.handlers:
                # check filters
                matched = True
                f_data = {}
                for f in h.filters:
                    try:
                        import inspect
                        bot_obj = AsyncMock(spec=Bot)
                        # check if takes bot
                        sig = inspect.signature(f)
                        if "bot" in sig.parameters:
                            res = await asyncio.wait_for(f(msg, bot=bot_obj), timeout=1.0)
                        else:
                            res = await asyncio.wait_for(f(msg), timeout=1.0)
                    except Exception as err:
                        try:
                            res = await asyncio.wait_for(f(msg, AsyncMock(spec=Bot)), timeout=1.0)
                        except Exception:
                            res = False
                    if not res:
                        matched = False
                        break
                    if isinstance(res, dict):
                        f_data.update(res)
                if matched:
                    print(f"[{text}] -> Router '{r.name}', Handler '{h.callback.__name__}', Data: {f_data}", flush=True)
                    found = True
                    break
            if found:
                break
        if not found:
            print(f"[{text}] -> NOT MATCHED BY ANY HANDLER!", flush=True)

asyncio.run(run_check())
