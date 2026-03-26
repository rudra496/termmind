"""Plugin system for TermMind."""

import importlib.util
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

PLUGIN_DIR = Path.home() / ".termind" / "plugins"


class BasePlugin(ABC):
    """Base class for TermMind plugins."""

    name: str = "unnamed"
    description: str = ""

    def on_start(self, session: "Session") -> None:
        """Called when a chat session starts."""
        pass

    def on_message(self, message: str, role: str = "user") -> None:
        """Called when a message is sent/received."""
        pass

    def on_response(self, response: str) -> None:
        """Called after AI responds."""
        pass

    def on_edit(self, filepath: str, old_content: str, new_content: str) -> None:
        """Called after a file edit."""
        pass

    def on_command(self, command: str, args: str) -> Optional[bool]:
        """Called when a slash command is invoked. Return True to indicate handled."""
        return None

    def on_exit(self) -> None:
        """Called when session ends."""
        pass


class TodoTrackerPlugin(BasePlugin):
    """Track TODO/FIXME/HACK comments in edited files."""

    name = "todo_tracker"
    description = "Extract and track TODO/FIXME/HACK from code"
    _pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)", re.IGNORECASE)
    _todo_items: List[Dict[str, str]] = []

    def on_edit(self, filepath: str, old_content: str, new_content: str) -> None:
        for line in new_content.splitlines():
            m = self._pattern.search(line)
            if m:
                self._todo_items.append({
                    "type": m.group(1).upper(),
                    "text": m.group(2).strip(),
                    "file": filepath,
                })

    def get_todos(self) -> List[Dict[str, str]]:
        return list(self._todo_items)


class CodeStatsPlugin(BasePlugin):
    """Show code statistics after file edits."""

    name = "code_stats"
    description = "Display code statistics after edits"
    _edit_log: List[Dict[str, Any]] = []

    def on_edit(self, filepath: str, old_content: str, new_content: str) -> None:
        old_lines = len(old_content.splitlines()) if old_content else 0
        new_lines = len(new_content.splitlines()) if new_content else 0
        self._edit_log.append({
            "file": filepath,
            "lines_added": max(0, new_lines - old_lines),
            "lines_removed": max(0, old_lines - new_lines),
        })

    def get_stats(self) -> Dict[str, Any]:
        total_added = sum(e["lines_added"] for e in self._edit_log)
        total_removed = sum(e["lines_removed"] for e in self._edit_log)
        files_edited = len(set(e["file"] for e in self._edit_log))
        return {
            "files_edited": files_edited,
            "total_lines_added": total_added,
            "total_lines_removed": total_removed,
            "total_edits": len(self._edit_log),
        }


class AutoCommitPlugin(BasePlugin):
    """Automatically commit after confirmed edits."""

    name = "auto_commit"
    description = "Auto-stage and commit after file edits"
    _pending_files: List[str] = []

    def on_edit(self, filepath: str, old_content: str, new_content: str) -> None:
        if old_content != new_content:
            self._pending_files.append(filepath)

    def commit_pending(self) -> Optional[str]:
        """Stage and commit pending files. Returns commit output or None."""
        if not self._pending_files:
            return None
        import subprocess
        files = list(set(self._pending_files))
        try:
            subprocess.run(["git", "add"] + files, capture_output=True, timeout=10)
            result = subprocess.run(
                ["git", "commit", "-m", f"Auto-commit: {', '.join(os.path.basename(f) for f in files)}"],
                capture_output=True, text=True, timeout=10,
            )
            self._pending_files.clear()
            return result.stdout.strip() or result.stderr.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._pending_files.clear()
            return None


# Built-in plugins
BUILTIN_PLUGINS: List[type] = [TodoTrackerPlugin, CodeStatsPlugin, AutoCommitPlugin]


def discover_plugins() -> List[BasePlugin]:
    """Discover and instantiate plugins from ~/.termind/plugins/ and built-ins."""
    plugins: List[BasePlugin] = []

    # Built-ins
    for cls in BUILTIN_PLUGINS:
        plugins.append(cls())

    # User plugins
    if PLUGIN_DIR.exists():
        for py_file in PLUGIN_DIR.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                            plugins.append(attr())
            except Exception:
                continue

    return plugins
