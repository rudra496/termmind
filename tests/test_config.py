"""Tests for configuration management."""

from unittest.mock import patch

import pytest

from termmind.config import (
    DEFAULT_CONFIG,
    get_provider_info,
    load_config,
    save_config,
    update_config,
)


@pytest.fixture
def config_dir(tmp_dir):
    with (
        patch("termmind.config.CONFIG_DIR", tmp_dir / ".termmind"),
        patch("termmind.config.SESSIONS_DIR", tmp_dir / ".termmind" / "sessions"),
        patch("termmind.config.CONFIG_FILE", tmp_dir / ".termmind" / "config.json"),
    ):
        yield tmp_dir / ".termmind"


class TestLoadConfig:
    def test_default_config(self, config_dir):
        cfg = load_config()
        assert cfg["provider"] == DEFAULT_CONFIG["provider"]
        assert cfg["temperature"] == DEFAULT_CONFIG["temperature"]

    def test_saved_config(self, config_dir):
        save_config({"provider": "openai", "api_key": "test-key", "model": "gpt-4o"})
        cfg = load_config()
        assert cfg["provider"] == "openai"
        assert cfg["api_key"] == "test-key"

    def test_corrupt_config_returns_defaults(self, config_dir):
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text("not json{{{")
        cfg = load_config()
        assert cfg["provider"] == DEFAULT_CONFIG["provider"]


class TestSaveConfig:
    def test_save_and_load(self, config_dir):
        save_config({"provider": "anthropic", "api_key": "sk-123"})
        cfg = load_config()
        assert cfg["provider"] == "anthropic"
        assert cfg["api_key"] == "sk-123"


class TestUpdateConfig:
    def test_update_single_key(self, config_dir):
        result = update_config("theme", "dracula")
        assert result["theme"] == "dracula"

    def test_update_preserves_other_keys(self, config_dir):
        save_config({"provider": "openai"})
        result = update_config("theme", "solarized")
        assert result["provider"] == "openai"
        assert result["theme"] == "solarized"


class TestGetProviderInfo:
    def test_known_provider(self):
        info = get_provider_info("openai")
        assert info["base_url"] == "https://api.openai.com/v1"
        assert "gpt-4o" in info["models"]

    def test_unknown_provider_returns_ollama(self):
        info = get_provider_info("nonexistent")
        assert info["base_url"] == "http://localhost:11434/v1"
