"""Суммаризация Telegram-каналов по запросу."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from telethon.tl.types import Channel

from client.telethon_client import TelethonClient
from summarizer.llm_client import GigaChatClient
from summarizer.formatter import format_summary
from storage.database import Database, normalize_channel_id
from config.settings import settings

logger = logging.getLogger(__name__)

# МСК (UTC+3)
MSK = timezone(timedelta(hours=3))


class Summarizer:
    """Выполнение суммаризации по запросу из чата."""

    def __init__(self, client: TelethonClient, db: Database):
        self.client = client
        self.db = db
        self.db_path = db.db_path
        self.llm_client = GigaChatClient(db_path=db.db_path)
        self._summarize_lock = asyncio.Lock()

    async def run_summarize(self, fmt: str = "short",
                            msg_count: Optional[int] = None,
                            only_unread: bool = False) -> bool:
        """
        Выполнить суммаризацию с защитой от параллельных вызовов.

        Логика:
        1. Взять N сообщений из Telegram (с пагинацией)
        2. Сохранить новые в БД
        3. Разделить на processed=0 (new) и processed=1 (old)
        4. LLM ТОЛЬКО для new
        5. Summary для old берётся из БД

        Args:
            fmt: формат суммаризации
            msg_count: количество сообщений для суммаризации (None = все)

        Returns:
            True при успехе, False при ошибке.
        """
        # Защита от параллельных вызовов
        if self._summarize_lock.locked():
            logger.warning("Суммаризация уже запущена")
            await self.client.send_message(
                settings.owner_chat_id,
                "⏳ Суммаризация уже выполняется. Подождите."
            )
            return False

        async with self._summarize_lock:
            return await self._run_summarize_internal(fmt, msg_count, only_unread)

    async def _run_summarize_internal(self, fmt: str,
                                      msg_count: Optional[int],
                                      only_unread: bool) -> bool:
        """Внутренняя логика суммаризации (вызывается внутри lock)."""
        logger.info("Запуск суммаризации (формат: %s, сообщений: %s)",
                     fmt, msg_count or "все")

        try:
            active_chat_ids = self._get_active_chat_ids()
            if not active_chat_ids:
                await self.client.send_message(
                    settings.owner_chat_id,
                    "📭 Нет активных чатов."
                )
                return False

            # 1. Взять N сообщений из Telegram (с пагинацией)
            telegram_msgs = await self._fetch_from_telegram(
                active_chat_ids, msg_count
            )

            if not telegram_msgs:
                await self.client.send_message(
                    settings.owner_chat_id,
                    "📭 Нет сообщений для суммаризации."
                )
                return False

            logger.info("Получено %d сообщений из Telegram", len(telegram_msgs))

            # 2. Сохранить в БД (deduplication через UNIQUE)
            for msg in telegram_msgs:
                chat_title = getattr(msg.chat, 'title', 'Unknown') if hasattr(msg, 'chat') else 'Unknown'
                content = getattr(msg, 'message', '') or ''
                if not content:
                    continue

                # Определить тип чата
                chat_type = "channel" if isinstance(msg.chat, Channel) else "chat"

                # Нормализовать chat_id
                raw_chat_id = msg.chat_id if hasattr(msg, 'chat_id') else (msg.chat.id if hasattr(msg.chat, 'id') else 0)
                chat_id = normalize_channel_id(raw_chat_id)

                self.db.save_message(
                    telegram_id=msg.id,
                    chat_id=chat_id,
                    chat_title=chat_title,
                    content=content,
                    timestamp=msg.date,
                    chat_type=chat_type,
                )

            # 3. Получить telegram_ids из Telegram
            telegram_ids = {m.id for m in telegram_msgs}

            # 4. Разделить на new (processed=0) и old (processed=1)
            all_new = self.db.get_unprocessed_messages(active_chat_ids)
            all_old = self.db.get_processed_messages(active_chat_ids)

            new_msgs = [m for m in all_new if m["telegram_id"] in telegram_ids]
            old_msgs = [m for m in all_old if m["telegram_id"] in telegram_ids]

            # 5. Финальный список: new + old, сортировка от старых к новым
            # Ограничить ОБЩЕЕ количество сообщений НА КАЖДЫЙ ЧАТ по msg_count
            if msg_count:
                from collections import Counter

                if only_unread:
                    # Только непрочитанные — лимит на new_msgs
                    chat_counts = Counter()
                    filtered_new = []
                    for m in new_msgs:
                        chat_title = m.get("chat_title", "")
                        if chat_counts[chat_title] < msg_count:
                            filtered_new.append(m)
                            chat_counts[chat_title] += 1
                    messages = filtered_new
                    if not messages:
                        await self.client.send_message(
                            settings.owner_chat_id,
                            "📭 Нет новых непрочитанных сообщений."
                        )
                        return True
                else:
                    # Обычный режим: new + old, суммарный лимит msg_count на чат
                    # Приоритет: новые сообщения, потом старые
                    combined = new_msgs + old_msgs
                    combined.sort(key=lambda m: m.get("timestamp", ""))

                    chat_counts = Counter()
                    filtered = []
                    for m in combined:
                        chat_title = m.get("chat_title", "")
                        if chat_counts[chat_title] < msg_count:
                            filtered.append(m)
                            chat_counts[chat_title] += 1
                    messages = filtered
                    
                    # Логирование для отладки
                    logger.info("Фильтрация: combined=%d, filtered=%d, chat_counts=%s", 
                               len(combined), len(filtered), dict(chat_counts))
            else:
                # Без ограничения — берём всё
                if only_unread:
                    messages = new_msgs
                    if not messages:
                        await self.client.send_message(
                            settings.owner_chat_id,
                            "📭 Нет новых непрочитанных сообщений."
                        )
                        return True
                else:
                    messages = new_msgs + old_msgs
                    messages.sort(key=lambda m: m.get("timestamp", ""))

            if not messages:
                await self.client.send_message(
                    settings.owner_chat_id,
                    "📭 Нет сообщений для суммаризации."
                )
                return False

            # 6. Сформировать текст для LLM (ТОЛЬКО новые)
            chat_titles = list({m.get("chat_title", "Unknown") for m in messages})

            messages_text = ""
            for i, msg in enumerate(new_msgs, 1):
                chat_title = msg.get("chat_title", "?")
                telegram_id = msg.get("telegram_id", "?")
                content = msg.get("content", "")
                messages_text += (
                    f"[MSG {i} | ID: {telegram_id} | CHAT: {chat_title}]\n"
                    f"{content}\n\n{'=' * 50}\n\n"
                )

            # 7. LLM ТОЛЬКО для new
            llm_summaries = {}
            summary = ""

            if new_msgs:
                # Проверка лимита токенов
                if self.db_path:
                    allowed, used = self.llm_client.check_token_limit()
                    if not allowed:
                        await self.client.send_message(
                            settings.owner_chat_id,
                            used
                        )
                        return False

                # Читаем уровень подробности из настроек
                fmt = self.db.get_setting("format") or "medium"
                detail_map = {
                    "краткое": "short",
                    "подробное": "detailed",
                    "тезисы": "detailed",
                }
                detail = detail_map.get(fmt, "medium")

                logger.info("Вызов GigaChat API для %d новых сообщений (detail: %s)", len(new_msgs), detail)

                summary = self.llm_client.summarize(messages_text, detail=detail)
                if summary is None:
                    logger.error("Ошибка GigaChat: summarize вернул None")
                    await self.client.send_message(
                        settings.owner_chat_id,
                        "❌ Ошибка вызова GigaChat."
                    )
                    return False

                logger.info(
                    "Суммаризация получена (%d символов)",
                    len(summary),
                )

                # Парсим per-message summaries
                logger.info("Ответ LLM (%d символов):\n%s", len(summary), summary[:2000])
                llm_summaries = self._parse_llm_summaries(summary, new_msgs)

                # Логируем сообщения без суммари
                for msg in new_msgs:
                    tid = msg["telegram_id"]
                    if tid not in llm_summaries:
                        logger.warning("Нет суммари для msg_id=%d: %s", tid, msg.get("content", "")[:100])

                # 8. Сохранить суммари в БД и пометить как processed
                for msg in new_msgs:
                    tid = msg["telegram_id"]  # int
                    if tid in llm_summaries:
                        self.db.update_message_summary(tid, llm_summaries[tid])
                        logger.info("Сохранено суммари для msg_id=%d", tid)

            # 9. Вычислить период
            timestamps = [m.get("timestamp", "") for m in messages if m.get("timestamp")]
            if timestamps:
                period_start = min(timestamps)
                period_end = max(timestamps)
                try:
                    period_start = datetime.fromisoformat(period_start)
                    period_end = datetime.fromisoformat(period_end)
                except Exception:
                    period_start = datetime.now(MSK) - timedelta(hours=24)
                    period_end = datetime.now(MSK)
            else:
                period_start = datetime.now(MSK) - timedelta(hours=24)
                period_end = datetime.now(MSK)

            # 10. Отформатировать и отправить
            #     Formatter сам возьмёт summary из БД для processed сообщений
            formatted = format_summary(
                summary_text=summary if summary else "",
                chat_titles=chat_titles,
                period_start=period_start,
                period_end=period_end,
                message_count=len(messages),
                messages=messages,
                llm_summaries=llm_summaries,
            )

            await self.client.send_message(settings.owner_chat_id, formatted)

            # 11. Сохранить в БД
            self.db.save_summary(
                chat_ids=active_chat_ids,
                period_start=period_start,
                period_end=period_end,
                summary_text=summary or "",
                fmt=fmt,
                status="success",
            )

            logger.info(
                "Суммаризация завершена (сообщений: %d, новых: %d, processed: %d)",
                len(messages), len(new_msgs), len(old_msgs)
            )
            return True

        except Exception as e:
            logger.error("Ошибка при суммаризации: %s", e, exc_info=True)
            await self.client.send_message(
                settings.owner_chat_id,
                f"❌ Ошибка суммаризации: {e}"
            )
            return False

    async def _fetch_from_telegram(self, chat_ids: list[int],
                                    msg_count: Optional[int]) -> list:
        """
        Взять N сообщений из Telegram с пагинацией.
        Из КАЖДОГО чата берётся msg_count сообщений.

        Args:
            chat_ids: список ID чатов
            msg_count: количество сообщений НА ОДИН ЧАТ (None = все)

        Returns:
            Список Message объектов из Telegram.
        """
        target = msg_count or 999999  # лимит на один чат

        all_messages = []
        for chat_id in chat_ids:
            chat_messages = []

            offset_id = 0
            while len(chat_messages) < target:
                remaining = target - len(chat_messages)
                limit = min(100, remaining)

                messages = await self.client.get_messages(
                    chat_id, limit=limit, offset_id=offset_id
                )
                if not messages:
                    break

                for msg in messages:
                    if len(chat_messages) >= target:
                        break

                    chat_messages.append(msg)

                offset_id = messages[-1].id
                if len(messages) < limit:
                    break

            logger.info("Чат %d: получено %d сообщений", chat_id, len(chat_messages))
            all_messages.extend(chat_messages)

        return all_messages

    def _parse_llm_summaries(self, summary_text: str,
                              new_messages: list[dict]) -> dict:
        """
        Парсить ответ LLM в словарь {telegram_id: summary_text}.
        Валидирует что telegram_id — число.
        """
        result = {}
        lines = summary_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or "SUMMARY:" not in line:
                continue

            parts = line.split("|")
            summary_part = ""
            telegram_id = ""

            for part in parts:
                part = part.strip()
                if part.startswith("SUMMARY:"):
                    summary_part = part.replace("SUMMARY:", "").strip()
                elif part.startswith("ID:"):
                    telegram_id = part.replace("ID:", "").strip()

            # Валидация telegram_id
            if not summary_part or not telegram_id:
                continue

            try:
                tid_int = int(telegram_id)
                result[tid_int] = summary_part
            except ValueError:
                logger.warning(
                    "Пропущен невалидный telegram_id от LLM: '%s'", telegram_id
                )

        logger.info("Распарсено %d суммари из ответа LLM", len(result))
        return result

    def _get_active_chat_ids(self) -> list[int]:
        """Получить список активных чатов из настроек (с нормализацией ID)."""
        active_ids_str = self.db.get_setting("active_chats")
        if not active_ids_str:
            return []
        return [
            normalize_channel_id(int(x.strip()))
            for x in active_ids_str.split(",") if x.strip()
        ]
