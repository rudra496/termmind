"""Smart Diff Preview System — beautiful, interactive diff views in the terminal."""

import difflib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


class EditType(Enum):
    """Type of edit detected between file versions."""
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    MOVE = "move"
    RENAME = "rename"
    IDENTICAL = "identical"
    NEW_FILE = "new_file"
    DELETED_FILE = "deleted_file"


@dataclass
class DiffStats:
    """Statistics for a diff operation."""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    insertions_by_file: Dict[str, int] = field(default_factory=dict)
    deletions_by_file: Dict[str, int] = field(default_factory=dict)

    def summary_text(self) -> str:
        """Return a human-readable summary string."""
        parts = []
        if self.files_changed:
            parts.append(f"{self.files_changed} file{'s' if self.files_changed != 1 else ''}")
        if self.insertions:
            parts.append(f"+{self.insertions}")
        if self.deletions:
            parts.append(f"-{self.deletions}")
        return ", ".join(parts) if parts else "no changes"


@dataclass
class DiffHunk:
    """A single hunk from a unified diff."""
    old_start: int = 0
    old_count: int = 0
    new_start: int = 0
    new_count: int = 0
    header: str = ""
    lines: List[Tuple[str, str]] = field(default_factory=list)  # (tag, text)
    accepted: Optional[bool] = None  # None = not yet decided

    @property
    def has_changes(self) -> bool:
        """Whether this hunk contains any actual changes."""
        return any(tag in ("+", "-") for tag, _ in self.lines)

    @property
    def insertions(self) -> int:
        return sum(1 for tag, _ in self.lines if tag == "+")

    @property
    def deletions(self) -> int:
        return sum(1 for tag, _ in self.lines if tag == "-")


@dataclass
class FileDiff:
    """Diff information for a single file."""
    old_path: str = ""
    new_path: str = ""
    edit_type: EditType = EditType.IDENTICAL
    hunks: List[DiffHunk] = field(default_factory=list)
    old_content: str = ""
    new_content: str = ""

    @property
    def display_path(self) -> str:
        """Get display-friendly path showing rename if applicable."""
        if self.edit_type == EditType.RENAME and self.old_path != self.new_path:
            return f"{self.old_path} → {self.new_path}"
        return self.new_path or self.old_path

    @property
    def insertions(self) -> int:
        return sum(h.insertions for h in self.hunks)

    @property
    def deletions(self) -> int:
        return sum(h.deletions for h in self.hunks)


@dataclass
class MultiFileDiff:
    """Collection of diffs across multiple files."""
    files: List[FileDiff] = field(default_factory=list)

    def get_stats(self) -> DiffStats:
        """Calculate aggregate statistics."""
        stats = DiffStats()
        for fd in self.files:
            if fd.edit_type not in (EditType.IDENTICAL, EditType.MOVE):
                stats.files_changed += 1
            ins = fd.insertions
            dels = fd.deletions
            stats.insertions += ins
            stats.deletions += dels
            path = fd.display_path
            if ins:
                stats.insertions_by_file[path] = ins
            if dels:
                stats.deletions_by_file[path] = dels
        return stats

    def get_changed_files(self) -> List[FileDiff]:
        """Return only files with actual changes."""
        return [f for f in self.files if f.edit_type != EditType.IDENTICAL]


# ─── Diff Generation ──────────────────────────────────────────────────────────

def _detect_edit_type(old_content: str, new_content: str,
                      old_path: str, new_path: str) -> EditType:
    """Detect the type of edit between two file states."""
    if not old_content and new_content:
        return EditType.NEW_FILE
    if old_content and not new_content:
        return EditType.DELETED_FILE
    if old_content == new_content:
        return EditType.IDENTICAL
    # Check for rename by comparing just the filenames at different paths
    if old_path and new_path and old_path != new_path:
        # If content is very similar, it might be a rename
        ratio = difflib.SequenceMatcher(None, old_content, new_content).ratio()
        if ratio > 0.95:
            return EditType.RENAME
    # Check for move: large content identical, location changed
    if old_path and new_path:
        old_basename = os.path.basename(old_path)
        new_basename = os.path.basename(new_path)
        if old_basename == new_basename and old_path != new_path:
            ratio = difflib.SequenceMatcher(None, old_content, new_content).ratio()
            if ratio > 0.8:
                return EditType.MOVE
    # Check if it's mostly insertions
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    matched = sum(size for _, _, size in sm.get_matching_blocks())
    # Count new lines not in old
    new_only = len(new_lines) - matched
    old_only = len(old_lines) - matched
    if old_only == 0 and new_only > 0:
        return EditType.INSERT
    if new_only == 0 and old_only > 0:
        return EditType.DELETE
    return EditType.REPLACE


def _parse_unified_diff(diff_text: str) -> List[DiffHunk]:
    """Parse unified diff text into hunks."""
    hunks: List[DiffHunk] = []
    current_hunk: Optional[DiffHunk] = None

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            if current_hunk:
                hunks.append(current_hunk)
            # Parse @@ -old_start,old_count +new_start,new_count @@
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                current_hunk = DiffHunk(
                    old_start=int(m.group(1)),
                    old_count=int(m.group(2)) if m.group(2) else 1,
                    new_start=int(m.group(3)),
                    new_count=int(m.group(4)) if m.group(4) else 1,
                    header=line,
                )
            continue

        if current_hunk is not None:
            if line.startswith("+"):
                current_hunk.lines.append(("+", line[1:]))
            elif line.startswith("-"):
                current_hunk.lines.append(("-", line[1:]))
            elif line.startswith(" "):
                current_hunk.lines.append((" ", line[1:]))

    if current_hunk:
        hunks.append(current_hunk)
    return hunks


def compute_file_diff(old_content: str, new_content: str,
                      old_path: str = "", new_path: str = "",
                      context_lines: int = 3) -> FileDiff:
    """Compute a FileDiff between two content strings."""
    edit_type = _detect_edit_type(old_content, new_content, old_path, new_path)
    if edit_type in (EditType.IDENTICAL,):
        return FileDiff(old_path=old_path, new_path=new_path,
                        edit_type=edit_type, old_content=old_content,
                        new_content=new_content)

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff_text = "".join(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=old_path or "a", tofile=new_path or "b",
        n=context_lines,
    ))
    hunks = _parse_unified_diff(diff_text)

    return FileDiff(
        old_path=old_path, new_path=new_path,
        edit_type=edit_type, hunks=hunks,
        old_content=old_content, new_content=new_content,
    )


def compute_diff_from_disk(old_path: str, new_content: str) -> FileDiff:
    """Compute diff between a file on disk and new content."""
    old_content = ""
    if os.path.exists(old_path):
        with open(old_path, "r", encoding="utf-8", errors="replace") as f:
            old_content = f.read()
    return compute_file_diff(old_content, new_content,
                             old_path=old_path, new_path=old_path)


def compute_multi_file_diff(changes: Dict[str, str],
                            old_contents: Optional[Dict[str, str]] = None) -> MultiFileDiff:
    """Compute diffs for multiple files at once.

    Args:
        changes: mapping of filepath -> new content
        old_contents: optional mapping of filepath -> old content (reads from disk if not provided)
    """
    if old_contents is None:
        old_contents = {}
    diffs: List[FileDiff] = []
    for filepath, new_content in changes.items():
        old_content = old_contents.get(filepath, "")
        if not old_content and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    old_content = f.read()
            except OSError:
                old_content = ""
        diffs.append(compute_file_diff(old_content, new_content,
                                       filepath, filepath))
    return MultiFileDiff(files=diffs)


# ─── Rendering ────────────────────────────────────────────────────────────────

def _render_inline_hunk(hunk: DiffHunk, line_numbers: bool = True) -> Text:
    """Render a single hunk as inline colored diff text."""
    text = Text()
    old_lineno = hunk.old_start
    new_lineno = hunk.new_start

    if line_numbers:
        header = Text(f"  {hunk.header}\n", style="dim")
        text.append(header)

    for tag, content in hunk.lines:
        # Strip trailing newline for display
        display_line = content.rstrip("\n\r")
        if tag == "+":
            prefix = "+"
            line_text = Text(f"{prefix} {display_line}\n")
            line_text.stylize("diff.plus", 0, len(prefix))
            line_text.stylize("diff.plus_text", len(prefix))
            text.append(line_text)
            new_lineno += 1
        elif tag == "-":
            prefix = "-"
            line_text = Text(f"{prefix} {display_line}\n")
            line_text.stylize("diff.minus", 0, len(prefix))
            line_text.stylize("diff.minus_text", len(prefix))
            text.append(line_text)
            old_lineno += 1
        else:
            prefix = " "
            text.append(f"{prefix}{display_line}\n", style="dim")
            old_lineno += 1
            new_lineno += 1

    return text


def _render_side_by_side(hunk: DiffHunk, width: int = 80) -> Group:
    """Render a single hunk in side-by-side layout."""
    half_width = max(width // 2 - 4, 20)
    left_lines: List[Text] = []
    right_lines: List[Text] = []

    old_lineno = hunk.old_start
    new_lineno = hunk.new_start

    for tag, content in hunk.lines:
        display_line = content.rstrip("\n\r")
        if tag == "+":
            left_lines.append(Text(" " * half_width))
            t = Text(display_line)
            t.stylize("diff.plus_text")
            right_lines.append(t)
            new_lineno += 1
        elif tag == "-":
            t = Text(display_line)
            t.stylize("diff.minus_text")
            left_lines.append(t)
            right_lines.append(Text(" " * half_width))
            old_lineno += 1
        else:
            left_lines.append(Text(display_line, style="dim"))
            right_lines.append(Text(display_line, style="dim"))
            old_lineno += 1
            new_lineno += 1

    left_panel = Panel(
        Group(*left_lines),
        title=f"[dim]Old (line {hunk.old_start})[/dim]",
        border_style="red",
        width=half_width + 4,
        padding=(0, 1),
    )
    right_panel = Panel(
        Group(*right_lines),
        title=f"[dim]New (line {hunk.new_start})[/dim]",
        border_style="green",
        width=half_width + 4,
        padding=(0, 1),
    )
    return Group(left_panel, right_panel)


def render_diff_inline(file_diff: FileDiff, console: Console) -> None:
    """Render a complete file diff in inline format (like git diff)."""
    if file_diff.edit_type == EditType.IDENTICAL:
        return

    # File header
    type_icons = {
        EditType.INSERT: "📝", EditType.DELETE: "🗑️", EditType.REPLACE: "✏️",
        EditType.RENAME: "🔄", EditType.MOVE: "📦",
        EditType.NEW_FILE: "🆕", EditType.DELETED_FILE: "💀",
    }
    icon = type_icons.get(file_diff.edit_type, "📝")
    header = f"{icon} {file_diff.display_path}"
    console.print(f"\n[bold cyan]{header}[/bold cyan]")

    # Edit type badge
    type_label = file_diff.edit_type.value.replace("_", " ").title()
    console.print(f"  [dim]{type_label}[/dim]  ", end="")
    if file_diff.insertions:
        console.print(f"[diff.plus]+{file_diff.insertions}[/diff.plus]", end="")
    if file_diff.deletions:
        console.print(f" [diff.minus]-{file_diff.deletions}[/diff.minus]", end="")
    console.print()

    for hunk in file_diff.hunks:
        text = _render_inline_hunk(hunk)
        console.print(text)


def render_diff_side_by_side(file_diff: FileDiff, console: Console,
                             width: Optional[int] = None) -> None:
    """Render a file diff in side-by-side format."""
    if file_diff.edit_type == EditType.IDENTICAL:
        return

    term_width = width or console.width or 120
    console.print(f"\n[bold cyan]📄 {file_diff.display_path}[/bold cyan]")

    for hunk in file_diff.hunks:
        if not hunk.has_changes:
            continue
        group = _render_side_by_side(hunk, width=term_width)
        console.print(group)
        console.print()  # spacing between hunks


def render_multi_diff(multi_diff: MultiFileDiff, console: Console,
                      side_by_side: bool = False) -> None:
    """Render all file diffs in a MultiFileDiff."""
    stats = multi_diff.get_stats()

    # Summary header
    console.print()
    console.rule(f"[bold]Diff Summary: {stats.summary_text()}[/bold]")

    changed = multi_diff.get_changed_files()
    if not changed:
        console.print("[dim]No changes detected.[/dim]")
        return

    # File list summary
    summary_table = Table(box=box.SIMPLE, border_style="dim")
    summary_table.add_column("File", style="file_path")
    summary_table.add_column("Type", style="dim")
    summary_table.add_column("+", style="diff.plus", justify="right")
    summary_table.add_column("-", style="diff.minus", justify="right")

    for fd in changed:
        ins = fd.insertions
        dels = fd.deletions
        type_label = fd.edit_type.value.replace("_", " ").title()
        summary_table.add_row(fd.display_path, type_label,
                              f"+{ins}" if ins else "",
                              f"-{dels}" if dels else "")
    console.print(summary_table)
    console.print()

    # Detailed diffs
    for fd in changed:
        if side_by_side:
            render_diff_side_by_side(fd, console)
        else:
            render_diff_inline(fd, console)


# ─── Interactive Hunk Confirmation ────────────────────────────────────────────

def _prompt_hunk_action(console: Console, hunk: DiffHunk, file_path: str,
                        index: int, total: int) -> str:
    """Prompt user to accept/reject a single hunk. Returns 'y', 'n', 'q', or 'a'."""
    console.print(f"\n[bold]Hunk {index + 1}/{total}[/bold] — "
                  f"[file_path]{file_path}[/file_path]")
    console.print(f"  [dim]{hunk.header}[/dim]")
    console.print(f"  [diff.plus]+{hunk.insertions}[/diff.plus]  "
                  f"[diff.minus]-{hunk.deletions}[/diff.minus]")
    console.print()
    text = _render_inline_hunk(hunk)
    console.print(text)
    console.print()

    try:
        choice = input("  [y]es / [n]o / [q]uit / accept [a]ll: ").strip().lower()
        return choice
    except (EOFError, KeyboardInterrupt):
        return "q"


def apply_hunks_interactive(file_diff: FileDiff, console: Console) -> Optional[str]:
    """Interactively review hunks and build a patched result.

    Returns the final content after applying accepted hunks, or None if aborted.
    """
    if not file_diff.hunks:
        return file_diff.new_content

    # Filter to only hunks that have changes
    change_hunks = [h for h in file_diff.hunks if h.has_changes]
    if not change_hunks:
        return file_diff.new_content

    old_lines = file_diff.old_content.splitlines()
    result_lines = list(old_lines)

    # Build a map of old line ranges -> replacement
    # We process hunks in reverse order to preserve line numbers
    accept_all = False
    aborted = False

    for i, hunk in enumerate(change_hunks):
        if not accept_all:
            choice = _prompt_hunk_action(console, hunk, file_diff.display_path,
                                         i, len(change_hunks))
            if choice == "q":
                aborted = True
                break
            elif choice == "a":
                accept_all = True
            elif choice == "n":
                continue

        # Apply the hunk: find the old lines and replace with new lines
        # Extract removals (lines with "-") and additions (lines with "+")
        removals = [text for tag, text in hunk.lines if tag == "-"]
        additions = [text for tag, text in hunk.lines if tag == "+"]

        # Find where in result_lines the removal lines are
        # Start searching from hunk.old_start - 1
        search_start = hunk.old_start - 1
        if search_start < 0:
            search_start = 0

        # Find the sequence of removal lines in the result
        found = False
        if removals:
            # Find each removal line in order
            positions = []
            pos = search_start
            for rem_line in removals:
                while pos < len(result_lines):
                    if result_lines[pos].rstrip("\n\r") == rem_line.rstrip("\n\r"):
                        positions.append(pos)
                        pos += 1
                        break
                    pos += 1

            if len(positions) == len(removals):
                # Replace: remove old lines, insert new ones
                for offset, pos in enumerate(positions):
                    if offset == 0:
                        result_lines[pos] = additions[offset] if offset < len(additions) else result_lines[pos]
                    else:
                        if offset - 1 < len(additions) - 1:
                            result_lines[pos] = additions[offset]
                # Handle extra additions beyond removals
                if len(additions) > len(removals) and positions:
                    for extra_idx in range(len(removals), len(additions)):
                        result_lines.insert(positions[-1] + 1, additions[extra_idx])
                found = True

        if not found and additions:
            # Insert additions at the old start position if we couldn't match removals
            insert_pos = min(hunk.old_start - 1 + hunk.old_count, len(result_lines))
            for offset, add_line in enumerate(additions):
                result_lines.insert(insert_pos + offset, add_line)

    if aborted:
        console.print("[yellow]⚠ Diff application aborted by user.[/yellow]")
        return None

    return "\n".join(result_lines)


def apply_multi_diff_interactive(multi_diff: MultiFileDiff,
                                 console: Console) -> Dict[str, Optional[str]]:
    """Interactively review and apply diffs for multiple files.

    Returns dict mapping filepath -> final content (or None if skipped).
    """
    results: Dict[str, Optional[str]] = {}
    changed = multi_diff.get_changed_files()

    if not changed:
        console.print("[dim]No changes to apply.[/dim]")
        return results

    console.print(f"\n[bold]Reviewing {len(changed)} file(s) with changes:[/bold]\n")

    for i, fd in enumerate(changed):
        console.rule(f"[bold]File {i + 1}/{len(changed)}: {fd.display_path}[/bold]")
        try:
            choice = input("  [r]eview hunks / [a]ccept all / [s]kip: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]⚠ Interrupted.[/yellow]")
            break

        if choice == "s":
            results[fd.new_path or fd.old_path] = None
            continue
        elif choice == "a":
            results[fd.new_path or fd.old_path] = fd.new_content
            console.print(f"  [success]✅ Accepted all changes to {fd.display_path}[/success]")
            continue
        elif choice == "r":
            result = apply_hunks_interactive(fd, console)
            if result is not None:
                results[fd.new_path or fd.old_path] = result
                console.print(f"  [success]✅ Applied accepted hunks to {fd.display_path}[/success]")
            else:
                results[fd.new_path or fd.old_path] = None
        else:
            results[fd.new_path or fd.old_path] = None

    return results


# ─── Preview Helper (integration with cli.py) ─────────────────────────────────

def preview_and_confirm_edit(filepath: str, old_content: str,
                             new_content: str, console: Console) -> bool:
    """Show a diff preview and ask for confirmation. Returns True if accepted."""
    file_diff = compute_file_diff(old_content, new_content,
                                   old_path=filepath, new_path=filepath)
    render_diff_inline(file_diff, console)

    stats = file_diff.insertions + file_diff.deletions
    if stats == 0:
        console.print("[dim]No changes detected.[/dim]")
        return True

    try:
        choice = input("\n  Apply these changes? [Y/n]: ").strip().lower()
        return choice in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def preview_edit_with_hunks(filepath: str, old_content: str,
                            new_content: str, console: Console) -> Optional[str]:
    """Show diff with hunk-by-hunk confirmation. Returns final content or None."""
    file_diff = compute_file_diff(old_content, new_content,
                                   old_path=filepath, new_path=filepath)
    return apply_hunks_interactive(file_diff, console)


def generate_diff_stats_text(old_content: str, new_content: str,
                             filepath: str = "") -> str:
    """Generate a compact one-line diff stats string for display."""
    fd = compute_file_diff(old_content, new_content, filepath, filepath)
    ins = fd.insertions
    dels = fd.deletions
    if ins == 0 and dels == 0:
        return "no changes"
    parts = []
    if ins:
        parts.append(f"[diff.plus]+{ins}[/diff.plus]")
    if dels:
        parts.append(f"[diff.minus]-{dels}[/diff.minus]")
    return " ".join(parts)
