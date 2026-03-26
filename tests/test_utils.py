"""Tests for the utility functions module."""

import pytest

from termind.utils import (
    estimate_tokens,
    calculate_cost,
    detect_language,
    extract_code_blocks,
    truncate_text,
    format_file_path,
    render_markdown,
)


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_none_like(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        text = "Hello, World!"
        assert estimate_tokens(text) == len(text) // 4

    def test_long_text(self):
        text = "word " * 10000
        assert estimate_tokens(text) > 0

    def test_code_like(self):
        text = "def foo():\n    return 42\n"
        assert estimate_tokens(text) > 0


class TestCalculateCost:
    def test_known_model(self):
        cost = calculate_cost("gpt-4o-mini", 1000, 500)
        # (1000/1000 * 0.00015) + (500/1000 * 0.0006)
        expected = 0.00015 + 0.0003
        assert abs(cost - expected) < 1e-10

    def test_free_model(self):
        cost = calculate_cost("gemini-2.0-flash", 10000, 5000)
        assert cost == 0.0

    def test_unknown_model(self):
        cost = calculate_cost("unknown-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens(self):
        assert calculate_cost("gpt-4o-mini", 0, 0) == 0.0

    def test_large_tokens(self):
        cost = calculate_cost("gpt-4o", 100000, 50000)
        assert cost > 0


class TestDetectLanguage:
    @pytest.mark.parametrize("filename,expected", [
        ("main.py", "python"),
        ("app.js", "javascript"),
        ("index.ts", "typescript"),
        ("main.go", "go"),
        ("lib.rs", "rust"),
        ("App.java", "java"),
        ("script.rb", "ruby"),
        ("main.c", "c"),
        ("lib.cpp", "cpp"),
        ("Program.cs", "csharp"),
        ("index.php", "php"),
        ("run.sh", "bash"),
        ("config.yaml", "yaml"),
        ("config.yml", "yaml"),
        ("setup.toml", "toml"),
        ("data.json", "json"),
        ("README.md", "markdown"),
        ("index.html", "html"),
        ("style.css", "css"),
        ("query.sql", "sql"),
        ("app.swift", "swift"),
        ("Main.kt", "kotlin"),
        ("App.scala", "scala"),
        ("script.lua", "lua"),
        ("analysis.r", "r"),
        ("app.dart", "dart"),
        ("App.jsx", "jsx"),
        ("App.tsx", "tsx"),
    ])
    def test_extensions(self, filename, expected):
        assert detect_language(filename) == expected

    def test_dockerfile(self):
        assert detect_language("Dockerfile") == "docker"

    def test_makefile(self):
        assert detect_language("Makefile") == "makefile"

    def test_cmakelists(self):
        assert detect_language("CMakeLists.txt") == "makefile"

    def test_no_extension(self):
        assert detect_language("Makefile") is not None
        assert detect_language("unknown") is None


class TestExtractCodeBlocks:
    def test_single_block(self):
        text = '```python\nprint("hello")\n```'
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0] == ("python", 'print("hello")\n')

    def test_multiple_blocks(self):
        text = '```js\nconsole.log("a")\n```\nSome text\n```py\nprint("b")\n```'
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2

    def test_no_blocks(self):
        assert extract_code_blocks("no code here") == []

    def test_empty_language(self):
        text = '```\nsome code\n```'
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0][0] == ""


class TestTruncateText:
    def test_no_truncate(self):
        text = "hello"
        assert truncate_text(text, 100) == "hello"

    def test_truncate(self):
        text = "a" * 100
        result = truncate_text(text, 50)
        assert len(result) < 100
        assert result.endswith("...")

    def test_custom_suffix(self):
        text = "a" * 100
        result = truncate_text(text, 50, suffix="…")
        assert result.endswith("…")


class TestFormatFilePath:
    def test_format(self):
        result = format_file_path("/path/to/file.py")
        assert "file.py" in result
        assert "\033[" in result  # ANSI codes


class TestRenderMarkdown:
    def test_render(self, capsys):
        render_markdown("# Hello")
        captured = capsys.readouterr()
        # Just verify it doesn't crash
        assert True
