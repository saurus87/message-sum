"""Telethon-клиент для работы с Telegram."""

import logging
import re
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import (
    PeerUser,
    PeerChat,
    PeerChannel,
    User,
    Chat,
    Channel,
    MessageEntityTextUrl,
)
from telethon.tl.functions.messages import SendMessageRequest

from config.settings import settings

logger = logging.getLogger(__name__)


class TelethonClient:
    """Управление Telethon-клиентом."""

    def __init__(self):
        self.client = TelegramClient(
            settings.session_file,
            settings.telethon_api_id,
            settings.telethon_api_hash,
        )

    async def start(self):
        """Запустить клиент (авторизация по номеру телефона)."""
        await self.client.start(phone=settings.telethon_phone)
        logger.info("Telethon-клиент авторизован")

    async def get_me(self):
        """Получить данные текущего пользователя."""
        return await self.client.get_me()

    async def send_message(self, chat_id: int, message: str, parse_mode: Optional[str] = None) -> int:
        """Отправить сообщение в чат/пользователю."""
        # Разбить длинное сообщение на части (лимит Telegram ~4096 символов)
        parts = self._split_message(message)
        for part in parts:
            entities = self._parse_urls(part)
            await self.client.send_message(chat_id, part, formatting_entities=entities)
        logger.info("Сообщение отправлено в %s", chat_id)
        return 0

    def _parse_urls(self, text: str) -> list:
        """Найти все URL в тексте и создать MessageEntityTextUrl.
        
        Важно: Telegram требует UTF-16 offsets для сущностей.
        Эмодзи занимают 2 UTF-16 юнита, но 1 символ Python.
        """
        entities = []
        # Паттерн: http(s):// + любые символы кроме пробельных
        pattern = r'https?://[^\s<>"\']+'
        
        # Конвертировать Python-смещение (code points) в UTF-16 (code units)
        def to_utf16_offset(text, py_offset: int) -> int:
            return len(text[:py_offset].encode('utf-16-le')) // 2
        
        for match in re.finditer(pattern, text):
            url = match.group()
            py_start = match.start()
            py_end = match.end()
            
            # Конвертировать в UTF-16
            start = to_utf16_offset(text, py_start)
            length = to_utf16_offset(text, py_end) - start
            
            entities.append(MessageEntityTextUrl(
                offset=start,
                length=length,
                url=url
            ))
        return entities

    async def get_dialogs(self) -> list:
        """Получить список всех диалогов (чатов/каналов)."""
        return await self.client.get_dialogs()

    async def get_messages(self, chat_id, limit: int = 100, offset_id: int = 0):
        """Получить сообщения из чата с поддержкой пагинации.
        
        Args:
            chat_id: ID чата
            limit: количество сообщений
            offset_id: ID сообщения, с которого начинать (0 = с самого свежего)
        """
        messages = []
        async for msg in self.client.iter_messages(
            chat_id, limit=limit, offset_id=offset_id
        ):
            messages.append(msg)
        return messages

    async def get_chat_info(self, entity) -> dict:
        """Получить информацию о чате/канале."""
        if isinstance(entity, (User, Chat, Channel)):
            entity = await self.client.get_entity(entity)

        title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
        peer = entity.peer_id if hasattr(entity, 'peer_id') else None

        return {
            "id": peer,
            "title": title,
            "type": self._get_entity_type(entity),
        }

    def _get_entity_type(self, entity) -> str:
        """Определить тип сущности."""
        if isinstance(entity.peer, PeerUser):
            return "user"
        elif isinstance(entity.peer, PeerChat):
            return "chat"
        elif isinstance(entity.peer, PeerChannel):
            return getattr(entity, 'megagroup', False) and "group" or "channel"
        return "unknown"

    def _split_message(self, text: str, max_length: int = 4000) -> list[str]:
        """Разбить текст на части по лимиту Telegram."""
        if len(text) <= max_length:
            return [text]
        parts = []
        while len(text) > max_length:
            # Ищем границу слова
            split_pos = text.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(text[:split_pos])
            text = text[split_pos:].lstrip('\n ')
        if text:
            parts.append(text)
        return parts

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.client.disconnect()
