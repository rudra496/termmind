"""Chat slash commands for interactive mode."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import CONFIG_DIR, SESSIONS_DIR, PROVIDER_PRESETS, load_config, save_config
from .file_ops import (
    edit_file, find_files, get_session_diffs, get_undo_history,
    read_file, search_in_files, undo_last_edit, write_file,
)
from .git import git_status, git_diff, git_is_repo, git_log, git_branch
from .utils import calculate_cost, estimate_tokens, render_markdown

if TYPE_CHECKING:
    from .api import APIClient


def handle_command(
    cmd: str,
    args: str,
    messages: List[Dict[str, str]],
    client: "APIClient",
    console: Console,
    cwd: str,
    context_files: List[str],
) -> bool:
    """Handle a slash command. Returns True if handled, False otherwise."""
    parts = args.strip().split(maxsplit=1)
    sub = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    handlers = {
        "help": cmd_help,
        "edit": cmd_edit,
        "run": cmd_run,
        "files": cmd_files,
        "add": cmd_add,
        "clear": cmd_clear,
        "save": cmd_save,
        "load": cmd_load,
        "model": cmd_model,
        "provider": cmd_provider,
        "cost": cmd_cost,
        "theme": cmd_theme,
        "undo": cmd_undo,
        "diff": cmd_diff,
        "status": cmd_status,
        "git": cmd_git,
        "search": cmd_search,
        "tree": cmd_tree,
    }
    handler = handlers.get(sub)
    if handler:
        handler(rest, messages, client, console, cwd, context_files)
        return True
    console.print(f"[error]Unknown command: /{sub}[/error]. Type [info]/help[/info] for commands.")
    return True


def cmd_help(rest: str, messages, client, console, cwd, ctx_files):
    table = Table(title="TermMind Commands", show_header=False, border_style="dim")
    table.add_column("Command", style="command")
    table.add_column("Description")
    commands = [
        ("/edit <file>", "Edit a file with AI"),
        ("/run <cmd>", "Run a shell command"),
        ("/files", "List files in context"),
        ("/add <file>", "Add file to context"),
        ("/search <query>", "Search in project files"),
        ("/tree", "Show project file tree"),
        ("/clear", "Clear conversation"),
        ("/save [name]", "Save session"),
        ("/load <name>", "Load session"),
        ("/model [model]", "Show/switch model"),
        ("/provider [name]", "Show/switch provider"),
        ("/cost", "Show token usage & cost"),
        ("/theme <dark|light>", "Change theme"),
        ("/undo", "Undo last file edit"),
        ("/diff", "Show session changes"),
        ("/status", "Git status + context info"),
        ("/git [status|log|diff]", "Git operations"),
        ("/help", "Show this help"),
    ]
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    console.print(table)


def cmd_edit(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /edit <file> <instruction>[/error]")
        return
    parts = rest.split(maxsplit=1)
    filepath = parts[0]
    instruction = parts[1] if len(parts) > 1 else "Improve this file"
    full_path = os.path.join(cwd, filepath)
    content = read_file(full_path)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    prompt = f"""I'll show you a file. Follow the instruction exactly.
File: {filepath}
```\n{content}\n```
Instruction: {instruction}

Apply the edit. If making changes, output ONLY the complete new file content inside a code block:
```REPLACE
<complete new file content>
```"""
    messages_copy = list(messages)
    messages_copy.append({"role": "user", "content": prompt})
    console.print("[system]🤖 Applying edit...[/system]")
    try:
        response_text = ""
        for chunk in client.chat_stream(messages_copy):
            response_text += chunk
            console.print(chunk, end="", highlight=False)
        console.print()
        # Try to extract and apply replacement
        import re
        match = re.search(r"```REPLACE\n(.*?)```", response_text, re.DOTALL)
        if match:
            new_content = match.group(1)
            write_file(full_path, new_content)
            console.print(f"[success]✅ File updated: {filepath}[/success]")
        else:
            console.print("[warning]⚠ No replacement block found. Edit not applied automatically.[/warning]")
    except Exception as e:
        console.print(f"[error]Edit failed: {e}[/error]")


def cmd_run(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /run <command>[/error]")
        return
    import subprocess
    console.print(f"[command]$ {rest}[/command]")
    try:
        result = subprocess.run(
            rest, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[error]{result.stderr}[/error]")
        if result.returncode != 0:
            console.print(f"[warning]Exit code: {result.returncode}[/warning]")
        # Add to context
        output = result.stdout + result.stderr
        if output.strip():
            messages.append({"role": "user", "content": f"[Ran: {rest}]\nOutput:\n{output[:2000]}"})
            messages.append({"role": "assistant", "content": f"Command completed with exit code {result.returncode}."})
    except subprocess.TimeoutExpired:
        console.print("[error]Command timed out (30s)[/error]")
    except Exception as e:
        console.print(f"[error]Failed: {e}[/error]")


def cmd_files(rest: str, messages, client, console, cwd, ctx_files):
    files = find_files(cwd, max_depth=5)
    if not files:
        console.print("[system]No files found.[/system]")
        return
    for f in files[:30]:
        rel = os.path.relpath(f, cwd)
        marker = " ★" if rel in ctx_files else ""
        console.print(f"  [file_path]{rel}[/file_path]{marker}")
    if len(files) > 30:
        console.print(f"  [dim]... and {len(files) - 30} more files[/dim]")


def cmd_add(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /add <file>[/error]")
        return
    ctx_files.append(rest)
    console.print(f"[success]✅ Added {rest} to context[/success]")


def cmd_clear(rest: str, messages, client, console, cwd, ctx_files):
    messages.clear()
    ctx_files.clear()
    console.print("[system]Conversation cleared.[/system]")


def cmd_save(rest: str, messages, client, console, cwd, ctx_files):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    name = rest or datetime.now().strftime("%Y-%m-%d_%H-%M")
    cfg = load_config()
    session = {
        "name": name,
        "provider": client.provider,
        "model": client.model,
        "messages": messages,
        "context_files": ctx_files,
        "saved_at": datetime.now().isoformat(),
    }
    path = SESSIONS_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(session, f, indent=2)
    console.print(f"[success]💾 Session saved: {name}[/success]")


def cmd_load(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        # List available sessions
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = sorted(SESSIONS_DIR.glob("*.json"))
        if not sessions:
            console.print("[system]No saved sessions.[/system]")
            return
        for s in sessions:
            console.print(f"  [file_path]{s.stem}[/file_path]")
        return
    path = SESSIONS_DIR / f"{rest}.json"
    if not path.exists():
        console.print(f"[error]Session not found: {rest}[/error]")
        return
    with open(path) as f:
        session = json.load(f)
    messages.clear()
    messages.extend(session.get("messages", []))
    ctx_files.clear()
    ctx_files.extend(session.get("context_files", []))
    console.print(f"[success]📂 Session loaded: {rest}[/success]")


def cmd_model(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print(f"[info]Current model: {client.model}[/info]")
        info = PROVIDER_PRESETS.get(client.provider, {})
        models = info.get("models", [])
        if models:
            console.print("[dim]Available models:[/dim]")
            for m in models:
                marker = " ← current" if m == client.model else ""
                console.print(f"  {m}{marker}")
        return
    client.model = rest
    cfg = load_config()
    cfg["model"] = rest
    save_config(cfg)
    console.print(f"[success]✅ Model switched to: {rest}[/success]")


def cmd_provider(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print(f"[info]Current provider: {client.provider}[/info]")
        console.print("[dim]Available providers:[/dim]")
        for name in PROVIDER_PRESETS:
            marker = " ← current" if name == client.provider else ""
            info = PROVIDER_PRESETS[name]
            console.print(f"  [command]{name}[/command] ({info['default_model']}){marker}")
        return
    if rest not in PROVIDER_PRESETS:
        console.print(f"[error]Unknown provider: {rest}[/error]")
        return
    client.provider = rest
    info = PROVIDER_PRESETS[rest]
    client.base_url = info["base_url"]
    if not client.model or client.model not in info.get("models", []):
        client.model = info["default_model"]
    cfg = load_config()
    cfg["provider"] = rest
    cfg["model"] = client.model
    save_config(cfg)
    console.print(f"[success]✅ Provider switched to: {rest} (model: {client.model})[/success]")


def cmd_cost(rest: str, messages, client, console, cwd, ctx_files):
    tokens = client.total_tokens()
    cost = client.get_cost()
    table = Table(title="Session Cost", border_style="dim")
    table.add_column("Metric", style="info")
    table.add_column("Value")
    table.add_row("Provider", client.provider)
    table.add_row("Model", client.model)
    table.add_row("Total tokens", f"{tokens:,}")
    table.add_row("Prompt tokens", f"{client.usage['prompt_tokens']:,}")
    table.add_row("Completion tokens", f"{client.usage['completion_tokens']:,}")
    table.add_row("Estimated cost", f"${cost:.6f}")
    table.add_row("Messages", str(len(messages) // 2))
    console.print(table)


def cmd_theme(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        cfg = load_config()
        console.print(f"[info]Current theme: {cfg.get('theme', 'dark')}[/info]")
        console.print("[dim]Available: dark, light[/dim]")
        return
    if rest not in ("dark", "light"):
        console.print("[error]Theme must be 'dark' or 'light'[/error]")
        return
    cfg = load_config()
    cfg["theme"] = rest
    save_config(cfg)
    console.print(f"[success]🎨 Theme changed to: {rest} (restart chat to apply)[/success]")


def cmd_undo(rest: str, messages, client, console, cwd, ctx_files):
    filepath = undo_last_edit()
    if filepath:
        console.print(f"[success]↩️ Undid edit to: {filepath}[/success]")
    else:
        console.print("[warning]Nothing to undo.[/warning]")


def cmd_diff(rest: str, messages, client, console, cwd, ctx_files):
    diffs = get_session_diffs()
    if not diffs:
        console.print("[system]No changes this session.[/system]")
        return
    for filepath, diff in diffs:
        console.print(f"[file_path]{filepath}[/file_path]")
        console.print(diff)
        console.print()


def cmd_status(rest: str, messages, client, console, cwd, ctx_files):
    # Git status
    if git_is_repo(cwd):
        console.print("[info]Git:[/info]")
        status = git_status(cwd)
        if status:
            for line in status.splitlines():
                console.print(f"  {line}")
    console.print(f"\n[info]Provider:[/info] {client.provider} / {client.model}")
    console.print(f"[info]Context files:[/info] {len(ctx_files)}")
    console.print(f"[info]Messages:[/info] {len(messages)}")
    console.print(f"[info]Tokens:[/info] {client.total_tokens():,}")


def cmd_git(rest: str, messages, client, console, cwd, ctx_files):
    if not git_is_repo(cwd):
        console.print("[error]Not a git repository.[/error]")
        return
    sub = rest.strip() or "status"
    if sub == "status":
        console.print(git_status(cwd) or "Clean")
    elif sub == "log":
        console.print(git_log(cwd) or "No commits")
    elif sub == "diff":
        d = git_diff(cwd)
        console.print(d if d else "No changes")
    elif sub == "branch":
        console.print(git_branch(cwd) or "No branches")
    else:
        console.print(f"[error]Unknown git subcommand: {sub}[/error]")


def cmd_search(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /search <query>[/error]")
        return
    results = search_in_files(rest, cwd)
    if not results:
        console.print(f"[system]No results for: {rest}[/system]")
        return
    console.print(f"[info]Found {len(results)} results:[/info]")
    for path, lineno, line in results[:20]:
        console.print(f"  [file_path]{path}:{lineno}[/file_path] {line[:100]}")
    if len(results) > 20:
        console.print(f"  [dim]... and {len(results) - 20} more[/dim]")


def cmd_tree(rest: str, messages, client, console, cwd, ctx_files):
    from .file_ops import build_file_tree
    tree = build_file_tree(cwd)
    if tree:
        console.print(tree)
    else:
        console.print("[system]Empty directory.[/system]")
