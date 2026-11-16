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

    # 3. Test arbitrary custom reasons (should now be accepted without rejection)
    ok, err = await validate_chat_rules(chat_id, "гс нецензурного характера")
    assert ok, f"Expected custom reason to be valid, got err: {err}"

    ok, err = await validate_chat_rules(chat_id, "лив")
    assert ok, f"Expected 'лив' to be valid, got err: {err}"

    ok, err = await validate_chat_rules(chat_id, "18+ гс")
    assert ok, f"Expected '18+ гс' to be valid, got err: {err}"

    # 4. Hints check
    assert "бан @username [причина]" in usage_hint("ban")
    assert "мут @username [срок] [причина]" in usage_hint("mute")
    assert "варн @username [причина]" in usage_hint("warn")
    assert "кик @username [причина]" in usage_hint("kick")

    # 5. Test reply to left_chat_member service message
    from unittest.mock import MagicMock
    from core_resolve import real_reply, resolve_target
    from core_punish import check_reason

    mock_msg = MagicMock()
    mock_rep = MagicMock()
    mock_left_user = MagicMock(id=555444, first_name="LeaverUser", username="leaver")
    mock_rep.left_chat_member = mock_left_user
    mock_rep.new_chat_members = None
    mock_rep.forum_topic_created = None
    mock_rep.forum_topic_edited = None
    mock_rep.forum_topic_closed = None
    mock_rep.forum_topic_reopened = None
    mock_rep.general_forum_topic_hidden = None
    mock_rep.general_forum_topic_unhidden = None
    mock_rep.pinned_message = None
    mock_rep.group_chat_created = None
    mock_rep.supergroup_chat_created = None
    mock_rep.message_id = 999
    mock_msg.reply_to_message = mock_rep
    mock_msg.entities = []

    res_rep = real_reply(mock_msg)
    assert res_rep is not None, "real_reply should not be None for left_chat_member"

    mock_bot = MagicMock()
    uid, name, rest = await resolve_target(mock_msg, "лив", mock_bot)
    assert uid == 555444, f"Expected uid 555444, got {uid}"
    assert name == "LeaverUser", f"Expected name LeaverUser, got {name}"
    assert rest == "лив", f"Expected rest 'лив', got {rest}"

    # 6. Single digit reason check (e.g. 1 or 1.1)
    mock_chat_msg = MagicMock()
    mock_chat_msg.chat.id = chat_id
    mock_chat_msg.reply = MagicMock()
    assert await check_reason(mock_chat_msg, "warn", "1"), "Reason '1' should be accepted"
    assert await check_reason(mock_chat_msg, "ban", "лив"), "Reason 'лив' should be accepted"

    await db.close()
    print("All unit tests passed successfully!")

asyncio.run(test())
