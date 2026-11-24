"""Тесты для Summarizer — суммаризация по запросу."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


class TestSummarizeCommand:
    """Тесты команды суммаризации."""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.send_message = AsyncMock()
        return client

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get_setting = MagicMock(return_value=None)
        db.set_setting = MagicMock()
        db.get_unprocessed_messages = MagicMock(return_value=[])
        db.get_processed_messages = MagicMock(return_value=[])
        db.save_message = MagicMock()
        db.update_message_summary = MagicMock()
        db.save_summary = MagicMock()
        db.get_last_summary = MagicMock(return_value=None)
        return db

    @pytest.mark.asyncio
    async def test_summarize_no_active_chats(self, mock_client, mock_db):
        """run_summarize должен вернуть False, если нет активных чатов."""
        from scheduler.runner import Summarizer

        mock_db.get_setting.return_value = ""

        summarizer = Summarizer(mock_client, mock_db)
        result = await summarizer.run_summarize()
        
        assert result is False
        mock_client.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_summarize_no_messages(self, mock_client, mock_db):
        """run_summarize должен вернуть False, если нет сообщений."""
        from scheduler.runner import Summarizer

        mock_db.get_setting.side_effect = lambda key: "-1001234567890" if key == "active_chats" else None
        mock_db.get_unprocessed_messages.return_value = []
        mock_db.get_processed_messages.return_value = []

        summarizer = Summarizer(mock_client, mock_db)
        
        # Mock get_messages to return empty
        mock_client.get_messages = AsyncMock(return_value=[])

        result = await summarizer.run_summarize()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_summarize_parallel_protection(self, mock_client, mock_db):
        """run_summarize должен блокировать параллельные вызовы."""
        from scheduler.runner import Summarizer

        mock_db.get_setting.return_value = "-1001234567890"

        summarizer = Summarizer(mock_client, mock_db)
        
        # Блокируем lock
        await summarizer._summarize_lock.acquire()
        
        # Второй вызов должен вернуть False
        result = await summarizer.run_summarize()
        
        assert result is False
        mock_client.send_message.assert_called()
        
        # Разблокируем
        summarizer._summarize_lock.release()


class TestGetActiveChatIds:
    """Тесты получения активных чатов."""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.send_message = AsyncMock()
        return client

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get_setting = MagicMock(return_value=None)
        db.set_setting = MagicMock()
        return db

    def test_get_active_chat_ids_empty(self, mock_client, mock_db):
        """_get_active_chat_ids должен вернуть пустой список, если нет активных чатов."""
        from scheduler.runner import Summarizer

        mock_db.get_setting.return_value = ""
        summarizer = Summarizer(mock_client, mock_db)
        result = summarizer._get_active_chat_ids()
        
        assert result == []

    def test_get_active_chat_ids_normalized(self, mock_client, mock_db):
        """_get_active_chat_ids должен нормализовать ID каналов."""
        from scheduler.runner import Summarizer

        # Positive ID → normalize to -100 format
        mock_db.get_setting.return_value = "1352895466,1466120158"
        summarizer = Summarizer(mock_client, mock_db)
        result = summarizer._get_active_chat_ids()
        
        assert len(result) == 2
        assert result[0] == -1001352895466
        assert result[1] == -1001466120158

    def test_get_active_chat_ids_already_normalized(self, mock_client, mock_db):
        """_get_active_chat_ids должен оставлять нормализованные ID."""
        from scheduler.runner import Summarizer

        mock_db.get_setting.return_value = "-1001352895466,-1001466120158"
        summarizer = Summarizer(mock_client, mock_db)
        result = summarizer._get_active_chat_ids()
        
        assert len(result) == 2
        assert result[0] == -1001352895466
        assert result[1] == -1001466120158
