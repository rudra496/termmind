"""Voice Mode — text-to-speech for AI responses.

Commands:
    /voice on              — Enable voice mode
    /voice off             — Disable voice mode
    /voice speed <0.5-2.0> — Set speech speed
    /voice language <code> — Set language (en, es, fr, de, etc.)
    /voice status          — Show current voice settings
    /voice list            — List available voices

Uses pyttsx3 if installed; gracefully falls back to a notification message.
Only reads the final complete response (not streaming tokens).
"""

import os
import threading
from typing import Optional


class VoiceMode:
    """Manages text-to-speech for AI responses."""

    def __init__(self):
        self.enabled = False
        self.speed: float = 1.0
        self.language: str = "en"
        self._engine = None
        self._engine_available = None  # None = not checked yet
        self._lock = threading.Lock()
        self._queue: list = []
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_worker = False

    def _check_engine(self) -> bool:
        """Check if pyttsx3 is available."""
        if self._engine_available is not None:
            return self._engine_available
        try:
            import pyttsx3  # noqa: F401
            self._engine_available = True
        except ImportError:
            self._engine_available = False
        return self._engine_available

    def _get_engine(self):
        """Get or create the TTS engine."""
        if self._engine is None and self._check_engine():
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                # Set speed (pyttsx3 rate: ~100-300, default ~200)
                self._engine.setProperty('rate', int(200 * self.speed))
                # Try to set language
                self._set_engine_language(self.language)
            except Exception:
                self._engine = None
                self._engine_available = False
        return self._engine

    def _set_engine_language(self, lang_code: str):
        """Set the engine language if possible."""
        engine = self._get_engine()
        if engine is None:
            return
        try:
            voices = engine.getProperty('voices')
            # Try to find a voice matching the language code
            lang_lower = lang_code.lower()
            for voice in voices:
                if hasattr(voice, 'languages'):
                    for voice_lang in voice.languages:
                        if lang_lower in str(voice_lang).lower():
                            engine.setProperty('voice', voice.id)
                            return
                if hasattr(voice, 'id') and lang_lower in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    return
                if hasattr(voice, 'name') and lang_lower in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    return
        except Exception:
            pass  # Language not available, continue with default

    def enable(self, console=None) -> bool:
        """Enable voice mode. Returns True if TTS engine is available."""
        self.enabled = True
        if not self._check_engine():
            self.enabled = False
            if console:
                console.print("[warning]⚠ pyttsx3 not installed. Voice mode unavailable.[/warning]")
                console.print("[dim]Install it with: pip install pyttsx3[/dim]")
            return False
        # Pre-initialize engine
        engine = self._get_engine()
        if engine is None:
            self.enabled = False
            if console:
                console.print("[error]❌ Failed to initialize TTS engine.[/error]")
            return False
        self._start_worker()
        if console:
            console.print("[success]🔊 Voice mode enabled[/success]")
        return True

    def disable(self, console=None):
        """Disable voice mode."""
        self.enabled = False
        self._stop_worker = True
        if console:
            console.print("[system]🔇 Voice mode disabled[/system]")

    def set_speed(self, speed: float, console=None):
        """Set speech speed (0.5 - 2.0)."""
        speed = max(0.5, min(2.0, float(speed)))
        self.speed = speed
        if self._engine is not None:
            try:
                self._engine.setProperty('rate', int(200 * speed))
            except Exception:
                pass
        if console:
            console.print(f"[success]🔊 Speech speed: {speed}x[/success]")

    def set_language(self, lang: str, console=None):
        """Set language code."""
        self.language = lang
        self._set_engine_language(lang)
        if console:
            console.print(f"[success]🔊 Language: {lang}[/success]")

    def speak(self, text: str):
        """Queue text to be spoken. Runs in background thread."""
        if not self.enabled or not text:
            return
        # Clean up the text for speech
        clean_text = self._clean_text(text)
        if not clean_text.strip():
            return
        with self._lock:
            self._queue.append(clean_text)

    def speak_sync(self, text: str):
        """Speak text synchronously (blocking)."""
        if not self.enabled or not self._check_engine():
            return
        clean_text = self._clean_text(text)
        if not clean_text.strip():
            return
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', int(200 * self.speed))
            self._set_engine_language(self.language)
            engine.say(clean_text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass

    def _clean_text(self, text: str) -> str:
        """Clean text for TTS by removing markdown, code blocks, etc."""
        import re
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        # Remove inline code
        text = re.sub(r'`[^`]+`', '', text)
        # Remove markdown links
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # Remove markdown tables (replace with space)
        text = re.sub(r'\|[^\n]+\|', '', text)
        # Remove horizontal rules
        text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove emoji-like sequences (keep basic ones)
        text = re.sub(r'[\U0001F600-\U0001F9FF]+', '', text)
        # Collapse whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _start_worker(self):
        """Start the background TTS worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_worker = False
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        """Background loop that processes the TTS queue."""
        while not self._stop_worker:
            text = None
            with self._lock:
                if self._queue:
                    text = self._queue.pop(0)
            if text is None:
                import time
                time.sleep(0.1)
                continue
            try:
                engine = self._get_engine()
                if engine is not None:
                    engine.say(text)
                    engine.runAndWait()
            except Exception:
                pass

    def stop(self):
        """Stop voice mode and clean up."""
        self.enabled = False
        self._stop_worker = True
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass
            self._engine = None

    def get_voices(self) -> list:
        """List available voices."""
        if not self._check_engine():
            return []
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            result = []
            for v in voices:
                info = {
                    "id": getattr(v, 'id', 'unknown'),
                    "name": getattr(v, 'name', 'Unknown'),
                }
                if hasattr(v, 'languages'):
                    info["languages"] = [str(l) for l in v.languages]
                result.append(info)
            engine.stop()
            return result
        except Exception:
            return []

    def get_status(self) -> dict:
        """Get current voice mode status."""
        return {
            "enabled": self.enabled,
            "engine_available": self._check_engine(),
            "speed": self.speed,
            "language": self.language,
            "queue_size": len(self._queue),
        }


# Global voice mode instance
_voice = None


def get_voice_mode() -> VoiceMode:
    """Get or create the global voice mode instance."""
    global _voice
    if _voice is None:
        _voice = VoiceMode()
    return _voice


def cmd_voice(rest: str, messages, client, console, cwd, ctx_files):
    """Handle /voice commands."""
    parts = rest.strip().split()
    if not parts:
        console.print("[error]Usage: /voice <on|off|speed|language|status|list>[/error]")
        return

    action = parts[0]
    rest_args = " ".join(parts[1:])

    voice = get_voice_mode()

    if action == "on":
        voice.enable(console=console)

    elif action == "off":
        voice.disable(console=console)

    elif action == "speed":
        if not rest_args:
            console.print(f"[info]Current speed: {voice.speed}x[/info]")
            console.print("[dim]Usage: /voice speed <0.5-2.0>[/dim]")
            return
        try:
            speed = float(rest_args)
            voice.set_speed(speed, console=console)
        except ValueError:
            console.print("[error]Invalid speed. Use a number between 0.5 and 2.0[/error]")

    elif action == "language":
        if not rest_args:
            console.print(f"[info]Current language: {voice.language}[/info]")
            console.print("[dim]Usage: /voice language <en|es|fr|de|...>[/dim]")
            return
        voice.set_language(rest_args.strip(), console=console)

    elif action == "status":
        status = voice.get_status()
        from rich.table import Table
        table = Table(title="🔊 Voice Mode", border_style="dim")
        table.add_column("Setting", style="info")
        table.add_column("Value")
        table.add_row("Status", "✅ Enabled" if status["enabled"] else "❌ Disabled")
        table.add_row("Engine", "✅ pyttsx3" if status["engine_available"] else "❌ Not installed")
        table.add_row("Speed", f"{status['speed']}x")
        table.add_row("Language", status["language"])
        table.add_row("Queue", str(status["queue_size"]))
        console.print(table)

    elif action == "list":
        voices = voice.get_voices()
        if not voices:
            console.print("[warning]⚠ No TTS engine available.[/warning]")
            console.print("[dim]Install pyttsx3: pip install pyttsx3[/dim]")
            return
        from rich.table import Table
        table = Table(title="Available Voices", border_style="dim")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Languages", style="dim")
        for i, v in enumerate(voices[:20]):
            langs = ", ".join(v.get("languages", [])[:3])
            table.add_row(str(i + 1), v["name"], v["id"][:40], langs)
        console.print(table)

    else:
        console.print(f"[error]Unknown voice action: {action}[/error]")
        console.print("[dim]Use: on, off, speed, language, status, list[/dim]")
