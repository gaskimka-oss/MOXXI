import asyncio
import db
import h_whisper_anon as whisper_anon

async def test_whisper():
    await db.init()
    await whisper_anon.init_whisper_tables()

    # Вставляем тестовый шёпот
    await db.execute(
        "INSERT INTO chat_whispers (chat_id, sender_id, target_id, sender_name, target_name, is_anon, text, created_at) "
        "VALUES (-1001, 111, 222, 'Гасим', 'Полина', 0, 'Привет, секрет!', 12345)"
    )
    row = await db.fetchone("SELECT * FROM chat_whispers WHERE sender_id = 111")
    assert row is not None
    assert row["text"] == "Привет, секрет!"
    assert row["target_id"] == 222

    # Вставляем анонимку
    await db.execute(
        "INSERT INTO chat_anon_letters (chat_id, sender_id, target_id, target_name, text, created_at) "
        "VALUES (-1001, 111, 222, 'Полина', 'Ты мне очень нравишься!', 12345)"
    )
    let = await db.fetchone("SELECT * FROM chat_anon_letters WHERE sender_id = 111")
    assert let is not None
    assert let["text"] == "Ты мне очень нравишься!"

    print("WHISPER & ANON TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_whisper())
