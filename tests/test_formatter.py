"""Тесты для formatter — ссылки на сообщения."""

import pytest
from datetime import datetime, timedelta


class TestMessageLinks:
    """Тесты генерации ссылок на сообщения."""

    def test_channel_link_format(self):
        """Ссылка на канал должна быть прямым URL."""
        from summarizer.formatter import format_summary

        messages = [
            {
                "chat_title": "Test Channel",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 12345,
                "chat_id": -1001234567890,  # Супергруппа/канал
                "content": "Test message",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=["Test Channel"],
            period_start=datetime.now() - timedelta(hours=24),
            period_end=datetime.now(),
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        # Ссылка должна быть прямым URL (chat_id=-1001234567890 → original=1234567890)
        assert "https://t.me/c/1234567890/12345" in result
        assert "🔗" in result

    def test_regular_group_no_link(self):
        """Ссылка на обычную группу должна быть fallback."""
        from summarizer.formatter import format_summary

        messages = [
            {
                "chat_title": "Test Group",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 12345,
                "chat_id": -123456789,  # Обычная группа (ID < 10^10)
                "content": "Test message",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=["Test Group"],
            period_start=datetime.now() - timedelta(hours=24),
            period_end=datetime.now(),
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        # Для обычной группы показываем telegram_id
        assert "12345" in result

    def test_missing_chat_id(self):
        """При отсутствии chat_id — fallback ссылка."""
        from summarizer.formatter import format_summary

        messages = [
            {
                "chat_title": "Test",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 12345,
                "chat_id": 0,  # Нет chat_id
                "content": "Test message",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=["Test"],
            period_start=datetime.now() - timedelta(hours=24),
            period_end=datetime.now(),
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        assert "12345" in result

    def test_channel_link_with_zero_chat_id(self):
        """При chat_id=0 должна быть fallback ссылка."""
        from summarizer.formatter import format_summary

        messages = [
            {
                "chat_title": "Test",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 12345,
                "chat_id": 0,  # chat_id = 0
                "content": "Test message",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=["Test"],
            period_start=datetime.now() - timedelta(hours=24),
            period_end=datetime.now(),
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        assert "12345" in result
