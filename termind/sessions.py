"""Session management for TermMind."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SESSIONS_DIR

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_session(
    name: str,
    messages: List[Dict[str, str]],
    provider: str = "",
    model: str = "",
    cost: float = 0.0,
    tokens: int = 0,
    context_files: Optional[List[str]] = None,
) -> Path:
    """Save a chat session to disk. Returns the session file path."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', name)
    session = {
        "name": safe_name,
        "provider": provider,
        "model": model,
        "messages": messages,
        "context_files": context_files or [],
        "cost": cost,
        "tokens": tokens,
        "saved_at": datetime.now().isoformat(),
        "message_count": len(messages),
    }
    path = SESSIONS_DIR / f"{safe_name}.json"
    with open(path, "w") as f:
        json.dump(session, f, indent=2)
    return path


def load_session(name: str) -> Optional[Dict[str, Any]]:
    """Load a session by name. Returns session dict or None."""
    safe_name = re.sub(r'[^\w\-]', '_', name)
    path = SESSIONS_DIR / f"{safe_name}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def list_sessions(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all saved sessions, optionally filtered by search term."""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            if search:
                search_lower = search.lower()
                haystack = f"{data.get('name', '')} {data.get('provider', '')} {data.get('model', '')}".lower()
                if search_lower not in haystack:
                    continue
            sessions.append({
                "name": data.get("name", path.stem),
                "provider": data.get("provider", "?"),
                "model": data.get("model", "?"),
                "messages": len(data.get("messages", [])),
                "cost": data.get("cost", 0.0),
                "tokens": data.get("tokens", 0),
                "saved_at": data.get("saved_at", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def delete_session(name: str) -> bool:
    """Delete a session. Returns True if deleted."""
    safe_name = re.sub(r'[^\w\-]', '_', name)
    path = SESSIONS_DIR / f"{safe_name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def export_session(name: str, format: str = "markdown") -> Optional[str]:
    """Export a session as markdown or JSON string."""
    session = load_session(name)
    if not session:
        return None

    if format == "json":
        return json.dumps(session, indent=2)

    # Markdown export
    lines = [
        f"# Session: {session.get('name', name)}",
        f"\n**Provider:** {session.get('provider', '?')} | **Model:** {session.get('model', '?')}",
        f"**Saved:** {session.get('saved_at', '?')} | **Cost:** ${session.get('cost', 0):.6f}",
        "\n---\n",
    ]
    for msg in session.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "system":
            lines.append(f"**System:** {content}\n")
        elif role == "user":
            lines.append(f"## You\n{content}\n")
        elif role == "assistant":
            lines.append(f"## TermMind\n{content}\n")
    return "\n".join(lines)
