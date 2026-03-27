"""Color themes for TermMind."""

from rich.theme import Theme

THEMES: dict = {}


def _make_theme(name: str, **styles) -> Theme:
    base = {
        "markdown.heading": "bold cyan",
        "markdown.text": "white",
        "markdown.code": "on #1a1a2e",
        "markdown.code_block": "on #1a1a2e",
        "markdown.link": "underline blue",
        "markdown.item": "yellow",
        "markdown.emphasis": "italic",
        "markdown.strong": "bold",
        "markdown.list": "yellow",
        "markdown.block": "italic",
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
    }
    base.update(styles)
    return Theme(base)


THEMES["dark"] = _make_theme("dark")

THEMES["light"] = _make_theme(
    "light",
    markdown_heading="bold blue",
    markdown_text="#333333",
    markdown_code="on #f0f0f0",
    markdown_code_block="on #f0f0f0",
    markdown_link="underline #0066cc",
    markdown_item="#cc6600",
    response="#222222",
    system="yellow",
    file_path="underline #0066cc",
    cost="gray50",
    divider="gray50",
)

THEMES["solarized"] = _make_theme(
    "solarized",
    markdown_heading="bold #268bd2",
    markdown_text="#839496",
    markdown_code="on #073642",
    markdown_code_block="on #073642",
    prompt="bold #859900",
    response="#93a1a1",
    system="#b58900",
    error="bold #dc322f",
    info="bold #268bd2",
    success="bold #859900",
    warning="bold #b58900",
    file_path="underline #268bd2",
    command="bold #d33682",
)

THEMES["dracula"] = _make_theme(
    "dracula",
    markdown_heading="bold #bd93f9",
    markdown_text="#f8f8f2",
    markdown_code="on #44475a",
    markdown_code_block="on #282a36",
    markdown_link="underline #8be9fd",
    markdown_item="#f1fa8c",
    prompt="bold #50fa7b",
    response="#f8f8f2",
    system="#ffb86c",
    error="bold #ff5555",
    info="bold #8be9fd",
    success="bold #50fa7b",
    warning="bold #f1fa8c",
    file_path="underline #8be9fd",
    command="bold #ff79c6",
    cost="#6272a4",
    divider="#6272a4",
)

THEMES["monokai"] = _make_theme(
    "monokai",
    markdown_heading="bold #a6e22e",
    markdown_text="#f8f8f2",
    markdown_code="on #49483e",
    markdown_code_block="on #272822",
    markdown_link="underline #66d9ef",
    markdown_item="#e6db74",
    prompt="bold #a6e22e",
    response="#f8f8f2",
    system="#fd971f",
    error="bold #f92672",
    info="bold #66d9ef",
    success="bold #a6e22e",
    warning="bold #e6db74",
    file_path="underline #66d9ef",
    command="bold #ae81ff",
    cost="#75715e",
    divider="#75715e",
)


def get_theme(name: str) -> Theme:
    """Get a theme by name, falling back to dark."""
    return THEMES.get(name, THEMES["dark"])


def list_themes() -> list:
    """Return list of available theme names."""
    return list(THEMES.keys())
