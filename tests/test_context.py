"""Tests for the context management module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from termind.context import (
    build_context,
    clear_cache,
    extract_relevant_files,
    get_files_in_context,
    _score_file,
    _smart_truncate,
    estimate_tokens,
)


@pytest.fixture(autouse=True)
def clear_context_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def project_dir(tmp_path):
    """Create a small project directory for testing."""
    (tmp_path / "README.md").write_text("# My Project\nA cool project.\n")
    (tmp_path / "main.py").write_text("import os\n\ndef hello():\n    print('hello')\n")
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    subdir = tmp_path / "pkg"
    subdir.mkdir()
    (subdir / "__init__.py").write_text("")
    (subdir / "core.py").write_text("class Core:\n    pass\n")
    # Add gitignore
    (tmp_path / ".gitignore").write_text("__pycache__\n*.pyc\n")
    return tmp_path


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_simple(self):
        assert estimate_tokens("hello world") == len("hello world") // 4

    def test_long(self):
        text = "word " * 1000
        assert estimate_tokens(text) == len(text) // 4


class TestScoreFile:
    def test_filename_match(self, project_dir):
        score = _score_file(str(project_dir / "main.py"), "main.py file", str(project_dir))
        assert score > 0

    def test_extension_match(self, project_dir):
        score = _score_file(str(project_dir / "main.py"), "python", str(project_dir))
        assert score > 0

    def test_content_match(self, project_dir):
        score = _score_file(str(project_dir / "main.py"), "print hello", str(project_dir))
        assert score > 0

    def test_no_match(self, project_dir):
        score = _score_file(str(project_dir / "main.py"), "xyzabcnothere", str(project_dir))
        # May have some score from source file bonus but should be low
        assert score < 5


class TestExtractRelevantFiles:
    def test_finds_files(self, project_dir):
        files = extract_relevant_files("main.py", str(project_dir))
        assert len(files) > 0
        # main.py should be top or included
        basenames = [os.path.basename(f) for f in files]
        assert "main.py" in basenames

    def test_respects_max_files(self, project_dir):
        files = extract_relevant_files("python", str(project_dir), max_files=2)
        assert len(files) <= 2

    def test_explicit_file_ref(self, project_dir):
        files = extract_relevant_files("look at utils.py", str(project_dir))
        basenames = [os.path.basename(f) for f in files]
        assert "utils.py" in basenames


class TestBuildContext:
    def test_builds_context(self, project_dir):
        ctx = build_context("hello", str(project_dir))
        assert "Project Structure" in ctx
        assert len(ctx) > 0

    def test_includes_file_tree(self, project_dir):
        ctx = build_context("main", str(project_dir))
        assert "main.py" in ctx

    def test_extra_files(self, project_dir):
        extra = [os.path.relpath(str(project_dir / "utils.py"), str(project_dir))]
        ctx = build_context("main", str(project_dir), extra_files=extra)
        assert "utils.py" in ctx or "utils" in ctx


class TestSmartTruncate:
    def test_no_truncate(self):
        text = "hello"
        assert _smart_truncate(text, 100) == text

    def test_short_truncate(self):
        text = "a" * 1000
        result = _smart_truncate(text, 500)
        assert len(result) <= 550  # some overhead for the truncation message

    def test_keeps_head_and_tail(self):
        text = "\n".join([f"line {i}" for i in range(100)])
        result = _smart_truncate(text, 200)
        assert "line 0" in result
        assert "omitted" in result.lower()


class TestGetFilesInContext:
    def test_returns_files(self, project_dir):
        files = get_files_in_context(str(project_dir))
        assert len(files) > 0
        basenames = [os.path.basename(f) for f in files]
        assert "main.py" in basenames


class TestIgnorePatterns:
    def test_gitignore_respected(self, project_dir):
        pycache = project_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "test.pyc").write_text("xxx")
        files = get_files_in_context(str(project_dir))
        # Should not include __pycache__ files
        for f in files:
            assert "__pycache__" not in f
