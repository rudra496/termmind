"""Tests for session management."""

import json
import time
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

import pytest

from termmind.sessions import save_session, load_session, list_sessions, export_session


@pytest.fixture
def sessions_dir(tmp_dir):
    d = tmp_dir / "sessions"
    d.mkdir()
    with patch("termmind.sessions.SESSIONS_DIR", d):
        yield d


class TestSaveSession:
    def test_save_creates_file(self, sessions_dir):
        messages = [{"role": "user", "content": "hello"}]
        save_session("test", messages, "ollama", "llama3.2", 0.001, 100, [])
        assert (sessions_dir / "test.json").exists()

    def test_save_content(self, sessions_dir):
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        save_session("test2", messages, "ollama", "llama3.2", 0.001, 100, ["main.py"])
        data = json.loads((sessions_dir / "test2.json").read_text())
        assert data["name"] == "test2"
        assert data["provider"] == "ollama"
        assert data["model"] == "llama3.2"
        assert data["tokens"] == 100
        assert "main.py" in data["context_files"]
        assert len(data["messages"]) == 2


class TestLoadSession:
    def test_load_existing(self, sessions_dir):
        messages = [{"role": "user", "content": "test"}]
        save_session("loadme", messages, "openai", "gpt-4o", 0.01, 500, [])
        result = load_session("loadme")
        assert result is not None
        assert result["provider"] == "openai"
        assert len(result["messages"]) == 1

    def test_load_nonexistent(self, sessions_dir):
        result = load_session("nonexistent")
        assert result is None


class TestListSessions:
    def test_empty(self, sessions_dir):
        result = list_sessions()
        assert result == []

    def test_list_sessions(self, sessions_dir):
        save_session("a", [], "ollama", "llama3.2", 0.0, 0, [])
        save_session("b", [], "openai", "gpt-4o", 0.01, 100, [])
        result = list_sessions()
        assert len(result) == 2

    def test_search(self, sessions_dir):
        save_session("python-help", [], "ollama", "llama3.2", 0.0, 0, [])
        save_session("rust-help", [], "openai", "gpt-4o", 0.01, 100, [])
        result = list_sessions(search="python")
        assert len(result) == 1


class TestExportSession:
    def test_export_json(self, sessions_dir):
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
        save_session("exportme", messages, "ollama", "llama3.2", 0.001, 50, [])
        result = export_session("exportme", "json")
        assert "hello" in result

    def test_export_markdown(self, sessions_dir):
        messages = [{"role": "user", "content": "hello"}]
        save_session("exportmd", messages, "ollama", "llama3.2", 0.0, 10, [])
        result = export_session("exportmd", "markdown")
        assert "# " in result or "hello" in result

    def test_export_nonexistent(self, sessions_dir):
        result = export_session("nope", "json")
        assert result is None
