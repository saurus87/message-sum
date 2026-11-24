"""Клиент для вызова GigaChat API."""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Generator

import httpx
from config.prompts import get_prompt
from config.settings import settings

logger = logging.getLogger(__name__)

# Лимит токенов в день — берём из конфига
DAILY_TOKEN_LIMIT = settings.daily_token_limit


class GigaChatClient:
    """Клиент для работы с GigaChat API."""

    def __init__(self, db_path: Optional[str] = None):
        self._token = None
        self._token_expires = None
        self.db_path = db_path

    @contextmanager
    def http_client(self, verify_ssl: bool = True) -> Generator[httpx.Client, None, None]:
        """Контекстный менеджер для httpx клиента."""
        with httpx.Client(timeout=120, verify=verify_ssl) as http:
            yield http

    def _get_token(self) -> Optional[str]:
        """Получить или обновить OAuth токен."""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        try:
            with httpx.Client(verify=True) as http:
                response = http.post(
                    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                    data={"scope": "GIGACHAT_API_PERS"},
                    headers={
                        "Authorization": f"Basic {settings.gigachat_key}",
                        "RqUID": settings.rquid,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                self._token = data.get("access_token")
                # Токен действует 30 минут, обновляем за 5 минут до истечения
                self._token_expires = datetime.now() + timedelta(minutes=25)
                logger.info("OAuth токен получен")
                return self._token
        except Exception as e:
            logger.error("Ошибка получения OAuth токена: %s", e)
            return None

    def get_token(self) -> Optional[str]:
        """Получить или обновить OAuth токен (публичный доступ)."""
        return self._get_token()

    def check_token_limit(self) -> tuple[bool, str]:
        """
        Проверить лимит токенов на сегодня.
        Возвращает (allowed, message).
        """
        if not self.db_path:
            return True, ""

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Получаем использованные токены за сегодня
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    (f"tokens_used:{today}",)
                ).fetchone()

                used = int(row["value"]) if row else 0

                if used >= DAILY_TOKEN_LIMIT:
                    remaining = DAILY_TOKEN_LIMIT - used
                    return False, (
                        f"⚠️ Достигнут суточный лимит токенов ({used}/{DAILY_TOKEN_LIMIT}). "
                        f"Лимит обновится завтра."
                    )

                return True, str(used)
        except Exception as e:
            logger.warning("Ошибка проверки лимита токенов: %s", e)
            return True, ""

    def record_tokens_used(self, tokens: int):
        """Накопить использованные токены за сегодня (НЕ перезаписывать)."""
        if not self.db_path:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"tokens_used:{today}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("BEGIN TRANSACTION")
                # Читаем текущее значение
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                ).fetchone()

                current = int(row["value"]) if row else 0
                new_value = current + tokens

                # Обновляем или вставляем
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(new_value))
                )
                conn.commit()
        except Exception as e:
            logger.warning("Ошибка записи использованных токенов: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass

    def summarize(self, messages_text: str, system_prompt: Optional[str] = None,
                  detail: str = "medium") -> Optional[str]:
        """
        Отправить тексты сообщений на суммаризацию.

        Args:
            messages_text: текст сообщений для LLM
            system_prompt: кастомный system промпт (опционально)
            detail: уровень подробности — "short", "medium", "detailed"

        Returns:
            Текст суммаризации или None при ошибке.
        """
        # Проверка лимита токенов
        if self.db_path:
            allowed, used = self.check_token_limit()
            if not allowed:
                logger.warning("Достигнут лимит токенов: %s", used)
                return None

        token = self.get_token()
        if not token:
            logger.error("Нет OAuth токена")
            return None

        # Выбрать промпт по уровню подробности
        if system_prompt is None:
            prompt_map = {
                "short": "per_message_short",
                "medium": "per_message",
                "detailed": "per_message_detailed",
            }
            prompt_key = prompt_map.get(detail, "per_message")
            system_prompt = get_prompt(prompt_key)

        try:
            logger.info("Вызов GigaChat API")

            with self.http_client() as http:
                response = http.post(
                    "https://api.giga.chat/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.gigachat_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt or get_prompt("per_message"),
                            },
                            {
                                "role": "user",
                                "content": messages_text,
                            },
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    },
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                summary = data["choices"][0]["message"]["content"]

                # Записываем использованные токены
                usage = data.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                if self.db_path:
                    self.record_tokens_used(total_tokens)

                logger.info(
                    "Суммаризация получена (%d символов, %d токенов)",
                    len(summary), total_tokens
                )
                return summary

        except httpx.HTTPStatusError as e:
            logger.error("Ошибка HTTP GigaChat: %s", e)
            return None
        except Exception as e:
            logger.error("Ошибка GigaChat: %s", e)
            return None
