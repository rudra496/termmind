"""Utility functions: token counting, cost calculation, markdown rendering."""

import re
from typing import Dict, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.theme import Theme

# Cost per 1k tokens for various models
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gemini-2.0-flash": {"input": 0.0, "output": 0.0},
    "gemini-1.5-pro": {"input": 0.0, "output": 0.0},
    "llama-3.3-70b-versatile": {"input": 0.0, "output": 0.0},
    "llama-3.1-8b-instant": {"input": 0.0, "output": 0.0},
    "llama3.2": {"input": 0.0, "output": 0.0},
}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~4 chars per token for English)."""
    if not text:
        return 0
    return len(text) // 4


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate cost for a request."""
    costs = MODEL_COSTS.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])


def detect_language(filename: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby", ".c": "c", ".cpp": "cpp",
        ".h": "c", ".cs": "csharp", ".php": "php", ".sh": "bash", ".bash": "bash",
        ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".json": "json",
        ".md": "markdown", ".html": "html", ".css": "css", ".sql": "sql",
        ".swift": "swift", ".kt": "kotlin", ".scala": "scala", ".lua": "lua",
        ".r": "r", ".dart": "dart", ".jsx": "jsx", ".tsx": "tsx",
        ".dockerfile": "docker", ".makefile": "makefile",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    # Special cases
    fn_lower = filename.lower()
    if fn_lower in ("dockerfile", "makefile", "cmakelists.txt"):
        return "docker" if "docker" in fn_lower else "makefile"
    return ext_map.get(ext)


def render_markdown(text: str, console: Optional[Console] = None) -> None:
    """Render markdown text to terminal using Rich."""
    if console is None:
        console = Console()
    md = Markdown(text)
    console.print(md)


def extract_code_blocks(text: str) -> list:
    """Extract code blocks from markdown text."""
    pattern = r"```(\w*)\n(.*?)```"
    return re.findall(pattern, text, re.DOTALL)


def format_file_path(path: str) -> str:
    """Format a file path for display (clickable-style)."""
    return f"\033[4;34m{path}\033[0m"


def truncate_text(text: str, max_length: int = 2000, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
