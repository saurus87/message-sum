"""Тесты для config/prompts.py."""

import pytest


class TestPrompts:
    """Тесты шаблонов промптов."""

    def test_get_prompt_short(self):
        """get_prompt('краткое') должен вернуть краткий промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("краткое")
        assert "краткое резюме" in prompt.lower()

    def test_get_prompt_detailed(self):
        """get_prompt('подробное') должен вернуть подробный промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("подробное")
        assert "подробный" in prompt.lower()

    def test_get_prompt_bullet(self):
        """get_prompt('тезисы') должен вернуть тезисный промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("тезисы")
        assert "тезис" in prompt.lower()

    def test_get_prompt_per_message(self):
        """get_prompt('per_message') должен вернуть per-message промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("per_message")
        assert "SUMMARY:" in prompt
        assert "ID:" in prompt
        assert "CHAT:" in prompt

    def test_get_prompt_per_message_short(self):
        """get_prompt('per_message_short') должен вернуть краткий per-message промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("per_message_short")
        assert "1 предложение" in prompt or "1-предложение" in prompt.lower()

    def test_get_prompt_per_message_detailed(self):
        """get_prompt('per_message_detailed') должен вернуть подробный per-message промпт."""
        from config.prompts import get_prompt

        prompt = get_prompt("per_message_detailed")
        assert "4-5 предложений" in prompt or "4-5" in prompt

    def test_get_prompt_fallback(self):
        """get_prompt(unknown) должен вернуть fallback."""
        from config.prompts import get_prompt

        prompt = get_prompt("unknown_format")
        assert prompt is not None
        assert len(prompt) > 0

    def test_all_formats_available(self):
        """Все форматы должны быть доступны."""
        from config.prompts import PROMPTS

        assert "краткое" in PROMPTS
        assert "подробное" in PROMPTS
        assert "тезисы" in PROMPTS
        assert "per_message" in PROMPTS
        assert "per_message_short" in PROMPTS
        assert "per_message_detailed" in PROMPTS
