"""Конфигурация приложения."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    # Telegram API
    telethon_phone: str
    telethon_api_id: int
    telethon_api_hash: str
    telethon_proxy: str = ""  # "socks5://user:pass@host:port" или ""

    # GigaChat API
    gigachat_key: str
    rquid: str
    gigachat_model: str = "GigaChat-2"

    # Куда отправлять результат
    owner_chat_id: int

    # Пути
    session_file: str = "message_sum.session"
    db_path: str = "data/messages.db"

    # --- Настраиваемые константы ---
    daily_token_limit: int = 50000  # Лимит токенов GigaChat в день
    cleanup_days: int = 30  # Дней хранения сообщений в БД
    collector_per_chat_limit: int = 100  # Сообщений на один чат при сборе

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
