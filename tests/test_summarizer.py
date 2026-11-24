"""Тесты для суммаризатора."""

import pytest


class TestSummarizerFormatter:
    def test_format_summary(self):
        from summarizer.formatter import format_summary
        from datetime import datetime, timedelta

        summary = "Это тестовая суммаризация."
        chats = ["Tech News", "Python Dev"]
        now = datetime.now()
        since = now - timedelta(hours=24)

        result = format_summary(
            summary_text=summary,
            chat_titles=chats,
            period_start=since,
            period_end=now,
            message_count=42,
        )

        assert "Суммаризация" in result
        assert "42" in result
        assert "Tech News" in result
        assert summary in result

    def test_format_summary_with_messages(self):
        from summarizer.formatter import format_summary
        from datetime import datetime, timedelta

        # Ответ LLM в формате SUMMARY: ... | ID: ... | CHAT: ...
        summary = "SUMMARY: Тестовое суммари | ID: 123 | CHAT: Test Chat"
        chats = ["Test Chat"]
        now = datetime.now()
        since = now - timedelta(hours=24)

        messages = [
            {
                "chat_title": "Test Chat",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 123,
                "chat_id": -1001234567890,
                "content": "Тестовое сообщение для проверки",
            }
        ]

        result = format_summary(
            summary_text=summary,
            chat_titles=chats,
            period_start=since,
            period_end=now,
            message_count=1,
            messages=messages,
            llm_summaries={123: "Тестовое суммари"},
        )

        assert "Суммаризация" in result
        assert "Тестовое суммари" in result
        assert "123" in result
        assert "Test Chat" in result

    def test_format_summary_with_stored_summaries(self):
        from summarizer.formatter import format_summary
        from datetime import datetime, timedelta

        chats = ["Test Chat"]
        now = datetime.now()
        since = now - timedelta(hours=24)

        # Сообщение с уже сохранённым суммари в БД
        messages = [
            {
                "chat_title": "Test Chat",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 123,
                "chat_id": -1001234567890,
                "content": "Тестовое сообщение",
                "summary": "Готовое суммари из БД",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=chats,
            period_start=since,
            period_end=now,
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        assert "Суммаризация" in result
        assert "Готовое суммари из БД" in result
        assert "Test Chat" in result

    def test_format_summary_fallback_to_content(self):
        from summarizer.formatter import format_summary
        from datetime import datetime, timedelta

        chats = ["Test Chat"]
        now = datetime.now()
        since = now - timedelta(hours=24)

        # Сообщение без суммари — fallback на content
        messages = [
            {
                "chat_title": "Test Chat",
                "timestamp": "2026-10-27T20:00:00+03:00",
                "telegram_id": 123,
                "chat_id": -1001234567890,
                "content": "Тестовое сообщение для проверки",
            }
        ]

        result = format_summary(
            summary_text="",
            chat_titles=chats,
            period_start=since,
            period_end=now,
            message_count=1,
            messages=messages,
            llm_summaries={},
        )

        assert "Суммаризация" in result
        assert "Тестовое сообщение для проверки" in result

    def test_get_prompt(self):
        from config.prompts import get_prompt

        prompt = get_prompt("краткое")
        assert "краткое резюме" in prompt

        prompt = get_prompt("подробное")
        assert "подробный" in prompt

        prompt = get_prompt("тезисы")
        assert "тезисный" in prompt

        # Неизвестный формат — fallback на краткое
        prompt = get_prompt("unknown")
        assert "краткое резюме" in prompt

    def test_format_summary_grouped_by_channel(self):
        from summarizer.formatter import format_summary
        from datetime import datetime, timedelta

        chats = ["Канал A", "Канал B"]
        now = datetime.now()
        since = now - timedelta(hours=24)

        # Сообщения из разных каналов вперемешку
        messages = [
            {
                "chat_title": "Канал B",
                "timestamp": "2026-10-27T10:00:00+03:00",
                "telegram_id": 101,
                "chat_id": -1001111111111,
                "content": "Сообщение 1 из Канала B",
                "summary": "Суммари 1 Канал B",
            },
            {
                "chat_title": "Канал A",
                "timestamp": "2026-10-27T09:00:00+03:00",
                "telegram_id": 201,
                "chat_id": -1002222222222,
                "content": "Сообщение 1 из Канала A",
                "summary": "Суммари 1 Канал A",
            },
            {
                "chat_title": "Канал B",
                "timestamp": "2026-10-27T11:00:00+03:00",
                "telegram_id": 102,
                "chat_id": -1001111111111,
                "content": "Сообщение 2 из Канала B",
                "summary": "Суммари 2 Канал B",
            },
            {
                "chat_title": "Канал A",
                "timestamp": "2026-10-27T12:00:00+03:00",
                "telegram_id": 202,
                "chat_id": -1002222222222,
                "content": "Сообщение 2 из Канала A",
                "summary": "Суммари 2 Канал A",
            },
        ]

        result = format_summary(
            summary_text="",
            chat_titles=chats,
            period_start=since,
            period_end=now,
            message_count=4,
            messages=messages,
            llm_summaries={},
        )

        # Проверка заголовков групп
        assert "Канал A | 2 сообщений" in result
        assert "Канал B | 2 сообщений" in result

        # Проверка что группировка работает: Канал A должен быть до Канал B
        pos_a = result.find("Канал A")
        pos_b = result.find("Канал B")
        assert pos_a < pos_b, "Каналы должны идти в порядке первого появления"

        # Проверка что суммари внутри группы
        assert "Суммари 1 Канал A" in result
        assert "Суммари 2 Канал A" in result
        assert "Суммари 1 Канал B" in result
        assert "Суммари 2 Канал B" in result

        # Проверка что нумерация сбрасывается для каждой группы
        # Внутри группы Канал A: 1. и 2.
        # Внутри группы Канал B: 1. и 2.
        assert result.count("1.") >= 2
        assert result.count("2.") >= 2
