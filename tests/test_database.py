"""Тесты для Database — фильтрация по chat_type."""

import pytest
import sqlite3
from datetime import datetime, timezone


class TestChatTypeFiltering:
    """Тесты фильтрации сообщений по типу чата."""

    @pytest.fixture
    def db_with_data(self, tmp_path):
        """Создать БД с тестовыми данными."""
        from storage.database import Database
        
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        
        # Добавить тестовые сообщения
        chat_id = -1001234567890
        ts = datetime.now(timezone.utc)
        
        # Канал — не обработан
        db.save_message(
            telegram_id=1001, chat_id=chat_id, chat_title="Test Channel",
            content="Channel message 1", timestamp=ts, chat_type="channel"
        )
        # Чат — не обработан
        db.save_message(
            telegram_id=1002, chat_id=chat_id, chat_title="Test Chat",
            content="Chat message 1", timestamp=ts, chat_type="chat"
        )
        # Канал — обработан (через update_message_summary)
        db.save_message(
            telegram_id=1003, chat_id=chat_id, chat_title="Test Channel",
            content="Channel message 2", timestamp=ts, chat_type="channel"
        )
        db.update_message_summary(1003, "Summary 2")
        # Чат — обработан
        db.save_message(
            telegram_id=1004, chat_id=chat_id, chat_title="Test Chat",
            content="Chat message 2", timestamp=ts, chat_type="chat"
        )
        db.update_message_summary(1004, "Summary 3")
        
        return db, chat_id

    def test_get_unprocessed_filters_channels_only(self, db_with_data):
        """get_unprocessed_messages должен возвращать только каналы."""
        db, chat_id = db_with_data
        
        messages = db.get_unprocessed_messages([chat_id])
        
        # Должен вернуть только 1 сообщение из канала
        assert len(messages) == 1
        assert messages[0]["chat_type"] == "channel"
        assert messages[0]["telegram_id"] == 1001

    def test_get_processed_filters_channels_only(self, db_with_data):
        """get_processed_messages должен возвращать только каналы."""
        db, chat_id = db_with_data
        
        messages = db.get_processed_messages([chat_id])
        
        # Должен вернуть только 1 сообщение из канала
        assert len(messages) == 1
        assert messages[0]["chat_type"] == "channel"
        assert messages[0]["telegram_id"] == 1003

    def test_get_all_filters_channels_only(self, db_with_data):
        """get_all_messages должен возвращать только каналы."""
        db, chat_id = db_with_data
        
        messages = db.get_all_messages([chat_id])
        
        # Должен вернуть 2 сообщения (1 не обработан + 1 обработан) из канала
        assert len(messages) == 2
        for msg in messages:
            assert msg["chat_type"] == "channel"

    def test_migration_chat_type_column(self, tmp_path):
        """Миграция должна добавить колонку chat_type."""
        from storage.database import Database
        
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        
        # Проверить, что колонка chat_type существует
        with db._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(messages)").fetchall()
            column_names = [col["name"] for col in columns]
            assert "chat_type" in column_names