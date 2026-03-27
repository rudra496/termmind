"""Git operations."""

import subprocess
from typing import Dict, List, Optional, Tuple


def _git(args: List[str], cwd: str = ".") -> Tuple[str, int]:
    """Run a git command, return (output, return_code)."""
    try:
        r = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=30
        )
        return (r.stdout.strip(), r.returncode)
    except FileNotFoundError:
        return ("git not found", 1)
    except subprocess.TimeoutExpired:
        return ("git command timed out", 1)


def git_status(cwd: str = ".") -> str:
    """Get git status output."""
    out, rc = _git(["status", "--short", "--branch"], cwd)
    return out if rc == 0 else "Not a git repository"


def git_diff(cwd: str = ".", staged: bool = False, file: Optional[str] = None) -> str:
    """Get git diff output."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if file:
        args.append("--")
        args.append(file)
    out, rc = _git(args, cwd)
    return out if rc == 0 else ""


def git_commit(message: str, cwd: str = ".", add_all: bool = True) -> Tuple[str, int]:
    """Commit changes with optional add-all."""
    if add_all:
        _git(["add", "-A"], cwd)
    out, rc = _git(["commit", "-m", message], cwd)
    return (out, rc)


def git_log(n: int = 10, cwd: str = ".") -> str:
    """Get recent commit log."""
    out, rc = _git(
        ["log", f"--max-count={n}", "--pretty=format:%h %s (%cr) <%an>"],
        cwd,
    )
    return out if rc == 0 else ""


def git_branch(show_current: bool = False, cwd: str = ".") -> str:
    """List branches or show current branch."""
    if show_current:
        out, rc = _git(["branch", "--show-current"], cwd)
    else:
        out, rc = _git(["branch"], cwd)
    return out if rc == 0 else ""


def git_is_repo(cwd: str = ".") -> bool:
    """Check if current directory is a git repository."""
    _, rc = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    return rc == 0


def git_checkout(branch: str, cwd: str = ".") -> Tuple[str, int]:
    """Checkout a branch."""
    return _git(["checkout", branch], cwd)


def git_get_changed_files(cwd: str = ".") -> List[str]:
    """Get list of files changed from HEAD."""
    out, rc = _git(["diff", "--name-only", "HEAD"], cwd)
    if rc != 0 or not out:
        return []
    return [f for f in out.splitlines() if f.strip()]


def git_get_contributors(cwd: str = ".") -> List[Dict[str, str]]:
    """Get contributors with commit counts."""
    out, rc = _git(["shortlog", "-sn", "--all"], cwd)
    if rc != 0 or not out:
        return []
    contributors = []
    for line in out.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) == 2:
            contributors.append({"count": int(parts[0].strip()), "name": parts[1].strip()})
    return contributors


def git_get_remote_url(cwd: str = ".") -> str:
    """Get the remote URL."""
    out, rc = _git(["remote", "get-url", "origin"], cwd)
    return out if rc == 0 else ""


async def ai_commit_message(client_api: object, diff_text: str) -> str:
    """Generate a conventional commit message from diff using AI."""
    if not diff_text.strip():
        return "chore: empty commit"
    prompt = f"""Generate a concise conventional commit message for these changes.
Use one of: feat, fix, docs, style, refactor, test, chore, build, ci, perf.
Output ONLY the commit message, nothing else.

Diff:
```\n{diff_text[:5000]}\n```"""
    try:
        result = ""
        for chunk in client_api.chat_stream([{"role": "user", "content": prompt}]):
            result += chunk
        return result.strip().strip('"').strip("'") or "chore: update"
    except Exception:
        return "chore: update"
