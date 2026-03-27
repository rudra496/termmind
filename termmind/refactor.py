"""Refactoring Engine — AI-powered code refactoring with undo support."""

import difflib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .config import CONFIG_DIR
from .file_ops import read_file, write_file

REFACTOR_HISTORY_DIR = CONFIG_DIR / "refactor_history"


def _ensure_history_dir() -> Path:
    REFACTOR_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return REFACTOR_HISTORY_DIR


def _save_refactor_record(
    filepath: str,
    operation: str,
    old_content: str,
    new_content: str,
) -> str:
    """Save a refactoring record for undo. Returns record ID."""
    _ensure_history_dir()
    record = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        "timestamp": datetime.now().isoformat(),
        "filepath": filepath,
        "operation": operation,
        "old_content": old_content,
        "new_content": new_content,
    }
    path = _ensure_history_dir() / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2))
    return record["id"]


def undo_last_refactor(console: Console) -> bool:
    """Undo the last refactoring operation."""
    _ensure_history_dir()
    records = sorted(REFACTOR_HISTORY_DIR.glob("*.json"), reverse=True)
    if not records:
        console.print("[system]No refactor history to undo.[/system]")
        return False

    try:
        record = json.loads(records[0].read_text())
    except (json.JSONDecodeError, OSError):
        return False

    filepath = record["filepath"]
    old_content = record["old_content"]
    current = read_file(filepath)
    if current is None:
        console.print(f"[error]Original file not found: {filepath}[/error]")
        return False

    # Only undo if the file content matches what we refactored to
    if current.strip() != record["new_content"].strip():
        console.print("[warning]File has been modified since refactoring. Skipping undo.[/warning]")
        return False

    write_file(filepath, old_content)
    records[0].unlink()
    console.print(f"[success]↩️ Undid refactoring: {record['operation']} on {filepath}[/success]")
    return True


def show_refactor_history(console: Console, limit: int = 10):
    """Show recent refactoring history."""
    _ensure_history_dir()
    records = sorted(REFACTOR_HISTORY_DIR.glob("*.json"), reverse=True)[:limit]

    if not records:
        console.print("[system]No refactoring history.[/system]")
        return

    table = Table(title="Refactoring History", border_style="dim")
    table.add_column("ID", style="dim", width=22)
    table.add_column("Operation", style="cyan")
    table.add_column("File", style="file_path")
    table.add_column("Time", style="dim", width=16)

    for path in records:
        try:
            record = json.loads(path.read_text())
            table.add_row(
                record["id"],
                record["operation"],
                os.path.basename(record["filepath"]),
                record["timestamp"][:16],
            )
        except Exception:
            continue

    console.print(table)


def _generate_diff(old: str, new: str, filepath: str) -> str:
    """Generate a unified diff between old and new content."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filepath}", tofile=f"b/{filepath}")
    return "".join(diff)


def _render_diff_to_console(diff_text: str, console: Console):
    """Render a diff string with colors to the console."""
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold cyan]{line}[/bold cyan]")
        elif line.startswith("@@"):
            console.print(f"[bold]{line}[/bold]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(f"[dim]{line}[/dim]")


def _confirm_refactoring(console: Console, diff_text: str, filepath: str) -> bool:
    """Show diff and ask user to confirm."""
    console.print(f"\n[bold]Proposed changes for: {filepath}[/bold]\n")
    _render_diff_to_console(diff_text, console)
    console.print()
    try:
        confirm = input("Apply this refactoring? [y/N] ").strip().lower()
        return confirm in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _ai_refactor_prompt(
    operation: str,
    code: str,
    filepath: str,
    instruction: str = "",
) -> str:
    """Build an AI prompt for a refactoring operation."""
    prompts = {
        "extract-function": f"""You are a refactoring assistant. Given the following code, extract a function from the code.

Instructions: {instruction or "Identify a suitable block of code to extract into a function. Choose a good name and parameters."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file. Use the same language as the input.
Do not add any explanation, only the code.""",

        "rename": f"""You are a refactoring assistant. Rename the identifier specified below across the entire file.

Instructions: {instruction or "Identify the most important variable, function, or class name that should be renamed for clarity."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file with all references updated.
Do not add any explanation, only the code.""",

        "inline": f"""You are a refactoring assistant. Inline the specified variable or function.

Instructions: {instruction or "Find a variable or small function that can be inlined (replaced with its value/body) for simplicity."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file.
Do not add any explanation, only the code.""",

        "extract-class": f"""You are a refactoring assistant. Extract related methods/variables into a class.

Instructions: {instruction or "Identify related functions and variables that should be grouped into a class."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file.
Do not add any explanation, only the code.""",

        "simplify": f"""You are a refactoring assistant. Simplify the code.

Instructions: {instruction or "Simplify complex expressions, reduce nesting, improve readability while preserving behavior."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file.
Do not add any explanation, only the code.""",

        "dead-code": f"""You are a refactoring assistant. Find and remove dead code.

Instructions: {instruction or "Identify unused imports, unreachable code, unused variables, and unused functions. Remove them."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file.
Do not add any explanation, only the code.""",

        "sort-imports": f"""You are a refactoring assistant. Sort and organize imports according to PEP 8.

Rules:
1. Standard library imports first
2. Third-party imports second
3. Local imports third
4. Each group separated by a blank line
5. Alphabetical within each group
6. Remove unused imports
7. Use absolute imports

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file.
Do not add any explanation, only the code.""",

        "add-types": f"""You are a refactoring assistant. Add type hints to all function signatures.

Instructions: {instruction or "Add proper type hints to all function parameters and return types. Use standard Python type hints."}

File: {filepath}
```python
{code}
```

Output the COMPLETE refactored file with type hints added.
Do not add any explanation, only the code.""",
    }
    return prompts.get(operation, prompts["simplify"])


def _apply_ai_refactoring(
    operation: str,
    filepath: str,
    messages: list,
    client,
    console: Console,
    cwd: str,
    instruction: str = "",
) -> bool:
    """Apply an AI-powered refactoring. Returns True if applied."""
    full_path = os.path.join(cwd, filepath) if not os.path.isabs(filepath) else filepath
    content = read_file(full_path)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return False

    prompt = _ai_refactor_prompt(operation, content, filepath, instruction)
    messages_copy = list(messages[-20:])  # Keep recent context
    messages_copy.append({"role": "user", "content": prompt})

    console.print(f"[system]🤖 Analyzing for: {operation}...[/system]")

    try:
        response_text = ""
        for chunk in client.chat_stream(messages_copy):
            response_text += chunk

        # Extract code from response
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        if not cleaned.strip():
            console.print("[warning]AI returned empty response.[/warning]")
            return False

        # Show diff and confirm
        diff_text = _generate_diff(content, cleaned, filepath)
        if not diff_text.strip():
            console.print("[system]No changes needed.[/system]")
            return False

        if _confirm_refactoring(console, diff_text, filepath):
            _save_refactor_record(full_path, operation, content, cleaned)
            write_file(full_path, cleaned)
            console.print(f"[success]✅ Refactoring applied: {operation} on {filepath}[/success]")
            return True
        else:
            console.print("[system]Refactoring cancelled.[/system]")
            return False

    except Exception as e:
        console.print(f"[error]Refactoring failed: {e}[/error]")
        return False


def _apply_regex_refactoring(
    operation: str,
    filepath: str,
    console: Console,
    cwd: str,
) -> bool:
    """Apply a regex-based refactoring (for sort-imports). Returns True if applied."""
    full_path = os.path.join(cwd, filepath) if not os.path.isabs(filepath) else filepath
    content = read_file(full_path)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return False

    if operation == "sort-imports":
        # Attempt local sort-imports without AI
        new_content = _sort_imports_local(content)
        if new_content == content:
            console.print("[system]Imports already sorted or no imports found.[/system]")
            return False

        diff_text = _generate_diff(content, new_content, filepath)
        if _confirm_refactoring(console, diff_text, filepath):
            _save_refactor_record(full_path, operation, content, new_content)
            write_file(full_path, new_content)
            console.print(f"[success]✅ Imports sorted in: {filepath}[/success]")
            return True
        return False

    return False


# Standard library modules for import sorting
STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asyncio", "atexit", "base64", "bdb",
    "binascii", "bisect", "builtins", "bz2", "calendar", "cgi", "cmath", "cmd",
    "code", "codecs", "collections", "colorsys", "concurrent", "configparser", "contextlib",
    "copy", "copyreg", "cProfile", "csv", "ctypes", "dataclasses", "datetime", "dbm",
    "decimal", "difflib", "dis", "doctest", "email", "enum", "errno", "faulthandler",
    "fcntl", "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "imaplib", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "keyword", "linecache", "locale", "logging", "lzma", "marshal",
    "math", "mimetypes", "mmap", "multiprocessing", "netrc", "numbers", "operator",
    "optparse", "os", "pathlib", "pdb", "pickle", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty",
    "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
    "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
    "tempfile", "termios", "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
    "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
}


def _sort_imports_local(content: str) -> str:
    """Sort imports locally without AI. Basic PEP 8 style."""
    lines = content.split("\n")
    import_block_start = None
    import_block_end = None
    from_imports = []
    bare_imports = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if import_block_start is None:
                import_block_start = i
            if stripped.startswith("from "):
                module = stripped.split()[1].split(".")[0]
                from_imports.append(stripped)
            else:
                module = stripped.split()[1].split(".")[0]
                bare_imports.append(stripped)
            import_block_end = i
        elif stripped == "" and import_block_start is not None:
            import_block_end = i
            break
        elif stripped and not stripped.startswith("#") and import_block_start is not None:
            break

    if not from_imports and not bare_imports:
        return content

    # Categorize imports
    stdlib = []
    third_party = []
    local = []

    for imp in from_imports + bare_imports:
        module = imp.split()[1].split(".")[0]
        if module in STDLIB_MODULES:
            stdlib.append(imp)
        elif module.startswith("."):
            local.append(imp)
        else:
            third_party.append(imp)

    # Sort each group alphabetically
    stdlib.sort(key=lambda x: x.lower())
    third_party.sort(key=lambda x: x.lower())
    local.sort(key=lambda x: x.lower())

    # Rebuild
    sorted_imports = []
    if stdlib:
        sorted_imports.extend(stdlib)
    if third_party and stdlib:
        sorted_imports.append("")
    if third_party:
        sorted_imports.extend(third_party)
    if local and (stdlib or third_party):
        sorted_imports.append("")
    if local:
        sorted_imports.extend(local)

    # Replace in original content
    new_lines = lines[:import_block_start] + sorted_imports + lines[import_block_end + 1:]
    return "\n".join(new_lines)


# ── Slash command handler ─────────────────────────────────────────────

VALID_OPERATIONS = [
    "extract-function", "rename", "inline", "extract-class",
    "simplify", "dead-code", "sort-imports", "add-types",
    "undo", "history", "list",
]


def cmd_refactor(rest: str, messages, client, console: Console, cwd: str, ctx_files):
    """Handle /refactor commands."""
    parts = rest.strip().split(maxsplit=2)
    operation = parts[0] if parts else ""
    filepath = parts[1] if len(parts) > 1 else ""
    instruction = parts[2] if len(parts) > 2 else ""

    if not operation:
        console.print(f"[error]Usage: /refactor <operation> <filepath> [instruction][/error]")
        console.print(f"[dim]Operations: {', '.join(VALID_OPERATIONS)}[/dim]")
        return

    if operation in ("undo",):
        undo_last_refactor(console)
        return

    if operation in ("history", "list"):
        show_refactor_history(console)
        return

    if operation not in VALID_OPERATIONS or not filepath:
        console.print(f"[error]Usage: /refactor <operation> <filepath> [instruction][/error]")
        console.print(f"[dim]Operations: {', '.join(VALID_OPERATIONS)}[/dim]")
        return

    # Try local refactoring first for simple operations
    if operation == "sort-imports":
        _apply_regex_refactoring(operation, filepath, console, cwd)
        return

    # AI-powered refactoring
    _apply_ai_refactoring(operation, filepath, messages, client, console, cwd, instruction)
