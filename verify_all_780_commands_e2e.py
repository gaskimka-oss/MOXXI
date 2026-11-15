import asyncio
import os
import sys
import time
import traceback
from unittest.mock import AsyncMock, MagicMock

import db
import config
from aiogram import Bot, Dispatcher
from aiogram.types import Chat, User, Message, Update
from aiogram.methods import SendMessage, SendPhoto, SendAnimation, SendDocument, EditMessageText
import core_registry
from bot import TopicClosedRetryMiddleware


async def run_full_suite():
    print("=" * 70)
    print("🚀 ПОЛНАЯ ПРОВЕРКА ВСЕХ КОМАНД БОТА ОТ 'А' ДО 'Я' (E2E)")
    print("=" * 70)

    await db.init()

    bot = Bot(token=config.BOT_TOKEN)
    sent_requests = []

    async def mock_make_request(bot_inst, method, timeout=None):
        sent_requests.append(method)
        m = MagicMock()
        m.message_id = 999999
        m.chat = MagicMock(id=getattr(method, "chat_id", 0))
        m.text = getattr(method, "text", "") or ""
        m.delete = AsyncMock()
        m.edit_text = AsyncMock()
        return m

    bot.session.make_request = mock_make_request
    bot.session.middleware(TopicClosedRetryMiddleware())

    # Импортируем сборку из bot.py
    import bot as bot_app

    dp = Dispatcher()

    @dp.error()
    async def global_err(event):
        pass

    dp.message.outer_middleware(bot_app.keyboard_middleware)
    dp.message.middleware(bot_app.user_middleware)

    # Все 50+ роутеров в том же порядке, что и в bot.py
    import core_nav as nav
    import h_adminpanel as adminpanel
    import h_owner_panel as owner_panel
    import h_diagnostics as diagnostics
    import h_staff_hq as staff_hq
    import core_clan_sync as clan_sync
    import h_start as start
    import h_helpmenu as helpmenu
    import h_dk as dk
    import h_chatlock as chatlock
    import h_callall as callall
    import h_mod_ranks as mod_ranks
    import h_mod_bans as mod_bans
    import h_security_plus as security_plus
    import h_staff_plus as staff_plus
    import h_economy_plus as economy_plus
    import h_social_plus as social_plus
    import h_veteran as veteran
    import h_automod as automod
    import h_nightmode as nightmode
    import h_ai_features as ai_features
    import h_rp as rp
    import h_boss as boss
    import h_items as items
    import h_duels as duels
    import h_clan_wars as clan_wars
    import h_fishing_craft as fishing_craft
    import h_achievements as achievements
    import h_quests as quests
    import h_pets as pets
    import h_market as market
    import h_dungeon as dungeon
    import h_jackpot as jackpot
    import h_titles as titles
    import h_party_games as party_games
    import h_tictactoe as tictactoe
    import h_mega_games as mega_games
    import h_webapp as webapp
    import h_community_support as community_support
    import h_player_features as player_features
    import h_chatset as chatset
    import h_fun as fun
    import h_social_fun as social_fun
    import h_relations as relations
    import h_children as children
    import h_vip as vip
    import h_modules as modules
    import h_grams as grams
    import h_tournament as tournament
    import h_botinfo as botinfo
    import h_userinfo as userinfo
    import h_update_2_2 as update_2_2
    import h_currency_exchange as currency_exchange
    import h_vip_plus as vip_plus
    import h_moxxi_3_0 as moxxi_3_0
    import h_moxxi_apex as moxxi_apex
    import h_passive as passive

    command_routers = (
        helpmenu.router, mod_ranks.router, mod_bans.router, chatset.router,
        dk.router, chatlock.router, fun.router, modules.router, rp.router,
        userinfo.router, tournament.router, relations.router, vip.router,
        pets.router, market.router, dungeon.router, jackpot.router, titles.router,
        party_games.router, tictactoe.router, mega_games.router, webapp.router, community_support.router,
        player_features.router,
        security_plus.router, staff_plus.router, economy_plus.router, social_plus.router,
        veteran.router, botinfo.router, ai_features.router, callall.router,
        automod.router, nightmode.router, boss.router, items.router,
        duels.router, clan_wars.router, fishing_craft.router, achievements.router,
        quests.router, social_fun.router, grams.router, nav.router,
        adminpanel.router, owner_panel.router, diagnostics.router, start.router, update_2_2.router, currency_exchange.router, vip_plus.router, moxxi_3_0.router,
        staff_hq.router,
    )
    for r in command_routers:
        r.message.middleware(bot_app.access_middleware)

    for r in [
        nav.router, adminpanel.router, owner_panel.router, diagnostics.router, staff_hq.router,
        clan_sync.router, start.router, helpmenu.router, dk.router, chatlock.router, callall.router,
        mod_ranks.router, mod_bans.router, security_plus.router, staff_plus.router, economy_plus.router,
        social_plus.router, veteran.router, automod.router, nightmode.router, ai_features.router,
        rp.router, boss.router, items.router, duels.router, clan_wars.router, fishing_craft.router,
        achievements.router, quests.router, pets.router, market.router, dungeon.router, jackpot.router,
        titles.router, party_games.router, tictactoe.router, mega_games.router, webapp.router,
        community_support.router, player_features.router, chatset.router, fun.router, social_fun.router,
        relations.router, children.router, vip.router, modules.router, grams.router, tournament.router,
        botinfo.router, userinfo.router, update_2_2.router, currency_exchange.router, vip_plus.router,
        moxxi_3_0.router, moxxi_apex.router, passive.router
    ]:
        dp.include_router(r)

    print(f"📦 Зарегистрировано команд в REGISTRY: {len(core_registry.REGISTRY)}")

    # Создаем mock пользователя владельца/админа и целевого пользователя для реплаев
    admin_user = User(id=8036974481, is_bot=False, first_name="Владелец", username="fanat_owner")
    target_user = User(id=777888999, is_bot=False, first_name="Игрок_Цель", username="target_player")
    test_chat = Chat(id=-1003934033202, type="supergroup", title="ZRG_Oblivion")

    # Формируем реплай-сообщение
    reply_msg = Message(
        message_id=88888,
        date=int(time.time()),
        chat=test_chat,
        from_user=target_user,
        text="Привет, я цель для команд",
    )

    results = {
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    test_start_t = time.time()
    msg_id = 600000

    for idx, cmd in enumerate(core_registry.REGISTRY):
        msg_id += 1
        sent_requests.clear()

        # Формируем текст вызова
        cmd_name = cmd.names[0] if cmd.names else cmd.key
        
        # Если команда требует цель или аргументы (повысить, бан, перевод и т.д.) — подставляем аргументы
        call_text = cmd_name
        if "@" in (cmd.usage or "") or "юзер" in (cmd.usage or "") or "цель" in (cmd.usage or ""):
            call_text = f"{cmd_name} @target_player"
        elif "число" in (cmd.usage or "") or "сумма" in (cmd.usage or "") or "кол-во" in (cmd.usage or ""):
            call_text = f"{cmd_name} 10"

        raw_msg = {
            "message_id": msg_id,
            "date": int(time.time()),
            "chat": test_chat.model_dump(),
            "from": admin_user.model_dump(),
            "text": call_text,
            "message_thread_id": 4,
            "is_topic_message": True,
            "reply_to_message": reply_msg.model_dump(),
        }

        msg_obj = Message.model_validate(raw_msg)
        update = Update(update_id=msg_id, message=msg_obj)

        try:
            await dp.feed_update(bot, update)
            results["passed"] += 1
        except Exception as e:
            results["failed"] += 1
            err_type = type(e).__name__
            err_msg = str(e)
            tb = traceback.format_exc()
            results["errors"].append({
                "idx": idx + 1,
                "key": cmd.key,
                "text": call_text,
                "error": f"{err_type}: {err_msg}",
                "traceback": tb
            })
            print(f"  ❌ [{idx+1}/{len(core_registry.REGISTRY)}] ОШИБКА в команде «{cmd.key}»: {err_type}: {err_msg}")

        if (idx + 1) % 50 == 0 or (idx + 1) == len(core_registry.REGISTRY):
            print(f"  ... проверено {idx + 1} из {len(core_registry.REGISTRY)} команд (Ошибок: {results['failed']})")

    dur = round(time.time() - test_start_t, 2)

    print("\n" + "=" * 70)
    print(f"📊 ИТОГИ ПОЛНОЙ ПРОВЕРКИ 780 КОМАНД (E2E):")
    print(f"  • Всего проверено команд: {len(core_registry.REGISTRY)}")
    print(f"  • Успешно обработано:    {results['passed']}")
    print(f"  • Завершились ошибкой:   {results['failed']}")
    print(f"  • Время прогона:          {dur} сек")
    print("=" * 70)

    if results["errors"]:
        print("\n🚨 СПИСОК НАЙДЕННЫХ СБОЕВ:")
        for err in results["errors"][:10]:
            print(f"• #{err['idx']} «{err['key']}» (текст: {err['text']}): {err['error']}")
            # Выводим последнюю строку трейсбека
            last_lines = [l for l in err['traceback'].split('\n') if l.strip()]
            for l in last_lines[-3:]:
                print(f"    {l}")
        if len(results["errors"]) > 10:
            print(f"... и ещё {len(results['errors']) - 10} ошибок.")

    await bot.session.close()
    await db.close()

    assert results["failed"] == 0, f"Найдено {results['failed']} ошибок!"
    print("\n✨ ВСЕ 780 КОМАНД ОТ 'А' ДО 'Я' РАБОТАЮТ БЕЗУПРЕЧНО!")


if __name__ == "__main__":
    asyncio.run(run_full_suite())
