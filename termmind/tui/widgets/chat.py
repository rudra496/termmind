"""Chat panel widget for TermMind TUI."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Markdown, Input
from textual import events

class ChatPanel(Vertical):
    """The main chat interface."""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat_history"):
            yield Markdown("# Welcome to TermMind\n\nHow can I help you today?", id="welcome_msg")
        
        yield Input(placeholder="Type your message here... (Enter to send)", id="chat_input")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle chat input."""
        if not event.value.strip():
            return
        
        # Clear input
        event.input.value = ""
        
        # Append user message
        history = self.query_one("#chat_history")
        await history.mount(Markdown(f"**You:**\n\n{event.value}"))
        history.scroll_end(animate=False)
        
        # Here we will hook into the Agent Loop
        # await self.app.agent.process_message(event.value)
