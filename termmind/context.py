"""Context management: smart file inclusion for AI context."""

import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .file_ops import find_files, read_file, _is_ignored, _load_ignores, get_file_info

# Cache: path -> (content, mtime)
_context_cache: Dict[str, Tuple[str, float]] = {}
MAX_CONTEXT_CHARS = 60_000


def _read_cached(path: str) -> Optional[str]:
    """Read file with caching based on mtime."""
    p = Path(path)
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    if path in _context_cache:
        cached_content, cached_mtime = _context_cache[path]
        if cached_mtime == mtime:
            return cached_content
    content = read_file(path)
    if content is not None:
        _context_cache[path] = (content, mtime)
    return content


def clear_cache() -> None:
    """Clear the context file cache."""
    _context_cache.clear()


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~4 chars per token for English)."""
    if not text:
        return 0
    return len(text) // 4


def _extract_imports(content: str) -> Set[str]:
    """Extract import references from Python code."""
    imports: Set[str] = set()
    for m in re.finditer(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))", content, re.MULTILINE):
        module = m.group(1) or m.group(2) or ""
        for part in module.replace(" as ", ",").split(","):
            part = part.strip().split(".")[0].strip()
            if part and part not in ("*",):
                imports.add(part.lower())
    return imports


def _score_file(filepath: str, query: str, cwd: str) -> float:
    """Score a file's relevance to a query. Higher = more relevant."""
    score = 0.0
    rel_path = os.path.relpath(filepath, cwd)

    # Filename matching
    fname = Path(filepath).stem.lower()
    query_lower = query.lower()
    query_words = set(re.findall(r"\b\w{3,}\b", query_lower))

    # Direct filename mention in query
    if fname in query_lower:
        score += 10.0
    # File extension mention
    ext = Path(filepath).suffix.lower()
    if ext and ext.lstrip(".") in query_lower:
        score += 3.0

    # Keyword matching in filename
    for word in query_words:
        if word in fname:
            score += 2.0

    # Content keyword matching (quick scan)
    content = _read_cached(filepath)
    if content:
        content_lower = content.lower()
        for word in query_words:
            score += content_lower.count(word) * 0.1

        # Import graph proximity
        file_imports = _extract_imports(content)
        for word in query_words:
            if word in file_imports:
                score += 1.5

    # Bonus for common project files
    important_files = {
        "readme.md": 5.0, "pyproject.toml": 3.0, "setup.py": 3.0,
        "package.json": 3.0, "makefile": 3.0, "dockerfile": 3.0,
        ".env.example": 2.0, "config.py": 2.0, "config.ts": 2.0,
    }
    if rel_path.lower() in important_files:
        score += important_files[rel_path.lower()]

    # Prefer source files over config/data
    source_exts = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".c", ".cpp", ".swift"}
    if ext in source_exts:
        score += 1.0

    return score


def extract_relevant_files(query: str, directory: str = ".", max_files: int = 20) -> List[str]:
    """Find files relevant to a query, ranked by relevance score."""
    # Extract explicit file references
    refs: Set[str] = set()
    for match in re.finditer(
        r"""[\w./\-]+\.(?:py|js|ts|go|rs|java|rb|c|cpp|h|cs|php|sh|bash|yaml|yml|toml|json|md|txt|html|css|sql|r|swift|kt|scala|lua|vim)""",
        query, re.IGNORECASE
    ):
        refs.add(match.group())
    for match in re.finditer(r'["\']([\w./\-]+\.\w+)["\']', query):
        refs.add(match.group(1))

    # Resolve explicit references
    explicit_files = []
    for ref in refs:
        p = Path(directory) / ref
        if p.exists():
            explicit_files.append(str(p))

    # If explicit files found and query is short, prefer those
    all_files = find_files(directory, max_depth=6)

    # Score all files
    scored = []
    for f in all_files:
        score = _score_file(f, query, directory)
        if f in explicit_files:
            score += 20.0  # Big bonus for explicitly mentioned files
        if score > 0:
            scored.append((f, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Start with explicit files, then top scored
    result = []
    seen = set()
    for f in explicit_files:
        if f not in seen:
            result.append(f)
            seen.add(f)
    for f, _ in scored:
        if f not in seen:
            result.append(f)
            seen.add(f)
        if len(result) >= max_files:
            break

    return result


def build_context(
    query: str,
    directory: str = ".",
    extra_files: Optional[List[str]] = None,
    max_tokens: int = 80000,
) -> str:
    """Build context string from relevant files and file tree."""
    parts: List[str] = []

    # File tree
    from .file_ops import build_file_tree
    tree = build_file_tree(directory, max_depth=4)
    if tree:
        parts.append(f"## Project Structure\n```\n{tree}\n```\n")

    # Gather files
    max_chars = max_tokens * 4  # rough conversion
    files = extract_relevant_files(query, directory)
    if extra_files:
        existing = set(files)
        for ef in extra_files:
            if ef not in existing:
                files.append(ef)

    total_chars = 0
    # Keep under 80% of max_tokens worth of chars
    budget = int(max_chars * 0.8)

    for fpath in files:
        content = _read_cached(fpath)
        if content is None:
            continue
        file_chars = len(content)
        if total_chars + file_chars > budget:
            remaining = budget - total_chars
            if remaining < 500:
                break
            # Smart truncation: keep first and last portions
            content = _smart_truncate(content, remaining)
            file_chars = remaining
        total_chars += file_chars
        rel = os.path.relpath(fpath, directory)
        parts.append(f"## File: {rel}\n```\n{content}\n```\n")

    # Code index context (if available)
    try:
        from .memory import get_context_for_query
        index_ctx = get_context_for_query(directory, query)
        if index_ctx:
            parts.append(index_ctx + "\n")
    except Exception:
        pass

    return "\n".join(parts)


def _smart_truncate(content: str, max_chars: int) -> str:
    """Truncate keeping first and last portions of the file."""
    if len(content) <= max_chars:
        return content
    keep_each = max_chars // 2 - 100
    if keep_each < 200:
        return content[:max_chars] + "\n[... truncated]"
    head = content[:keep_each]
    tail = content[-keep_each:]
    line_count = content.count("\n")
    omitted = line_count - head.count("\n") - tail.count("\n")
    return f"{head}\n\n... ({omitted} lines omitted) ...\n\n{tail}"


def get_files_in_context(directory: str = ".") -> List[str]:
    """List files that would be included in context."""
    return find_files(directory, max_depth=5)[:20]
