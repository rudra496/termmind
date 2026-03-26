"""TermMind CLI — the main entry point."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from . import __version__
from .api import APIError, APIClient
from .commands import handle_command
from .config import PROVIDER_PRESETS, load_config, save_config
from .context import build_context
from .file_ops import build_file_tree, find_files, read_file, write_file
from .git import git_is_repo
from .themes import get_theme
from .utils import estimate_tokens, render_markdown

HISTORY_FILE = Path.home() / ".termind" / "history"
BANNER = r"""
[bold cyan]  ╔═══════════════════════════════╗
  ║     [bold white]T e r m M i n d[/bold white]             ║
  ║  [dim]AI Terminal Assistant v0.1.0[/dim]    ║
  ╚═══════════════════════════════╝[/bold cyan]
"""

SLASH_COMMANDS = [
    "/edit", "/run", "/files", "/add", "/search", "/tree",
    "/clear", "/save", "/load", "/model", "/provider",
    "/cost", "/theme", "/undo", "/diff", "/status", "/git", "/help",
]


def _get_console() -> Console:
    cfg = load_config()
    return Console(theme=get_theme(cfg.get("theme", "dark")))


def _get_key_bindings():
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    return kb


def _stream_response(client: APIClient, messages: List[dict], console: Console, system_prompt: Optional[str] = None) -> str:
    """Stream response and render markdown. Returns full response text."""
    full = ""
    console.print()
    try:
        for chunk in client.chat_stream(messages, system_prompt):
            full += chunk
        # Render the full response as markdown
        console.print()
        if full.strip():
            console.print(Markdown(full))
    except APIError as e:
        console.print(f"\n[error]❌ {e}[/error]")
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ Interrupted[/yellow]")
    console.print()
    return full


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="termind")
@click.pass_context
def main(ctx: click.Context):
    """TermMind — AI terminal assistant."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


def _interactive_init() -> dict:
    """Interactive setup wizard."""
    console = _get_console()
    console.print(BANNER)
    console.print("[bold]Welcome to TermMind! Let's set things up.[/bold]\n")

    # Provider selection
    console.print("[info]Select a provider:[/info]")
    providers = list(PROVIDER_PRESETS.keys())
    for i, p in enumerate(providers):
        info = PROVIDER_PRESETS[p]
        free = "[green]free[/green]" if info["cost_per_1k_input"] == 0 else ""
        key_req = "[dim](no key needed)[/dim]" if not info["requires_key"] else ""
        console.print(f"  [cyan]{i+1}[/cyan]. [command]{p}[/command] — {info['default_model']} {free} {key_req}")

    choice = click.prompt("\nProvider number", default="6", type=int) - 1
    choice = max(0, min(choice, len(providers) - 1))
    provider = providers[choice]
    info = PROVIDER_PRESETS[provider]

    console.print(f"\n[success]Selected: {provider}[/success]")

    # API key
    api_key = ""
    if info["requires_key"]:
        console.print(f"\nGet your API key at the provider's website.")
        api_key = click.prompt(f"[info]{provider} API key[/info]", default="", show_default=False)

    # Model
    console.print(f"\n[info]Available models:[/info]")
    for m in info["models"]:
        console.print(f"  [cyan]•[/cyan] {m}")
    model = click.prompt("[info]Model[/info]", default=info["default_model"])

    # Temperature
    temp = click.prompt("[info]Temperature (0-2)[/info]", default=0.7, type=float)

    cfg = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "max_tokens": 4096,
        "temperature": temp,
        "theme": "dark",
        "system_prompt": "You are TermMind, a helpful AI assistant in the terminal. "
            "You help with coding, file operations, and general questions. "
            "Be concise and practical. When showing code, use markdown code blocks with language hints.",
    }
    save_config(cfg)
    console.print(f"\n[success]✅ Configuration saved to ~/.termind/config.json[/success]")
    console.print(f"[dim]Provider: {provider} | Model: {model}[/dim]\n")
    return cfg


@main.command()
def init():
    """Configure TermMind (API provider, key, model)."""
    _interactive_init()


@main.command()
@click.argument("question", required=False)
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def ask(question: Optional[str], provider: Optional[str], model: Optional[str]):
    """Ask a question (one-shot, no session)."""
    if not question:
        console = _get_console()
        console.print("[error]Usage: termind ask \"your question\"[/error]")
        return

    cfg = load_config()
    if not cfg.get("api_key") and PROVIDER_PRESETS.get(cfg.get("provider"), {}).get("requires_key", True):
        console = _get_console()
        console.print("[warning]No API key configured. Run [command]termind init[/command] first.[/warning]")
        return

    console = _get_console()
    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
        max_tokens=cfg.get("max_tokens", 4096),
        temperature=cfg.get("temperature", 0.7),
    )

    # Build context from current directory
    cwd = os.getcwd()
    context = build_context(question, cwd)
    user_msg = f"{question}\n\n{context}" if context else question

    console.print(f"[prompt]❯[/prompt] {question}\n")
    start = time.time()
    response = _stream_response(client, [{"role": "user", "content": user_msg}], console)
    elapsed = time.time() - start
    tokens = client.total_tokens()
    if tokens:
        console.print(f"[cost]⚡ {tokens:,} tokens • {elapsed:.1f}s • ${client.get_cost():.6f}[/cost]")


@main.command()
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
@click.option("--system", "-s", help="Custom system prompt")
def chat(provider: Optional[str], model: Optional[str], system: Optional[str]):
    """Start interactive chat session."""
    cfg = load_config()

    # Check if configured
    needs_key = PROVIDER_PRESETS.get(cfg.get("provider"), {}).get("requires_key", True)
    if not cfg.get("api_key") and needs_key:
        # Check if ollama is available
        if cfg.get("provider") != "ollama":
            _interactive_init()
            cfg = load_config()

    console = _get_console()
    console.print(BANNER)

    # Show status
    p = cfg.get("provider", "ollama")
    m = cfg.get("model", "unknown")
    console.print(f"[dim]Provider: {p} | Model: {m} | CWD: {os.getcwd()}[/dim]")
    if git_is_repo("."):
        console.print("[dim]Git: detected ✓[/dim]")
    console.print("[dim]Type /help for commands • Shift+Enter for multiline • Ctrl+C to quit[/dim]\n")

    # Setup client
    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
        max_tokens=cfg.get("max_tokens", 4096),
        temperature=cfg.get("temperature", 0.7),
    )

    system_prompt = system or cfg.get("system_prompt")

    # State
    messages: List[dict] = []
    context_files: List[str] = []

    # Prompt session
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        completer=WordCompleter(SLASH_COMMANDS),
        key_bindings=_get_key_bindings(),
        multiline=True,
        prompt_continuation="... ",
    )

    while True:
        try:
            user_input = session.prompt(
                "\n[prompt]❯ [/prompt]",
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]👋 Bye![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            handle_command(user_input[1:], user_input[1:], messages, client, console, os.getcwd(), context_files)
            continue

        # Add context
        cwd = os.getcwd()
        context = build_context(user_input, cwd, context_files)
        full_msg = f"{user_input}\n\n{context}" if context else user_input

        messages.append({"role": "user", "content": full_msg})

        console.print(f"[system]🤖 Thinking...[/system]")
        start = time.time()
        response = _stream_response(client, messages, console, system_prompt)
        elapsed = time.time() - start

        if response:
            messages.append({"role": "assistant", "content": response})

        # Cost footer
        tokens = client.total_tokens()
        if tokens:
            console.print(f"[cost]⚡ {tokens:,} tokens • {elapsed:.1f}s • ${client.get_cost():.6f}[/cost]")

    # Auto-save on exit
    if messages:
        from .config import SESSIONS_DIR
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        name = time.strftime("%Y-%m-%d_%H-%M")
        session_data = {
            "name": name,
            "messages": messages[-20:],  # Keep last 10 exchanges
            "provider": client.provider,
            "model": client.model,
        }
        with open(SESSIONS_DIR / f"{name}.json", "w") as f:
            json.dump(session_data, f)


@main.command()
@click.argument("filepath")
@click.argument("instruction", required=False)
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def edit(filepath: str, instruction: Optional[str], provider: Optional[str], model: Optional[str]):
    """Edit a file with AI assistance."""
    cfg = load_config()
    console = _get_console()

    full_path = os.path.abspath(filepath)
    content = read_file(full_path)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return

    if not instruction:
        instruction = click.prompt("[info]Edit instruction[/info]")

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    prompt = f"""You are a code editor. Apply the requested edit to the file below.
Output ONLY the complete new file content. No explanations, no markdown fences.

File: {filepath}
```\n{content}\n```

Instruction: {instruction}"""

    console.print(f"[system]🤖 Editing {filepath}...[/system]")
    response = ""
    for chunk in client.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk
        console.print(chunk, end="", highlight=False)
    console.print()

    # Apply if it looks like code (not wrapped in fences)
    clean = response.strip()
    if clean.startswith("```"):
        # Remove fences
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines)

    write_file(full_path, clean)
    console.print(f"[success]✅ File updated: {filepath}[/success]")


@main.command()
@click.argument("path", default=".")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def review(path: str, provider: Optional[str], model: Optional[str]):
    """Review code in a directory or file."""
    cfg = load_config()
    console = _get_console()
    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    target = os.path.abspath(path)
    p = Path(target)
    if p.is_file():
        content = read_file(target)
        if content is None:
            console.print(f"[error]File not found: {path}[/error]")
            return
        code_context = f"File: {target}\n```\n{content}\n```"
    else:
        tree = build_file_tree(target)
        files = find_files(target)[:10]
        parts = [f"Directory: {target}\n\n## Structure\n```\n{tree}\n```"]
        for f in files:
            c = read_file(f)
            if c:
                rel = os.path.relpath(f, target)
                parts.append(f"\n## {rel}\n```\n{c[:5000]}\n```")
        code_context = "\n".join(parts)

    prompt = f"""Review this code. Be constructive and concise. Check for:
- Bugs or logic errors
- Security issues
- Code style and best practices
- Performance concerns

{code_context}"""

    console.print(f"[system]🤖 Reviewing {path}...[/system]\n")
    start = time.time()
    _stream_response(client, [{"role": "user", "content": prompt}], console)
    elapsed = time.time() - start
    console.print(f"[cost]⚡ {elapsed:.1f}s • ${client.get_cost():.6f}[/cost]")


@main.command()
@click.argument("filepath")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def explain(filepath: str, provider: Optional[str], model: Optional[str]):
    """Explain a file."""
    cfg = load_config()
    console = _get_console()

    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    prompt = f"""Explain this file clearly and concisely:
- What does it do?
- Key functions/classes and their purpose
- How does it fit into a larger project?

File: {filepath}
```\n{content}\n```"""

    console.print(f"[system]🤖 Explaining {filepath}...[/system]\n")
    _stream_response(client, [{"role": "user", "content": prompt}], console)


@main.command()
@click.argument("filepath")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
@click.option("--framework", "-f", default="pytest", help="Test framework")
def test(filepath: str, provider: Optional[str], model: Optional[str], framework: str):
    """Generate tests for a file."""
    cfg = load_config()
    console = _get_console()

    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    prompt = f"""Generate comprehensive tests using {framework} for this file.
Output ONLY the test code, no explanations.

File: {filepath}
```\n{content}\n```"""

    console.print(f"[system]🤖 Generating tests for {filepath}...[/system]\n")
    response = _stream_response(client, [{"role": "user", "content": prompt}], console)

    # Auto-save tests
    if response:
        p = Path(filepath)
        test_file = p.parent / f"test_{p.stem}{p.suffix}"
        clean = response.strip()
        # Remove code fences if present
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        test_content = "\n".join(lines)
        write_file(str(test_file), test_content)
        console.print(f"\n[success]💾 Tests saved to: {test_file}[/success]")


@main.command(name="history")
def show_history():
    """Show saved chat sessions."""
    console = _get_console()
    from .config import SESSIONS_DIR
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)
    if not sessions:
        console.print("[system]No saved sessions.[/system]")
        return
    from rich.table import Table
    table = Table(title="Session History", border_style="dim")
    table.add_column("Name", style="file_path")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Messages")
    table.add_column("Saved")
    for s in sessions[:20]:
        try:
            data = json.loads(s.read_text())
            table.add_row(
                s.stem,
                data.get("provider", "?"),
                data.get("model", "?"),
                str(len(data.get("messages", [])) // 2),
                data.get("saved_at", "?")[:16],
            )
        except (json.JSONDecodeError, OSError):
            table.add_row(s.stem, "?", "?", "?", "?")
    console.print(table)


@main.command()
def config():
    """Show current configuration."""
    console = _get_console()
    cfg = load_config()
    # Mask API key
    display = dict(cfg)
    if display.get("api_key"):
        key = display["api_key"]
        display["api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "****"
    console.print_json(json=display)


if __name__ == "__main__":
    main()
