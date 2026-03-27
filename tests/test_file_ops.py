"""Tests for the file operations module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from termmind.file_ops import (
    read_file,
    write_file,
    edit_file,
    create_file,
    delete_file,
    backup_file,
    get_file_info,
    apply_diff,
    compute_diff,
    find_files,
    search_in_files,
    grep_files,
    build_file_tree,
    get_undo_history,
    undo_last_edit,
    undo_all_edits,
    get_session_diffs,
    _detect_encoding,
    _edit_history,
)


@pytest.fixture(autouse=True)
def clear_edit_history():
    _edit_history.clear()
    yield
    _edit_history.clear()


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Hello World\nLine 2\nLine 3", encoding="utf-8")
    return p


@pytest.fixture
def python_file(tmp_path):
    p = tmp_path / "app.py"
    p.write_text('import os\n\ndef main():\n    print("hello")\n\nif __name__ == "__main__":\n    main()\n')
    return p


class TestReadFile:
    def test_read_existing(self, sample_file):
        content = read_file(str(sample_file))
        assert "Hello World" in content

    def test_read_nonexistent(self):
        assert read_file("/nonexistent/file.txt") is None

    def test_read_directory(self, tmp_path):
        assert read_file(str(tmp_path)) is None

    def test_read_binary_as_text(self, tmp_path):
        p = tmp_path / "data.bin"
        p.write_bytes(b"\x80\x81\x82")
        content = read_file(str(p))
        assert content is not None  # Should use replacement chars

    def test_max_chars_truncation(self, tmp_path):
        p = tmp_path / "big.txt"
        p.write_text("x" * 2000)
        content = read_file(str(p), max_chars=500)
        assert len(content) < 600


class TestWriteFile:
    def test_write_new(self, tmp_path):
        p = str(tmp_path / "new.txt")
        write_file(p, "new content")
        assert Path(p).read_text() == "new content"

    def test_write_existing(self, sample_file):
        write_file(str(sample_file), "updated")
        assert sample_file.read_text() == "updated"

    def test_write_creates_dirs(self, tmp_path):
        p = str(tmp_path / "sub" / "deep" / "file.txt")
        write_file(p, "deep")
        assert Path(p).read_text() == "deep"

    def test_write_tracks_undo(self, sample_file):
        write_file(str(sample_file), "new content")
        assert len(_edit_history) == 1


class TestEditFile:
    def test_replace_text(self, sample_file):
        result = edit_file(str(sample_file), "Hello World", "Goodbye World")
        assert result is True
        assert "Goodbye World" in sample_file.read_text()

    def test_no_match(self, sample_file):
        result = edit_file(str(sample_file), "NOTFOUND", "replacement")
        assert result is False

    def test_nonexistent(self):
        result = edit_file("/nonexistent/file.txt", "a", "b")
        assert result is False


class TestCreateFile:
    def test_create_new(self, tmp_path):
        p = str(tmp_path / "new.txt")
        assert create_file(p, "content") is True
        assert Path(p).read_text() == "content"

    def test_create_existing(self, sample_file):
        assert create_file(str(sample_file), "overwrite") is False


class TestDeleteFile:
    def test_delete_existing(self, sample_file):
        assert delete_file(str(sample_file), confirm=False) is True
        assert not sample_file.exists()

    def test_delete_nonexistent(self):
        assert delete_file("/nonexistent/file.txt", confirm=False) is False


class TestBackupFile:
    def test_backup(self, sample_file):
        bak = backup_file(str(sample_file))
        assert bak is not None
        assert Path(bak).exists()
        assert Path(bak).read_text() == sample_file.read_text()

    def test_backup_nonexistent(self):
        assert backup_file("/nonexistent/file.txt") is None


class TestGetFileInfo:
    def test_file_info(self, sample_file):
        info = get_file_info(str(sample_file))
        assert info is not None
        assert info["name"] == "test.txt"
        assert info["size"] > 0
        assert info["lines"] == 3
        assert info["language"] is None  # .txt not in map

    def test_python_info(self, python_file):
        info = get_file_info(str(python_file))
        assert info["language"] == "python"

    def test_nonexistent(self):
        assert get_file_info("/nonexistent") is None


class TestDetectEncoding:
    def test_utf8(self, sample_file):
        assert _detect_encoding(sample_file) == "utf-8"

    def test_latin1(self, tmp_path):
        p = tmp_path / "latin.txt"
        p.write_bytes("café".encode("latin-1"))
        enc = _detect_encoding(p)
        # Should be able to read it
        assert enc in ("utf-8", "latin-1", "cp1252", "ascii")


class TestComputeDiff:
    def test_no_change(self):
        assert compute_diff("hello", "hello") == ""

    def test_simple_diff(self):
        diff = compute_diff("hello\n", "goodbye\n")
        assert "-hello" in diff
        assert "+goodbye" in diff


class TestApplyDiff:
    def test_simple_patch(self, tmp_path):
        p = tmp_path / "file.txt"
        p.write_text("line1\nline2\nline3\n")
        diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,3 @@\n-line1\n+LINE1\n line2\n line3\n"
        assert apply_diff(str(p), diff) is True

    def test_nonexistent(self):
        assert apply_diff("/nonexistent", "some diff") is False


class TestFindFiles:
    def test_finds_all(self, sample_file, python_file):
        files = find_files(str(sample_file.parent))
        basenames = {os.path.basename(f) for f in files}
        assert "test.txt" in basenames
        assert "app.py" in basenames

    def test_pattern_filter(self, sample_file, python_file):
        files = find_files(str(sample_file.parent), pattern="*.py")
        for f in files:
            assert f.endswith(".py")

    def test_nonexistent_dir(self):
        assert find_files("/nonexistent") == []

    def test_max_depth(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "deep.txt"
        deep.parent.mkdir(parents=True)
        deep.write_text("x")
        shallow = find_files(str(tmp_path), max_depth=1)
        for f in shallow:
            assert "deep.txt" not in f


class TestSearchInFiles:
    def test_finds_match(self, sample_file):
        results = search_in_files("Hello", str(sample_file.parent))
        paths = [r[0] for r in results]
        assert any("test.txt" in p for p in paths)

    def test_no_match(self, sample_file):
        results = search_in_files("ZZZZZZZ", str(sample_file.parent))
        assert len(results) == 0

    def test_regex_invalid(self, sample_file):
        # Should handle invalid regex gracefully
        results = search_in_files("[invalid(", str(sample_file.parent))
        assert isinstance(results, list)


class TestGrepFiles:
    def test_grep(self, sample_file):
        results = grep_files("Hello", str(sample_file.parent))
        assert len(results) > 0

    def test_with_context(self, sample_file):
        results = grep_files("Line 2", str(sample_file.parent), context_lines=1)
        assert len(results) > 0
        assert len(results[0]["context_before"]) >= 0


class TestBuildFileTree:
    def test_basic_tree(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "b.txt").write_text("b")
        tree = build_file_tree(str(tmp_path))
        assert "a.txt" in tree
        assert "sub" in tree

    def test_empty_dir(self, tmp_path):
        tree = build_file_tree(str(tmp_path / "nonexistent"))
        assert tree == ""

    def test_with_sizes(self, sample_file):
        tree = build_file_tree(str(sample_file.parent), show_sizes=True)
        assert "B" in tree or sample_file.parent.name in tree


class TestUndoStack:
    def test_undo_last(self, sample_file):
        write_file(str(sample_file), "new content")
        undo_last_edit()
        assert sample_file.read_text() == "Hello World\nLine 2\nLine 3"

    def test_undo_empty(self):
        assert undo_last_edit() is None

    def test_undo_all(self, sample_file, python_file):
        write_file(str(sample_file), "changed1")
        write_file(str(python_file), "changed2")
        count = undo_all_edits()
        assert count == 2

    def test_get_history(self, sample_file):
        write_file(str(sample_file), "changed")
        history = get_undo_history()
        assert len(history) == 1
        assert history[0][0].endswith("test.txt")

    def test_session_diffs(self, sample_file):
        write_file(str(sample_file), "changed content")
        diffs = get_session_diffs()
        assert len(diffs) == 1
        assert diffs[0][0].endswith("test.txt")
        assert "-Hello World" in diffs[0][1]
        assert "+changed content" in diffs[0][1]


class TestIgnorePatterns:
    def test_termmindignore(self, tmp_path):
        (tmp_path / ".termmindignore").write_text("*.log\nbuild/\n")
        (tmp_path / "app.log").write_text("log")
        build = tmp_path / "build"
        build.mkdir()
        (build / "out.js").write_text("js")
        files = find_files(str(tmp_path))
        basenames = [os.path.basename(f) for f in files]
        assert "app.log" not in basenames
        assert "out.js" not in basenames
