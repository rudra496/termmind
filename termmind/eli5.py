"""Explain Like I'm 5 Mode — simplifies AI responses."""

from typing import Optional

ELI5_SYSTEM_PROMPT = """You are an AI assistant that explains things in the simplest possible terms, as if talking to a curious 5-year-old child. 

Rules:
- Use very simple words and short sentences
- Compare complex concepts to everyday things a child knows (toys, food, animals, games)
- Use lots of analogies and metaphors
- Keep explanations under 200 words unless asked for more
- If the user asks something truly inappropriate for a child, gently redirect
- Never be condescending — be warm, patient, and enthusiastic
- End with a simple follow-up question to encourage curiosity
- Use emojis occasionally to make it friendly"""

class ELI5Mode:
    """Manages Explain Like I'm 5 mode for AI responses."""

    def __init__(self):
        self.enabled = False

    def enable(self) -> None:
        """Enable ELI5 mode."""
        self.enabled = True

    def disable(self) -> None:
        """Disable ELI5 mode."""
        self.enabled = False

    def toggle(self) -> bool:
        """Toggle ELI5 mode on/off. Returns new state."""
        self.enabled = not self.enabled
        return self.enabled

    def is_enabled(self) -> bool:
        """Check if ELI5 mode is active."""
        return self.enabled

    def get_system_prompt(self) -> Optional[str]:
        """Return the ELI5 system prompt if enabled, else None."""
        if self.enabled:
            return ELI5_SYSTEM_PROMPT
        return None

    def modify_user_message(self, message: str) -> str:
        """Prepend ELI5 context to user message if mode is on."""
        if not self.enabled:
            return message
        return f"[ELI5 Mode — explain simply] {message}"

    def get_status_text(self) -> str:
        """Get status display text."""
        status = "🧒 ON" if self.enabled else "🧒 OFF"
        return f"ELI5 Mode: {status}"

    def get_help_text(self) -> str:
        """Get help text for ELI5 mode."""
        return """ELI5 (Explain Like I'm 5) Mode:
  /eli5 <topic>    — Explain a topic in simple terms
  /eli5 mode on    — Enable ELI5 mode for all responses
  /eli5 mode off   — Disable ELI5 mode"""
