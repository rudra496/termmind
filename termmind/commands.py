"""Chat slash commands for interactive mode."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import CONFIG_DIR, SESSIONS_DIR, PROVIDER_PRESETS, load_config, save_config
from .file_ops import (
    edit_file, find_files, get_session_diffs, get_undo_history,
    read_file, search_in_files, undo_last_edit, undo_all_edits,
    write_file, build_file_tree, grep_files,
)
from .git import (
    git_status, git_diff, git_is_repo, git_log, git_branch,
    git_checkout, git_commit, git_get_changed_files, git_get_remote_url,
)
from .sessions import list_sessions, load_session, save_session, export_session
from .themes import list_themes
from .utils import calculate_cost, estimate_tokens, render_markdown
from .snippets import cmd_snippet
from .templates import cmd_template
from .refactor import cmd_refactor
from . import __version__

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
    """Handle a slash command. Returns True if handled."""
    parts = args.strip().split(maxsplit=1)
    sub = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    handlers: Dict[str, Callable] = {
        "help": cmd_help, "edit": cmd_edit, "run": cmd_run, "files": cmd_files,
        "add": cmd_add, "remove": cmd_remove, "clear": cmd_clear, "save": cmd_save,
        "load": cmd_load, "sessions": cmd_sessions, "model": cmd_model,
        "models": cmd_models, "provider": cmd_provider, "providers": cmd_providers,
        "cost": cmd_cost, "theme": cmd_theme, "themes": cmd_themes,
        "undo": cmd_undo, "diff": cmd_diff, "status": cmd_status,
        "git": cmd_git, "search": cmd_search, "grep": cmd_grep, "tree": cmd_tree,
        "export": cmd_export, "compact": cmd_compact, "system": cmd_system,
        "version": cmd_version, "quit": cmd_quit, "q": cmd_quit,
        "exit": cmd_quit,
        "index": cmd_index, "symbols": cmd_symbols, "capabilities": cmd_capabilities,
        "snippet": cmd_snippet, "snippets": cmd_snippet,
        "template": cmd_template, "templates": cmd_template,
        "refactor": cmd_refactor, "refactoring": cmd_refactor,
        "record": cmd_record,
        "voice": cmd_voice,
        "eli5": cmd_eli5,
    }
    handler = handlers.get(sub)
    if handler:
        handler(rest, messages, client, console, cwd, context_files)
        return True
    console.print(f"[error]Unknown command: /{sub}[/error]. Type [info]/help[/info] for commands.")
    return True


def cmd_help(rest: str, messages, client, console, cwd, ctx_files):
    table = Table(title="🧠 TermMind Commands", show_header=False, border_style="dim")
    table.add_column("Command", style="cyan", min_width=25)
    table.add_column("Description", min_width=40)
    commands = [
        ("File Operations", "", True),
        ("/edit <file> [inst]", "Edit a file with AI", False),
        ("/add <file|--dir>", "Add file/dir to context", False),
        ("/remove <file>", "Remove file from context", False),
        ("/run <cmd>", "Run a shell command", False),
        ("/run --timeout 30 <cmd>", "Run with timeout", False),
        ("/files", "List files in context", False),
        ("/search <query>", "Search in project files", False),
        ("/grep <pattern>", "Grep through project (regex)", False),
        ("/tree [--depth N]", "Show project file tree", False),
        ("/undo [--all]", "Undo last/all file edits", False),
        ("/diff [file]", "Show session changes", False),
        ("Session", "", True),
        ("/clear", "Clear conversation", False),
        ("/save [name]", "Save session", False),
        ("/load [name]", "Load saved session", False),
        ("/sessions [search]", "List saved sessions", False),
        ("/export [--json]", "Export conversation", False),
        ("/compact", "Compact history to save tokens", False),
        ("Provider & Model", "", True),
        ("/model [name]", "Show/switch model", False),
        ("/models", "List available models", False),
        ("/provider [name]", "Show/switch provider", False),
        ("/providers", "List all providers", False),
        ("/cost", "Show token usage & cost", False),
        ("Git", "", True),
        ("/git status", "Git status", False),
        ("/git diff", "Git diff", False),
        ("/git log", "Recent commits", False),
        ("/git commit", "AI-generated commit msg", False),
        ("/git branch", "List branches", False),
        ("/git checkout <br>", "Switch branch", False),
        ("Config", "", True),
        ("/status", "Full session status", False),
        ("/theme <name>", "Change color theme", False),
        ("/themes", "List available themes", False),
        ("/system <msg>", "Set system prompt", False),
        ("/version", "Show version", False),
        ("/help", "Show this help", False),
        ("/quit", "Exit TermMind", False),
        ("Snippets", "", True),
        ("/snippet save <name>", "Save code/context as snippet", False),
        ("/snippet list", "List saved snippets", False),
        ("/snippet load <name>", "Load snippet into context", False),
        ("/snippet search <q>", "Search snippets", False),
        ("/snippet delete <name>", "Delete a snippet", False),
        ("/snippet export [path]", "Export snippets as JSON", False),
        ("/snippet import <file>", "Import snippets from JSON", False),
        ("/snippet suggest", "Suggest relevant snippets", False),
        ("Templates", "", True),
        ("/template list", "List project templates", False),
        ("/template use <name>", "Scaffold a project", False),
        ("Refactoring", "", True),
        ("/refactor <op> <file>", "AI-powered refactoring", False),
        ("/refactor sort-imports <f>", "Sort imports (PEP 8)", False),
        ("/refactor add-types <f>", "Add type hints", False),
        ("/refactor simplify <f>", "Simplify complex code", False),
        ("/refactor dead-code <f>", "Remove dead code", False),
        ("/refactor extract-fn <f>", "Extract a function", False),
        ("/refactor rename <f>", "Rename identifiers", False),
        ("/refactor inline <f>", "Inline variables/functions", False),
        ("/refactor extract-class <f>", "Extract into a class", False),
        ("/refactor history", "Show refactor history", False),
        ("/refactor undo", "Undo last refactoring", False),
    ]
    for cmd, desc, is_header in commands:
        if is_header:
            table.add_row(f"\n[bold]{cmd}[/bold]", "", style="")
        else:
            table.add_row(cmd, desc)
    console.print(table)


def cmd_edit(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /edit <file> [instruction][/error]")
        return
    parts = rest.split(maxsplit=1)
    filepath = parts[0]
    instruction = parts[1] if len(parts) > 1 else "Improve this file"
    full_path = os.path.join(cwd, filepath) if not os.path.isabs(filepath) else filepath
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
    timeout = 30
    if rest.startswith("--timeout"):
        parts = rest.split(maxsplit=2)
        if len(parts) >= 3:
            try:
                timeout = int(parts[1])
                rest = parts[2]
            except ValueError:
                pass
    import subprocess
    console.print(f"[command]$ {rest}[/command]")
    try:
        result = subprocess.run(rest, shell=True, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[error]{result.stderr}[/error]")
        if result.returncode != 0:
            console.print(f"[warning]Exit code: {result.returncode}[/warning]")
        output = result.stdout + result.stderr
        if output.strip():
            messages.append({"role": "user", "content": f"[Ran: {rest}]\nOutput:\n{output[:2000]}"})
            messages.append({"role": "assistant", "content": f"Command completed with exit code {result.returncode}."})
    except subprocess.TimeoutExpired:
        console.print(f"[error]Command timed out ({timeout}s)[/error]")
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
        console.print("[error]Usage: /add <file> or /add --dir <dir>[/error]")
        return
    if rest.startswith("--dir"):
        dir_path = rest.split(maxsplit=1)[1] if len(rest.split()) > 1 else cwd
        dir_path = os.path.join(cwd, dir_path) if not os.path.isabs(dir_path) else dir_path
        files = find_files(dir_path, max_depth=3)
        added = 0
        for f in files[:20]:
            rel = os.path.relpath(f, cwd)
            if rel not in ctx_files:
                ctx_files.append(rel)
                added += 1
        console.print(f"[success]✅ Added {added} files from {dir_path}[/success]")
    else:
        ctx_files.append(rest)
        console.print(f"[success]✅ Added {rest} to context[/success]")


def cmd_remove(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /remove <file>[/error]")
        return
    if rest in ctx_files:
        ctx_files.remove(rest)
        console.print(f"[success]✅ Removed {rest} from context[/success]")
    else:
        console.print(f"[warning]File not in context: {rest}[/warning]")


def cmd_clear(rest: str, messages, client, console, cwd, ctx_files):
    messages.clear()
    ctx_files.clear()
    console.print("[system]Conversation cleared.[/system]")


def cmd_save(rest: str, messages, client, console, cwd, ctx_files):
    name = rest or datetime.now().strftime("%Y-%m-%d_%H-%M")
    save_session(name, messages, client.provider, client.model, client.get_cost(),
                 client.total_tokens(), ctx_files)
    console.print(f"[success]💾 Session saved: {name}[/success]")


def cmd_load(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        sessions = list_sessions()
        if not sessions:
            console.print("[system]No saved sessions.[/system]")
            return
        table = Table(title="Sessions", border_style="dim")
        table.add_column("Name", style="file_path")
        table.add_column("Provider")
        table.add_column("Model")
        table.add_column("Msgs")
        table.add_column("Saved")
        for s in sessions[:15]:
            table.add_row(s["name"], s["provider"], s["model"], str(s["messages"]), s["saved_at"][:16])
        console.print(table)
        return
    session = load_session(rest)
    if not session:
        console.print(f"[error]Session not found: {rest}[/error]")
        return
    messages.clear()
    messages.extend(session.get("messages", []))
    ctx_files.clear()
    ctx_files.extend(session.get("context_files", []))
    console.print(f"[success]📂 Session loaded: {rest}[/success]")


def cmd_sessions(rest: str, messages, client, console, cwd, ctx_files):
    sessions = list_sessions(search=rest or None)
    if not sessions:
        console.print("[system]No saved sessions.[/system]")
        return
    table = Table(title="Sessions", border_style="dim")
    table.add_column("Name", style="file_path")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Msgs")
    table.add_column("Tokens")
    table.add_column("Saved")
    for s in sessions[:15]:
        table.add_row(s["name"], s["provider"], s["model"], str(s["messages"]),
                      f"{s['tokens']:,}", s["saved_at"][:16])
    console.print(table)


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


def cmd_models(rest: str, messages, client, console, cwd, ctx_files):
    info = PROVIDER_PRESETS.get(client.provider, {})
    models = info.get("models", [])
    console.print(f"[info]Provider: {client.provider}[/info]")
    console.print(f"[info]Current model: {client.model}[/info]\n")
    if models:
        for m in models:
            marker = " ← current" if m == client.model else ""
            console.print(f"  [cyan]•[/cyan] {m}{marker}")
    else:
        console.print("[dim]No predefined models. Use any model name with /model.[/dim]")


def cmd_provider(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print(f"[info]Current provider: {client.provider}[/info]")
        return
    if rest not in PROVIDER_PRESETS:
        console.print(f"[error]Unknown provider: {rest}. Available: {list(PROVIDER_PRESETS.keys())}[/error]")
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


def cmd_providers(rest: str, messages, client, console, cwd, ctx_files):
    table = Table(title="Providers", border_style="dim")
    table.add_column("Provider", style="cyan")
    table.add_column("Default Model")
    table.add_column("Requires Key")
    table.add_column("Status")
    for name, info in PROVIDER_PRESETS.items():
        marker = " ← current" if name == client.provider else ""
        needs_key = "Yes" if info["requires_key"] else "No"
        has_key = "✅" if (not info["requires_key"] or load_config().get("providers", {}).get(name, {}).get("api_key") or (name == load_config().get("provider") and load_config().get("api_key"))) else "⚠ No key"
        table.add_row(f"{name}{marker}", info["default_model"], needs_key, has_key)
    console.print(table)


def cmd_cost(rest: str, messages, client, console, cwd, ctx_files):
    tokens = client.total_tokens()
    cost = client.get_cost()
    table = Table(title="Session Cost", border_style="dim")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value")
    table.add_row("Provider", client.provider)
    table.add_row("Model", client.model)
    table.add_row("Total tokens", f"{tokens:,}")
    table.add_row("Prompt tokens", f"{client.usage['prompt_tokens']:,}")
    table.add_row("Completion tokens", f"{client.usage['completion_tokens']:,}")
    table.add_row("Estimated cost", f"${cost:.6f}")
    table.add_row("Messages", str(len([m for m in messages if m['role'] == 'user'])))
    console.print(table)


def cmd_theme(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        cfg = load_config()
        console.print(f"[info]Current theme: {cfg.get('theme', 'dark')}[/info]")
        return
    if rest not in list_themes():
        console.print(f"[error]Unknown theme: {rest}. Available: {list_themes()}[/error]")
        return
    cfg = load_config()
    cfg["theme"] = rest
    save_config(cfg)
    console.print(f"[success]🎨 Theme changed to: {rest} (restart chat to apply)[/success]")


def cmd_themes(rest: str, messages, client, console, cwd, ctx_files):
    cfg = load_config()
    current = cfg.get("theme", "dark")
    for t in list_themes():
        marker = " ← current" if t == current else ""
        console.print(f"  [cyan]•[/cyan] {t}{marker}")


def cmd_undo(rest: str, messages, client, console, cwd, ctx_files):
    if rest.strip() == "--all":
        count = undo_all_edits()
        console.print(f"[success]↩️ Undid {count} edits[/success]")
        return
    filepath = undo_last_edit()
    if filepath:
        console.print(f"[success]↩️ Undid edit to: {filepath}[/success]")
    else:
        console.print("[warning]Nothing to undo.[/warning]")


def cmd_diff(rest: str, messages, client, console, cwd, ctx_files):
    from .diff_engine import compute_diff_from_disk, render_diff_inline
    if rest:
        p = os.path.join(cwd, rest) if not os.path.isabs(rest) else rest
        content = read_file(p)
        if content is None:
            console.print(f"[error]File not found: {rest}[/error]")
            return
        history = get_undo_history()
        for fp, old_content, _ in reversed(history):
            if os.path.abspath(fp) == os.path.abspath(p):
                fd = compute_diff_from_disk(p, content)
                # Temporarily set old_content for rendering
                import dataclasses
                fd.old_content = old_content
                fd.hunks = []
                import difflib
                diff_text = "".join(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{rest}", tofile=f"b/{rest}",
                ))
                from .diff_engine import _parse_unified_diff
                fd.hunks = _parse_unified_diff(diff_text)
                fd.edit_type = fd.edit_type if fd.edit_type.value != "identical" else __import__("termmind.diff_engine", fromlist=["EditType"]).EditType.REPLACE
                render_diff_inline(fd, console)
                return
        console.print("[system]No changes recorded for this file.[/system]")
        return
    diffs = get_session_diffs()
    if not diffs:
        console.print("[system]No changes this session.[/system]")
        return
    from .diff_engine import compute_file_diff, render_diff_inline, MultiFileDiff
    multi = MultiFileDiff()
    for filepath, diff in diffs:
        multi.files.append(compute_file_diff("", "", filepath, filepath))
    # Fallback to simple display
    for filepath, diff in diffs:
        console.print(f"[file_path]{filepath}[/file_path]")
        console.print(diff)
        console.print()


def cmd_status(rest: str, messages, client, console, cwd, ctx_files):
    table = Table(title="Session Status", border_style="dim")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value")
    if git_is_repo(cwd):
        table.add_row("Git", git_branch(show_current=True, cwd=cwd))
        status = git_status(cwd)
        changed = len(status.splitlines()) - 1 if status else 0
        table.add_row("Changed files", str(changed))
        remote = ""
        try:
            from .git import git_get_remote_url
            remote = git_get_remote_url(cwd)
        except Exception:
            pass
        if remote:
            table.add_row("Remote", remote)
    table.add_row("Provider", client.provider)
    table.add_row("Model", client.model)
    table.add_row("Context files", str(len(ctx_files)))
    table.add_row("Messages", str(len([m for m in messages if m['role'] == 'user'])))
    table.add_row("Tokens", f"{client.total_tokens():,}")
    table.add_row("Cost", f"${client.get_cost():.6f}")
    table.add_row("CWD", cwd)
    table.add_row("Theme", load_config().get("theme", "dark"))
    console.print(table)


def cmd_git(rest: str, messages, client, console, cwd, ctx_files):
    if not git_is_repo(cwd):
        console.print("[error]Not a git repository.[/error]")
        return
    sub = rest.strip().split()[0] if rest.strip() else "status"
    rest_args = rest.strip().split(maxsplit=1)[1] if len(rest.strip().split()) > 1 else ""
    if sub == "status":
        console.print(git_status(cwd) or "✨ Working tree clean")
    elif sub == "log":
        console.print(git_log(cwd) or "No commits")
    elif sub == "diff":
        d = git_diff(cwd)
        console.print(d if d else "No changes")
    elif sub == "branch":
        console.print(git_branch(cwd) or "No branches")
    elif sub == "checkout" and rest_args:
        out, rc = git_checkout(rest_args, cwd)
        console.print(f"[success]{out}[/success]" if rc == 0 else f"[error]{out}[/error]")
    elif sub == "commit":
        # AI-generated commit message
        diff_text = git_diff(cwd)
        if not diff_text.strip():
            console.print("[system]Nothing to commit.[/system]")
            return
        import asyncio
        from .git import ai_commit_message
        console.print("[system]🤖 Generating commit message...[/system]")
        try:
            loop = asyncio.new_event_loop()
            commit_msg = loop.run_until_complete(ai_commit_message(client, diff_text))
            loop.close()
        except Exception:
            commit_msg = "chore: update"
        console.print(f"[info]Suggested:[/info] {commit_msg}")
        from prompt_toolkit import prompt
        confirm = input("Commit with this message? [Y/n] ").strip().lower()
        if confirm in ("", "y", "yes"):
            out, rc = git_commit(commit_msg, cwd)
            if rc == 0:
                console.print(f"[success]✅ {out}[/success]")
            else:
                console.print(f"[error]{out}[/error]")
        else:
            console.print("[system]Commit cancelled.[/system]")
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


def cmd_grep(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        console.print("[error]Usage: /grep <pattern>[/error]")
        return
    results = grep_files(rest, cwd)
    if not results:
        console.print(f"[system]No matches for: {rest}[/system]")
        return
    console.print(f"[info]Found {len(results)} matches:[/info]")
    for r in results[:30]:
        console.print(f"  [file_path]{r['path']}:{r['line']}[/file_path]: {r['text'][:100]}")


def cmd_tree(rest: str, messages, client, console, cwd, ctx_files):
    depth = 3
    show_sizes = False
    for part in rest.split():
        if part == "--depth" or part == "-d":
            continue
        try:
            depth = int(part)
        except ValueError:
            if part == "--sizes" or part == "-s":
                show_sizes = True
    tree = build_file_tree(cwd, max_depth=depth, show_sizes=show_sizes)
    if tree:
        console.print(tree)
    else:
        console.print("[system]Empty directory.[/system]")


def cmd_export(rest: str, messages, client, console, cwd, ctx_files):
    fmt = "json" if "--json" in rest else "markdown"
    name = rest.replace("--json", "").strip() or datetime.now().strftime("%Y-%m-%d_%H-%M")
    content = export_session(name, fmt)
    if not content:
        console.print(f"[error]Session not found: {name}[/error]")
        return
    out_path = os.path.join(cwd, f"termmind_export_{name}.{fmt[:4]}")
    with open(out_path, "w") as f:
        f.write(content)
    console.print(f"[success]📤 Exported to: {out_path}[/success]")


def cmd_compact(rest: str, messages, client, console, cwd, ctx_files):
    """Compact conversation history to save tokens."""
    if len(messages) < 4:
        console.print("[system]Not enough messages to compact.[/system]")
        return
    # Keep system messages and last exchange, summarize middle
    system_msgs = [m for m in messages if m["role"] == "system"]
    if system_msgs and messages[0]["role"] == "system":
        summary = {"role": "system", "content": messages[0]["content"]}
    else:
        summary = {"role": "system", "content": "[Previous conversation was compacted to save context space.]"}
    # Keep last 4 messages (2 exchanges)
    tail = messages[-4:] if len(messages) >= 4 else messages[-2:]
    # Summarize middle
    middle_count = len(messages) - len(system_msgs) - len(tail)
    summary_text = summary["content"]
    summary_text += f"\n\n[Compacted {middle_count} messages from earlier in the conversation.]"
    summary["content"] = summary_text
    messages.clear()
    messages.append(summary)
    messages.extend(tail)
    removed = middle_count
    console.print(f"[success]🔄 Compacted conversation: removed {removed} messages, kept {len(tail)}[/success]")


def cmd_system(rest: str, messages, client, console, cwd, ctx_files):
    if not rest:
        cfg = load_config()
        console.print(f"[info]Current system prompt:[/info]\n{cfg.get('system_prompt', '(none)')}")
        return
    cfg = load_config()
    cfg["system_prompt"] = rest
    save_config(cfg)
    console.print("[success]✅ System prompt updated.[/success]")


def cmd_index(rest: str, messages, client, console, cwd, ctx_files):
    import time
    from .memory import build_index, get_project_summary
    force = "--force" in rest or "-f" in rest
    console.print("[system]Building code index...[/system]")
    start = time.time()
    idx = build_index(cwd, force=force)
    elapsed = time.time() - start
    summary = get_project_summary(cwd)
    table = Table(title="Code Index", border_style="dim")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value")
    table.add_row("Files", str(summary["total_files"]))
    table.add_row("Functions", str(summary["total_functions"]))
    table.add_row("Classes", str(summary["total_classes"]))
    table.add_row("Languages", ", ".join(summary["languages"]))
    table.add_row("Build time", f"{elapsed:.2f}s")
    console.print(table)


def cmd_symbols(rest: str, messages, client, console, cwd, ctx_files):
    from .memory import query_functions, query_classes, build_index
    parts = rest.strip().split(maxsplit=1)
    pattern = parts[0] if parts else ""
    table = Table(title="Symbols", border_style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("File", style="file_path")
    table.add_column("Line", justify="right")
    for func in query_functions(cwd, pattern):
        table.add_row(func["name"], "func", func.get("file", ""), str(func.get("line", 0)))
    for cls in query_classes(cwd, pattern):
        table.add_row(cls["name"], "class", cls.get("file", ""), str(cls.get("line", 0)))
    console.print(table)


def cmd_capabilities(rest: str, messages, client, console, cwd, ctx_files):
    from .shell import get_capability_report
    report = get_capability_report()
    table = Table(title="Terminal Capabilities", border_style="dim")
    table.add_column("Capability", style="bold cyan")
    table.add_column("Value")
    table.add_row("Shell", report["shell"])
    table.add_row("Terminal", f"{report['term_program']} ({report['term']})")
    table.add_row("Size", f"{report['terminal_size']['rows']}×{report['terminal_size']['cols']}")
    table.add_row("True Color", "✅" if report["truecolor"] else "❌")
    table.add_row("Unicode", "✅" if report["unicode"] else "❌")
    table.add_row("Emoji", "✅" if report["emoji"] else "❌")
    for k, v in report["copy_paste"].items():
        table.add_row(f"Clipboard: {k}", "✅" if v else "❌")
    console.print(table)


def cmd_version(rest: str, messages, client, console, cwd, ctx_files):
    console.print(f"[bold]TermMind[/bold] v{__version__}")


def cmd_quit(rest: str, messages, client, console, cwd, ctx_files):
    raise SystemExit(0)


def cmd_eli5(rest: str, messages, client, console, cwd, ctx_files):
    """Explain Like I'm 5 mode."""
    if not hasattr(cmd_eli5, 'eli5'):
        from .eli5 import ELI5Mode
        cmd_eli5.eli5 = ELI5Mode()
    if rest.strip() == "mode on":
        cmd_eli5.eli5.enable()
        console.print("🧒 [green]ELI5 Mode ON[/green] — Responses will be simplified")
    elif rest.strip() == "mode off":
        cmd_eli5.eli5.disable()
        console.print("🧒 [yellow]ELI5 Mode OFF[/yellow]")
    elif rest.strip() == "status":
        console.print(cmd_eli5.eli5.get_status_text())
    elif rest.strip():
        # Explain the given topic
        prompt = cmd_eli5.eli5.modify_user_message(rest)
        messages.append({"role": "user", "content": prompt})
        sys_prompt = cmd_eli5.eli5.get_system_prompt()
        extra = {"system": sys_prompt} if sys_prompt else {}
        response = client.send_message(messages, **extra)
        console.print(f"\n{response}\n")
        messages.append({"role": "assistant", "content": response})
    else:
        console.print(cmd_eli5.eli5.get_help_text())


def cmd_voice(rest: str, messages, client, console, cwd, ctx_files):
    """Voice mode controls."""
    if not hasattr(cmd_voice, 'voice'):
        from .voice import VoiceMode
        cmd_voice.voice = VoiceMode()
    if rest.strip() == "on":
        cmd_voice.voice.enable()
        console.print("🔊 [green]Voice Mode ON[/green] — AI responses will be spoken aloud")
    elif rest.strip() == "off":
        cmd_voice.voice.disable()
        console.print("🔇 [yellow]Voice Mode OFF[/yellow]")
    elif rest.strip().startswith("speed"):
        try:
            speed = float(rest.split()[-1])
            cmd_voice.voice.set_speed(speed)
            console.print(f"🔊 Speed set to {speed}x")
        except (ValueError, IndexError):
            console.print(cmd_voice.voice.get_help_text())
    elif rest.strip().startswith("lang"):
        lang = rest.split()[-1] if len(rest.split()) > 1 else "en"
        cmd_voice.voice.set_language(lang)
        console.print(f"🔊 Language set to {lang}")
    else:
        console.print(cmd_voice.voice.get_help_text())


def cmd_record(rest: str, messages, client, console, cwd, ctx_files):
    """Session recording controls."""
    if not hasattr(cmd_record, 'recorder'):
        from .recorder import SessionRecorder
        cmd_record.recorder = SessionRecorder()
    if rest.strip() == "start":
        cmd_record.recorder.start()
        console.print("🔴 [green]Recording started[/green]")
    elif rest.strip() == "stop":
        name = cmd_record.recorder.stop()
        console.print(f"⏹️ [yellow]Recording saved: {name}[/yellow]")
    elif rest.strip() == "list":
        recordings = cmd_record.recorder.list_recordings()
        if not recordings:
            console.print("No recordings found")
        else:
            from rich.table import Table
            table = Table(title="Recordings")
            table.add_column("Name", style="cyan")
            table.add_column("Date")
            table.add_column("Events")
            table.add_column("Duration")
            for r in recordings:
                table.add_row(r["name"], r["date"], str(r["events"]), r.get("duration", "N/A"))
            console.print(table)
    elif rest.strip().startswith("replay"):
        parts = rest.strip().split()
        speed = 1.0
        name = None
        for i, p in enumerate(parts):
            if p == "--speed" and i + 1 < len(parts):
                speed = float(parts[i + 1])
            elif p != "replay":
                name = p
        if name:
            console.print(f"▶️ Replaying {name} (speed: {speed}x)...")
            events = cmd_record.recorder.replay(name, speed)
            for event in events:
                console.print(f"  [{event['time']}] {event['type']}: {event.get('summary', '')[:80]}")
        else:
            console.print("Usage: /record replay <name> [--speed 2x]")
    elif rest.strip().startswith("export"):
        name = rest.strip().split()[-1] if len(rest.strip().split()) > 1 else None
        if name:
            path = cmd_record.recorder.export_html(name)
            console.print(f"📄 Exported to: {path}")
        else:
            console.print("Usage: /record export <name>")
    else:
        console.print("""🔴 Recording Controls:
  /record start         — Start recording
  /record stop          — Stop and save
  /record list          — List recordings
  /record replay <name> — Replay a recording
  /record export <name> — Export as HTML
  /record replay <name> --speed 2x""")


def cmd_cost(rest: str, messages, client, console, cwd, ctx_files):
    """Cost tracking and optimization."""
    if not hasattr(cmd_cost, 'optimizer'):
        from .cost_optimizer import CostOptimizer
        cmd_cost.optimizer = CostOptimizer()
    if rest.strip() == "analyze" or rest.strip() == "":
        console.print(cmd_cost.optimizer.get_analysis_text())
    elif rest.strip() == "history":
        daily = cmd_cost.optimizer.get_daily_history(30)
        from rich.table import Table
        table = Table(title="Cost History (30 days)")
        table.add_column("Date", style="cyan")
        table.add_column("Cost", style="green")
        for d in daily:
            table.add_row(d["date"], f"${d['cost']:.4f}")
        console.print(table)
    elif rest.strip().startswith("budget"):
        try:
            amount = float(rest.split()[-1])
            cmd_cost.optimizer.set_budget(amount)
            console.print(f"💰 Budget set to ${amount:.2f}")
        except ValueError:
            budget = cmd_cost.optimizer.get_budget_status()
            if budget:
                console.print(f"Budget: ${budget['spent']:.2f} / ${budget['budget']:.2f} ({budget['percent']:.0f}%)")
            else:
                console.print("No budget set. Usage: /cost budget <amount>")
    elif rest.strip() == "optimize":
        result = cmd_cost.optimizer.optimize_context(messages, "openai", "gpt-4")
        console.print(f"\n📊 Context: ~{result['current_context_tokens']:,} tokens")
        console.print(f"💰 Estimated cost: ${result['estimated_request_cost']:.6f}")
        if result["suggestions"]:
            console.print(f"\n💡 Savings: ~{result['total_potential_savings_tokens']:,} tokens possible")
            from rich.table import Table
            table = Table(title="Optimization Suggestions")
            table.add_column("Type")
            table.add_column("Description")
            table.add_column("Savings", style="green")
            for s in result["suggestions"]:
                table.add_row(s["type"], s["description"], f"~{s['estimated_savings_tokens']:,} tokens")
            console.print(table)
        else:
            console.print("[green]Context looks good, no optimizations needed![/green]")
    elif rest.strip() == "compare":
        tokens = cmd_cost.optimizer.get_token_stats()
        comparisons = cmd_cost.optimizer.compare_providers(tokens["input"], tokens["output"])
        from rich.table import Table
        table = Table(title="Provider Cost Comparison")
        table.add_column("Provider", style="cyan")
        table.add_column("Model")
        table.add_column("Cost", style="green")
        for c in comparisons[:10]:
            table.add_row(c["provider"], c["model"], f"${c['cost']:.6f}")
        console.print(table)
    elif rest.strip() == "save":
        cmd_cost.optimizer._save_history()
        console.print("[green]Cost history saved[/green]")
    else:
        console.print("""💰 Cost Controls:
  /cost               — Show cost analysis
  /cost analyze       — Detailed analysis
  /cost history       — Daily cost history
  /cost budget <amt>  — Set session budget
  /cost optimize      — Suggest context optimizations
  /cost compare       — Compare provider costs
  /cost save          — Save cost history""")
