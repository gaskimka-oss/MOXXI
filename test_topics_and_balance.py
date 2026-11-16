import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

import bot
import h_chatset
import h_grams


class TestClosedTopicsAndBalance(unittest.IsolatedAsyncioTestCase):

    async def test_topic_closed_retry_success_reopen(self):
        """Когда у бота есть право управление темами: переоткрывает, шлет и закрывает."""
        middleware = bot.TopicClosedRetryMiddleware()
        mock_bot = MagicMock()
        mock_bot.reopen_forum_topic = AsyncMock()
        mock_bot.close_forum_topic = AsyncMock()

        make_request = AsyncMock()
        # Первый вызов падает с topic_closed, второй (после reopen) успешен
        sent_result = MagicMock(message_id=123)
        make_request.side_effect = [
            TelegramBadRequest(method=SendMessage(chat_id=-1001, text="test"), message="Bad Request: TOPIC_CLOSED"),
            sent_result
        ]

        method = SendMessage(chat_id=-1001, message_thread_id=55, text="Бан 1.1")
        res = await middleware(make_request, mock_bot, method)

        self.assertEqual(res, sent_result)
        mock_bot.reopen_forum_topic.assert_awaited_once_with(chat_id=-1001, message_thread_id=55)
        mock_bot.close_forum_topic.assert_awaited_once_with(chat_id=-1001, message_thread_id=55)

    async def test_topic_closed_no_rights_sends_pm_to_actor(self):
        """Когда у бота НЕТ права управления темами: шлет уведомление в ЛС админу, а не в чат."""
        middleware = bot.TopicClosedRetryMiddleware()
        mock_bot = MagicMock()
        mock_bot.reopen_forum_topic = AsyncMock(side_effect=TelegramBadRequest(method=SendMessage(chat_id=-1001, text="test"), message="CHAT_ADMIN_REQUIRED"))
        mock_bot.send_message = AsyncMock()

        make_request = AsyncMock(side_effect=TelegramBadRequest(method=SendMessage(chat_id=-1001, text="test"), message="Bad Request: TOPIC_CLOSED"))

        bot.current_actor_id.set(999888)
        bot.current_actor_name.set("AdminBob")
        bot.current_chat_title.set("SuperChat")

        method = SendMessage(chat_id=-1001, message_thread_id=55, text="Пользователь забанен!")
        res = await middleware(make_request, mock_bot, method)

        self.assertIsNone(res)
        mock_bot.send_message.assert_awaited_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], 999888)
        self.assertIn("Бот не имеет доступа к данной теме", call_kwargs["text"])
        self.assertIn("Пользователь забанен!", call_kwargs["text"])

    async def test_topic_ok_autodel(self):
        """В topic_ok сообщение перенаправления удаляется через 20 секунд."""
        mock_msg = MagicMock()
        mock_msg.chat.type = "supergroup"
        mock_msg.chat.id = -1001
        mock_msg.message_thread_id = 999
        sent_mock = MagicMock()
        mock_msg.reply = AsyncMock(return_value=sent_mock)

        with patch("h_grams.get_gram_topic", AsyncMock(return_value=132681)), \
             patch("h_grams.casino_enabled", AsyncMock(return_value=True)), \
             patch("h_grams._autodel", AsyncMock()) as mock_del:
            ok = await h_grams.topic_ok(mock_msg)
            self.assertFalse(ok)
            mock_msg.reply.assert_awaited_once()
            # Проверяем, что _autodel был запущен
            await asyncio.sleep(0.01)
            mock_del.assert_called_once_with(sent_mock, 20.0)

    async def test_topic_subcommands_delegation(self):
        """Проверяем, что 'тема казик' и другие подкоманды делегируют в нужные обработчики."""
        mock_msg = MagicMock()
        mock_msg.chat.id = -1001
        mock_bot = MagicMock()

        with patch("h_chatset.require", AsyncMock(return_value=True)):
            with patch("h_grams.cmd_gram_topic", AsyncMock()) as mock_gram:
                await h_chatset.topic(mock_msg, mock_bot, args="казик")
                mock_gram.assert_awaited_once_with(mock_msg, mock_bot, args="")

            with patch("h_userinfo.cmd_form_topic", AsyncMock()) as mock_form:
                await h_chatset.topic(mock_msg, mock_bot, args="описание")
                mock_form.assert_awaited_once_with(mock_msg, mock_bot, args="")

            with patch("h_chatset.cmd_set_sms_topic", AsyncMock()) as mock_sms:
                await h_chatset.topic(mock_msg, mock_bot, args="смс")
                mock_sms.assert_awaited_once_with(mock_msg, mock_bot, args="")

            with patch("h_chatset.cmd_set_rules_topic", AsyncMock()) as mock_rules:
                await h_chatset.topic(mock_msg, mock_bot, args="правила")
                mock_rules.assert_awaited_once_with(mock_msg, mock_bot, args="")


if __name__ == "__main__":
    unittest.main()
