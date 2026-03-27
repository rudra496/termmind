"""Snippet Manager — save, search, and reuse code snippets from conversations."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import CONFIG_DIR

SNIPPETS_DIR = CONFIG_DIR / "snippets"

# Template variables that get expanded when loading snippets
TEMPLATE_VARS = {
    "{{filename}}": lambda ctx: ctx.get("filename", "untitled"),
    "{{datetime}}": lambda ctx: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "{{date}}": lambda ctx: datetime.now().strftime("%Y-%m-%d"),
    "{{time}}": lambda ctx: datetime.now().strftime("%H:%M:%S"),
    "{{user}}": lambda ctx: os.environ.get("USER", os.environ.get("USERNAME", "user")),
    "{{cwd}}": lambda ctx: os.getcwd(),
    "{{project}}": lambda ctx: os.path.basename(os.getcwd()),
    "{{year}}": lambda ctx: str(datetime.now().year),
    "{{month}}": lambda ctx: datetime.now().strftime("%m"),
    "{{day}}": lambda ctx: datetime.now().strftime("%d"),
}


def _ensure_snippets_dir() -> Path:
    """Create snippets directory."""
    SNIPPETS_DIR.mkdir(parents=True, exist_ok=True)
    return SNIPPETS_DIR


def _snippet_path(name: str) -> Path:
    """Get the file path for a snippet."""
    safe_name = re.sub(r'[^\w\-.]', '_', name)
    return _ensure_snippets_dir() / f"{safe_name}.json"


def _list_snippet_files() -> List[Path]:
    """List all snippet JSON files."""
    _ensure_snippets_dir()
    return sorted(SNIPPETS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def save_snippet(
    name: str,
    description: str = "",
    language: str = "",
    code: str = "",
    tags: Optional[List[str]] = None,
    conversation_context: str = "",
) -> Dict[str, Any]:
    """Save a new snippet. If one with the same name exists, update it."""
    path = _snippet_path(name)
    existing = None
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    snippet = {
        "name": name,
        "description": description or (existing or {}).get("description", ""),
        "language": language or (existing or {}).get("language", _detect_language(code or conversation_context)),
        "code": code or (existing or {}).get("code", ""),
        "tags": tags or (existing or {}).get("tags", []),
        "created_date": (existing or {}).get("created_date", datetime.now().isoformat()),
        "modified_date": datetime.now().isoformat(),
        "usage_count": (existing or {}).get("usage_count", 0),
        "conversation_context": conversation_context[:2000] if conversation_context else (existing or {}).get("conversation_context", ""),
    }

    path.write_text(json.dumps(snippet, indent=2))
    return snippet


def load_snippet(name: str, expand_templates: bool = True, ctx: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Load a snippet by name."""
    path = _snippet_path(name)
    if not path.exists():
        return None
    try:
        snippet = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Expand template variables
    if expand_templates and snippet.get("code"):
        context = ctx or {}
        for var, resolver in TEMPLATE_VARS.items():
            try:
                snippet["code"] = snippet["code"].replace(var, resolver(context))
            except Exception:
                pass

    # Increment usage count
    snippet["usage_count"] = snippet.get("usage_count", 0) + 1
    path.write_text(json.dumps(snippet, indent=2))
    return snippet


def delete_snippet(name: str) -> bool:
    """Delete a snippet by name."""
    path = _snippet_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def list_snippets(tag: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List all snippets, optionally filtered by tag."""
    results = []
    for path in _list_snippet_files():
        try:
            snippet = json.loads(path.read_text())
            if tag and tag not in snippet.get("tags", []):
                continue
            results.append(snippet)
            if len(results) >= limit:
                break
        except (json.JSONDecodeError, OSError):
            continue
    return results


def search_snippets(query: str) -> List[Dict[str, Any]]:
    """Search snippets by name, description, tags, or code content."""
    query_lower = query.lower()
    results = []
    for path in _list_snippet_files():
        try:
            snippet = json.loads(path.read_text())
            searchable = " ".join([
                snippet.get("name", ""),
                snippet.get("description", ""),
                snippet.get("language", ""),
                " ".join(snippet.get("tags", [])),
                snippet.get("code", "")[:500],
            ]).lower()
            if query_lower in searchable:
                # Score based on match location
                score = 0
                if query_lower in snippet.get("name", "").lower():
                    score += 10
                if query_lower in snippet.get("description", "").lower():
                    score += 5
                if query_lower in " ".join(snippet.get("tags", [])).lower():
                    score += 7
                snippet["_score"] = score
                results.append(snippet)
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda s: s.get("_score", 0), reverse=True)
    return results


def export_snippets(filepath: str) -> int:
    """Export all snippets to a JSON file. Returns count."""
    snippets = []
    for path in _list_snippet_files():
        try:
            snippets.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue

    output = Path(filepath)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snippets, indent=2))
    return len(snippets)


def import_snippets(filepath: str, overwrite: bool = False) -> Tuple[int, int]:
    """Import snippets from a JSON file. Returns (imported, skipped)."""
    path = Path(filepath)
    if not path.exists():
        return 0, 0
    try:
        snippets = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0, 0

    imported = 0
    skipped = 0
    for snippet in snippets:
        if not isinstance(snippet, dict) or "name" not in snippet:
            skipped += 1
            continue
        dest = _snippet_path(snippet["name"])
        if dest.exists() and not overwrite:
            skipped += 1
            continue
        save_snippet(
            name=snippet["name"],
            description=snippet.get("description", ""),
            language=snippet.get("language", ""),
            code=snippet.get("code", ""),
            tags=snippet.get("tags", []),
        )
        imported += 1
    return imported, skipped


def suggest_snippets(conversation: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Auto-suggest relevant snippets based on conversation context."""
    if not conversation.strip():
        return []

    # Extract keywords from conversation
    words = re.findall(r'\b\w{3,}\b', conversation.lower())
    # Remove common stop words
    stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
                  "her", "was", "one", "our", "out", "has", "have", "this", "that",
                  "with", "from", "they", "been", "will", "each", "make", "like",
                  "just", "over", "such", "take", "than", "them", "very", "some"}
    keywords = [w for w in words if w not in stop_words]

    if not keywords:
        return []

    # Score snippets by keyword overlap
    scored = []
    for path in _list_snippet_files():
        try:
            snippet = json.loads(path.read_text())
            searchable = " ".join([
                snippet.get("name", ""),
                snippet.get("description", ""),
                snippet.get("language", ""),
                " ".join(snippet.get("tags", [])),
                snippet.get("code", "")[:1000],
            ]).lower()
            searchable_words = set(re.findall(r'\b\w{3,}\b', searchable))
            overlap = len(set(keywords) & searchable_words)
            if overlap > 0:
                snippet["_score"] = overlap
                scored.append(snippet)
        except (json.JSONDecodeError, OSError):
            continue

    scored.sort(key=lambda s: s.get("_score", 0), reverse=True)
    return scored[:limit]


def _detect_language(text: str) -> str:
    """Guess the programming language from text content."""
    if not text:
        return "text"
    text_lower = text.lower()
    indicators = [
        ("python", ["def ", "import ", "from ", "class ", "print(", "self.", "# ", "pip install", "pyproject.toml"]),
        ("javascript", ["const ", "let ", "function ", "=>", "console.log", "require(", "module.exports"]),
        ("typescript", ["interface ", ": string", ": number", "as ", "<T>", "npm install", "tsconfig"]),
        ("rust", ["fn ", "let mut", "impl ", "pub fn", "use std", "cargo "]),
        ("go", ["func ", "package ", "import (", "fmt.Println", "go func", "go mod"]),
        ("java", ["public class", "System.out", "private ", "protected ", "import java"]),
        ("html", ["<html", "<div", "<body", "<head", "<!DOCTYPE"]),
        ("css", ["{", "margin:", "padding:", "display:", "@media", ":root"]),
        ("bash", ["#!/bin/bash", "#!/bin/sh", "echo ", "export ", "sudo ", "apt-get"]),
        ("sql", ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE", "ALTER TABLE"]),
        ("json", ["{", ":", "[", "true", "false", "null"]),
        ("yaml", ["---", "key:", "- ", "true", "false"]),
        ("dockerfile", ["FROM ", "RUN ", "COPY ", "CMD ", "ENTRYPOINT", "WORKDIR"]),
        ("markdown", ["# ", "## ", "- ", "```", "**", "__"]),
    ]
    for lang, markers in indicators:
        count = sum(1 for m in markers if m in text_lower)
        if count >= 2:
            return lang
    return "text"


# ── Slash command handlers ─────────────────────────────────────────────


def cmd_snippet(rest: str, messages, client, console: Console, cwd: str, ctx_files):
    """Handle /snippet commands."""
    parts = rest.strip().split(maxsplit=2)
    sub = parts[0] if parts else ""
    arg1 = parts[1] if len(parts) > 1 else ""
    arg2 = parts[2] if len(parts) > 2 else ""

    handlers = {
        "save": _snippet_save,
        "list": _snippet_list,
        "load": _snippet_load,
        "search": _snippet_search,
        "delete": _snippet_delete,
        "export": _snippet_export,
        "import": _snippet_import,
        "suggest": _snippet_suggest,
    }

    handler = handlers.get(sub)
    if not handler:
        console.print("[error]Usage: /snippet <save|list|load|search|delete|export|import|suggest> [args][/error]")
        return
    handler(arg1, arg2, messages, client, console, cwd, ctx_files)


def _snippet_save(name: str, description: str, messages, client, console, cwd, ctx_files):
    """Save conversation context or last code block as a snippet."""
    if not name:
        console.print("[error]Usage: /snippet save <name> [description][/error]")
        return

    # Try to extract code blocks from recent messages
    code = ""
    language = ""
    conversation_context = ""

    for msg in reversed(messages[-10:]):
        content = msg.get("content", "")
        if "```" in content:
            # Extract last code block
            blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
            if blocks:
                last_block = blocks[-1]
                language = last_block[0] or _detect_language(last_block[1])
                code = last_block[1].strip()
                break

    if not code:
        # Use the last user message as conversation context
        for msg in reversed(messages[-5:]):
            if msg.get("role") == "user":
                conversation_context = msg.get("content", "")[:2000]
                break

    if not code and not conversation_context:
        console.print("[warning]No code or conversation context found to save.[/warning]")
        return

    snippet = save_snippet(
        name=name,
        description=description,
        language=language,
        code=code,
        conversation_context=conversation_context,
    )
    what = "code snippet" if code else "conversation context"
    console.print(f"[success]💾 Saved {what}: {name}[/success]")
    if snippet.get("tags"):
        console.print(f"[dim]Tags: {', '.join(snippet['tags'])}[/dim]")


def _snippet_list(rest: str, _arg2, messages, client, console, cwd, ctx_files):
    """List all saved snippets."""
    tag = rest.strip() or None
    snippets = list_snippets(tag=tag)

    if not snippets:
        console.print("[system]No snippets saved yet. Use /snippet save <name> to create one.[/system]")
        return

    table = Table(title="📦 Snippets", border_style="dim")
    table.add_column("Name", style="cyan", min_width=18)
    table.add_column("Lang", style="dim", width=8)
    table.add_column("Description", max_width=40)
    table.add_column("Tags", style="dim", max_width=20)
    table.add_column("Uses", justify="right", width=4)
    table.add_column("Modified", style="dim", width=16)

    for s in snippets:
        name = s.get("name", "?")
        lang = s.get("language", "")
        desc = s.get("description", "")[:40]
        tags = ", ".join(s.get("tags", [])[:3])
        uses = str(s.get("usage_count", 0))
        modified = s.get("modified_date", "")[:16]
        table.add_row(name, lang, desc, tags, uses, modified)

    console.print(table)
    if tag:
        console.print(f"[dim]Filtered by tag: {tag}[/dim]")


def _snippet_load(name: str, _arg2, messages, client, console, cwd, ctx_files):
    """Load a snippet into the conversation context."""
    if not name:
        console.print("[error]Usage: /snippet load <name>[/error]")
        return

    ctx = {"filename": "", "cwd": cwd}
    snippet = load_snippet(name, expand_templates=True, ctx=ctx)
    if not snippet:
        console.print(f"[error]Snippet not found: {name}[/error]")
        return

    # Add snippet content to conversation
    content_parts = []
    if snippet.get("code"):
        lang = snippet.get("language", "")
        content_parts.append(f"[Loaded snippet: {name}]\n```{lang}\n{snippet['code']}\n```")
    if snippet.get("conversation_context"):
        content_parts.append(f"[Context from snippet: {name}]\n{snippet['conversation_context']}")

    full_content = "\n\n".join(content_parts)
    messages.append({"role": "user", "content": full_content})
    messages.append({"role": "assistant", "content": f"Snippet '{name}' loaded into context. How can I help you with it?"})

    what = "code" if snippet.get("code") else "conversation context"
    console.print(f"[success]📂 Loaded {what} from snippet: {name}[/success]")
    if snippet.get("description"):
        console.print(f"[dim]{snippet['description']}[/dim]")


def _snippet_search(query: str, _arg2, messages, client, console, cwd, ctx_files):
    """Search snippets by name, description, or content."""
    if not query:
        console.print("[error]Usage: /snippet search <query>[/error]")
        return

    results = search_snippets(query)
    if not results:
        console.print(f"[system]No snippets matching: {query}[/system]")
        return

    console.print(f"[info]Found {len(results)} matching snippets:[/info]")
    for s in results:
        name = s.get("name", "?")
        desc = s.get("description", "") or "(no description)"
        lang = s.get("language", "")
        tags = ", ".join(s.get("tags", []))
        score = s.get("_score", 0)
        console.print(f"  [cyan]• {name}[/cyan] [{lang}] — {desc} [dim]({tags}) score={score}[/dim]")


def _snippet_delete(name: str, _arg2, messages, client, console, cwd, ctx_files):
    """Delete a snippet."""
    if not name:
        console.print("[error]Usage: /snippet delete <name>[/error]")
        return

    if delete_snippet(name):
        console.print(f"[success]🗑️ Deleted snippet: {name}[/success]")
    else:
        console.print(f"[error]Snippet not found: {name}[/error]")


def _snippet_export(arg1: str, _arg2, messages, client, console, cwd, ctx_files):
    """Export all snippets to JSON."""
    filepath = arg1.strip() or os.path.join(cwd, "termmind_snippets_export.json")
    count = export_snippets(filepath)
    if count == 0:
        console.print("[system]No snippets to export.[/system]")
        return
    console.print(f"[success]📤 Exported {count} snippets to: {filepath}[/success]")


def _snippet_import(filepath: str, _arg2, messages, client, console, cwd, ctx_files):
    """Import snippets from a JSON file."""
    if not filepath:
        console.print("[error]Usage: /snippet import <filepath>[/error]")
        return

    imported, skipped = import_snippets(filepath)
    console.print(f"[success]📥 Imported {imported} snippets, skipped {skipped}[/success]")
    if skipped > 0:
        console.print("[dim]Use /snippet import --force <file> to overwrite existing[/dim]")


def _snippet_suggest(_arg1, _arg2, messages, client, console, cwd, ctx_files):
    """Suggest relevant snippets based on current conversation."""
    # Build conversation text from recent messages
    conv_text = " ".join(m.get("content", "") for m in messages[-10:])
    suggestions = suggest_snippets(conv_text)

    if not suggestions:
        console.print("[system]No relevant snippets found for this conversation.[/system]")
        return

    console.print("[info]💡 Suggested snippets:[/info]")
    for s in suggestions:
        name = s.get("name", "?")
        desc = s.get("description", "") or "(no description)"
        score = s.get("_score", 0)
        console.print(f"  [cyan]• {name}[/cyan] — {desc} [dim](relevance: {score})[/dim]")
    console.print("[dim]Use /snippet load <name> to load a suggestion.[/dim]")
