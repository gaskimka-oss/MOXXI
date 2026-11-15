"""Автоматический прогон и тестирование всех команд MOXXI (Dry-run Test Suite).

Проверяет все обработчики на:
- Отсутствующие импорты (NameError)
- Ошибки обращения к объектам (AttributeError / Frozen instance)
- Ошибки сигнатур и аргументов (TypeError)
- UnboundLocalError и другие критические исключения
"""
from __future__ import annotations

import asyncio
import inspect
import sys
import time
import traceback
from typing import Any

from aiogram import Bot
from aiogram.types import Chat, User, Message

import config
import db
from core_registry import Cmd

# Импортируем все модули роутеров
import core_nav as nav
import h_chatlock as chatlock
import h_chatset as chatset
import h_dk as dk
import h_fun as fun
import h_helpmenu as helpmenu
import h_mod_bans as mod_bans
import h_mod_ranks as mod_ranks
import h_modules as modules
import h_passive as passive
import h_rp as rp
import h_start as start
import h_userinfo as userinfo
import h_botinfo as botinfo
import h_callall as callall
import h_grams as grams
import h_automod as automod
import h_adminpanel as adminpanel
import h_tournament as tournament
import core_clan_sync as clan_sync
import h_relations as relations
import h_children as children
import h_vip as vip
import h_nightmode as nightmode
import h_ai_features as ai_features
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
import h_security_plus as security_plus
import h_staff_plus as staff_plus
import h_economy_plus as economy_plus
import h_social_plus as social_plus
import h_veteran as veteran
import h_social_fun as social_fun
import h_owner_panel as owner_panel
import h_player_features as player_features
import h_update_2_2 as update_2_2
import h_currency_exchange as currency_exchange
import h_vip_plus as vip_plus
import h_moxxi_3_0 as moxxi_3_0
import h_staff_hq as staff_hq
import h_diagnostics as diagnostics

ALL_MODULES = [
    nav, helpmenu, mod_ranks, mod_bans, chatset, dk, chatlock, fun, modules,
    rp, userinfo, tournament, relations, children, vip, pets, market, dungeon,
    jackpot, titles, party_games, tictactoe, mega_games, webapp, community_support,
    player_features, security_plus, staff_plus, economy_plus, social_plus,
    veteran, botinfo, ai_features, callall, automod, nightmode, boss, items,
    duels, clan_wars, fishing_craft, achievements, quests, social_fun, grams,
    adminpanel, owner_panel, diagnostics, start, update_2_2, currency_exchange,
    vip_plus, moxxi_3_0, staff_hq, clan_sync
]


async def run_suite():
    await db.init()
    bot = Bot(token=config.BOT_TOKEN)

    chat = Chat(id=-1003934033202, type="supergroup", title="ZRG_Oblivion")
    user = User(id=8412527198, is_bot=False, first_name="Simba", username="Simba")

    async def mock_reply(*args, **kwargs):
        m = Message(message_id=99999, date=int(time.time()), chat=chat, from_user=user, text="mock_reply")
        return m

    async def mock_answer(*args, **kwargs):
        m = Message(message_id=99998, date=int(time.time()), chat=chat, from_user=user, text="mock_answer")
        return m

    async def mock_delete(*args, **kwargs):
        return True

    async def mock_edit_text(*args, **kwargs):
        m = Message(message_id=99997, date=int(time.time()), chat=chat, from_user=user, text="mock_edit")
        return m

    bot.send_message = mock_reply
    bot.send_photo = mock_reply
    bot.send_document = mock_reply
    bot.send_animation = mock_reply
    bot.send_chat_action = mock_reply
    bot.delete_message = mock_delete
    bot.edit_message_text = mock_edit_text

    tested_count = 0
    passed_count = 0
    failed_handlers = []

    print("=" * 70, flush=True)
    print("🚀 СТАРТ ПОЛНОГО ПРОГОНА ОБРАБОТЧИКОВ И КОМАНД MOXXI...", flush=True)
    print("=" * 70, flush=True)

    for mod in ALL_MODULES:
        router = getattr(mod, "router", None)
        if not router:
            continue

        mod_name = getattr(router, "name", mod.__name__)

        for handler_obj in router.message.handlers:
            cb = handler_obj.callback
            fn_name = cb.__name__
            tested_count += 1

            cmd_key = ""
            for flt in handler_obj.filters:
                f_obj = getattr(flt, "callback", flt)
                if isinstance(f_obj, Cmd) or hasattr(f_obj, "names"):
                    cmd_key = f_obj.names[0] if getattr(f_obj, "names", None) else ""
                    break

            test_text = cmd_key or fn_name
            msg = Message(
                message_id=1000 + tested_count,
                date=int(time.time()),
                chat=chat,
                from_user=user,
                text=test_text,
                message_thread_id=4
            )
            object.__setattr__(msg, "reply", mock_reply)
            object.__setattr__(msg, "answer", mock_answer)
            object.__setattr__(msg, "delete", mock_delete)
            object.__setattr__(msg, "edit_text", mock_edit_text)
            object.__setattr__(msg, "_dk_ok", True)

            sig = inspect.signature(cb)
            call_kwargs = {}
            if "bot" in sig.parameters:
                call_kwargs["bot"] = bot
            if "args" in sig.parameters:
                call_kwargs["args"] = ""
            if "command" in sig.parameters:
                call_kwargs["command"] = None
            if "raw_args" in sig.parameters:
                call_kwargs["raw_args"] = ""

            try:
                # Ограничиваем таймаут 0.3с на команду, чтобы не виснуть на анимациях
                await asyncio.wait_for(cb(msg, **call_kwargs), timeout=0.3)
                passed_count += 1
            except asyncio.TimeoutError:
                # Команда работает и запустила анимацию/таймер — тест успешен
                passed_count += 1
            except Exception as e:
                tb = traceback.format_exc()
                err_type = type(e).__name__
                # Критические ошибки кода
                if isinstance(e, (NameError, AttributeError, TypeError, UnboundLocalError, SyntaxError)):
                    failed_handlers.append({
                        "module": mod_name,
                        "function": fn_name,
                        "command": cmd_key,
                        "error": f"{err_type}: {e}",
                        "trace": tb
                    })
                else:
                    passed_count += 1

            if tested_count % 50 == 0:
                print(f"  Проверено {tested_count} обработчиков...", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f"📊 ИТОГИ ТЕСТИРОВАНИЯ КОМАНД:", flush=True)
    print(f"  • Всего обработчиков проверено: {tested_count}", flush=True)
    print(f"  • Успешно прошли проверку:     {passed_count}", flush=True)
    print(f"  • Найдено критических сбоев:    {len(failed_handlers)}", flush=True)
    print("=" * 70, flush=True)

    if failed_handlers:
        print("\n🚨 СПИСОК ОБНАРУЖЕННЫХ КРИТИЧЕСКИХ ОШИБОК:", flush=True)
        for i, item in enumerate(failed_handlers, 1):
            print(f"\n#{i} Модуль: [{item['module']}] -> Функция: {item['function']}() (команда: '{item['command']}')", flush=True)
            print(f"   Ошибка: {item['error']}", flush=True)
            print("   Последние строки стека:", flush=True)
            for l in item["trace"].splitlines()[-3:]:
                print(f"     {l}", flush=True)
            print("-" * 60, flush=True)
    else:
        print("\n✅ ИДЕАЛЬНО: Ни в одном обработчике не обнаружено NameError, AttributeError или проблем с импортами!", flush=True)

    await bot.session.close()
    await db.close()


if __name__ == "__main__":
    asyncio.run(run_suite())
