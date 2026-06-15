"""Smart autocomplete and suggestions for TermMind commands and queries."""

import os
import re
from pathlib import Path

# Common coding patterns for intelligent suggestions
_CODE_PATTERNS: dict[str, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".jsx", ".mjs"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],
    "rust": [".rs"],
    "java": [".java"],
    "ruby": [".rb"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".hpp", ".cc"],
    "config": [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
    "docs": [".md", ".rst", ".txt"],
}


def suggest_files(query: str, directory: str = ".", max_results: int = 10) -> list[str]:
    """Suggest files based on partial query match."""
    query_lower = query.lower()
    results: list[tuple[float, str]] = []

    try:
        for root, dirs, files in os.walk(directory):
            # Skip hidden and common non-useful dirs
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d
                not in {
                    "node_modules",
                    "__pycache__",
                    ".git",
                    "venv",
                    ".venv",
                    "dist",
                    "build",
                }
            ]
            depth = root.replace(directory, "").count(os.sep)
            if depth > 5:
                dirs.clear()
                continue

            for fname in files:
                if fname.startswith("."):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, directory)
                score = _score_file_match(rel, query_lower)
                if score > 0:
                    results.append((score, rel))
    except OSError:
        return []

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:max_results]]


def _score_file_match(filepath: str, query: str) -> float:
    """Score how well a file matches a query."""
    score = 0.0
    fp_lower = filepath.lower()
    fname = Path(filepath).stem.lower()

    # Exact filename match
    if query == fname:
        score += 20.0
    # Filename starts with query
    elif fname.startswith(query):
        score += 10.0
    # Filename contains query
    elif query in fname:
        score += 5.0
    # Full path contains query
    elif query in fp_lower:
        score += 3.0

    # Extension match bonus
    ext = Path(filepath).suffix.lower()
    if query.lstrip(".") == ext.lstrip("."):
        score += 2.0

    # Prefer source files
    source_exts = {".py", ".js", ".ts", ".go", ".rs", ".java"}
    if ext in source_exts:
        score += 1.0

    return score


def suggest_commands(partial: str, available_commands: list[str]) -> list[str]:
    """Suggest commands based on partial input."""
    partial_lower = partial.lower()
    results: list[tuple[float, str]] = []

    for cmd in available_commands:
        cmd_lower = cmd.lower()
        if cmd_lower == partial_lower:
            results.append((20.0, cmd))
        elif cmd_lower.startswith(partial_lower):
            results.append((10.0, cmd))
        elif partial_lower in cmd_lower:
            results.append((5.0, cmd))
        else:
            # Fuzzy: check if all chars appear in order
            score = _fuzzy_score(partial_lower, cmd_lower)
            if score > 0:
                results.append((score, cmd))

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:10]]


def _fuzzy_score(query: str, target: str) -> float:
    """Calculate fuzzy match score."""
    if not query:
        return 0.0
    qi = 0
    score = 0.0
    for char in target:
        if qi < len(query) and char == query[qi]:
            score += 1.0
            qi += 1
    if qi < len(query):
        return 0.0
    return score / len(target)


def suggest_context_actions(message: str) -> list[dict[str, str]]:
    """Suggest contextual actions based on user message content."""
    suggestions: list[dict[str, str]] = []
    msg_lower = message.lower()

    # File-related suggestions
    file_mentions = re.findall(
        r"""[\w./\-]+\.(?:py|js|ts|go|rs|java|rb|c|cpp|json|yaml|yml|toml|md)""",
        message,
        re.IGNORECASE,
    )

    if any(kw in msg_lower for kw in ["review", "check", "audit", "analyze"]) and file_mentions:
        suggestions.append(
            {
                "action": "/review",
                "args": file_mentions[0],
                "description": f"Review {file_mentions[0]}",
            }
        )

    if (
        any(kw in msg_lower for kw in ["test", "tests", "testing", "unittest", "pytest"])
        and file_mentions
    ):
        suggestions.append(
            {
                "action": "/test",
                "args": file_mentions[0],
                "description": f"Generate tests for {file_mentions[0]}",
            }
        )

    if (
        any(kw in msg_lower for kw in ["explain", "what does", "how does", "understand"])
        and file_mentions
    ):
        suggestions.append(
            {
                "action": "/explain",
                "args": file_mentions[0],
                "description": f"Explain {file_mentions[0]}",
            }
        )

    if (
        any(kw in msg_lower for kw in ["edit", "modify", "change", "update", "fix", "refactor"])
        and file_mentions
    ):
        suggestions.append(
            {
                "action": "/edit",
                "args": f"{file_mentions[0]} {message}",
                "description": f"Edit {file_mentions[0]}",
            }
        )

    if (
        any(kw in msg_lower for kw in ["debug", "error", "bug", "broken", "failing"])
        and file_mentions
    ):
        suggestions.append(
            {
                "action": "/debug",
                "args": file_mentions[0],
                "description": f"Debug {file_mentions[0]}",
            }
        )

    if any(kw in msg_lower for kw in ["security", "vuln", "vulnerability", "insecure"]):
        suggestions.append(
            {
                "action": "/scan",
                "args": file_mentions[0] if file_mentions else ".",
                "description": "Run security scan",
            }
        )

    if any(kw in msg_lower for kw in ["generate", "create", "scaffold", "make", "build"]):
        if any(kw in msg_lower for kw in ["api", "endpoint", "route"]):
            suggestions.append(
                {
                    "action": "generate",
                    "args": "api",
                    "description": "Generate API code",
                }
            )
        elif any(kw in msg_lower for kw in ["class", "model", "schema"]):
            suggestions.append(
                {
                    "action": "generate",
                    "args": "class",
                    "description": "Generate class code",
                }
            )
        elif any(kw in msg_lower for kw in ["test", "spec"]):
            suggestions.append(
                {
                    "action": "generate",
                    "args": "test",
                    "description": "Generate test code",
                }
            )

    if any(kw in msg_lower for kw in ["git", "commit", "branch", "merge", "push"]):
        suggestions.append(
            {
                "action": "/git status",
                "args": "",
                "description": "Check git status",
            }
        )

    if any(kw in msg_lower for kw in ["cost", "price", "usage", "tokens", "budget"]):
        suggestions.append(
            {
                "action": "/cost",
                "args": "",
                "description": "Show cost analysis",
            }
        )

    return suggestions


def get_smart_completions(partial_input: str, cwd: str = ".") -> list[str]:
    """Get smart completions for partial input."""
    completions: list[str] = []

    # If starts with /, suggest commands
    if partial_input.startswith("/"):
        from .cli import SLASH_COMMANDS

        cmd_part = partial_input[1:]
        completions.extend(suggest_commands("/" + cmd_part, SLASH_COMMANDS))
        return completions

    # Otherwise, suggest files
    completions.extend(suggest_files(partial_input, cwd))

    return completions
