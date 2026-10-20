"""Точка входа. Запуск: python bot.py"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (TelegramBadRequest, TelegramConflictError,
                                TelegramUnauthorizedError)
from aiogram.types import BotCommand, Message

import config
import db
import core_backup as backup
import core_docs as docs
import core_health as health
import core_nav as nav
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
import core_yookassa as yookassa
import h_pets as pets
import h_market as market
import h_dungeon as dungeon
import h_jackpot as jackpot
import h_titles as titles
import h_party_games as party_games
import h_webapp as webapp
import h_community_support as community_support
import h_security_plus as security_plus
import h_staff_plus as staff_plus
import h_economy_plus as economy_plus
import h_social_plus as social_plus
import h_veteran as veteran
import h_social_fun as social_fun
import h_owner_panel as owner_panel

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
log = logging.getLogger("irisbot")


async def _delayed_delete_msg(msg: Message, delay: float = 2.0) -> None:
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


async def keyboard_middleware(handler, event, data: dict):
    """Нажатие кнопки старого нижнего меню = скрытие клавиатуры + вызов команды.

    Если у пользователя на клиенте (ПК/телефон) осталась старая reply-клавиатура:
    1) Отправляем удаление клавиатуры ReplyKeyboardRemove.
    2) Подменяем текст на команду, чтобы сработал нужный хэндлер.
    """
    text = getattr(event, "text", None)
    if text:
        cmd = kbd.resolve(text)
        if cmd:
            chat = getattr(event, "chat", None)
            if isinstance(event, Message) and chat and getattr(chat, "type", "") == "private":
                try:
                    rm = await event.answer("🧹 <i>Обновление интерфейса...</i>", reply_markup=kbd.hide())
                    asyncio.create_task(_delayed_delete_msg(rm, 2.0))
                except Exception:
                    pass
            try:
                copy = event.model_copy(update={"text": cmd})
                bot = data.get("bot") or getattr(event, "bot", None)
                if bot is not None:
                    try:
                        copy = copy.as_(bot)
                    except Exception:
                        pass
                event = copy
            except Exception:
                pass
    return await handler(event, data)


async def user_middleware(handler, event, data: dict):
    """Регистрация пользователя/чата, глобальный бан, «тихий режим» чата."""
    user = getattr(event, "from_user", None)
    if user and not user.is_bot and user.id != 777000:
        row = await db.get_user(user.id)
        if row["banned"]:
            return
        await db.touch_user(user.id, user.username, user.first_name)
    chat = getattr(event, "chat", None)
    if chat is not None and chat.type in {"group", "supergroup"}:
        # Любое сообщение/нажатие в группе подтверждает, что пользователь
        # сейчас в чате. События выхода отдельно запишет core_clan_sync.
        if user and not user.is_bot:
            try:
                import core_members as _members
                await _members.remember_member(chat.id, user.id, "member", True)
            except Exception:
                pass
        # Если мут/бан был задан по ещё неизвестному @username, применяем его
        # сразу, как только Telegram прислал событие с настоящим user_id.
        if user and not user.is_bot:
            try:
                import core_pending_punish as _pending
                await _pending.apply_for_user(data.get("bot"), chat.id, user)
            except Exception:
                pass
            if user.username:
                try:
                    s_rows = await db.fetchall(
                        "SELECT chat_id, rank FROM staff WHERE lower(username)=lower(?) AND (user_id=0 OR user_id IS NULL)",
                        (user.username,)
                    )
                    if s_rows:
                        from core_ranks import set_rank
                        for s in s_rows:
                            await db.execute(
                                "UPDATE staff SET user_id=?, name=? WHERE chat_id=? AND lower(username)=lower(?)",
                                (user.id, user.first_name, s["chat_id"], user.username)
                            )
                            await set_rank(s["chat_id"], user.id, s["rank"], by=0)
                except Exception:
                    pass
        await db.register_chat(chat.id, chat.title)
        if isinstance(event, Message):
            try:
                from h_security_plus import check_security_violations
                if await check_security_violations(event, data.get("bot")):
                    return
            except Exception as _e:
                log.warning("security check: %s", _e)
        if user and not user.is_bot and getattr(event, "text", None):
            try:
                from h_ai_features import record_chat_message
                record_chat_message(chat.id, user.first_name, event.text)
            except Exception:
                pass
            if isinstance(event, Message):
                try:
                    import core_modlog as modlog
                    await modlog.remember(event)
                except Exception:
                    pass
        if await db.get_setting(chat.id, "silent") == "1":
            txt = (getattr(event, "text", "") or "").lower().lstrip("!./ ")
            if not txt.startswith(("включить чат", "проверка", "команды")):
                return
    return await handler(event, data)


async def timers_worker(bot: Bot) -> None:
    """Фоновая задача: срабатывание напоминаний."""
    while True:
        try:
            now = int(time.time())
            rows = await db.fetchall(
                "SELECT * FROM timers WHERE done=0 AND fire_at<=?", (now,))
            for r in rows:
                try:
                    await bot.send_message(
                        r["chat_id"],
                        f'⏰ Напоминание для <a href="tg://user?id={r["user_id"]}">вас</a>: '
                        f'{r["text"]}')
                except Exception:
                    pass
                await db.execute("UPDATE timers SET done=1 WHERE id=?", (r["id"],))
        except Exception as e:
            log.warning("timers: %s", e)
        await asyncio.sleep(20)


async def support_tickets_loop(bot: Bot) -> None:
    """Фоновая проверка тикетов техподдержки старше 6 часов с автоответом ИИ."""
    while True:
        try:
            from h_community_support import check_unanswered_support_tickets
            await check_unanswered_support_tickets(bot)
        except Exception as e:
            log.warning("support tickets loop: %s", e)
        await asyncio.sleep(60)


async def set_commands(bot: Bot) -> None:
    from aiogram.types import MenuButtonCommands
    cmds = [
        BotCommand(command="start", description="🚀 Главное меню бота"),
        BotCommand(command="menu", description="🍸 Главное меню бота"),
        BotCommand(command="app", description="📱 Mini App (Казино и Игры)"),
        BotCommand(command="help", description="📖 Все команды бота"),
        BotCommand(command="balance", description="💰 Баланс и финансы"),
        BotCommand(command="bonus", description="🎁 Ежедневный бонус"),
        BotCommand(command="biz", description="🏢 Рынок и бизнесы"),
        BotCommand(command="games", description="🎰 Казино и мини-игры"),
        BotCommand(command="boss", description="🐉 Рейдовые боссы"),
        BotCommand(command="duels", description="⚔️ PvP-Дуэли"),
        BotCommand(command="shop", description="🛍 Магазин и кейсы"),
        BotCommand(command="reviews", description="⭐ Отзывы о боте"),
        BotCommand(command="ideas", description="💡 Идеи и предложения"),
        BotCommand(command="chat", description="💬 Официальный чат бота"),
        BotCommand(command="support", description="🆘 Техподдержка"),
    ]
    try:
        await bot.set_my_commands(cmds)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except TelegramBadRequest as e:
        log.warning("меню команд: %s", e)
    except Exception as e:
        log.warning("кнопка меню: %s", e)


# Владелец бота. Дублируется здесь специально: если на хостинге почему-то
# остался старый config.py, бот всё равно поднимется, а не уйдёт в цикл
# падений с «OWNER_ID не задан».
FALLBACK_OWNER = 8036974481          # @Фанат


def _selfheal_config() -> None:
    """Чиним неполный config.py, чтобы бот не падал при частичной заливке."""
    if not getattr(config, "OWNER_ID", 0):
        config.OWNER_ID = FALLBACK_OWNER
        log.warning("OWNER_ID пуст — подставил владельца из кода: %s",
                    config.OWNER_ID)
    if not getattr(config, "DEFAULT_OWNER", 0):
        config.DEFAULT_OWNER = config.OWNER_ID or FALLBACK_OWNER
    admins = set(getattr(config, "ADMINS", []) or [])
    admins.add(config.OWNER_ID)
    config.ADMINS = sorted(admins - {0})
    if not getattr(config, "MAIN_CHAT", 0):
        config.MAIN_CHAT = -1003934033202
    if not getattr(config, "STORAGE_INFO", None):
        try:
            import core_storage as _st
            config.STORAGE_INFO = _st.INFO
            config.DATA_DIR = _st.DATA_DIR
            config.DB_PATH = _st.DB_FILE
            log.warning("config.py устарел — путь к базе взят из storage")
        except Exception:
            config.STORAGE_INFO = {"dir": str(getattr(config, "DB_PATH", "?")),
                                   "boots": 0, "db_existed": False,
                                   "persistent": False}


from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import (TelegramMethod, SendMessage, SendPhoto,
                             SendAnimation, SendDocument, SendVideo, EditMessageText)


class TopicClosedRetryMiddleware(BaseRequestMiddleware):
    """Перехватывает ошибки закрытых/удалённых тем в форумах (TOPIC_CLOSED)."""
    async def __call__(self, make_request, bot: Bot, method: TelegramMethod):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "topic_closed" in err or "topic_deleted" in err or "message thread not found" in err:
                tid = getattr(method, "message_thread_id", None)
                cid = getattr(method, "chat_id", None)
                if tid is not None:
                    log.warning("Тема #%s в чате %s закрыта/удалена — отправляю в основной чат", tid, cid)
                    setattr(method, "message_thread_id", None)
                    try:
                        return await make_request(bot, method)
                    except Exception as e2:
                        log.debug("Повторная отправка в основной чат не удалась: %s", e2)
                        return None
                return None
            raise


AUTO_DELETE_FOOTER = "\n\n⏱ <i>Это сообщение автоматически удалится через 5 минут</i>"


def _is_sms_topic(chat_id: int, thread_id: int | None) -> bool:
    if chat_id >= 0:
        return False
    tid = int(thread_id or 0)
    # Только топик СМС (ID 4) удаляет сообщения бота через 5 минут.
    # В казино (132681), анкетах (148507), правилах (5) и других темах ничего НЕ удаляется.
    return tid == 4


async def main() -> None:
    _selfheal_config()
    config.validate()

    info = config.STORAGE_INFO
    log.info("Хранилище: %s (запуск №%d, база на месте: %s)",
             info.get("dir"), info.get("boots", 0),
             "да" if info.get("db_existed") else "нет")

    bot = Bot(token=config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(TopicClosedRetryMiddleware())

    # если база пустая (хостинг стёр диск) — тянем последнюю копию из Telegram
    try:
        if await backup.restore_if_needed(bot):
            log.info("✅ Настройки восстановлены из резервной копии")
    except Exception as e:
        log.warning("Восстановление пропущено: %s", e)

    await db.init()
    try:
        await seed.apply()
    except Exception as e:
        log.warning("seed: %s", e)

    dp = Dispatcher()
    dp.message.outer_middleware(keyboard_middleware)
    dp.message.middleware(user_middleware)
    dp.callback_query.middleware(user_middleware)

    # порядок важен: passive — последним, он ловит любой текст
    # ДК применяется ко всем командным роутерам
    command_routers = (
        helpmenu.router, mod_ranks.router, mod_bans.router, chatset.router,
        dk.router, chatlock.router, fun.router, modules.router, rp.router,
        userinfo.router, tournament.router, relations.router, vip.router,
        pets.router, market.router, dungeon.router, jackpot.router, titles.router,
        party_games.router, webapp.router, community_support.router,
        security_plus.router, staff_plus.router, economy_plus.router, social_plus.router,
        veteran.router, botinfo.router, ai_features.router, callall.router,
        automod.router, nightmode.router, boss.router, items.router,
        duels.router, clan_wars.router, fishing_craft.router, achievements.router,
        quests.router, social_fun.router, grams.router, nav.router,
        adminpanel.router, owner_panel.router, start.router,
    )
    for r in command_routers:
        r.message.middleware(access_middleware)

    dp.include_router(nav.router)
    dp.include_router(adminpanel.router)
    dp.include_router(owner_panel.router)
    # До passive: отслеживает выходы/кики и связывает две группы клана.
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
    dp.include_router(webapp.router)
    dp.include_router(community_support.router)
    dp.include_router(chatset.router)
    dp.include_router(fun.router)
    dp.include_router(social_fun.router)
    dp.include_router(relations.router)
    dp.include_router(vip.router)
    dp.include_router(modules.router)
    dp.include_router(grams.router)
    dp.include_router(tournament.router)
    dp.include_router(rp.router)
    dp.include_router(botinfo.router)
    dp.include_router(userinfo.router)
    dp.include_router(passive.router)

    me = None
    attempt = 0
    while me is None:
        attempt += 1
        try:
            me = await bot.get_me()
            break
        except TelegramUnauthorizedError:
            await db.close(); await bot.session.close()
            raise SystemExit("❌ Токен неверный или отозван.\n"
                             "Проверьте переменную BOT_TOKEN "
                             "(в .env или в настройках хостинга).")
        except Exception as e:
            if attempt % 5 == 1 or attempt <= 3:
                log.warning("Ожидание подключения к Telegram API (попытка %d: %s)... повтор через 5с", attempt, e)
            await asyncio.sleep(5)

    from core_registry import REGISTRY
    log.info("Запущен @%s | команд: %d | владелец: %s",
             me.username, len(REGISTRY), config.OWNER_ID)

    async def _pub_docs():
        try:
            st = await asyncio.to_thread(docs.publish)
            log.info("Справка: %s", st.get("url"))
        except Exception as e:
            log.warning("Не удалось опубликовать справку: %s", e)

    asyncio.create_task(_pub_docs())

    await set_commands(bot)
    asyncio.create_task(timers_worker(bot))
    asyncio.create_task(chatlock.schedule_worker(bot))
    asyncio.create_task(tournament.schedule_worker(bot))
    asyncio.create_task(boss.boss_schedule_worker(bot))
    asyncio.create_task(grams.auction_schedule_worker(bot))
    asyncio.create_task(backup.worker(bot))
    asyncio.create_task(botinfo.announce_update_on_startup(bot))
    asyncio.create_task(botinfo.auto_restart_worker(bot))
    asyncio.create_task(yookassa.yookassa_poller(bot))
    asyncio.create_task(support_tickets_loop(bot))
    await health.start()          # порт для healthcheck хостинга

    loop = asyncio.get_running_loop()
    import signal
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(dp.stop_polling()))
        except (NotImplementedError, AttributeError):
            pass

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramConflictError:
        log.error("❌ Бот уже запущен где-то ещё (другой сервер или локально). "
                  "Остановите второй экземпляр — Telegram разрешает только один.")
    except asyncio.CancelledError:
        log.info("Получен сигнал остановки — завершаюсь.")
    finally:
        log.info("Закрываю соединения…")
        try:
            await asyncio.wait_for(backup.save(bot, "🔻 копия перед остановкой"), 25)
        except Exception as e:
            log.warning("копия перед остановкой не сделана: %s", e)
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as e:
        print(str(e) or "Остановлено.")
