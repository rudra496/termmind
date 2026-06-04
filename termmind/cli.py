"""TermMind CLI — the main entry point."""

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from . import __version__
from .api import APIClient, APIError
from .commands import handle_command
from .config import PROVIDER_PRESETS, load_config, save_config
from .context import build_context
from .file_ops import build_file_tree, find_files, read_file, write_file
from .git import git_is_repo
from .themes import get_theme

HISTORY_FILE = Path.home() / ".termmind" / "history"
BANNER = r"""
[bold cyan]  ╔═══════════════════════════════════╗
  ║      [bold white]T e r m M i n d[/bold white]                ║
  ║   [dim]AI Terminal Assistant v2.0.0[/dim]       ║
  ║   [dim]9 Providers • Security • Generate[/dim]  ║
  ╚═══════════════════════════════════╝[/bold cyan]
"""

SLASH_COMMANDS = [
    "/edit", "/run", "/files", "/add", "/remove", "/search", "/grep", "/tree",
    "/clear", "/save", "/load", "/sessions", "/model", "/models", "/provider",
    "/providers", "/cost", "/theme", "/themes", "/undo", "/diff", "/status",
    "/git", "/export", "/compact", "/system", "/help", "/version", "/quit",
    "/index", "/symbols", "/capabilities",
    "/snippet", "/snippets", "/snippet save", "/snippet list", "/snippet load",
    "/snippet search", "/snippet delete", "/snippet export", "/snippet import",
    "/snippet suggest",
    "/template", "/templates", "/template list", "/template use",
    "/refactor", "/refactor extract-function", "/refactor rename", "/refactor inline",
    "/refactor extract-class", "/refactor simplify", "/refactor dead-code",
    "/refactor sort-imports", "/refactor add-types", "/refactor undo", "/refactor history",
    "/record", "/record start", "/record stop", "/record list", "/record replay", "/record export",
    "/voice", "/voice on", "/voice off", "/voice speed", "/voice lang",
    "/eli5", "/eli5 mode on", "/eli5 mode off", "/eli5 status",
    "/cost optimize", "/cost history", "/cost budget", "/cost compare", "/cost save",
    "/scan", "/scan file", "/scan dir", "/scan ai",
    "/generate", "/generate api", "/generate class", "/generate cli", "/generate test",
    "/generate docker", "/generate config", "/generate script", "/generate regex",
    "/prompt", "/prompt list", "/prompt use", "/prompt save", "/prompt categories",
    "/suggest",
]


def _get_console() -> Console:
    cfg = load_config()
    return Console(theme=get_theme(cfg.get("theme", "dark")))


def _get_key_bindings():
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("up")
    def _history_back(event):
        buff = event.current_buffer
        if buff.document.cursor_position_row == 0:
            buff.history_backward()

    @kb.add("down")
    def _history_forward(event):
        buff = event.current_buffer
        doc = buff.document
        if doc.cursor_position_row == doc.line_count - 1:
            buff.history_forward()

    return kb


def _stream_response(client: APIClient, messages: list[dict], console: Console, system_prompt: Optional[str] = None) -> str:
    """Stream response and render markdown. Returns full response text."""
    full = ""
    console.print()
    try:
        for chunk in client.chat_stream(messages, system_prompt):
            full += chunk
        console.print()
        if full.strip():
            console.print(Markdown(full))
    except APIError as e:
        console.print(f"\n[error]❌ {e}[/error]")
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ Interrupted[/yellow]")
    console.print()
    return full


def _interactive_init() -> dict:
    """Interactive setup wizard."""
    console = _get_console()
    console.print(BANNER)
    console.print("[bold]Welcome to TermMind! Let's set things up.[/bold]\n")

    console.print("[info]Select a provider:[/info]")
    providers = list(PROVIDER_PRESETS.keys())
    for i, p in enumerate(providers):
        info = PROVIDER_PRESETS[p]
        free = "[green]free[/green]" if info["cost_per_1k_input"] == 0 else f"${info['cost_per_1k_input']}/1k"
        key_req = "[dim](no key needed)[/dim]" if not info["requires_key"] else ""
        console.print(f"  [cyan]{i+1}[/cyan]. [command]{p}[/command] — {info['default_model']} {free} {key_req}")

    choice = click.prompt("\nProvider number", default="6", type=int) - 1
    choice = max(0, min(choice, len(providers) - 1))
    provider = providers[choice]
    info = PROVIDER_PRESETS[provider]
    console.print(f"\n[success]Selected: {provider}[/success]")

    api_key = ""
    if info["requires_key"]:
        console.print("\nGet your API key at the provider's website.")
        api_key = click.prompt(f"[info]{provider} API key[/info]", default="", show_default=False)
        # Test connection
        console.print("[system]Testing connection...[/system]")
        from .providers import get_provider
        try:
            p_instance = get_provider(provider, api_key=api_key, base_url=info["base_url"])
            if p_instance.validate_connection():
                console.print("[success]✅ Connection successful![/success]")
            else:
                console.print("[warning]⚠ Connection failed. Check your API key.[/warning]")
        except Exception as e:
            console.print(f"[warning]⚠ Connection test error: {e}[/warning]")

    console.print("\n[info]Available models:[/info]")
    for m in info["models"]:
        console.print(f"  [cyan]•[/cyan] {m}")
    model = click.prompt("[info]Model[/info]", default=info["default_model"])

    temp = click.prompt("[info]Temperature (0-2)[/info]", default=0.7, type=float)

    cfg = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "max_tokens": 4096,
        "temperature": temp,
        "theme": "dark",
        "stream": True,
        "auto_context": True,
        "max_context_files": 20,
        "max_context_tokens": 100000,
        "confirm_edits": True,
        "confirm_runs": True,
        "history_size": 100,
        "system_prompt": "You are TermMind, a helpful AI assistant in the terminal. "
            "You help with coding, file operations, and general questions. "
            "Be concise and practical. When showing code, use markdown code blocks with language hints.",
    }
    save_config(cfg)
    console.print("\n[success]✅ Configuration saved to ~/.termmind/config.json[/success]")
    console.print(f"[dim]Provider: {provider} | Model: {model}[/dim]\n")
    return cfg


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="termmind")
@click.pass_context
def main(ctx: click.Context):
    """TermMind — AI terminal assistant with 7 providers, streaming, plugins, and more."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


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
        console.print("[error]Usage: termmind ask \"your question\"[/error]")
        return

    cfg = load_config()
    if not cfg.get("api_key") and PROVIDER_PRESETS.get(cfg.get("provider"), {}).get("requires_key", True):
        console = _get_console()
        console.print("[warning]No API key configured. Run [command]termmind init[/command] first.[/warning]")
        return

    console = _get_console()
    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
        max_tokens=cfg.get("max_tokens", 4096),
        temperature=cfg.get("temperature", 0.7),
    )

    cwd = os.getcwd()
    context = build_context(question, cwd)
    user_msg = f"{question}\n\n{context}" if context else question

    console.print(f"[prompt]❯[/prompt] {question}\n")
    start = time.time()
    _stream_response(client, [{"role": "user", "content": user_msg}], console)
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

    needs_key = PROVIDER_PRESETS.get(cfg.get("provider"), {}).get("requires_key", True)
    if not cfg.get("api_key") and needs_key and cfg.get("provider") != "ollama":
        _interactive_init()
        cfg = load_config()

    console = _get_console()
    console.print(BANNER)

    p = cfg.get("provider", "ollama")
    m = cfg.get("model", "unknown")
    console.print(f"[dim]Provider: {p} | Model: {m} | CWD: {os.getcwd()}[/dim]")
    if git_is_repo("."):
        console.print("[dim]Git: detected ✓[/dim]")
    console.print("[dim]Type /help for commands • Shift+Enter for multiline • Ctrl+C to quit[/dim]\n")

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
        max_tokens=cfg.get("max_tokens", 4096),
        temperature=cfg.get("temperature", 0.7),
    )

    system_prompt = system or cfg.get("system_prompt")

    messages: list[dict] = []
    context_files: list[str] = []

    # Initialize plugins
    from .plugins import discover_plugins
    plugins = discover_plugins()
    for plugin in plugins:
        with contextlib.suppress(Exception):
            plugin.on_start({"messages": messages, "client": client})

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
            user_input = session.prompt("\n[prompt]❯ [/prompt]")
        except (EOFError, KeyboardInterrupt):
            # Run plugin exit hooks
            for plugin in plugins:
                with contextlib.suppress(Exception):
                    plugin.on_exit()
            console.print("\n[dim]👋 Bye![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            try:
                handle_command(user_input[1:], user_input[1:], messages, client, console, os.getcwd(), context_files)
            except SystemExit:
                raise
            except Exception as e:
                console.print(f"[error]Command error: {e}[/error]")
            continue

        # Build context
        cwd = os.getcwd()
        if cfg.get("auto_context", True):
            context = build_context(user_input, cwd, context_files)
        else:
            context = ""
        full_msg = f"{user_input}\n\n{context}" if context else user_input

        messages.append({"role": "user", "content": full_msg})

        # Plugin hooks
        for plugin in plugins:
            with contextlib.suppress(Exception):
                plugin.on_message(user_input, "user")

        console.print("[system]🤖 Thinking...[/system]")
        start = time.time()
        response = _stream_response(client, messages, console, system_prompt)
        elapsed = time.time() - start

        if response:
            messages.append({"role": "assistant", "content": response})
            for plugin in plugins:
                with contextlib.suppress(Exception):
                    plugin.on_response(response)

        tokens = client.total_tokens()
        if tokens:
            console.print(f"[cost]⚡ {tokens:,} tokens • {elapsed:.1f}s • ${client.get_cost():.6f}[/cost]")

    # Auto-save on exit
    if messages:
        from .config import SESSIONS_DIR
        from .sessions import save_session as _save
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        name = time.strftime("%Y-%m-%d_%H-%M")
        _save(name, messages[-40:], client.provider, client.model,
              client.get_cost(), client.total_tokens(), context_files)


@main.command()
@click.argument("filepath")
@click.argument("instruction", required=False)
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def edit(filepath: str, instruction: Optional[str], provider: Optional[str], model: Optional[str]):
    """Edit a file with AI assistance."""
    cfg = load_config()
    console = _get_console()
    full_path = str(Path(filepath).resolve())
    content = read_file(full_path)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    if not instruction:
        instruction = click.prompt("[info]Edit instruction[/info]")

    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))

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

    clean = response.strip()
    if clean.startswith("```"):
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
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))

    target = str(Path(path).resolve())
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
                parts.append(f"\n## {os.path.relpath(f, target)}\n```\n{c[:5000]}\n```")
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
    """Explain a file in plain English."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
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
    """Generate unit tests for a file."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
    prompt = f"""Generate comprehensive tests using {framework} for this file.
Output ONLY the test code, no explanations.

File: {filepath}
```\n{content}\n```"""
    console.print(f"[system]🤖 Generating tests for {filepath}...[/system]\n")
    response = _stream_response(client, [{"role": "user", "content": prompt}], console)
    if response:
        p = Path(filepath)
        test_file = p.parent / f"test_{p.stem}{p.suffix}"
        clean = response.strip()
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        write_file(str(test_file), "\n".join(lines))
        console.print(f"\n[success]💾 Tests saved to: {test_file}[/success]")


@main.command()
@click.argument("filepath")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def refactor(filepath: str, provider: Optional[str], model: Optional[str]):
    """Suggest/implement refactoring for a file."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
    prompt = f"""Suggest and implement refactoring for this file. Focus on:
- DRY principle (remove duplication)
- Better naming
- Simpler logic
- Modern patterns
Output the complete refactored file.

File: {filepath}
```\n{content}\n```"""
    console.print(f"[system]🤖 Refactoring {filepath}...[/system]\n")
    response = _stream_response(client, [{"role": "user", "content": prompt}], console)
    if response:
        clean = response.strip()
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        console.print(f"\n[dim]Run /edit {filepath} to apply changes.[/dim]")


@main.command()
@click.argument("filepath")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def docstring(filepath: str, provider: Optional[str], model: Optional[str]):
    """Generate docstrings for a file."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
    prompt = f"""Add comprehensive Google-style docstrings to all functions, classes, and methods in this file.
Output ONLY the complete file with docstrings added. Keep all existing code unchanged.

File: {filepath}
```\n{content}\n```"""
    console.print(f"[system]🤖 Adding docstrings to {filepath}...[/system]\n")
    response = _stream_response(client, [{"role": "user", "content": prompt}], console)
    if response:
        clean = response.strip()
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        full_path = str(Path(filepath).resolve())
        write_file(full_path, "\n".join(lines))
        console.print(f"\n[success]✅ Docstrings added: {filepath}[/success]")


@main.command()
@click.argument("filepath")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def debug(filepath: str, provider: Optional[str], model: Optional[str]):
    """Help debug issues in a file."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
    prompt = f"""Debug this file. Identify:
- Potential bugs and errors
- Edge cases not handled
- Possible runtime errors
- Logic issues
Suggest fixes with explanations.

File: {filepath}
```\n{content}\n```"""
    console.print(f"[system]🤖 Debugging {filepath}...[/system]\n")
    _stream_response(client, [{"role": "user", "content": prompt}], console)


@main.command()
@click.argument("filepath")
@click.option("--to", "lang", required=True, help="Target language")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def translate(filepath: str, lang: str, provider: Optional[str], model: Optional[str]):
    """Translate comments and docstrings to another language."""
    cfg = load_config()
    console = _get_console()
    filepath = str(Path(filepath).resolve())
    content = read_file(filepath)
    if content is None:
        console.print(f"[error]File not found: {filepath}[/error]")
        return
    client = APIClient(provider=provider or cfg.get("provider"), api_key=cfg.get("api_key"), model=model or cfg.get("model"))
    prompt = f"""Translate all comments and docstrings in this file to {lang}.
Keep all code, variable names, and structure exactly the same.
Only translate text in comments (# ...) and docstrings ("""  """).
Output the complete file.

File: {filepath}
```\n{content}\n```"""
    console.print(f"[system]🤖 Translating {filepath} to {lang}...[/system]\n")
    response = _stream_response(client, [{"role": "user", "content": prompt}], console)
    if response:
        clean = response.strip()
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        full_path = str(Path(filepath).resolve())
        write_file(full_path, "\n".join(lines))
        console.print(f"\n[success]✅ Translated: {filepath}[/success]")


@main.command(name="history")
def show_history():
    """Show saved chat sessions."""
    console = _get_console()
    from .sessions import list_sessions
    sessions = list_sessions()
    if not sessions:
        console.print("[system]No saved sessions.[/system]")
        return
    from rich.table import Table
    table = Table(title="Session History", border_style="dim")
    table.add_column("Name", style="file_path")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Messages")
    table.add_column("Tokens")
    table.add_column("Saved")
    for s in sessions[:20]:
        table.add_row(s["name"], s["provider"], s["model"], str(s["messages"]),
                      f"{s['tokens']:,}", s["saved_at"][:16])
    console.print(table)


@main.command()
def config():
    """Show current configuration."""
    console = _get_console()
    cfg = load_config()
    display = dict(cfg)
    if display.get("api_key"):
        key = display["api_key"]
        display["api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "****"
    console.print_json(data=display)


@main.command()
@click.argument("action", default="install", type=click.Choice(["install", "generate", "capabilities"]))
def completions(action: str):
    """Manage shell completions."""
    from .shell import generate_all_completions, get_capability_report, install_completions
    if action == "install":
        success, msg = install_completions()
        if success:
            click.echo(f"✅ {msg}")
        else:
            click.echo(f"⚠ {msg}")
    elif action == "generate":
        output_dir = str(Path.home() / ".termmind" / "completions")
        results = generate_all_completions(output_dir)
        for shell, path in results.items():
            click.echo(f"  {shell}: {path}")
    elif action == "capabilities":
        report = get_capability_report()
        click.echo(json.dumps(report, indent=2))


@main.command()
@click.argument("path", default=".")
@click.option("--force", "-f", is_flag=True, help="Rebuild from scratch")
@click.option("--query", "-q", help="Query the index for matching symbols")
def index(path: str, force: bool, query: str):
    """Build or query the code context index."""
    from .memory import build_index, get_context_for_query, get_project_summary
    console = _get_console()
    if query:
        ctx = get_context_for_query(path, query)
        if ctx:
            from rich.markdown import Markdown
            console.print(Markdown(ctx))
        else:
            console.print("[dim]No matching symbols found.[/dim]")
        return
    console.print("[system]Building code index...[/system]")
    import time
    start = time.time()
    idx = build_index(path, force=force)
    elapsed = time.time() - start
    summary = get_project_summary(path)
    table = Table(title="Code Index", border_style="dim")
    table.add_column("Metric", style="info")
    table.add_column("Value")
    table.add_row("Files", str(summary["total_files"]))
    table.add_row("Functions", str(summary["total_functions"]))
    table.add_row("Classes", str(summary["total_classes"]))
    table.add_row("Languages", ", ".join(summary["languages"]))
    table.add_row("Build time", f"{elapsed:.2f}s")
    table.add_row("Cached", str(Path.home() / ".termmind" / "memory" / idx.project_hash))
    console.print(table)


@main.command()
@click.argument("path", default=".")
@click.option("--pattern", "-p", default="", help="Regex pattern to filter names")
@click.option("--type", "sym_type", default="all", type=click.Choice(["all", "functions", "classes"]))
def symbols(path: str, pattern: str, sym_type: str):
    """List functions and classes in the project index."""
    from .memory import query_classes, query_functions
    console = _get_console()
    table = Table(title="Symbols", border_style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Signature")
    table.add_column("File", style="file_path")
    table.add_column("Line", justify="right")

    if sym_type in ("all", "functions"):
        for func in query_functions(path, pattern):
            table.add_row(func["name"], "func", func.get("signature", ""),
                          func.get("file", ""), str(func.get("line", 0)))
    if sym_type in ("all", "classes"):
        for cls in query_classes(path, pattern):
            bases = ", ".join(cls.get("bases", []))
            table.add_row(cls["name"], "class", f"class {cls['name']}({bases})",
                          cls.get("file", ""), str(cls.get("line", 0)))
    console.print(table)


@main.command()
def doctors():
    """Check system health and dependencies."""
    console = _get_console()
    console.print("[bold]🏥 TermMind Health Check[/bold]\n")

    import importlib
    checks = [
        ("Python", lambda: f"{sys.version}"),
        ("click", lambda: importlib.import_module("click").__version__),
        ("rich", lambda: importlib.metadata.version("rich")),
        ("httpx", lambda: importlib.import_module("httpx").__version__),
        ("prompt_toolkit", lambda: importlib.import_module("prompt_toolkit").__version__),
    ]
    table = Table(border_style="dim")
    table.add_column("Check", style="info")
    table.add_column("Status")
    table.add_column("Detail")

    for name, check_fn in checks:
        try:
            result = check_fn()
            table.add_row(name, "[success]✅[/success]", str(result))
        except ImportError:
            table.add_row(name, "[error]❌[/error]", "Not installed")

    # Config check
    cfg = load_config()
    provider = cfg.get("provider", "ollama")
    if cfg.get("api_key") or provider == "ollama":
        table.add_row("API Key", "[success]✅[/success]", "Configured")
    else:
        table.add_row("API Key", "[warning]⚠[/warning]", "Not configured — run termmind init")

    # Git check
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        table.add_row("Git", "[success]✅[/success]", result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        table.add_row("Git", "[warning]⚠[/warning]", "Not found")

    # Connection check
    from .providers import get_provider
    try:
        p = get_provider(provider, api_key=cfg.get("api_key", ""),
                         base_url=PROVIDER_PRESETS.get(provider, {}).get("base_url", ""))
        if p.validate_connection(timeout=5):
            table.add_row("Provider connection", "[success]✅[/success]", f"{provider} is reachable")
        else:
            table.add_row("Provider connection", "[error]❌[/error]", f"{provider} unreachable")
    except Exception as e:
        table.add_row("Provider connection", "[error]❌[/error]", str(e))

    console.print(table)


@main.command()
@click.argument("path", default=".")
@click.option("--provider", "-p", help="Override provider for AI scan")
@click.option("--model", "-m", help="Override model for AI scan")
@click.option("--ai", "-a", is_flag=True, help="Use AI for deep security review")
def scan(path: str, provider: Optional[str], model: Optional[str], ai: bool):
    """Scan code for security vulnerabilities."""
    from .security import scan_directory, scan_file, ai_security_review
    cfg = load_config()
    console = _get_console()
    target = str(Path(path).resolve())

    p = Path(target)
    if ai and p.is_file():
        content = read_file(target)
        if content is None:
            console.print(f"[error]File not found: {path}[/error]")
            return
        client = APIClient(
            provider=provider or cfg.get("provider"),
            api_key=cfg.get("api_key"),
            model=model or cfg.get("model"),
        )
        console.print(f"[system]🤖 AI security review of {path}...[/system]\n")
        response = ai_security_review(client, path, content)
        console.print(Markdown(response))
        return

    console.print(f"[system]🔍 Scanning {path}...[/system]")
    if p.is_file():
        issues = scan_file(target)
    else:
        result = scan_directory(target)
        issues = result.issues

    # Display results
    from .security import ScanResult
    if p.is_file():
        result = ScanResult(files_scanned=1, issues=issues)
    
    summary = result.summary()
    table = Table(title="Security Scan Results", border_style="dim")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value")
    table.add_row("Files scanned", str(result.files_scanned))
    table.add_row("Total issues", str(summary.get("total", len(issues))))
    table.add_row("Critical", f"[red]{summary.get('critical', 0)}[/red]")
    table.add_row("High", f"[yellow]{summary.get('high', 0)}[/yellow]")
    table.add_row("Medium", f"[cyan]{summary.get('medium', 0)}[/cyan]")
    table.add_row("Low", f"[dim]{summary.get('low', 0)}[/dim]")
    console.print(table)

    if issues:
        console.print()
        for issue in issues[:20]:
            sev_color = {"critical": "red", "high": "yellow", "medium": "cyan", "low": "dim"}.get(issue.severity, "dim")
            console.print(f"  [{sev_color}][{issue.severity.upper()}][/{sev_color}] {issue.title}")
            console.print(f"    [file_path]{issue.file}:{issue.line}[/file_path]")
            console.print(f"    [dim]{issue.code_snippet[:80]}[/dim]")
            if issue.recommendation:
                console.print(f"    [green]Fix: {issue.recommendation}[/green]")
            console.print()


@main.command()
@click.argument("template_type", default="script")
@click.argument("description", required=False)
@click.option("--framework", "-f", default="", help="Framework to use")
@click.option("--output", "-o", default="", help="Output file path")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def generate(template_type: str, description: Optional[str], framework: str, output: str,
             provider: Optional[str], model: Optional[str]):
    """Generate code from a description using AI."""
    from .codegen import generate_code, generate_and_save, list_template_types
    cfg = load_config()
    console = _get_console()

    if not description:
        console.print("[bold]Available generation templates:[/bold]")
        for t in list_template_types():
            console.print(f"  [cyan]•[/cyan] {t}")
        console.print("\nUsage: [command]termmind generate <type> \"description\" [--framework X] [--output file][/command]")
        return

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    console.print(f"[system]🤖 Generating {template_type} code...[/system]\n")

    if output:
        response = generate_and_save(client, description, output, template_type, framework)
        console.print(Markdown(response))
        console.print(f"\n[success]💾 Saved to: {output}[/success]")
    else:
        response = generate_code(client, description, template_type, framework)
        console.print(Markdown(response))


@main.command(name="pipe")
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
def pipe_cmd(provider: Optional[str], model: Optional[str]):
    """Read from stdin and process with AI (pipe support)."""
    cfg = load_config()
    console = _get_console()

    if sys.stdin.isatty():
        console.print("[error]No input piped. Usage: echo 'code' | termmind pipe[/error]")
        return

    stdin_content = sys.stdin.read()
    if not stdin_content.strip():
        console.print("[error]Empty input.[/error]")
        return

    client = APIClient(
        provider=provider or cfg.get("provider"),
        api_key=cfg.get("api_key"),
        model=model or cfg.get("model"),
    )

    prompt = f"""Analyze and respond to this input. If it's code, explain it and suggest improvements.
If it's a question, answer it. If it's a command description, generate the code.

Input:
```
{stdin_content}
```"""

    _stream_response(client, [{"role": "user", "content": prompt}], console)


@main.command(name="prompts")
@click.argument("action", default="list")
@click.argument("name", required=False)
def prompts_cmd(action: str, name: Optional[str]):
    """Manage prompt templates."""
    from .promptlib import list_templates, get_template, list_categories
    console = _get_console()

    if action == "list":
        templates = list_templates()
        table = Table(title="Prompt Library", border_style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Category")
        table.add_column("Description")
        table.add_column("Tags", style="dim")
        for t in templates:
            table.add_row(t.name, t.category, t.description, ", ".join(t.tags))
        console.print(table)
    elif action == "categories":
        for cat in list_categories():
            console.print(f"  [cyan]•[/cyan] {cat}")
    elif action == "use" and name:
        t = get_template(name)
        if not t:
            console.print(f"[error]Template not found: {name}[/error]")
            return
        console.print(f"[bold]{t.name}[/bold] — {t.description}")
        console.print(f"[dim]Category: {t.category}[/dim]")
        console.print(f"[dim]Variables: {', '.join(t.variables)}[/dim]")
        console.print(f"\n[info]System prompt:[/info]\n{t.system_prompt}")
        console.print(f"\n[info]User prompt:[/info]\n{t.user_prompt}")
    else:
        console.print("Usage: termmind prompts [list|categories|use <name>]")
