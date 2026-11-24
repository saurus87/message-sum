"""SQLite хранилище данных."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ключевые колонки для частых запросов
MESSAGE_INDEX_COLS = "chat_id, processed, timestamp"


def normalize_channel_id(chat_id: int) -> int:
    """
    Нормализовать ID канала для Telethon.
    
    Telegram channels требуют ID в формате -100XXXXXXXXXX.
    Если ID положительный и не начинается с -100, добавляем -100 префикс.
    Отрицательные ID возвращаются без изменений.
    """
    if chat_id < 0:
        return chat_id
    # Positive ID → normalize to -100 format
    return -1000000000000 - chat_id


class Database:
    """Управление SQLite базой данных."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Создать таблицы, если не существуют."""
        with self._get_connection() as conn:
            # 1. Сначала создать таблицы
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    chat_id INTEGER NOT NULL,
                    chat_title TEXT,
                    content TEXT,
                    timestamp DATETIME,
                    processed BOOLEAN DEFAULT 0,
                    summary TEXT,
                    chat_type TEXT
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_ids TEXT,
                    period_start DATETIME,
                    period_end DATETIME,
                    summary_text TEXT,
                    format TEXT,
                    status TEXT DEFAULT 'pending'
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
                CREATE INDEX IF NOT EXISTS idx_messages_processed ON messages(processed);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_telegram ON messages(telegram_id);
            """)

            # 2. Миграции для существующих БД
            # Миграция: добавить колонку summary если нет
            try:
                conn.execute("SELECT summary FROM messages LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE messages ADD COLUMN summary TEXT")
                logger.info("Миграция: добавлена колонка summary")

            # Миграция: добавить колонку chat_type если нет
            try:
                conn.execute("SELECT chat_type FROM messages LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE messages ADD COLUMN chat_type TEXT DEFAULT 'channel'")
                logger.info("Миграция: добавлена колонка chat_type")

            # Миграция: установить chat_type для существующих сообщений
            try:
                conn.execute(
                    "UPDATE messages SET chat_type = 'channel' WHERE chat_type IS NULL"
                )
                updated = conn.total_changes
                if updated > 0:
                    logger.info("Миграция: chat_type установлен для %d сообщений", updated)
            except sqlite3.OperationalError:
                pass

            # Миграция: добавить composite индекс для оптимизации запросов
            try:
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_messages_optimized "
                    f"ON messages({MESSAGE_INDEX_COLS})"
                )
                logger.info("Миграция: создан оптимизированный индекс")
            except sqlite3.OperationalError:
                pass
        logger.info("База данных инициализирована: %s", self.db_path)

    # --- Messages ---

    def save_message(self, telegram_id: int, chat_id: int, chat_title: str,
                     content: str, timestamp: datetime, summary: str = "",
                     chat_type: str = "channel") -> int:
        """Сохранить сообщение. Вернуть id."""
        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO messages (telegram_id, chat_id, chat_title, content, timestamp, processed, summary, chat_type) "
                    "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                    (telegram_id, chat_id, chat_title, content, timestamp.isoformat(), summary, chat_type),
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Сообщение уже есть в БД
                return -1

    def update_message_summary(self, telegram_id: int, summary: str):
        """Обновить суммари для существующего сообщения."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE messages SET summary = ? WHERE telegram_id = ?",
                (summary, telegram_id),
            )
            conn.execute(
                "UPDATE messages SET processed = 1 WHERE telegram_id = ?",
                (telegram_id,),
            )

    def get_unprocessed_messages(self, chat_ids: list[int], since: Optional[datetime] = None) -> list[dict]:
        """
        Получить необработанные сообщения из указанных чатов (только каналы).
        Если since указан — фильтровать по дате, иначе — все необработанные.
        """
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(chat_ids))
            if since:
                rows = conn.execute(
                    f"SELECT * FROM messages WHERE chat_id IN ({placeholders}) "
                    "AND timestamp >= ? AND processed = 0 AND chat_type = 'channel' "
                    "ORDER BY timestamp DESC",
                    (*chat_ids, since.isoformat()),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM messages WHERE chat_id IN ({placeholders}) "
                    "AND processed = 0 AND chat_type = 'channel' "
                    "ORDER BY timestamp DESC",
                    chat_ids,
                ).fetchall()
            return [dict(r) for r in rows]

    def get_all_messages(self, chat_ids: list[int]) -> list[dict]:
        """Получить ВСЕ сообщения из указанных чатов (без фильтра processed), ORDER BY timestamp DESC."""
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(chat_ids))
            rows = conn.execute(
                f"SELECT * FROM messages WHERE chat_id IN ({placeholders}) "
                "AND chat_type = 'channel' "
                "ORDER BY timestamp DESC",
                chat_ids,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_processed_messages(self, chat_ids: list[int],
                               limit: Optional[int] = None) -> list[dict]:
        """Получить обработанные сообщения из указанных чатов (для повторной суммаризации)."""
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(chat_ids))
            query = (
                f"SELECT * FROM messages WHERE chat_id IN ({placeholders}) "
                "AND processed = 1 AND chat_type = 'channel' "
                "ORDER BY timestamp DESC"
            )
            params: list = list(chat_ids)
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def mark_processed(self, message_ids: list[int]):
        """Пометить сообщения как обработанные."""
        if not message_ids:
            return
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(message_ids))
            conn.execute(
                f"UPDATE messages SET processed = 1 WHERE id IN ({placeholders})",
                message_ids,
            )

    def get_all_chats(self) -> list[dict]:
        """Получить список всех чатов."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT chat_id, chat_title FROM messages ORDER BY chat_title"
            ).fetchall()
            return [dict(r) for r in rows]

    def cleanup_old_messages(self, days: int = 30):
        """Удалить сообщения старше заданного количества дней."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
        logger.info("Удалено %d старых сообщений", cursor.rowcount)

    # --- Summaries ---

    def save_summary(self, chat_ids: list[int], period_start: datetime,
                     period_end: datetime, summary_text: str,
                     fmt: str, status: str = "success") -> int:
        """Сохранить результат суммаризации."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO summaries (chat_ids, period_start, period_end, summary_text, format, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (json.dumps(chat_ids), period_start.isoformat(),
                 period_end.isoformat(), summary_text, fmt, status),
            )
            return cursor.lastrowid

    def get_last_summary(self) -> Optional[dict]:
        """Получить последнюю суммаризацию."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM summaries ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # --- Settings ---

    def get_setting(self, key: str) -> Optional[str]:
        """Получить настройку по ключу."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_setting(self, key: str, value: str):
        """Установить настройку."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
