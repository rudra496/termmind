"""Tests for the API client module."""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import httpx
import pytest

from termind.api import APIClient, APIError


@pytest.fixture
def mock_config():
    with patch("termind.api.load_config") as mc, \
         patch("termind.api.get_provider_info") as mp:
        mc.return_value = {
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-4o-mini",
            "max_tokens": 4096,
            "temperature": 0.7,
        }
        mp.return_value = {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "cost_per_1k_input": 0.00015,
            "cost_per_1k_output": 0.0006,
        }
        yield mc, mp


class TestAPIClient:
    def test_init_defaults(self, mock_config):
        client = APIClient()
        assert client.provider == "openai"
        assert client.api_key == "test-key"
        assert client.model == "gpt-4o-mini"
        assert client.max_tokens == 4096
        assert client.temperature == 0.7
        assert client.usage == {"prompt_tokens": 0, "completion_tokens": 0}

    def test_init_with_overrides(self, mock_config):
        client = APIClient(provider="ollama", api_key="", model="llama3.2", max_tokens=2048, temperature=0.5)
        assert client.provider == "ollama"
        assert client.api_key == ""
        assert client.model == "llama3.2"
        assert client.max_tokens == 2048
        assert client.temperature == 0.5

    def test_headers_with_key(self, mock_config):
        client = APIClient()
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    def test_headers_without_key(self, mock_config):
        mock_config[0].return_value["api_key"] = ""
        client = APIClient()
        headers = client._headers()
        assert "Authorization" not in headers

    def test_build_messages_with_system_prompt(self, mock_config):
        mock_config[0].return_value["system_prompt"] = "You are helpful."
        client = APIClient()
        msgs = client._build_messages([{"role": "user", "content": "hi"}], system_prompt="Be brief.")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Be brief."
        assert len(msgs) == 2

    def test_build_messages_without_system(self, mock_config):
        mock_config[0].return_value["system_prompt"] = ""
        client = APIClient()
        msgs = client._build_messages([{"role": "user", "content": "hi"}])
        assert all(m["role"] != "system" for m in msgs)

    def test_estimate_tokens(self, mock_config):
        client = APIClient()
        assert client.estimate_tokens("hello world") == len("hello world") // 4
        assert client.estimate_tokens("") == 0

    def test_total_tokens(self, mock_config):
        client = APIClient()
        client.usage = {"prompt_tokens": 100, "completion_tokens": 50}
        assert client.total_tokens() == 150

    def test_get_cost(self, mock_config):
        client = APIClient()
        client.usage = {"prompt_tokens": 1000, "completion_tokens": 500}
        # (1000/1000 * 0.00015) + (500/1000 * 0.0006) = 0.00015 + 0.0003
        cost = client.get_cost()
        assert abs(cost - 0.00045) < 1e-10

    def test_chat_success(self, mock_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        client = APIClient()
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            result = client.chat([{"role": "user", "content": "hi"}])
        assert result == "Hello!"

    def test_chat_api_error(self, mock_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        client = APIClient()
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            with pytest.raises(APIError, match="401"):
                client.chat([{"role": "user", "content": "hi"}])

    def test_chat_retry_on_429(self, mock_config):
        call_count = 0
        def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            if call_count < 3:
                r.status_code = 429
                r.text = "Rate limited"
            else:
                r.status_code = 200
                r.json.return_value = {
                    "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            return r
        client = APIClient()
        with patch.object(httpx.Client, "post", side_effect=fake_post):
            result = client.chat([{"role": "user", "content": "hi"}])
        assert result == "OK"
        assert call_count == 3

    def test_chat_retry_exhausted(self, mock_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server error"
        client = APIClient()
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            with pytest.raises(APIError, match="500"):
                client.chat([{"role": "user", "content": "hi"}])

    def test_chat_stream_success(self, mock_config):
        client = APIClient()
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ]
        mock_stream_ctx = MagicMock()
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.iter_lines.return_value = iter(lines)
        mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_resp)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_ctx
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_client):
            result = list(client.chat_stream([{"role": "user", "content": "hi"}]))
        assert result == ["Hello", " world"]

    def test_chat_stream_error(self, mock_config):
        client = APIClient()
        mock_stream_ctx = MagicMock()
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 500
        mock_stream_resp.read.return_value = b"Server error"
        mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_resp)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_ctx
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_client):
            with pytest.raises(APIError, match="500"):
                list(client.chat_stream([{"role": "user", "content": "hi"}]))

    def test_chat_stream_connect_error(self, mock_config):
        client = APIClient()
        with patch("httpx.Client", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(APIError, match="Cannot connect"):
                list(client.chat_stream([{"role": "user", "content": "hi"}]))

    def test_chat_stream_timeout(self, mock_config):
        client = APIClient()
        with patch("httpx.Client", side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(APIError, match="timed out"):
                list(client.chat_stream([{"role": "user", "content": "hi"}]))

    def test_chat_empty_response(self, mock_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "   "}}],
            "usage": {},
        }
        client = APIClient()
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            result = client.chat([{"role": "user", "content": "hi"}])
        assert result == ""
