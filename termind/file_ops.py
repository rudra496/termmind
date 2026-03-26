"""File operations: read, write, edit, search."""

import difflib
import fnmatch
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Global edit history for undo support
_edit_history: List[Tuple[str, str, str]] = []  # (filepath, old_content, timestamp)


def read_file(path: str, max_chars: int = 100_000) -> Optional[str]:
    """Read file content, respecting size limits."""
    p = Path(path)
    if not p.exists():
        return None
    if p.stat().st_size > max_chars:
        return p.read_text(errors="replace")[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"
    return p.read_text(errors="replace")


def write_file(path: str, content: str) -> None:
    """Write content to a file, creating parent dirs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_text(errors="replace") if p.exists() else ""
    p.write_text(content)
    _edit_history.append((str(p.resolve()), old, __import__("time").ctime()))


def edit_file(path: str, old_text: str, new_text: str) -> bool:
    """Replace exact text in a file. Returns True on success."""
    content = read_file(path)
    if content is None:
        return False
    if old_text not in content:
        return False
    original = content
    content = content.replace(old_text, new_text, 1)
    write_file(path, content)
    _edit_history[-1] = (_edit_history[-1][0], original, _edit_history[-1][2])  # fix old_content
    return True


def apply_diff(path: str, diff_text: str) -> bool:
    """Apply a unified diff to a file."""
    content = read_file(path)
    if content is None:
        return False
    lines = content.splitlines(keepends=True)
    try:
        patch = difflib.unified_diff(lines, lines, fromfile="a", tofile="b")
        # Parse the diff manually for simplicity
        new_lines = _apply_unified_diff(lines, diff_text)
        if new_lines is not None:
            original = content
            write_file(path, "".join(new_lines))
            _edit_history[-1] = (_edit_history[-1][0], original, _edit_history[-1][2])
            return True
    except Exception:
        pass
    return False


def _apply_unified_diff(original: List[str], diff_text: str) -> Optional[List[str]]:
    """Simple unified diff applier."""
    diff_lines = diff_text.splitlines(keepends=True)
    result = list(original)
    offset = 0
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i].rstrip("\n")
        if line.startswith("@@"):
            # Parse hunk header
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not match:
                i += 1
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2) or 1)
            new_count = int(match.group(4) or 1)
            # Skip to changes
            i += 1
            removals = []
            additions = []
            while i < len(diff_lines):
                dl = diff_lines[i]
                if dl.startswith("@@") or (dl.startswith("---") or dl.startswith("+++")):
                    break
                stripped = dl.rstrip("\n")
                if stripped.startswith("+"):
                    additions.append(stripped[1:] + "\n")
                    i += 1
                elif stripped.startswith("-"):
                    removals.append(stripped[1:] + "\n")
                    i += 1
                elif stripped.startswith(" "):
                    i += 1
                elif stripped == "":
                    i += 1
                else:
                    break
            idx = old_start - 1 + offset
            # Remove old lines
            if removals:
                end = idx + len(removals)
                removed = result[idx:end]
                result[idx:end] = []
            result[idx:idx] = additions
            offset += len(additions) - len(removals)
        else:
            i += 1
    return result


def find_files(
    directory: str = ".",
    pattern: str = "*",
    ignore_patterns: Optional[List[str]] = None,
    max_depth: int = 10,
) -> List[str]:
    """Find files matching pattern, respecting ignore lists."""
    d = Path(directory)
    if not d.exists():
        return []
    ignores = _load_ignores(directory) | set(ignore_patterns or [])
    results = []
    for root, dirs, files in os.walk(d):
        depth = str(Path(root)).count(os.sep) - str(d).count(os.sep)
        if depth > max_depth:
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if not _is_ignored(d, ignores)]
        for f in files:
            rel = str(Path(root) / f)
            if fnmatch.fnmatch(f, pattern) and not _is_ignored(rel, ignores):
                results.append(rel)
    return sorted(results)


def search_in_files(query: str, directory: str = ".") -> List[Tuple[str, int, str]]:
    """Search for text in files. Returns (path, line_no, line)."""
    results = []
    for path in find_files(directory):
        try:
            lines = Path(path).read_text(errors="replace").splitlines()
            for i, line in enumerate(lines, 1):
                if query.lower() in line.lower():
                    results.append((path, i, line.strip()))
        except OSError:
            continue
        if len(results) > 50:
            break
    return results


def get_undo_history() -> List[Tuple[str, str, str]]:
    return list(_edit_history)


def undo_last_edit() -> Optional[str]:
    """Undo the last file edit. Returns filepath or None."""
    if not _edit_history:
        return None
    filepath, old_content, _ = _edit_history.pop()
    p = Path(filepath)
    if p.exists():
        p.write_text(old_content)
        return filepath
    return None


def get_session_diffs() -> List[Tuple[str, str]]:
    """Get all files changed this session with their diffs."""
    diffs = []
    seen = set()
    for filepath, old_content, _ in reversed(_edit_history):
        if filepath in seen:
            continue
        seen.add(filepath)
        p = Path(filepath)
        if p.exists():
            new_content = p.read_text(errors="replace")
            if old_content != new_content:
                udiff = difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{Path(filepath).name}",
                    tofile=f"b/{Path(filepath).name}",
                )
                diffs.append((filepath, "".join(udiff)))
    return diffs


def build_file_tree(directory: str = ".", max_depth: int = 3) -> str:
    """Build a visual file tree string."""
    d = Path(directory)
    if not d.exists():
        return ""
    ignores = _load_ignores(directory)
    lines = [d.name + "/"]
    _walk_tree(d, lines, "", ignores, max_depth, 0)
    return "\n".join(lines)


def _walk_tree(
    path: Path, lines: List[str], prefix: str, ignores: set, max_depth: int, depth: int
) -> None:
    if depth >= max_depth:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return
    entries = [e for e in entries if not _is_ignored(e.name, ignores) and not e.name.startswith(".")]
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            _walk_tree(entry, lines, prefix + ("    " if is_last else "│   "), ignores, max_depth, depth + 1)
        else:
            lines.append(f"{prefix}{connector}{entry.name}")


def _load_ignores(directory: str) -> set:
    """Load ignore patterns from .termindignore and .gitignore."""
    patterns: set = set()
    for name in [".termindignore", ".gitignore"]:
        p = Path(directory) / name
        if p.exists():
            for line in p.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.add(line)
    patterns.update(["__pycache__", ".git", "node_modules", ".venv", "venv", ".tox"])
    return patterns


def _is_ignored(name: str, patterns: set) -> bool:
    """Check if a file/dir name matches any ignore pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith("/") and name.startswith(pattern.rstrip("/")):
            return True
    return False
