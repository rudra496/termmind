"""Sidebar widget for TermMind TUI."""

from textual.containers import Vertical
from textual.widgets import DirectoryTree, Label


class Sidebar(Vertical):
    """Sidebar containing file tree and context info."""

    def __init__(self, widget_id: str, path: str):
        super().__init__(id=widget_id)
        self.path = path

    def compose(self):
        yield Label(" Explorer", classes="sidebar-title")
        yield DirectoryTree(self.path, id="file_tree")
        yield Label(" Context", classes="sidebar-title")
        # Placeholder for context files
        yield Label(" No files in context.", id="context_info")
