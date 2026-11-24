"""Тесты для GigaChatClient — подсчёт токенов."""

import pytest
import sqlite3
from datetime import datetime, timezone, timedelta


class TestTokenLimit:
    """Тесты подсчёта и проверки лимита токенов."""

    def test_record_tokens_accumulates(self, tmp_path):
        """record_tokens_used должен НАКАПЛИВАТЬ токены, а не перезаписывать."""
        from summarizer.llm_client import GigaChatClient

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        client = GigaChatClient(db_path=db_path)
        client.record_tokens_used(5000)
        client.record_tokens_used(3000)
        client.record_tokens_used(2000)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (f"tokens_used:{today}",)
        ).fetchone()
        conn.close()

        assert row is not None
        assert int(row["value"]) == 10000  # 5000 + 3000 + 2000

    def test_check_token_limit_blocks_at_limit(self, tmp_path):
        """check_token_limit должен блокировать при достижении лимита."""
        from summarizer.llm_client import GigaChatClient

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            (f"tokens_used:{today}", "50000")
        )
        conn.commit()
        conn.close()

        client = GigaChatClient(db_path=db_path)
        allowed, msg = client.check_token_limit()

        assert allowed is False
        assert "Достигнут суточный лимит" in msg

    def test_check_token_limit_allows_under_limit(self, tmp_path):
        """check_token_limit должен разрешать, если лимит не достигнут."""
        from summarizer.llm_client import GigaChatClient

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        client = GigaChatClient(db_path=db_path)
        allowed, msg = client.check_token_limit()

        assert allowed is True
        assert msg == "0"

    def test_record_tokens_no_db_path(self):
        """record_tokens_used должен корректно обрабатывать db_path=None."""
        from summarizer.llm_client import GigaChatClient

        client = GigaChatClient(db_path=None)
        client.record_tokens_used(1000)  # Не должен выбрасывать исключение


class TestTokenLimitEdgeCases:
    """Граничные случаи для лимита токенов."""

    def test_daily_reset(self, tmp_path):
        """Лимит должен сбрасываться каждый день."""
        from summarizer.llm_client import GigaChatClient

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            (f"tokens_used:{yesterday}", "50000")
        )
        conn.commit()
        conn.close()

        client = GigaChatClient(db_path=db_path)
        allowed, msg = client.check_token_limit()
        assert allowed is True          # Сегодня лимит свободен

    def test_get_token_is_public(self):
        """get_token() должен быть публичным методом."""
        from summarizer.llm_client import GigaChatClient

        client = GigaChatClient(db_path=None)
        # Не должен выбрасывать AttributeError
        assert hasattr(client, 'get_token')
        assert callable(client.get_token)

    def test_get_token_returns_same_as_private(self):
        """get_token() должен возвращать то же значение, что _get_token()."""
        from summarizer.llm_client import GigaChatClient

        client = GigaChatClient(db_path=None)
        # _get_token вернёт None (нет реального API)
        result_public = client.get_token()
        result_private = client._get_token()
        assert result_public == result_private
