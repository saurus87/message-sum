"""Тесты для main.py — обработка команд."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestCmdSummarize:
    """Тесты команды /summarize."""

    @pytest.fixture
    def mock_app(self):
        """Создать мокированное приложение."""
        from main import MessageSumApp

        app = MagicMock(spec=MessageSumApp)
        app.client = AsyncMock()
        app.client.send_message = AsyncMock()
        app.db = MagicMock()
        app.summarizer = AsyncMock()
        app.summarizer.run_summarize = AsyncMock(return_value=True)
        return app

    def test_summarize_uses_db_format(self, mock_app):
        """_cmd_summarize должен читать формат из БД."""
        from main import MessageSumApp

        mock_app.db.get_setting = MagicMock(return_value="подробное")

        app_instance = MessageSumApp.__new__(MessageSumApp)
        app_instance.client = mock_app.client
        app_instance.db = mock_app.db
        app_instance.summarizer = mock_app.summarizer

        async def mock_send(chat_id, msg):
            pass
        app_instance.client.send_message = mock_send

        import asyncio
        asyncio.run(app_instance._cmd_summarize("50"))

        call_args = mock_app.summarizer.run_summarize.call_args
        assert call_args[1]['fmt'] == "подробное"

    def test_summarize_falls_back_to_short(self, mock_app):
        """_cmd_summarize должен использовать 'short', если формат не установлен."""
        from main import MessageSumApp

        mock_app.db.get_setting = MagicMock(return_value=None)

        app_instance = MessageSumApp.__new__(MessageSumApp)
        app_instance.client = mock_app.client
        app_instance.db = mock_app.db
        app_instance.summarizer = mock_app.summarizer

        async def mock_send(chat_id, msg):
            pass
        app_instance.client.send_message = mock_send

        import asyncio
        asyncio.run(app_instance._cmd_summarize("50"))

        call_args = mock_app.summarizer.run_summarize.call_args
        assert call_args[1]['fmt'] == "short"
