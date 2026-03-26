"""File operations: read, write, edit, search."""

import difflib
import fnmatch
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Global edit history for undo support
_edit_history: List[Tuple[str, str, str]] = []  # (filepath, old_content, timestamp)


def _detect_encoding(path: Path) -> str:
    """Detect file encoding by trying common encodings."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "ascii"):
        try:
            path.read_text(encoding=enc)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def read_file(path: str, max_chars: int = 100_000) -> Optional[str]:
    """Read file content with encoding detection, respecting size limits."""
    p = Path(path)
    if not p.exists():
        return None
    if not p.is_file():
        return None
    enc = _detect_encoding(p)
    if p.stat().st_size > max_chars:
        return p.read_text(encoding=enc, errors="replace")[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"
    return p.read_text(encoding=enc, errors="replace")


def write_file(path: str, content: str) -> None:
    """Write content to a file, creating parent dirs. Tracks for undo."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_text(errors="replace") if p.exists() else ""
    p.write_text(content, encoding="utf-8")
    _edit_history.append((str(p.resolve()), old, time.ctime()))


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
    _edit_history[-1] = (_edit_history[-1][0], original, _edit_history[-1][2])
    return True


def create_file(path: str, content: str = "") -> bool:
    """Create a new file. Returns False if it already exists."""
    p = Path(path)
    if p.exists():
        return False
    write_file(path, content)
    return True


def delete_file(path: str, confirm: bool = True) -> bool:
    """Delete a file. Returns True if deleted."""
    p = Path(path)
    if not p.exists():
        return False
    if confirm:
        # Caller should handle confirmation
        pass
    old = p.read_text(errors="replace") if p.is_file() else ""
    p.unlink()
    _edit_history.append((str(p.resolve()), old, f"deleted {time.ctime()}"))
    return True


def backup_file(path: str) -> Optional[str]:
    """Create a .bak backup. Returns backup path or None."""
    p = Path(path)
    if not p.exists():
        return None
    bak_path = str(p) + ".bak"
    shutil.copy2(str(p), bak_path)
    return bak_path


def get_file_info(path: str) -> Optional[Dict[str, object]]:
    """Get detailed file info: size, mtime, encoding, language, lines."""
    p = Path(path)
    if not p.exists():
        return None
    stat = p.stat()
    content = read_file(path)
    lines = content.count("\n") + 1 if content else 0
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby", ".c": "c", ".cpp": "cpp",
        ".h": "c", ".cs": "csharp", ".php": "php", ".sh": "bash", ".bash": "bash",
        ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".json": "json",
        ".md": "markdown", ".html": "html", ".css": "css", ".sql": "sql",
        ".swift": "swift", ".kt": "kotlin", ".scala": "scala", ".lua": "lua",
        ".r": "r", ".dart": "dart",
    }
    ext = p.suffix.lower()
    language = ext_map.get(ext)
    fn_lower = p.name.lower()
    if fn_lower in ("dockerfile",):
        language = "docker"
    elif fn_lower in ("makefile",):
        language = "makefile"
    return {
        "path": str(p),
        "name": p.name,
        "size": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "mtime": time.ctime(stat.st_mtime),
        "encoding": _detect_encoding(p),
        "language": language,
        "lines": lines,
    }


def _human_size(size: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def apply_diff(path: str, diff_text: str) -> bool:
    """Apply a unified diff to a file."""
    content = read_file(path)
    if content is None:
        return False
    lines = content.splitlines(keepends=True)
    try:
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
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not match:
                i += 1
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2) or 1)
            new_count = int(match.group(4) or 1)
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
            if removals:
                end = idx + len(removals)
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
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
    for path in find_files(directory):
        try:
            lines = Path(path).read_text(errors="replace").splitlines()
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    results.append((path, i, line.strip()))
        except OSError:
            continue
        if len(results) > 50:
            break
    return results


def grep_files(pattern: str, directory: str = ".", context_lines: int = 0) -> List[Dict[str, object]]:
    """Grep through project files with optional context. Returns list of match dicts."""
    results = []
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))
    for path in find_files(directory):
        try:
            lines = Path(path).read_text(errors="replace").splitlines()
            for i, line in enumerate(lines):
                if regex.search(line):
                    context_before = lines[max(0, i - context_lines):i] if context_lines else []
                    context_after = lines[i + 1:i + 1 + context_lines] if context_lines else []
                    results.append({
                        "path": path,
                        "line": i + 1,
                        "text": line.strip(),
                        "context_before": context_before,
                        "context_after": context_after,
                    })
        except OSError:
            continue
    return results[:100]


def get_undo_history() -> List[Tuple[str, str, str]]:
    """Return all edits in history."""
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


def undo_all_edits() -> int:
    """Undo all edits this session. Returns number of edits undone."""
    count = 0
    while _edit_history:
        filepath, old_content, _ = _edit_history.pop()
        p = Path(filepath)
        if p.exists():
            p.write_text(old_content)
        count += 1
    return count


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


def compute_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate unified diff between two strings."""
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    ))


def build_file_tree(directory: str = ".", max_depth: int = 3, show_sizes: bool = False) -> str:
    """Build a visual file tree string, optionally with file sizes."""
    d = Path(directory)
    if not d.exists():
        return ""
    ignores = _load_ignores(directory)
    lines = [d.name + "/"]
    _walk_tree(d, lines, "", ignores, max_depth, 0, show_sizes)
    return "\n".join(lines)


def _walk_tree(
    path: Path, lines: List[str], prefix: str, ignores: set, max_depth: int, depth: int, show_sizes: bool = False
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
            _walk_tree(entry, lines, prefix + ("    " if is_last else "│   "), ignores, max_depth, depth + 1, show_sizes)
        else:
            size_str = f" ({_human_size(entry.stat().st_size)})" if show_sizes else ""
            lines.append(f"{prefix}{connector}{entry.name}{size_str}")


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
    patterns.update(["__pycache__", ".git", "node_modules", ".venv", "venv", ".tox", ".egg-info"])
    return patterns


def _is_ignored(name: str, patterns: set) -> bool:
    """Check if a file/dir name matches any ignore pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith("/") and name.startswith(pattern.rstrip("/")):
            return True
    return False
