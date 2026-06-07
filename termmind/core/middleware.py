"""Middleware/interceptor system."""

from typing import Any, Callable


class MiddlewareChain:
    """Chain of responsibility pattern for interceptors.

    Usage:
        chain = MiddlewareChain()
        chain.add(lambda data: data.strip())
        chain.add(lambda data: data.upper())
        result = chain.process("  hello  ")  # "HELLO"
    """

    def __init__(self) -> None:
        self._middlewares: list[Callable[..., Any]] = []

    def add(self, middleware: Callable[..., Any]) -> None:
        """Add middleware to chain."""
        self._middlewares.append(middleware)

    def process(self, data: Any, **kwargs: Any) -> Any:
        """Process data through all middlewares."""
        result = data
        for middleware in self._middlewares:
            result = middleware(result, **kwargs)
        return result

    def clear(self) -> None:
        """Clear all middlewares."""
        self._middlewares.clear()

    def count(self) -> int:
        """Count middlewares."""
        return len(self._middlewares)
