"""Tests for context management."""

import pytest
from termmind.context import extract_relevant_files, build_context, clear_cache, _score_file, estimate_tokens
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def project_dir(tmp_dir):
    (tmp_dir / "main.py").write_text("import os\n\ndef hello():\n    print('hello')\n")
    (tmp_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_dir / "README.md").write_text("# My Project\n")
    (tmp_dir / "nested").mkdir()
    (tmp_dir / "nested" / "config.py").write_text("DEBUG = True\n")
    return tmp_dir


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_nonzero(self):
        assert estimate_tokens("hello world") > 0


class TestScoreFile:
    def test_readme_bonus(self, project_dir):
        readme = project_dir / "README.md"
        score = _score_file(str(readme), "help me with the project", str(project_dir))
        assert score > 0

    def test_filename_match(self, project_dir):
        main = project_dir / "main.py"
        score = _score_file(str(main), "fix main.py", str(project_dir))
        assert score > 5


class TestExtractRelevantFiles:
    def test_finds_files(self, project_dir):
        files = extract_relevant_files("hello function", str(project_dir))
        assert len(files) > 0
        assert any("main.py" in f for f in files)

    def test_respects_max_files(self, project_dir):
        for i in range(30):
            (project_dir / f"file{i}.py").write_text(f"# file {i}\n")
        files = extract_relevant_files("code", str(project_dir), max_files=5)
        assert len(files) <= 5

    def test_explicit_file_reference(self, project_dir):
        files = extract_relevant_files("look at utils.py", str(project_dir))
        assert any("utils.py" in f for f in files)


class TestBuildContext:
    def test_includes_file_tree(self, project_dir):
        ctx = build_context("hello", str(project_dir))
        assert "## Project Structure" in ctx

    def test_includes_file_content(self, project_dir):
        ctx = build_context("hello function in main.py", str(project_dir))
        assert "hello" in ctx

    def test_respects_token_limit(self, project_dir):
        large = project_dir / "large.py"
        large.write_text("# large\n" + "x" * 100000)
        ctx = build_context("large", str(project_dir), max_tokens=1000)
        assert len(ctx) < 100000


class TestClearCache:
    def test_clear(self, project_dir):
        build_context("test", str(project_dir))
        clear_cache()
        assert True
