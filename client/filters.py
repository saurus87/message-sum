"""Фильтрация чатов и сообщений."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def filter_text_content(message) -> Optional[str]:
    """
    Извлечь текстовое содержимое из сообщения.
    Возвращает None для медиа, стикеров, голосовых и т.п.
    """
    if hasattr(message, 'message') and message.message:
        return message.message
    if hasattr(message, 'text') and message.text:
        return message.text
    return None


def is_media_message(message) -> bool:
    """Проверить, является ли сообщение медиа."""
    from telethon.tl.types import (
        MessageMediaPhoto, MessageMediaDocument,
        MessageMediaGeo, MessageMediaContact,
    )
    if hasattr(message, 'media') and message.media:
        return isinstance(message.media, (
            MessageMediaPhoto, MessageMediaDocument,
            MessageMediaGeo, MessageMediaContact,
        ))
    return False


def filter_active_chats(dialogs: list, active_chat_ids: Optional[list[int]] = None) -> list[int]:
    """
    Вернуть список ID активных чатов.
    Если active_chat_ids не указан — вернуть все чаты/каналы.
    """
    from telethon.tl.types import PeerChannel, PeerChat

    if active_chat_ids:
        return active_chat_ids

    chat_ids = []
    for dialog in dialogs:
        if not dialog.entity:
            continue
        peer = getattr(dialog.entity, 'peer', None)
        if peer and isinstance(peer, (PeerChannel, PeerChat)):
            chat_ids.append(getattr(peer, 'channel_id',
                             getattr(peer, 'chat_id', None)))
    return chat_ids


def format_chat_list(chats: list[dict]) -> str:
    """Отформатировать список чатов для отправки."""
    if not chats:
        return "Нет подключённых чатов."
    lines = ["📋 Подключённые чаты:"]
    for i, chat in enumerate(chats, 1):
        lines.append(f"  {i}. {chat.get('title', 'Unknown')} (ID: {chat.get('id')})")
    return "\n".join(lines)
