"""Tests for the provider implementations."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from termind.providers import (
    BaseProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    TogetherProvider,
    OpenRouterProvider,
    OllamaProvider,
    get_provider,
    _retry_request,
    PROVIDERS,
)


OPENAI_SSE_LINES = [
    'data: {"choices":[{"delta":{"content":"Hello"}}]}',
    'data: {"choices":[{"delta":{"content":" world"}}]}',
    'data: [DONE]',
]

ANTHROPIC_SSE_LINES = [
    'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
    'data: {"type":"content_block_delta","delta":{"text":" world"}}',
    'data: {"type":"message_stop"}',
]


def _mock_stream_response(lines, status_code=200):
    mock_ctx = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.iter_lines.return_value = iter(lines)
    if status_code != 200:
        mock_resp.read.return_value = b"Error"
    mock_ctx.__enter__ = MagicMock(return_value=mock_resp)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_client = MagicMock()
    mock_client.stream.return_value = mock_ctx
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return mock_client


def _mock_non_stream_response(content, status_code=200, usage=None):
    resp = MagicMock()
    resp.status_code = status_code
    if status_code == 200:
        resp.json.return_value = {
            "choices": [{"message": {"content": content}}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
        }
    else:
        resp.text = "Error"
    return resp


class TestGetProvider:
    def test_known_provider(self):
        p = get_provider("openai", api_key="test")
        assert isinstance(p, OpenAIProvider)

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_all_registered(self):
        for name in PROVIDERS:
            p = get_provider(name)
            assert p.name == name


class TestOpenAIProvider:
    def test_list_models(self):
        p = OpenAIProvider()
        models = p.list_models()
        assert "gpt-4o" in models
        assert len(models) > 0

    def test_estimate_cost(self):
        p = OpenAIProvider(model="gpt-4o-mini")
        cost = p.estimate_cost(1000, 500)
        assert cost > 0

    def test_send_non_stream(self):
        p = OpenAIProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hello!")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hello!"]

    def test_send_stream(self):
        p = OpenAIProvider()
        with patch("httpx.Client", return_value=_mock_stream_response(OPENAI_SSE_LINES)):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=True))
        assert result == ["Hello", " world"]

    def test_send_stream_error(self):
        p = OpenAIProvider()
        with patch("httpx.Client", return_value=_mock_stream_response([], status_code=500)):
            with pytest.raises(Exception, match="500"):
                list(p.send_message([{"role": "user", "content": "hi"}], stream=True))

    def test_validate_connection_ok(self):
        p = OpenAIProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(httpx, "get", return_value=mock_resp):
            assert p.validate_connection() is True

    def test_validate_connection_fail(self):
        p = OpenAIProvider()
        with patch.object(httpx, "get", side_effect=httpx.ConnectError("fail")):
            assert p.validate_connection() is False


class TestAnthropicProvider:
    def test_convert_messages(self):
        p = AnthropicProvider()
        msgs = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "hi"},
        ]
        system, anth = p._convert_messages(msgs)
        assert system == "Be helpful"
        assert len(anth) == 1
        assert anth[0]["role"] == "user"

    def test_list_models(self):
        p = AnthropicProvider()
        models = p.list_models()
        assert len(models) > 0

    def test_estimate_cost(self):
        p = AnthropicProvider(model="claude-3-haiku-20240307")
        cost = p.estimate_cost(1000, 500)
        assert cost > 0

    def test_send_non_stream(self):
        p = AnthropicProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"type": "text", "text": "Hello!"}]}
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hello!"]

    def test_send_stream(self):
        p = AnthropicProvider()
        with patch("httpx.Client", return_value=_mock_stream_response(ANTHROPIC_SSE_LINES)):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=True))
        assert result == ["Hello", " world"]

    def test_validate_no_key(self):
        p = AnthropicProvider(api_key="")
        assert p.validate_connection() is False


class TestGeminiProvider:
    def test_list_models(self):
        p = GeminiProvider()
        assert len(p.list_models()) > 0

    def test_estimate_cost(self):
        p = GeminiProvider()
        assert p.estimate_cost(10000, 5000) == 0.0

    def test_send_non_stream(self):
        p = GeminiProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hi")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hi"]

    def test_send_stream(self):
        p = GeminiProvider()
        with patch("httpx.Client", return_value=_mock_stream_response(OPENAI_SSE_LINES)):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=True))
        assert "Hello" in result


class TestGroqProvider:
    def test_estimate_cost(self):
        p = GroqProvider()
        assert p.estimate_cost(1000, 500) == 0.0

    def test_send_non_stream(self):
        p = GroqProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hi")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hi"]

    def test_list_models(self):
        p = GroqProvider()
        assert len(p.list_models()) > 0


class TestTogetherProvider:
    def test_estimate_cost(self):
        p = TogetherProvider()
        cost = p.estimate_cost(1000, 500)
        assert cost > 0

    def test_send_non_stream(self):
        p = TogetherProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hi")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hi"]


class TestOpenRouterProvider:
    def test_estimate_cost(self):
        p = OpenRouterProvider()
        assert p.estimate_cost(1000, 500) == 0.0

    def test_list_models(self):
        p = OpenRouterProvider()
        assert p.list_models() == ["*"]

    def test_send_non_stream(self):
        p = OpenRouterProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hi")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hi"]


class TestOllamaProvider:
    def test_estimate_cost(self):
        p = OllamaProvider()
        assert p.estimate_cost(1000, 500) == 0.0

    def test_send_non_stream(self):
        p = OllamaProvider()
        with patch.object(httpx.Client, "post", return_value=_mock_non_stream_response("Hi")):
            result = list(p.send_message([{"role": "user", "content": "hi"}], stream=False))
        assert result == ["Hi"]

    def test_list_models_from_api(self):
        p = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
        with patch.object(httpx, "get", return_value=mock_resp):
            models = p.list_models()
        assert models == ["llama3.2", "mistral"]

    def test_list_models_fallback(self):
        p = OllamaProvider()
        with patch.object(httpx, "get", side_effect=httpx.ConnectError("fail")):
            models = p.list_models()
        assert "llama3.2" in models

    def test_validate_connection(self):
        p = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(httpx, "get", return_value=mock_resp):
            assert p.validate_connection() is True


class TestRetryRequest:
    def test_success_first_try(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        call_count = 0
        def func():
            nonlocal call_count
            call_count += 1
            return mock_resp
        result = _retry_request(func, max_retries=3)
        assert result.status_code == 200
        assert call_count == 1

    def test_retry_on_429(self):
        call_count = 0
        def func():
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            r.status_code = 429 if call_count < 3 else 200
            return r
        with patch("time.sleep"):
            result = _retry_request(func, max_retries=3)
        assert result.status_code == 200
        assert call_count == 3

    def test_retry_on_connection_error(self):
        call_count = 0
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("fail")
            return MagicMock(status_code=200)
        with patch("time.sleep"):
            result = _retry_request(func, max_retries=3)
        assert result.status_code == 200
