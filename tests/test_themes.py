"""Tests for themes."""

import pytest
from termmind.themes import get_theme, list_themes


class TestListThemes:
    def test_returns_list(self):
        themes = list_themes()
        assert isinstance(themes, list)
        assert len(themes) >= 3

    def test_known_themes(self):
        themes = list_themes()
        assert "dark" in themes
        assert "light" in themes


class TestGetTheme:
    def test_dark_theme(self):
        theme = get_theme("dark")
        assert theme is not None

    def test_light_theme(self):
        theme = get_theme("light")
        assert theme is not None

    def test_unknown_theme_returns_default(self):
        theme = get_theme("nonexistent")
        assert theme is not None
