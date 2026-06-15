"""TermMind Textual TUI Application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from termmind.api import APIClient
from termmind.config import load_config
from termmind.tui.widgets.chat import ChatPanel
from termmind.tui.widgets.sidebar import Sidebar


class TermMindApp(App):
    """The main Terminal UI for TermMind."""

    CSS = """
    Screen {
        background: $surface;
    }

    #sidebar {
        width: 30;
        dock: left;
        border-right: solid $primary;
        height: 100%;
    }

    #main_panel {
        width: 100%;
        height: 100%;
        background: $surface-dark;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+t", "toggle_sidebar", "Sidebar"),
        ("ctrl+n", "new_chat", "New Chat"),
        ("f1", "show_help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.client = APIClient()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with Horizontal():
            yield Sidebar(id="sidebar", path=str(Path.cwd()))
            with Vertical(id="main_panel"):
                yield ChatPanel(id="chat_panel")
        yield Footer()

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display
