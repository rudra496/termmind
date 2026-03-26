"""Color themes for TermMind."""

from rich.theme import Theme

THEMES = {
    "dark": Theme({
        "markdown.heading": "bold cyan",
        "markdown.text": "white",
        "markdown.code": "on #1a1a2e",
        "markdown.code_block": "on #1a1a2e",
        "markdown.link": "underline blue",
        "markdown.item": "yellow",
        "markdown.emphasis": "italic",
        "markdown.strong": "bold",
        "prompt": "bold green",
        "response": "white",
        "system": "dim yellow",
        "error": "bold red",
        "info": "bold blue",
        "success": "bold green",
        "warning": "bold yellow",
        "file_path": "underline blue",
        "command": "bold magenta",
        "cost": "dim",
        "divider": "dim",
    }),
    "light": Theme({
        "markdown.heading": "bold blue",
        "markdown.text": "#333333",
        "markdown.code": "on #f0f0f0",
        "markdown.code_block": "on #f0f0f0",
        "markdown.link": "underline #0066cc",
        "markdown.item": "#cc6600",
        "markdown.emphasis": "italic",
        "markdown.strong": "bold",
        "prompt": "bold green",
        "response": "#222222",
        "system": "yellow",
        "error": "bold red",
        "info": "bold blue",
        "success": "bold green",
        "warning": "bold yellow",
        "file_path": "underline #0066cc",
        "command": "bold magenta",
        "cost": "gray50",
        "divider": "gray50",
    }),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["dark"])
