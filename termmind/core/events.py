"""Event bus for decoupled communication."""

from typing import Callable, Any
from collections import defaultdict


class EventBus:
    """Simple event bus for pub/sub communication.
    
    Usage:
        bus = EventBus()
        bus.subscribe("chat.completed", lambda msg, resp: print("Done!"))
        bus.emit("chat.completed", message="Hello", response="Hi")
    """
    
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
    
    def subscribe(self, event: str, handler: Callable[..., Any]) -> None:
        """Subscribe to an event."""
        self._handlers[event].append(handler)
    
    def unsubscribe(self, event: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe from an event."""
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)
    
    def emit(self, event: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Emit an event to all subscribers."""
        results = []
        for handler in self._handlers[event]:
            try:
                result = handler(*args, **kwargs)
                results.append(result)
            except Exception:
                continue
        return results
    
    def listeners(self, event: str) -> int:
        """Count listeners for an event."""
        return len(self._handlers[event])
