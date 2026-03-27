"""Session Recorder & Replay — records entire coding sessions and replays them.

Commands:
    /record start           — Start recording session
    /record stop            — Stop recording, save to ~/.termmind/recordings/
    /record list            — List all recordings
    /record replay <name>   — Replay a recording step by step
    /record replay --speed 2x <name> — Replay at 2x speed
    /record export <name>   — Export recording as HTML timeline
"""

import difflib
import html
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

RECORDINGS_DIR = Path.home() / ".termmind" / "recordings"


class SessionRecorder:
    """Records all events in a session with timestamps."""

    def __init__(self, cwd: str = "."):
        self.cwd = cwd
        self.recording = False
        self.name = ""
        self.events: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self._file_snapshots: Dict[str, str] = {}

    def start(self, name: Optional[str] = None) -> str:
        """Start recording. Returns the recording name."""
        if self.recording:
            return self.name
        self.name = name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.recording = True
        self.events = []
        self.start_time = time.time()
        self._file_snapshots = {}
        self._add_event("system", "Recording started", {"cwd": os.path.abspath(self.cwd)})
        return self.name

    def stop(self) -> bool:
        """Stop recording and save to disk."""
        if not self.recording:
            return False
        self._add_event("system", "Recording stopped", {"duration": time.time() - self.start_time})
        self.recording = False
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = RECORDINGS_DIR / f"{self.name}.json"
        data = {
            "name": self.name,
            "created_at": datetime.now().isoformat(),
            "cwd": os.path.abspath(self.cwd),
            "duration_seconds": time.time() - self.start_time if self.start_time else 0,
            "events": self.events,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        self.events = []
        self._file_snapshots = {}
        return True

    def record_message(self, role: str, content: str):
        """Record a user or assistant message."""
        if not self.recording:
            return
        self._add_event("message", f"{role} message", {
            "role": role,
            "content": content[:10000],
        })

    def record_file_edit(self, filepath: str, old_content: str, new_content: str):
        """Record a file edit with before/after content and diff."""
        if not self.recording:
            return
        rel_path = os.path.relpath(filepath, self.cwd)
        # Generate diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}",
        ))
        self._add_event("file_edit", f"Edited {rel_path}", {
            "filepath": rel_path,
            "old_content": old_content[:10000],
            "new_content": new_content[:10000],
            "diff": diff[:5000],
            "lines_added": sum(1 for l in new_lines if not l.startswith("-")),
            "lines_removed": sum(1 for l in old_lines if not l.startswith("+")),
        })

    def record_command(self, command: str, output: str, exit_code: int):
        """Record a shell command execution."""
        if not self.recording:
            return
        self._add_event("command", f"Ran: {command[:100]}", {
            "command": command,
            "output": output[:5000],
            "exit_code": exit_code,
        })

    def record_git_operation(self, operation: str, details: str):
        """Record a git operation."""
        if not self.recording:
            return
        self._add_event("git", f"Git {operation}", {
            "operation": operation,
            "details": details[:5000],
        })

    def record_file_read(self, filepath: str, content: str):
        """Record a file being read into context."""
        if not self.recording:
            return
        rel_path = os.path.relpath(filepath, self.cwd)
        self._add_event("file_read", f"Read {rel_path}", {
            "filepath": rel_path,
            "content_length": len(content),
        })

    def record_model_change(self, new_model: str, old_model: str):
        """Record a model switch."""
        if not self.recording:
            return
        self._add_event("model_change", f"Model: {old_model} → {new_model}", {
            "old_model": old_model,
            "new_model": new_model,
        })

    def record_provider_change(self, new_provider: str, old_provider: str):
        """Record a provider switch."""
        if not self.recording:
            return
        self._add_event("provider_change", f"Provider: {old_provider} → {new_provider}", {
            "old_provider": old_provider,
            "new_provider": new_provider,
        })

    def _add_event(self, event_type: str, description: str, data: dict):
        """Add a timestamped event."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        self.events.append({
            "type": event_type,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed, 3),
            "data": data,
        })


def list_recordings() -> List[Dict[str, Any]]:
    """List all saved recordings."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    recordings = []
    for f in sorted(RECORDINGS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fh:
                data = json.load(fh)
            recordings.append({
                "name": data.get("name", f.stem),
                "created_at": data.get("created_at", ""),
                "duration_seconds": data.get("duration_seconds", 0),
                "events": len(data.get("events", [])),
                "filepath": str(f),
                "cwd": data.get("cwd", ""),
            })
        except (json.JSONDecodeError, KeyError):
            recordings.append({
                "name": f.stem,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "duration_seconds": 0,
                "events": 0,
                "filepath": str(f),
                "cwd": "",
            })
    return recordings


def load_recording(name: str) -> Optional[Dict[str, Any]]:
    """Load a recording by name or path."""
    filepath = Path(name)
    if filepath.exists():
        target = filepath
    else:
        target = RECORDINGS_DIR / f"{name}.json"
    if not target.exists():
        return None
    try:
        with open(target) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def replay_recording(name: str, console, speed: float = 1.0):
    """Replay a recording step by step, showing each event with a delay."""
    data = load_recording(name)
    if data is None:
        console.print(f"[error]Recording not found: {name}[/error]")
        return

    events = data.get("events", [])
    if not events:
        console.print("[system]Recording is empty.[/system]")
        return

    recording_name = data.get("name", name)
    created = data.get("created_at", "unknown")
    duration = data.get("duration_seconds", 0)

    console.print(f"\n[bold cyan]📹 Replaying: {recording_name}[/bold cyan]")
    console.print(f"[dim]Created: {created} | Duration: {duration:.1f}s | Events: {len(events)}[/dim]")
    console.print(f"[dim]Speed: {speed}x | Press Enter to skip to next event, Ctrl+C to quit[/dim]\n")

    base_delay = 0.5 / speed

    try:
        for i, event in enumerate(events):
            elapsed = event.get("elapsed_seconds", 0)
            event_type = event.get("type", "unknown")
            description = event.get("description", "")
            timestamp = event.get("timestamp", "")[11:19]  # HH:MM:SS
            event_data = event.get("data", {})

            # Type indicator
            type_icons = {
                "system": "🔵", "message": "💬", "file_edit": "✏️",
                "command": "⚡", "git": "🐙", "file_read": "📖",
                "model_change": "🔄", "provider_change": "🔄",
            }
            icon = type_icons.get(event_type, "📌")
            console.print(f"\n[dim]── Event {i+1}/{len(events)} ── {timestamp} (+{elapsed:.1f}s) ──[/dim]")

            if event_type == "system":
                console.print(f"  {icon} [system]{description}[/system]")
                if "duration" in event_data:
                    console.print(f"    [dim]Total duration: {event_data['duration']:.1f}s[/dim]")

            elif event_type == "message":
                role = event_data.get("role", "unknown")
                content = event_data.get("content", "")
                color = "prompt" if role == "user" else "success"
                console.print(f"  {icon} [{color}]{role.upper()}[/color]")
                # Truncate long messages
                display = content[:500]
                if len(content) > 500:
                    display += f"\n    [dim]... ({len(content)} chars total)[/dim]"
                console.print(f"    {display}")

            elif event_type == "file_edit":
                filepath = event_data.get("filepath", "")
                lines_added = event_data.get("lines_added", 0)
                lines_removed = event_data.get("lines_removed", 0)
                console.print(f"  {icon} [file_path]{filepath}[/file_path]")
                console.print(f"    [dim]+{lines_added} / -{lines_removed} lines[/dim]")
                diff = event_data.get("diff", "")
                if diff:
                    for line in diff.splitlines()[:30]:
                        if line.startswith("+"):
                            console.print(f"    [green]{html.escape(line)}[/green]")
                        elif line.startswith("-"):
                            console.print(f"    [red]{html.escape(line)}[/red]")
                        elif line.startswith("@"):
                            console.print(f"    [cyan]{html.escape(line)}[/cyan]")
                        elif line.startswith(" "):
                            console.print(f"    [dim]{html.escape(line)}[/dim]")
                    remaining = len(diff.splitlines()) - 30
                    if remaining > 0:
                        console.print(f"    [dim]... {remaining} more diff lines[/dim]")

            elif event_type == "command":
                command = event_data.get("command", "")
                exit_code = event_data.get("exit_code", 0)
                output = event_data.get("output", "")[:300]
                color = "success" if exit_code == 0 else "error"
                console.print(f"  {icon} [command]$ {command}[/command]")
                if output.strip():
                    console.print(f"    [dim]{output[:300]}[/dim]")
                console.print(f"    [{color}]Exit code: {exit_code}[/{color}]")

            elif event_type == "git":
                operation = event_data.get("operation", "")
                details = event_data.get("details", "")[:200]
                console.print(f"  {icon} [info]Git {operation}[/info]")
                if details.strip():
                    console.print(f"    [dim]{details}[/dim]")

            elif event_type == "file_read":
                filepath = event_data.get("filepath", "")
                content_length = event_data.get("content_length", 0)
                console.print(f"  {icon} [file_path]{filepath}[/file_path] [dim]({content_length:,} chars)[/dim]")

            else:
                console.print(f"  {icon} [info]{description}[/info]")
                if event_data:
                    for k, v in event_data.items():
                        console.print(f"    [dim]{k}: {str(v)[:100]}[/dim]")

            # Delay between events (skip for speed >= 4x)
            if speed < 4.0:
                time.sleep(base_delay)

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ Replay stopped by user.[/yellow]")
        return

    console.print(f"\n[success]✅ Replay finished: {recording_name} ({len(events)} events)[/success]")


def export_recording_html(name: str, output_path: Optional[str] = None) -> Optional[str]:
    """Export a recording as a beautiful HTML timeline."""
    data = load_recording(name)
    if data is None:
        return None

    events = data.get("events", [])
    recording_name = data.get("name", name)
    created = data.get("created_at", "unknown")
    duration = data.get("duration_seconds", 0)
    cwd = data.get("cwd", "")

    # Build event timeline HTML
    events_html = []
    for i, event in enumerate(events):
        elapsed = event.get("elapsed_seconds", 0)
        timestamp = event.get("timestamp", "")[11:19]
        event_type = event.get("type", "unknown")
        description = event.get("description", "")
        event_data = event.get("data", {})

        type_icons = {
            "system": "🔵", "message": "💬", "file_edit": "✏️",
            "command": "⚡", "git": "🐙", "file_read": "📖",
            "model_change": "🔄", "provider_change": "🔄",
        }
        icon = type_icons.get(event_type, "📌")

        body_html = ""
        expandable = False

        if event_type == "message":
            role = event_data.get("role", "user")
            content = html.escape(event_data.get("content", ""))
            role_class = "user-msg" if role == "user" else "ai-msg"
            body_html = f'<div class="msg {role_class}"><strong>{role.upper()}</strong><pre class="msg-content">{content}</pre></div>'
            expandable = len(content) > 200

        elif event_type == "file_edit":
            filepath = event_data.get("filepath", "")
            diff = event_data.get("diff", "")
            lines_added = event_data.get("lines_added", 0)
            lines_removed = event_data.get("lines_removed", 0)
            diff_escaped = html.escape(diff)
            # Syntax highlight the diff
            diff_escaped = diff_escaped.replace("\n+", "\n<span class='diff-add'>+")
            diff_escaped = diff_escaped.replace("\n-", "\n<span class='diff-del'>-")
            diff_escaped = diff_escaped.replace("\n@", "\n<span class='diff-hunk'>@")
            # Close spans at line ends
            diff_escaped = re.sub(r'(<span class="diff-(?:add|del|hunk)">.*?)(\n|$)', r'\1</span>\2', diff_escaped)
            body_html = f"""
                <div class="file-edit-info">
                    <strong>{html.escape(filepath)}</strong>
                    <span class="diff-stats">+{lines_added} / -{lines_removed} lines</span>
                </div>
                <pre class="diff-content">{diff_escaped}</pre>
            """
            expandable = True

        elif event_type == "command":
            command = html.escape(event_data.get("command", ""))
            exit_code = event_data.get("exit_code", 0)
            output = html.escape(event_data.get("output", ""))
            status = "success" if exit_code == 0 else "error"
            body_html = f"""
                <div class="cmd-line"><code>${command}</code> <span class="exit-{status}">exit: {exit_code}</span></div>
                <pre class="cmd-output">{output}</pre>
            """
            expandable = len(output) > 200

        elif event_type == "git":
            operation = event_data.get("operation", "")
            details = html.escape(event_data.get("details", ""))
            body_html = f"<strong>Git {html.escape(operation)}</strong><pre class='git-output'>{details}</pre>"
            expandable = len(details) > 200

        elif event_type == "file_read":
            filepath = event_data.get("filepath", "")
            content_length = event_data.get("content_length", 0)
            body_html = f"<strong>{html.escape(filepath)}</strong> <span class='dim'>({content_length:,} chars)</span>"

        else:
            body_html = f"<div>{html.escape(description)}</div>"

        expand_attr = ' data-expandable="true"' if expandable else ""
        events_html.append(f"""
            <div class="timeline-event" id="event-{i}"{expand_attr}>
                <div class="event-header" onclick="toggleEvent(event-{i})">
                    <span class="event-time">{timestamp}</span>
                    <span class="event-elapsed">+{elapsed:.1f}s</span>
                    <span class="event-icon">{icon}</span>
                    <span class="event-desc">{html.escape(description)}</span>
                    <span class="event-toggle">▼</span>
                </div>
                <div class="event-body">{body_html}</div>
            </div>
        """)

    all_events = "\n".join(events_html)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TermMind Recording — {html.escape(recording_name)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; color: #e6edf3; line-height: 1.6;
            max-width: 960px; margin: 0 auto; padding: 20px;
        }}
        h1 {{
            font-size: 1.5rem; margin-bottom: 4px; color: #58a6ff;
        }}
        .meta {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 24px; }}
        .meta span {{ margin-right: 16px; }}
        .timeline {{ position: relative; padding-left: 24px; }}
        .timeline::before {{
            content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
            width: 2px; background: #30363d;
        }}
        .timeline-event {{
            position: relative; margin-bottom: 16px;
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; overflow: hidden;
        }}
        .timeline-event::before {{
            content: ''; position: absolute; left: -20px; top: 12px;
            width: 10px; height: 10px; border-radius: 50%;
            background: #58a6ff; border: 2px solid #0d1117;
        }}
        .event-header {{
            padding: 8px 16px; cursor: pointer; display: flex;
            align-items: center; gap: 8px; font-size: 0.9rem;
        }}
        .event-header:hover {{ background: #1c2128; }}
        .event-time {{ color: #58a6ff; font-family: monospace; font-size: 0.8rem; }}
        .event-elapsed {{ color: #8b949e; font-size: 0.8rem; }}
        .event-icon {{ font-size: 1rem; }}
        .event-desc {{ color: #e6edf3; flex: 1; }}
        .event-toggle {{ color: #8b949e; font-size: 0.7rem; transition: transform 0.2s; }}
        .event-body {{ padding: 0 16px 12px; }}
        .msg {{ border-radius: 6px; padding: 8px 12px; margin-bottom: 4px; }}
        .user-msg {{ background: #1f2937; border-left: 3px solid #f59e0b; }}
        .ai-msg {{ background: #1a2332; border-left: 3px solid #3b82f6; }}
        .msg-content {{ font-family: monospace; font-size: 0.85rem; white-space: pre-wrap;
            word-break: break-word; max-height: 400px; overflow-y: auto; margin-top: 4px; }}
        .file-edit-info {{ display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 8px; }}
        .diff-stats {{ color: #8b949e; font-size: 0.8rem; }}
        .diff-content {{
            font-family: monospace; font-size: 0.82rem; background: #0d1117;
            padding: 12px; border-radius: 6px; overflow-x: auto;
            max-height: 300px; overflow-y: auto;
        }}
        .diff-add {{ color: #3fb950; }}
        .diff-del {{ color: #f85149; }}
        .diff-hunk {{ color: #58a6ff; }}
        .cmd-line {{ margin-bottom: 4px; }}
        .cmd-line code {{
            font-family: monospace; background: #1c2128; padding: 2px 8px;
            border-radius: 4px; color: #e6edf3;
        }}
        .exit-success {{ color: #3fb950; font-size: 0.8rem; }}
        .exit-error {{ color: #f85149; font-size: 0.8rem; }}
        .cmd-output, .git-output {{
            font-family: monospace; font-size: 0.82rem; background: #0d1117;
            padding: 8px; border-radius: 6px; color: #8b949e;
            max-height: 200px; overflow-y: auto; white-space: pre-wrap;
        }}
        .dim {{ color: #8b949e; }}
        pre {{ margin: 0; }}
        /* Collapsed expandable events */
        [data-expandable="true"] .event-body {{ max-height: 120px; overflow: hidden;
            position: relative; transition: max-height 0.3s; }}
        [data-expandable="true"] .event-body::after {{
            content: ''; position: absolute; bottom: 0; left: 0; right: 0;
            height: 40px; background: linear-gradient(transparent, #161b22);
            pointer-events: none;
        }}
        [data-expandable="true"].expanded .event-body {{ max-height: 2000px; }}
        [data-expandable="true"].expanded .event-body::after {{ display: none; }}
        [data-expandable="true"].expanded .event-toggle {{ transform: rotate(180deg); }}
    </style>
</head>
<body>
    <h1>📹 {html.escape(recording_name)}</h1>
    <div class="meta">
        <span>📅 {created[:19]}</span>
        <span>⏱ {duration:.1f}s</span>
        <span>📊 {len(events)} events</span>
        <span>📁 {html.escape(cwd)}</span>
    </div>
    <div class="timeline">
        {all_events}
    </div>
    <script>
        function toggleEvent(id) {{
            const el = document.getElementById(id);
            if (el) el.classList.toggle('expanded');
        }}
    </script>
</body>
</html>"""

    if output_path is None:
        output_path = os.path.join(os.getcwd(), f"termmind_recording_{recording_name}.html")
    with open(output_path, "w") as f:
        f.write(html_content)
    return output_path


def delete_recording(name: str) -> bool:
    """Delete a recording."""
    target = RECORDINGS_DIR / f"{name}.json"
    if not target.exists():
        target = Path(name)
    if target.exists():
        target.unlink()
        return True
    return False


# Global recorder instance
_recorder = None


def get_recorder(cwd: str = ".") -> SessionRecorder:
    """Get or create the global recorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = SessionRecorder(cwd=cwd)
    return _recorder


def cmd_record(rest: str, messages, client, console, cwd, ctx_files):
    """Handle /record commands."""
    parts = rest.strip().split()
    if not parts:
        console.print("[error]Usage: /record <start|stop|list|replay|export|delete> [args][/error]")
        return

    action = parts[0]
    rest_args = " ".join(parts[1:])

    if action == "start":
        recorder = get_recorder(cwd)
        if recorder.recording:
            console.print(f"[warning]⚠ Already recording: {recorder.name}[/warning]")
            return
        name = rest_args.strip() or None
        rec_name = recorder.start(name)
        console.print(f"[success]🔴 Recording started: {rec_name}[/success]")
        console.print("[dim]All messages, edits, and commands will be recorded.[/dim]")

    elif action == "stop":
        recorder = get_recorder(cwd)
        if not recorder.recording:
            console.print("[warning]⚠ No recording in progress.[/warning]")
            return
        name = recorder.name
        if recorder.stop():
            console.print(f"[success]⏹ Recording saved: {name}[/success]")
            console.print(f"[dim]Location: ~/.termmind/recordings/{name}.json[/dim]")
        else:
            console.print("[error]Failed to save recording.[/error]")

    elif action == "list":
        recordings = list_recordings()
        if not recordings:
            console.print("[system]No recordings found. Use /record start to begin.[/system]")
            return
        from rich.table import Table
        table = Table(title="📹 Recordings", border_style="dim")
        table.add_column("Name", style="file_path")
        table.add_column("Created")
        table.add_column("Duration")
        table.add_column("Events")
        for r in recordings[:20]:
            dur = r["duration_seconds"]
            dur_str = f"{dur:.0f}s" if dur < 60 else f"{dur/60:.1f}m"
            table.add_row(
                r["name"],
                r["created_at"][:16] if r["created_at"] else "",
                dur_str,
                str(r["events"]),
            )
        console.print(table)

    elif action == "replay":
        if not rest_args:
            console.print("[error]Usage: /record replay [--speed Nx] <name>[/error]")
            return
        # Parse --speed flag
        speed = 1.0
        name = rest_args
        if "--speed" in rest_args:
            match = re.search(r"--speed\s+([\d.]+(?:x)?)\s*(.*)", rest_args)
            if match:
                speed_str = match.group(1).rstrip("x")
                try:
                    speed = float(speed_str)
                    speed = max(0.25, min(speed, 16.0))
                except ValueError:
                    pass
                name = match.group(2).strip()
        if not name:
            console.print("[error]Please specify a recording name.[/error]")
            return
        replay_recording(name, console, speed=speed)

    elif action == "export":
        if not rest_args:
            console.print("[error]Usage: /record export <name>[/error]")
            return
        result = export_recording_html(rest_args.strip())
        if result:
            console.print(f"[success]📄 Exported to: {result}[/success]")
        else:
            console.print(f"[error]Recording not found: {rest_args.strip()}[/error]")

    elif action == "delete":
        if not rest_args:
            console.print("[error]Usage: /record delete <name>[/error]")
            return
        if delete_recording(rest_args.strip()):
            console.print(f"[success]🗑 Deleted recording: {rest_args.strip()}[/success]")
        else:
            console.print(f"[error]Recording not found: {rest_args.strip()}[/error]")

    else:
        console.print(f"[error]Unknown record action: {action}[/error]")
        console.print("[dim]Use: start, stop, list, replay, export, delete[/dim]")
