"""Tests for provider implementations."""

import pytest

from termmind.providers import (
    PROVIDERS,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    get_provider,
)


class TestGetProvider:
    def test_all_providers(self):
        for name in PROVIDERS:
            provider = get_provider(name, api_key="test" if name != "ollama" else "")
            assert provider.name == name

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_custom_model(self):
        p = get_provider("openai", api_key="test", model="gpt-4o")
        assert p.model == "gpt-4o"


class TestOpenAIProvider:
    def test_defaults(self):
        p = OpenAIProvider()
        assert p.base_url == "https://api.openai.com/v1"
        assert p.model == "gpt-4o-mini"
        assert p.requires_key is True

    def test_list_models(self):
        p = OpenAIProvider()
        models = p.list_models()
        assert "gpt-4o" in models
        assert len(models) >= 5

    def test_estimate_cost(self):
        p = OpenAIProvider(model="gpt-4o")
        cost = p.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_unknown_model(self):
        p = OpenAIProvider(model="unknown")
        cost = p.estimate_cost(1000, 500)
        assert cost == 0.0  # Unknown model falls back to (0.0, 0.0)


class TestAnthropicProvider:
    def test_defaults(self):
        p = AnthropicProvider()
        assert p.model == "claude-sonnet-4-20250514"
        assert p.requires_key is True

    def test_convert_messages(self):
        p = AnthropicProvider()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        system, anth = p._convert_messages(messages)
        assert system == "You are helpful."
        assert len(anth) == 1
        assert anth[0]["role"] == "user"

    def test_headers(self):
        p = AnthropicProvider(api_key="sk-test")
        h = p._anthropic_headers()
        assert h["x-api-key"] == "sk-test"
        assert "anthropic-version" in h


class TestOllamaProvider:
    def test_defaults(self):
        p = OllamaProvider()
        assert p.base_url == "http://localhost:11434/v1"
        assert p.requires_key is False

    def test_estimate_cost_always_zero(self):
        p = OllamaProvider()
        assert p.estimate_cost(100000, 50000) == 0.0


class TestOpenRouterProvider:
    def test_headers_include_referer(self):
        p = OpenRouterProvider(api_key="test")
        h = p._headers()
        assert h["HTTP-Referer"] == "https://github.com/rudra496/termmind"
        assert h["X-Title"] == "TermMind"

    def test_list_models_returns_wildcard(self):
        p = OpenRouterProvider()
        assert p.list_models() == ["*"]


class TestGeminiProvider:
    def test_defaults(self):
        p = GeminiProvider()
        assert "googleapis.com" in p.base_url

    def test_validate_connection_no_key(self):
        p = GeminiProvider()
        assert p.validate_connection() is False
