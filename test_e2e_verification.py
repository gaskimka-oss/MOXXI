import asyncio
import os
import py_compile
import time
from unittest.mock import AsyncMock, MagicMock

import db
import config
from aiogram import Bot, Dispatcher
from aiogram.types import Chat, User, Message, Update
from aiogram.methods import SendMessage, EditMessageText
from bot import TopicClosedRetryMiddleware


def test_syntax_all_files():
    print("--- 1. Проверка синтаксиса всех .py файлов ---")
    py_files = [f for f in os.listdir(".") if f.endswith(".py") and not f.startswith("temp_")]
    failed = []
    for f in py_files:
        try:
            py_compile.compile(f, doraise=True)
        except Exception as e:
            failed.append((f, str(e)))
    if failed:
        for f, err in failed:
            print(f"❌ Ошибка компиляции {f}: {err}")
        assert False, f"Найдено {len(failed)} файлов с ошибками синтаксиса!"
    print(f"✅ Успешно: все {len(py_files)} файлов скомпилированы без ошибок!")


async def test_full_pipeline():
    print("\n--- 2. Инициализация БД и сборка диспетчера ---")
    await db.init()

    bot = Bot(token=config.BOT_TOKEN)
    sent_requests = []

    # Мокаем aiohttp сессию бота, перехватывая все методы Telegram Bot API
    async def mock_make_request(bot_inst, method, timeout=None):
        sent_requests.append(method)
        m = MagicMock()
        m.message_id = 123456
        m.chat = MagicMock(id=getattr(method, "chat_id", 0))
        m.text = getattr(method, "text", "") or ""
        m.delete = AsyncMock()
        return m

    bot.session.make_request = mock_make_request
    bot.session.middleware(TopicClosedRetryMiddleware())

    # Импортируем сборку из bot.py
    import bot as bot_app

    dp = Dispatcher()
    dp.message.outer_middleware(bot_app.keyboard_middleware)
    dp.message.middleware(bot_app.user_middleware)
    dp.message.middleware(bot_app.access_middleware)

    # Регистрируем роутеры
    import h_start as start
    import h_userinfo as userinfo
    import h_botinfo as botinfo
    import h_mod_ranks as mod_ranks
    import h_grams as grams
    import h_social_fun as social_fun
    import h_passive as passive
    import h_diagnostics as diagnostics

    command_routers = [
        userinfo.router,
        botinfo.router,
        mod_ranks.router,
        grams.router,
        social_fun.router,
        start.router,
        diagnostics.router,
    ]
    for r in command_routers:
        dp.include_router(r)
    dp.include_router(passive.router)

    print("✅ Диспетчер и роутеры собраны успешно!")

    print("\n--- 3. Сценарии тестирования сообщений ---")

    test_cases = [
        # (Название сценария, chat_id, thread_id, user_id, username, text, expected_min_answers)
        (
            "Клан СОН - Топик 'Чатик' (#4) - команда 'бот'",
            -1004368868650, 4, 99887766, "j0_test", "бот", 1
        ),
        (
            "Клан СОН - Топик 'Чатик' (#4) - команда 'кто я'",
            -1004368868650, 4, 99887766, "j0_test", "кто я", 1
        ),
        (
            "Клан СОН - Топик 'Чатик' (#4) - команда 'шаблон'",
            -1004368868650, 4, 99887766, "j0_test", "шаблон", 1
        ),
        (
            "ZRG_Oblivion - Топик 'CMC' (#4) - команда 'бот'",
            -1003934033202, 4, 8412527198, "Simba", "бот", 1
        ),
        (
            "ZRG_Oblivion - Топик 'CMC' (#4) - команда 'кто я'",
            -1003934033202, 4, 8412527198, "Simba", "кто я", 1
        ),
        (
            "ZRG_Oblivion - Топик 'CMC' (#4) - команда 'шаблон'",
            -1003934033202, 4, 8412527198, "Simba", "шаблон", 1
        ),
        (
            "Обычная группа (без тем) - команда 'бот'",
            -1004373090684, None, 11223344, "test_user", "бот", 1
        ),
        (
            "Обычная группа (без тем) - команда 'кто я'",
            -1004373090684, None, 11223344, "test_user", "кто я", 1
        ),
        (
            "Новичок без анкеты пишет обычное сообщение в общий чат",
            -1004368868650, 4, 777666555, "newbie", "привет всем", 0
        ),
    ]

    all_ok = True
    msg_id = 500000

    for title, cid, tid, uid, uname, text, min_answers in test_cases:
        msg_id += 1
        sent_requests.clear()

        chat = Chat(id=cid, type="supergroup", title=f"Test Chat {cid}")
        user = User(id=uid, is_bot=False, first_name=uname, username=uname)

        raw_msg = {
            "message_id": msg_id,
            "date": int(time.time()),
            "chat": chat.model_dump(),
            "from": user.model_dump(),
            "text": text,
        }
        if tid is not None:
            raw_msg["message_thread_id"] = tid
            raw_msg["is_topic_message"] = True

        msg_obj = Message.model_validate(raw_msg)
        update = Update(update_id=msg_id, message=msg_obj)

        try:
            await dp.feed_update(bot, update)
            cnt = len(sent_requests)
            if cnt >= min_answers:
                text_preview = ""
                for req in sent_requests:
                    t = getattr(req, "text", "") or getattr(req, "caption", "") or ""
                    if t:
                        text_preview = t[:60].replace("\n", " ")
                        break
                print(f"  ✅ [{title}] -> Успех! Ответов: {cnt}. Превью: «{text_preview}...»")
            else:
                print(f"  ❌ [{title}] -> НЕТ ОТВЕТА (отправлено 0 сообщений)")
                all_ok = False
        except Exception as e:
            print(f"  💥 [{title}] -> ИСКЛЮЧЕНИЕ: {e}")
            import traceback
            traceback.print_exc()
            all_ok = False

    await bot.session.close()
    await db.close()

    print("\n" + "=" * 60)
    if all_ok:
        print("🎉 ВСЕ ТЕСТОВЫЕ СЦЕНАРИИ ПРОЙДЕНЫ НА 100%! БОТ ПОЛНОСТЬЮ ИСПРАВЕН!")
    else:
        print("❌ НЕКОТОРЫЕ СЦЕНАРИИ ЗАВЕРШИЛИСЬ С ОШИБКОЙ!")
    print("=" * 60)
    assert all_ok


if __name__ == "__main__":
    test_syntax_all_files()
    asyncio.run(test_full_pipeline())
