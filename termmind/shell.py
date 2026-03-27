"""Shell Integration — detect shell capabilities, generate completions."""

import os
import re
import shutil
import sys
import signal
import struct
import fcntl
import termios
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Shell Detection ──────────────────────────────────────────────────────────

def detect_shell() -> str:
    """Detect the current shell type.

    Returns one of: 'bash', 'zsh', 'fish', 'sh', 'unknown'.
    """
    # Check SHELL environment variable
    shell_path = os.environ.get("SHELL", "")
    if "zsh" in shell_path:
        return "zsh"
    if "bash" in shell_path:
        return "bash"
    if "fish" in shell_path:
        return "fish"
    if "dash" in shell_path or "sh" in shell_path:
        return "sh"

    # Check parent process
    try:
        ppid = os.getppid()
        proc_comm = f"/proc/{ppid}/comm"
        if os.path.exists(proc_comm):
            with open(proc_comm) as f:
                proc_name = f.read().strip()
            if "zsh" in proc_name:
                return "zsh"
            if "bash" in proc_name:
                return "bash"
            if "fish" in proc_name:
                return "fish"
    except (OSError, PermissionError):
        pass

    return "unknown"


def get_shell_config_path(shell: Optional[str] = None) -> Optional[str]:
    """Get the path to the shell's main config file.

    Returns the most likely config file path, or None if not found.
    """
    shell = shell or detect_shell()
    home = str(Path.home())

    candidates: Dict[str, List[str]] = {
        "bash": [
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".bash_profile"),
            os.path.join(home, ".profile"),
        ],
        "zsh": [
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".zprofile"),
        ],
        "fish": [
            os.path.join(home, ".config", "fish", "config.fish"),
            os.path.join(home, ".config", "fish", "completions", "termmind.fish"),
        ],
    }

    for candidate in candidates.get(shell, []):
        # For fish completions dir, check if parent exists
        parent = os.path.dirname(candidate)
        if os.path.isdir(parent):
            return candidate
        if os.path.exists(candidate):
            return candidate

    # Return first candidate for creation
    paths = candidates.get(shell, [])
    return paths[0] if paths else None


# ─── Terminal Capabilities ────────────────────────────────────────────────────

def get_terminal_size() -> Tuple[int, int]:
    """Get terminal dimensions (rows, columns). Returns (24, 80) as fallback."""
    try:
        cols, rows = os.get_terminal_size()
        return rows, cols
    except OSError:
        return 24, 80


def supports_truecolor() -> bool:
    """Check if the terminal supports 24-bit true color."""
    colorterm = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in colorterm or "24bit" in colorterm:
        return True
    # Check TERM
    term = os.environ.get("TERM", "")
    if term in ("xterm-256color", "screen-256color", "tmux-256color"):
        return True
    return False


def supports_unicode() -> bool:
    """Check if the terminal likely supports Unicode."""
    # Check LANG/LC_ALL for UTF-8
    lang = os.environ.get("LANG", "").lower()
    lc_all = os.environ.get("LC_ALL", "").lower()
    lc_ctype = os.environ.get("LC_CTYPE", "").lower()

    for env_var in (lc_all, lang, lc_ctype):
        if "utf-8" in env_var or "utf8" in env_var or "utf" in env_var:
            return True

    # Common terminals that support Unicode
    term = os.environ.get("TERM_PROGRAM", "")
    if term in ("iTerm.app", "WezTerm", "Hyper", "ghostty", "kitty",
                "vscode", "WindowsTerminal"):
        return True

    return False


def supports_emoji() -> bool:
    """Check if the terminal can render emoji."""
    if not supports_unicode():
        return False
    # Most modern terminals with Unicode support can render emoji
    term_program = os.environ.get("TERM_PROGRAM", "")
    no_emoji_terms = {"Apple_Terminal", "Terminal"}
    if term_program in no_emoji_terms:
        return False
    return True


def detect_copy_paste_support() -> Dict[str, bool]:
    """Detect clipboard/copy-paste support.

    Returns dict with keys: 'osc52', 'xclip', 'xsel', 'pbcopy', 'tmux'.
    """
    result: Dict[str, bool] = {
        "osc52": False,
        "xclip": False,
        "xsel": False,
        "pbcopy": False,
        "tmux": False,
    }

    # Check for clipboard tools
    result["xclip"] = shutil.which("xclip") is not None
    result["xsel"] = shutil.which("xsel") is not None
    result["pbcopy"] = shutil.which("pbcopy") is not None

    # Check for OSC 52 support (works over SSH)
    term = os.environ.get("TERM", "")
    if "screen" in term or "tmux" in term or "xterm" in term:
        result["osc52"] = True

    # Check if inside tmux
    result["tmux"] = os.environ.get("TMUX") is not None

    return result


def get_capability_report() -> Dict[str, Any]:
    """Get a full report of terminal capabilities."""
    rows, cols = get_terminal_size()
    return {
        "shell": detect_shell(),
        "terminal_size": {"rows": rows, "cols": cols},
        "term": os.environ.get("TERM", "unknown"),
        "term_program": os.environ.get("TERM_PROGRAM", "unknown"),
        "truecolor": supports_truecolor(),
        "unicode": supports_unicode(),
        "emoji": supports_emoji(),
        "copy_paste": detect_copy_paste_support(),
        "lang": os.environ.get("LANG", ""),
    }


# ─── Auto-resize Handling ────────────────────────────────────────────────────

_resize_callbacks: List = []


def on_resize(callback) -> None:
    """Register a callback for terminal resize events.

    The callback receives (rows, cols) as arguments.
    """
    _resize_callbacks.append(callback)


def setup_resize_handler() -> None:
    """Set up signal handler for SIGWINCH (terminal resize)."""
    try:
        signal.signal(signal.SIGWINCH, _handle_resize)
    except (OSError, ValueError):
        pass


def _handle_resize(signum, frame) -> None:
    """Internal handler for SIGWINCH."""
    rows, cols = get_terminal_size()
    for callback in _resize_callbacks:
        try:
            callback(rows, cols)
        except Exception:
            pass


# ─── Completion Script Generation ─────────────────────────────────────────────

TERMIND_COMMANDS = [
    "init", "chat", "ask", "edit", "review", "explain", "test",
    "refactor", "docstring", "debug", "translate", "history", "config",
    "doctors",
]

TERMIND_CHAT_COMMANDS = [
    "edit", "run", "files", "add", "remove", "search", "grep", "tree",
    "clear", "save", "load", "sessions", "model", "models", "provider",
    "providers", "cost", "theme", "themes", "undo", "diff", "status",
    "git", "export", "compact", "system", "help", "version", "quit",
]

TERMIND_GIT_SUBCOMMANDS = [
    "status", "log", "diff", "branch", "checkout", "commit",
]


def generate_bash_completion() -> str:
    """Generate a Bash completion script for termmind."""
    subcommands = " ".join(TERMIND_COMMANDS)
    chat_cmds = " ".join(TERMIND_CHAT_COMMANDS)
    git_subs = " ".join(TERMIND_GIT_SUBCOMMANDS)

    return f'''# TermMind Bash completion
_termmind_completions() {{
    local cur prev subcmd
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    if [ ${{COMP_CWORD}} -eq 1 ]; then
        COMPREPLY=( $(compgen -W "{subcommands}" -- "$cur") )
        return 0
    fi

    subcmd="${{COMP_WORDS[1]}}"

    # Global options
    case "$prev" in
        --provider|-p)
            COMPREPLY=( $(compgen -W "openai anthropic gemini groq together openrouter ollama" -- "$cur") )
            return 0
            ;;
        --model|-m)
            return 0
            ;;
        --framework|-f)
            COMPREPLY=( $(compgen -W "pytest unittest jest mocha go-test" -- "$cur") )
            return 0
            ;;
    esac

    case "$subcmd" in
        chat)
            # In chat mode, complete /commands
            if [[ "$cur" == /* ]]; then
                local slash_cmds="{chat_cmds}"
                COMPREPLY=( $(compgen -P '/' -W "$slash_cmds" -- "${{cur#/}}") )
            fi
            return 0
            ;;
        ask)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "--provider --model" -- "$cur") )
            fi
            return 0
            ;;
        edit|review|explain|test|refactor|docstring|debug)
            # File completion
            compopt -o default
            COMPREPLY=()
            return 0
            ;;
        translate)
            if [ ${{COMP_CWORD}} -eq 2 ]; then
                compopt -o default
                COMPREPLY=()
            elif [ ${{COMP_CWORD}} -eq 3 ]; then
                COMPREPLY=( $(compgen -W "--provider --model --to" -- "$cur") )
            fi
            return 0
            ;;
    esac

    # Long options for any subcommand
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "--provider --model --help" -- "$cur") )
    fi
}}

_termmind_chat_completions() {{
    local cur prev
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    # Complete slash commands
    if [[ "$cur" == /* ]]; then
        local slash_cmds="{chat_cmds}"
        COMPREPLY=( $(compgen -P '/' -W "$slash_cmds" -- "${{cur#/}}") )
        return 0
    fi

    # Sub-command arguments
    case "$prev" in
        /edit|/explain|/test|/refactor|/docstring|/debug)
            compopt -o default
            COMPREPLY=()
            return 0
            ;;
        /model)
            return 0
            ;;
        /provider)
            COMPREPLY=( $(compgen -W "openai anthropic gemini groq together openrouter ollama" -- "$cur") )
            return 0
            ;;
        /theme)
            COMPREPLY=( $(compgen -W "dark light monokai solarized dracula nord gruvbox" -- "$cur") )
            return 0
            ;;
        /git)
            COMPREPLY=( $(compgen -W "{git_subs}" -- "$cur") )
            return 0
            ;;
    esac
}}

complete -F _termmind_completions termmind
'''


def generate_zsh_completion() -> str:
    """Generate a Zsh completion script for termmind."""
    commands_list = " \\\n    ".join(f'"{c}"' for c in TERMIND_COMMANDS)
    chat_list = " \\\n    ".join(f'"{c}"' for c in TERMIND_CHAT_COMMANDS)

    return f'''#compdef termmind

_termmind_commands() {{
    local -a commands
    commands=(
{commands_list}
    )
    _describe 'command' commands
}}

_termmind() {{
    local curcontext="$curcontext" state line
    typeset -A opt_args

    _arguments -C \\
        '--provider[AI provider]:provider:(openai anthropic gemini groq together openrouter ollama)' \\
        '--model[Model name]:model:' \\
        '--help[Show help]' \\
        '1: :_termmind_commands' \\
        '*::arg:->args'

    case $line[1] in
        edit|review|explain|test|refactor|docstring|debug|translate)
            _arguments '*:file:_files' && return 0
            ;;
        ask)
            _arguments '*:question:' && return 0
            ;;
    esac
}}

_termmind "$@"
'''


def generate_fish_completion() -> str:
    """Generate a Fish shell completion script for termmind."""
    commands_lines = "\n".join(
        f"complete -c termmind -f -n '__fish_is_first_arg' -a {c}"
        for c in TERMIND_COMMANDS
    )
    return f'''# TermMind Fish shell completion

# Disable file completions for the main command
complete -c termmind -f

# Top-level commands
{commands_lines}

# Option completions
complete -c termmind -l provider -s p -d 'AI provider' -xa "openai anthropic gemini groq together openrouter ollama"
complete -c termmind -l model -s m -d 'Model name'
complete -c termmind -l framework -s f -d 'Test framework' -xa "pytest unittest jest"

# File argument for edit, review, explain, etc.
complete -c termmind -f -n '__fish_seen_subcommand_from edit review explain test refactor docstring debug' -a '(frog "*")'

# Ask takes any argument (no file restriction)
complete -c termmind -f -n '__fish_seen_subcommand_from ask'
'''


def install_completions(shell: Optional[str] = None) -> Tuple[bool, str]:
    """Install shell completion scripts.

    Returns (success, message).
    """
    shell = shell or detect_shell()
    config_path = get_shell_config_path(shell)

    if not config_path:
        return False, f"Could not determine config path for shell: {shell}"

    completion_dir = Path.home() / ".termmind" / "completions"
    completion_dir.mkdir(parents=True, exist_ok=True)

    if shell == "bash":
        script = generate_bash_completion()
        comp_file = completion_dir / "termmind.bash"
        comp_file.write_text(script)

        # Add source line to bashrc
        source_line = f"\n# TermMind completions\n[ -f {comp_file} ] && source {comp_file}\n"
        if os.path.exists(config_path):
            with open(config_path) as f:
                content = f.read()
            if "termmind" not in content.lower():
                with open(config_path, "a") as f:
                    f.write(source_line)
                return True, f"Completions installed. Restart shell or run: source {config_path}"
            else:
                return True, "Completions already installed."
        else:
            return False, f"Config file not found: {config_path}"

    elif shell == "zsh":
        script = generate_zsh_completion()
        comp_file = completion_dir / "_termmind"
        comp_file.write_text(script)

        # Add to fpath
        source_line = f"\n# TermMind completions\nfpath=({completion_dir} $fpath)\n"
        if os.path.exists(config_path):
            with open(config_path) as f:
                content = f.read()
            if "termmind" not in content.lower():
                with open(config_path, "a") as f:
                    f.write(source_line)
                return True, f"Completions installed. Restart shell or run: source {config_path}"
            else:
                return True, "Completions already installed."
        else:
            return False, f"Config file not found: {config_path}"

    elif shell == "fish":
        script = generate_fish_completion()
        comp_dir = Path(config_path).parent  # completions dir
        if comp_dir.name != "completions":
            comp_dir = Path.home() / ".config" / "fish" / "completions"
        comp_dir.mkdir(parents=True, exist_ok=True)
        comp_file = comp_dir / "termmind.fish"
        comp_file.write_text(script)
        return True, f"Completions installed to {comp_file}. Fish picks them up automatically."

    else:
        return False, f"Shell completions not supported for: {shell}"


def generate_all_completions(output_dir: str) -> Dict[str, str]:
    """Generate all completion scripts and save to a directory.

    Returns dict of shell -> file path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = {}
    for shell_name, gen_fn in [
        ("bash", generate_bash_completion),
        ("zsh", generate_zsh_completion),
        ("fish", generate_fish_completion),
    ]:
        ext = {3: "bash"}.get(shell_name, shell_name)
        filename = f"termmind.{ext}" if shell_name != "zsh" else "_termmind"
        filepath = out / filename
        filepath.write_text(gen_fn())
        results[shell_name] = str(filepath)

    return results
