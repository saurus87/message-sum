"""Тесты для фильтров."""

import pytest


class TestFilters:
    def test_filter_text_content(self):
        from client.filters import filter_text_content

        # Текстовое сообщение
        msg = type('Msg', (), {'message': 'Test message'})()
        assert filter_text_content(msg) == "Test message"

        # Пустое сообщение
        msg_empty = type('Msg', (), {'message': ''})()
        assert filter_text_content(msg_empty) is None

    def test_filter_text_content_text_attr(self):
        from client.filters import filter_text_content

        # Сообщение с атрибутом text
        msg = type('Msg', (), {'text': 'Text content'})()
        assert filter_text_content(msg) == "Text content"

    def test_is_media_message(self):
        from client.filters import is_media_message
        from telethon.tl.types import MessageMediaPhoto

        # Медиа-сообщение
        msg_media = type('Msg', (), {'media': MessageMediaPhoto()})()
        assert is_media_message(msg_media) is True

        # Обычное сообщение
        msg_text = type('Msg', (), {'media': None, 'message': 'Hello'})()
        assert is_media_message(msg_text) is False

    def test_filter_active_chats_with_ids(self):
        from client.filters import filter_active_chats

        result = filter_active_chats([], active_chat_ids=[123, 456])
        assert result == [123, 456]

    def test_filter_active_chats_empty(self):
        from client.filters import filter_active_chats

        result = filter_active_chats([])
        assert result == []
