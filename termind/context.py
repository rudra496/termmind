"""Context management: smart file inclusion for AI context."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .file_ops import find_files, read_file, _is_ignored, _load_ignores

MAX_CONTEXT_CHARS = 60_000


def extract_relevant_files(query: str, directory: str = ".") -> List[str]:
    """Find files relevant to a query by keyword matching."""
    # Extract potential file references from query
    refs: Set[str] = set()
    # Explicit file mentions
    for match in re.finditer(r"""[\w./\-]+\.(?:py|js|ts|go|rs|java|rb|c|cpp|h|cs|php|sh|bash|yaml|yml|toml|json|md|txt|html|css|sql|r|swift|kt|scala|lua|vim|dockerfile|makefile)""", query, re.IGNORECASE):
        refs.add(match.group())
    # Also look for quoted filenames
    for match in re.finditer(r'["\']([\w./\-]+\.\w+)["\']', query):
        refs.add(match.group(1))
    results = []
    for ref in refs:
        p = Path(directory) / ref
        if p.exists():
            results.append(str(p))
    # If no explicit refs, look for keyword matches in filenames
    if not results:
        words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        words -= {"the", "and", "for", "that", "this", "with", "from", "file", "what", "how", "can"}
        all_files = find_files(directory, max_depth=5)
        for f in all_files:
            fname = Path(f).stem.lower()
            if any(w in fname for w in words):
                results.append(f)
    # Always include key project files
    for key in ["README.md", "package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "Makefile"]:
        p = Path(directory) / key
        if p.exists() and str(p) not in results:
            results.append(str(p))
    return results[:10]


def build_context(query: str, directory: str = ".", extra_files: Optional[List[str]] = None) -> str:
    """Build context string from relevant files and file tree."""
    parts: List[str] = []
    # File tree
    from .file_ops import build_file_tree
    tree = build_file_tree(directory, max_depth=4)
    if tree:
        parts.append(f"## Project Structure\n```\n{tree}\n```\n")
    # Gather files
    files = extract_relevant_files(query, directory)
    if extra_files:
        files = list(set(files + extra_files))
    total_chars = 0
    for fpath in files:
        content = read_file(fpath)
        if content is None:
            continue
        if total_chars + len(content) > MAX_CONTEXT_CHARS:
            # Truncate to fit
            remaining = MAX_CONTEXT_CHARS - total_chars
            if remaining < 500:
                break
            content = content[:remaining] + "\n[... truncated]"
        total_chars += len(content)
        rel = os.path.relpath(fpath, directory)
        parts.append(f"## File: {rel}\n```\n{content}\n```\n")
        if total_chars >= MAX_CONTEXT_CHARS:
            break
    return "\n".join(parts)


def get_files_in_context(directory: str = ".") -> List[str]:
    """List files that would be included in context."""
    return find_files(directory, max_depth=5)[:20]
