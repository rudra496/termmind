# Contributing to TermMind 🧠

Thank you for your interest in contributing to TermMind! This guide covers everything you need to get started.

## Table of Contents

- [Dev Setup](#dev-setup)
- [Code Style](#code-style)
- [Adding New Providers](#adding-new-providers)
- [Adding New Commands](#adding-new-commands)
- [Plugin Development](#plugin-development)
- [Testing](#testing)
- [PR Template](#pr-template)
- [Issue Templates](#issue-templates)

## Dev Setup

### Prerequisites

- Python 3.8+
- pip

### Clone & Install

```bash
git clone https://github.com/rudra496/termmind.git
cd termmind

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or just the basics
pip install -e .
```

### Verify Installation

```bash
python -m termmind.cli --version
python -m termmind.cli doctors
```

### Project Structure

```
termmind/
├── termmind/
│   ├── __init__.py          # Version and metadata
│   ├── cli.py               # CLI entry point (click commands)
│   ├── api.py               # API client (HTTP, streaming)
│   ├── config.py            # Configuration management
│   ├── context.py           # Smart context builder
│   ├── commands.py          # Slash command handlers
│   ├── file_ops.py          # File read/write/search/undo
│   ├── git.py               # Git integration
│   ├── providers.py         # Provider protocol implementations
│   ├── plugins.py           # Plugin system
│   ├── sessions.py          # Session save/load
│   ├── themes.py            # Color themes
│   ├── diff_engine.py       # Smart diff preview system
│   ├── memory.py            # Code context memory/index
│   ├── shell.py             # Shell integration & completions
│   └── utils.py             # Utilities
├── tests/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── CONTRIBUTING.md
└── README.md
```

## Code Style

### Type Hints

All public functions **must** have type hints:

```python
def calculate_cost(tokens: int, provider: str) -> float:
    ...
```

### Docstrings

Use Google-style docstrings for all public modules, classes, and functions:

```python
def search_files(query: str, directory: str = ".", max_results: int = 50) -> List[Dict[str, str]]:
    """Search for a query string across project files.

    Args:
        query: The text to search for.
        directory: Root directory to search in.
        max_results: Maximum number of results to return.

    Returns:
        A list of dicts with 'path', 'line', and 'text' keys.

    Raises:
        ValueError: If query is empty.
    """
```

### Formatting

- **Max line length:** 100 characters
- **Indentation:** 4 spaces (no tabs)
- **Imports:** Grouped — stdlib, third-party, local — with blank lines between
- **String quotes:** Double quotes for strings, single quotes inside
- **Trailing whitespace:** None
- **Trailing commas:** Yes in collections spanning multiple lines

### Naming

- `snake_case` for functions, methods, variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- `_leading_underscore` for private/internal

## Adding New Providers

Follow these steps to add a new AI provider:

### 1. Add Provider Preset

In `config.py`, add to `PROVIDER_PRESETS`:

```python
"my_provider": {
    "base_url": "https://api.myprovider.com/v1",
    "models": ["model-a", "model-b"],
    "default_model": "model-a",
    "cost_per_1k_input": 0.001,
    "cost_per_1k_output": 0.002,
    "requires_key": True,
},
```

### 2. Implement Provider Class

In `providers.py`, create a provider class:

```python
class MyProvider(BaseProvider):
    """My Provider implementation."""

    def __init__(self, api_key: str = "", base_url: str = "", **kwargs):
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)
        self.headers["Authorization"] = f"Bearer {api_key}"

    def _make_request(self, payload: dict) -> dict:
        # Implement HTTP request following OpenAI-compatible format
        response = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
```

### 3. Register Provider

Add to `get_provider()` in `providers.py`:

```python
elif name == "my_provider":
    return MyProvider(api_key=api_key, base_url=base_url, **kwargs)
```

### 4. Test

```bash
TERMIND_TEST_PROVIDER=my_provider python -m pytest tests/test_providers.py -v
```

## Adding New Commands

### CLI Commands (subcommands like `termmind review`)

Add a new `@main.command()` in `cli.py`:

```python
@main.command()
@click.argument("filepath")
@click.option("--verbose", "-v", is_flag=True)
def mycommand(filepath: str, verbose: bool):
    """Brief description of what it does."""
    cfg = load_config()
    console = _get_console()
    # ... implementation ...
```

### Slash Commands (in-chat commands like `/diff`)

1. Define the handler function in `commands.py`:

```python
def cmd_mycommand(rest: str, messages, client, console, cwd, ctx_files):
    """Handle the /mycommand slash command."""
    console.print(f"[info]My command: {rest}[/info]")
```

2. Register in the `handlers` dict in `handle_command()`:

```python
handlers: Dict[str, Callable] = {
    # ... existing ...
    "mycommand": cmd_mycommand,
}
```

3. Add to `SLASH_COMMANDS` list in `cli.py` for tab completion.

4. Add to `cmd_help` table.

## Plugin Development

TermMind has a plugin system with lifecycle hooks.

### Plugin Interface

```python
class MyPlugin:
    """A TermMind plugin."""

    name = "my_plugin"

    def on_start(self, context: dict) -> None:
        """Called when TermMind starts."""
        pass

    def on_message(self, message: str, role: str) -> None:
        """Called for each message sent/received."""
        pass

    def on_response(self, response: str) -> None:
        """Called when AI responds."""
        pass

    def on_exit(self) -> None:
        """Called when TermMind exits."""
        pass
```

### Plugin Discovery

Plugins are discovered from:
1. `~/.termmind/plugins/` directory
2. Entry point: `termmind.plugins` in installed packages

### Plugin Context

The `on_start` method receives a dict with:
- `messages`: The conversation message list
- `client`: The APIClient instance
- `console`: The Rich Console instance
- `cwd`: Current working directory

## Testing

### Running Tests

```bash
# All tests
python -m pytest

# With verbose output
python -m pytest -v

# Specific test file
python -m pytest tests/test_context.py -v

# With coverage
python -m pytest --cov=termmind --cov-report=term-missing
```

### Writing Tests

Use pytest. Place tests in `tests/`:

```python
import pytest
from termmind.context import extract_relevant_files, estimate_tokens


class TestContextBuilding:
    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0

    def test_estimate_tokens_text(self):
        # ~4 chars per token
        assert estimate_tokens("hello world") == 3

    def test_extract_files_basic(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        files = extract_relevant_files("main.py", str(tmp_path))
        assert len(files) >= 1

    def test_extract_files_with_cache(self, tmp_path):
        """Test that caching works correctly."""
        (tmp_path / "test.py").write_text("x = 1")
        files1 = extract_relevant_files("test.py", str(tmp_path))
        files2 = extract_relevant_files("test.py", str(tmp_path))
        assert files1 == files2
```

### Mocking API Calls

```python
from unittest.mock import patch, MagicMock

def test_stream_response(capsys):
    with patch("termmind.cli.APIClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat_stream.return_value = iter(["Hello", " world"])
        mock_instance.total_tokens.return_value = 5
        # ... run your test ...
```

## PR Template

When submitting a PR, use this checklist:

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactor

## Testing
- [ ] Tests pass locally (`python -m pytest`)
- [ ] New tests added for new functionality
- [ ] Tested with at least 2 providers

## Checklist
- [ ] Code follows style guidelines
- [ ] Type hints on all public functions
- [ ] Docstrings on new/modified functions
- [ ] No breaking changes (or documented)
- [ ] `CONTRIBUTING.md` updated if needed
```

## Issue Templates

### Bug Report

```markdown
**Bug description:** Clear description of the bug.

**To reproduce:**
1. Step 1
2. Step 2

**Expected behavior:** What should happen.

**Actual behavior:** What happens instead.

**Environment:**
- OS:
- Python version:
- TermMind version:
- Provider:
- Model:
```

### Feature Request

```markdown
**Feature:** One-line description.

**Problem:** What problem does this solve?

**Proposed solution:** How should it work?

**Alternatives considered:** Any other approaches?
```
