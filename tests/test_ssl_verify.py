"""Тесты SSL-верификации GigaChat API."""

import pytest
from unittest.mock import patch, MagicMock


class TestSSLVerification:
    """Тесты проверки SSL-сертификатов."""

    def test_http_client_uses_ssl_verification(self):
        """http_client() должен использовать httpx.Client с параметром verify."""
        from summarizer.llm_client import GigaChatClient

        client = GigaChatClient(db_path=None)

        with patch('summarizer.llm_client.httpx.Client') as mock_client:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=MagicMock())
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_context

            with client.http_client():
                pass

            # Проверяем, что httpx.Client был создан
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args[1]
            # verify может быть False (локальная среда) или True/путь к CA
            assert 'verify' in call_kwargs

    def test_get_token_uses_ssl_verification(self):
        """_get_token() должен использовать httpx.Client с параметром verify."""
        from summarizer.llm_client import GigaChatClient

        client = GigaChatClient(db_path=None)

        with patch('summarizer.llm_client.httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"access_token": "test_token"}
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.post = MagicMock(return_value=mock_response)

            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_http)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_context

            with patch('summarizer.llm_client.datetime') as mock_dt:
                mock_dt.now.return_value = MagicMock()
                client._get_token()

            # Проверяем, что httpx.Client был создан с verify
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args[1]
            assert 'verify' in call_kwargs
