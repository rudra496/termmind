"""Git operations."""

import subprocess
from typing import List, Optional, Tuple


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
    out, rc = _git(["status", "--short", "--branch"], cwd)
    return out if rc == 0 else "Not a git repository"


def git_diff(cwd: str = ".", staged: bool = False) -> str:
    args = ["diff"]
    if staged:
        args.append("--staged")
    out, rc = _git(args, cwd)
    return out if rc == 0 else ""


def git_commit(message: str, cwd: str = ".", add_all: bool = True) -> Tuple[str, int]:
    if add_all:
        _git(["add", "-A"], cwd)
    out, rc = _git(["commit", "-m", message], cwd)
    return (out, rc)


def git_log(n: int = 10, cwd: str = ".") -> str:
    out, rc = _git(
        ["log", f"--max-count={n}", "--pretty=format:%h %s (%cr) <%an>"],
        cwd,
    )
    return out if rc == 0 else ""


def git_branch(show_current: bool = False, cwd: str = ".") -> str:
    if show_current:
        out, rc = _git(["branch", "--show-current"], cwd)
    else:
        out, rc = _git(["branch"], cwd)
    return out if rc == 0 else ""


def git_is_repo(cwd: str = ".") -> bool:
    _, rc = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    return rc == 0
