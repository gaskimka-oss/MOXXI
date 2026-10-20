import asyncio
import re

async def test():
    import db
    await db.init()

    chat_id = -1009999999999
    # Set rules for test chat
    rules_text = (
        "1.1 Уважительное общение без мата и токсичности.\n"
        "1.2 Оскорбление участников строго запрещено.\n"
        "1.3 Спам, реклама и несанкционированные ссылки запрещены.\n"
        "1.4 Флуд и капс запрещены."
    )
    await db.set_setting(chat_id, "rules_text", rules_text)

    from core_punish import validate_chat_rules, usage_hint

    # 1. Test valid rule numbers
    ok, err = await validate_chat_rules(chat_id, "1.1")
    assert ok, f"Expected 1.1 to be valid, got err: {err}"

    ok, err = await validate_chat_rules(chat_id, "1.2 оск")
    assert ok, f"Expected '1.2 оск' to be valid, got err: {err}"

    # 2. Test valid keywords
    ok, err = await validate_chat_rules(chat_id, "оскорбление")
    assert ok, f"Expected 'оскорбление' to be valid, got err: {err}"

    ok, err = await validate_chat_rules(chat_id, "спам")
    assert ok, f"Expected 'спам' to be valid, got err: {err}"

    ok, err = await validate_chat_rules(chat_id, "реклама")
    assert ok, f"Expected 'реклама' to be valid, got err: {err}"

    # 3. Test invalid reason
    ok, err = await validate_chat_rules(chat_id, "123")
    assert not ok, "Expected '123' to be rejected!"
    assert "Наказание отклонено" in err, f"Expected rejection message, got {err}"

    ok, err = await validate_chat_rules(chat_id, "просто так")
    assert not ok, "Expected 'просто так' to be rejected!"

    # 4. Hints check
    assert "бан @username [причина]" in usage_hint("ban")
    assert "мут @username [срок] [причина]" in usage_hint("mute")
    assert "варн @username [причина]" in usage_hint("warn")
    assert "кик @username [причина]" in usage_hint("kick")

    await db.close()
    print("All unit tests passed successfully!")

asyncio.run(test())
