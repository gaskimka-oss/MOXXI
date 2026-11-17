"""Запуск тестового бота MOXXI (Staging & Testing Environment).

Строгая изоляция:
- Токен: @testbotmoxxxi_bot (9275249158:AAFVcEQKCVmwgdrbO1llz4NidXwqiy1EAnY)
- База данных: data/test_moxxi.db (полностью изолирована от data/iris.db)
- Отключены выгрузки бэкапов в Telegram владельца и автоанонсы в чаты.
- Порт Healthcheck: 8089 (не конфликтует с основным ботом на 8080).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# --- 1. ПРИНУДИТЕЛЬНАЯ ИЗОЛЯЦИЯ ОКРУЖЕНИЯ ТЕСТ-БОТА ---
BASE_DIR = Path(__file__).resolve().parent
TEST_DB_PATH = (BASE_DIR / "data" / "test_moxxi.db").resolve()
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

TEST_BOT_TOKEN = "9275249158:AAFVcEQKCVmwgdrbO1llz4NidXwqiy1EAnY"

os.environ["TZ"] = "Europe/Moscow"
os.environ["BOT_TOKEN"] = TEST_BOT_TOKEN
os.environ["DB_PATH"] = str(TEST_DB_PATH)
os.environ["PORT"] = "8089"
os.environ["IS_TEST_BOT"] = "1"
os.environ["DISABLE_TELEGRAM_BACKUP"] = "1"

if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [TEST_BOT] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("moxxi.testbot")

# --- 2. ИМПОРТЫ КОНФИГУРАЦИИ И ЗАЩИТА ОТ ПРОДАКШНА ---
import config
import db

# Жёсткая проверка изоляции перед любыми действиями:
config.BOT_TOKEN = TEST_BOT_TOKEN
config.DB_PATH = TEST_DB_PATH
db.DB_PATH = TEST_DB_PATH

assert "test_moxxi.db" in str(config.DB_PATH), "КРИТИЧЕСКАЯ ОШИБКА: config.DB_PATH не указывает на test_moxxi.db!"
assert "test_moxxi.db" in str(db.DB_PATH), "КРИТИЧЕСКАЯ ОШИБКА: db.DB_PATH не указывает на test_moxxi.db!"
assert not str(db.DB_PATH).endswith("iris.db"), "КРИТИЧЕСКАЯ ОШИБКА: обнаружена попытка подключения к базе iris.db!"

# Отключаем автобэкапы в Telegram, чтобы не затирать бэкапы продакшна:
import core_backup
async def _noop_async(*args, **kwargs):
    return None
def _noop_sync(*args, **kwargs):
    return None

core_backup.restore_if_needed = _noop_async
core_backup.worker = _noop_async
core_backup.save = _noop_async
core_backup.schedule_quick_backup = _noop_sync

import h_botinfo
h_botinfo.announce_update_on_startup = _noop_async

import core_telemetry
core_telemetry.telemetry_worker = _noop_async

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

# Импортируем роутеры бота
import core_docs as docs
import core_seed as seed
import core_keyboard as kbd
from core_access import access_middleware
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
import h_moxxi_apex as moxxi_apex
import h_staff_hq as staff_hq
import h_diagnostics as diagnostics
import core_nav as nav
import h_webapp as webapp


async def set_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 Запуск тест-бота MOXXI"),
            BotCommand(command="help", description="📖 Меню помощи"),
            BotCommand(command="menu", description="📱 Интерактивное меню"),
            BotCommand(command="profile", description="👤 Профиль игрока"),
            BotCommand(command="topics", description="🧵 Управление темами"),
            BotCommand(command="balance", description="💰 Баланс монет"),
        ])
    except Exception as e:
        log.warning("Не удалось установить команды тест-бота: %s", e)


async def main() -> None:
    log.info("🧪 Инициализация тестовой базы данных: %s", TEST_DB_PATH)
    await db.init()
    await staff_hq.init_staff_tables()
    log.info("✅ Тестовая база данных готова (изолирована от продакшна).")

    bot = Bot(
        token=TEST_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключаем middleware в точности как в основном боте:
    from bot import user_middleware, keyboard_middleware, TopicClosedRetryMiddleware
    dp.message.outer_middleware(keyboard_middleware)
    dp.message.middleware(user_middleware)
    dp.callback_query.middleware(user_middleware)
    bot.session.middleware(TopicClosedRetryMiddleware())

    # ДК применяется к командным роутерам
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
        r.message.middleware(access_middleware)

    dp.include_router(nav.router)
    dp.include_router(adminpanel.router)
    dp.include_router(owner_panel.router)
    dp.include_router(diagnostics.router)
    dp.include_router(staff_hq.router)
    dp.include_router(clan_sync.router)
    dp.include_router(start.router)
    dp.include_router(helpmenu.router)
    dp.include_router(dk.router)
    dp.include_router(chatlock.router)
    dp.include_router(callall.router)
    dp.include_router(mod_ranks.router)
    dp.include_router(mod_bans.router)
    dp.include_router(security_plus.router)
    dp.include_router(staff_plus.router)
    dp.include_router(economy_plus.router)
    dp.include_router(social_plus.router)
    dp.include_router(veteran.router)
    dp.include_router(automod.router)
    dp.include_router(nightmode.router)
    dp.include_router(ai_features.router)
    dp.include_router(rp.router)
    dp.include_router(boss.router)
    dp.include_router(items.router)
    dp.include_router(duels.router)
    dp.include_router(clan_wars.router)
    dp.include_router(fishing_craft.router)
    dp.include_router(achievements.router)
    dp.include_router(quests.router)
    dp.include_router(pets.router)
    dp.include_router(market.router)
    dp.include_router(dungeon.router)
    dp.include_router(jackpot.router)
    dp.include_router(titles.router)
    dp.include_router(party_games.router)
    dp.include_router(tictactoe.router)
    dp.include_router(mega_games.router)
    dp.include_router(community_support.router)
    dp.include_router(player_features.router)
    dp.include_router(chatset.router)
    dp.include_router(fun.router)
    dp.include_router(social_fun.router)
    dp.include_router(relations.router)
    dp.include_router(children.router)
    dp.include_router(vip.router)
    dp.include_router(modules.router)
    dp.include_router(grams.router)
    dp.include_router(tournament.router)
    dp.include_router(botinfo.router)
    dp.include_router(userinfo.router)
    dp.include_router(update_2_2.router)
    dp.include_router(currency_exchange.router)
    dp.include_router(vip_plus.router)
    dp.include_router(moxxi_3_0.router)
    dp.include_router(moxxi_apex.router)
    dp.include_router(passive.router)

    me = None
    attempt = 0
    while me is None:
        attempt += 1
        try:
            me = await bot.get_me()
            break
        except Exception as e:
            if attempt % 5 == 1 or attempt <= 3:
                log.warning("Ожидание подключения к Telegram API (попытка %d: %s)... повтор через 5с", attempt, e)
            await asyncio.sleep(5)

    log.info("🚀 ТЕСТ-БОТ ЗАПУЩЕН УСПЕШНО: @%s (ID: %s)", me.username, me.id)
    log.info("🛡 Безопасность: Продакшн-база iris.db НЕ задействована. Все тесты идут в %s", TEST_DB_PATH.name)

    await set_commands(bot)

    loop = asyncio.get_running_loop()
    import signal
    stopping_event = asyncio.Event()

    def _on_stop():
        stopping_event.set()
        asyncio.create_task(dp.stop_polling())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _on_stop)
        except (NotImplementedError, AttributeError):
            pass

    try:
        while not stopping_event.is_set():
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                if stopping_event.is_set():
                    break
                log.warning("start_polling завершился без сигнала остановки. Авто-перезапуск через 3с...")
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                log.info("Получен сигнал остановки — завершаюсь.")
                break
            except Exception as e:
                log.warning("Сбой сетевого соединения (%s): %s. Автоматическое переподключение через 5с...", type(e).__name__, e)
                await asyncio.sleep(5)
    finally:
        log.info("🛑 Остановка тест-бота...")
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Тест-бот остановлен.")
