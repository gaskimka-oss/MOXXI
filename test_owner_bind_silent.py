import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.stdout.reconfigure(encoding='utf-8')

import config
import db
from h_owner_panel import cmd_bind_official_chat, cmd_show_bound_chats
from h_community_support import cmd_bind_commands_topic, cmd_unbind_commands_topic
from h_chatlock import cmd_open

async def run_tests():
    await db.init()
    print("--- 1. Testing Bot Owner (Fanat 8036974481) Permissions ---")
    owner_id = 8036974481
    assert config.is_bot_owner(owner_id), "Fanat must be bot owner"

    # Test +чат общение https://t.me/moxxi_chat
    bot = AsyncMock()
    msg = MagicMock()
    msg.from_user.id = owner_id
    msg.from_user.first_name = "Фанат"
    msg.chat.id = -1001234567890
    msg.chat.type = "supergroup"
    msg.text = "+чат общения https://t.me/moxxi_chat"
    msg.message_thread_id = None
    msg.reply = AsyncMock()

    await cmd_bind_official_chat(msg, bot, args="https://t.me/moxxi_chat")
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    print("Owner bind result:", reply_text[:60] + "...")
    assert "Группа успешно привязана" in reply_text
    assert "Официальный чат общения" in reply_text
    bound = await db.get_global_setting("global_community_chat")
    assert bound == "https://t.me/moxxi_chat", f"Got: {bound}"
    print("✅ +чат общения successfully bound by owner!")

    # Test +чат команды inside forum topic
    msg.reply.reset_mock()
    msg.text = "+чат команды"
    msg.message_thread_id = 777
    await cmd_bind_official_chat(msg, bot, args="")
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    print("Owner bind commands topic:", reply_text[:60] + "...")
    assert "Группа успешно привязана" in reply_text
    assert "Группа/Тема команд" in reply_text
    assert await db.get_global_setting("global_commands_chat") == str(msg.chat.id)
    assert await db.get_global_setting("global_commands_chat_topic") == "777"
    assert await db.get_global_setting("global_commands_topic") == "777"
    print("✅ +чат команды with topic successfully bound!")

    # Test тема команды by owner
    msg.reply.reset_mock()
    msg.text = "+тема команды"
    msg.chat.is_forum = True
    msg.message_thread_id = 888
    await cmd_bind_commands_topic(msg, bot, args="")
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    print("Owner тема команды result:", reply_text[:60] + "...")
    assert "успешно установлена" in reply_text
    assert await db.get_setting(msg.chat.id, "commands_topic") == "888"
    print("✅ +тема команды successfully set by owner!")

    # Test -тема команды by owner
    msg.reply.reset_mock()
    msg.text = "-тема команды"
    await cmd_unbind_commands_topic(msg, bot)
    msg.reply.assert_called_once()
    assert "снята" in msg.reply.call_args[0][0]
    print("✅ -тема команды successfully unset by owner!")

    print("\n--- 2. Testing Non-Owner / Non-Staff (Silent Passthrough) ---")
    random_user_id = 999999999
    assert not config.is_bot_owner(random_user_id)
    
    # Non-owner types +чат общения
    msg_random = MagicMock()
    msg_random.from_user.id = random_user_id
    msg_random.from_user.first_name = "ОбычныйИгрок"
    msg_random.chat.id = -1001234567890
    msg_random.chat.type = "supergroup"
    msg_random.text = "+чат общения https://t.me/fake_chat"
    msg_random.reply = AsyncMock()

    await cmd_bind_official_chat(msg_random, bot, args="https://t.me/fake_chat")
    assert not msg_random.reply.called, "Must be SILENT! No reply allowed."
    print("✅ +чат общения by non-owner: SILENT PASSTHROUGH (0 messages sent)!")

    # Non-owner types +тема команды
    msg_random.reply.reset_mock()
    msg_random.text = "+тема команды"
    await cmd_bind_commands_topic(msg_random, bot, args="")
    assert not msg_random.reply.called, "Must be SILENT! No reply allowed."
    print("✅ +тема команды by non-owner: SILENT PASSTHROUGH (0 messages sent)!")

    # Non-owner types -тема команды
    msg_random.reply.reset_mock()
    msg_random.text = "-тема команды"
    await cmd_unbind_commands_topic(msg_random, bot)
    assert not msg_random.reply.called, "Must be SILENT! No reply allowed."
    print("✅ -тема команды by non-owner: SILENT PASSTHROUGH (0 messages sent)!")

    # Non-owner types привязанные чаты
    msg_random.reply.reset_mock()
    msg_random.text = "привязанные чаты"
    await cmd_show_bound_chats(msg_random, bot)
    assert not msg_random.reply.called, "Must be SILENT! No reply allowed."
    print("✅ привязанные чаты by non-owner: SILENT PASSTHROUGH (0 messages sent)!")

    print("\n--- 3. Testing Collision Protection in h_chatlock ---")
    msg_lock = MagicMock()
    msg_lock.from_user.id = owner_id
    msg_lock.chat.id = -1001234567890
    msg_lock.chat.type = "supergroup"
    msg_lock.text = "+чат общение"
    msg_lock.reply = AsyncMock()
    await cmd_open(msg_lock, bot, args="общение")
    assert not msg_lock.reply.called, "h_chatlock must ignore 'общение'!"
    print("✅ h_chatlock successfully ignored +чат общение!")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
