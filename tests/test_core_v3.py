"""Tests for new v3.0 core modules."""

import pytest

from termmind.core.cache import Cache
from termmind.core.events import EventBus
from termmind.core.exceptions import (
    AgentError,
    KnowledgeBaseError,
    ProviderAuthError,
    ProviderError,
    TermMindError,
)
from termmind.core.middleware import MiddlewareChain


class TestExceptions:
    def test_base_exception(self):
        with pytest.raises(TermMindError):
            raise TermMindError("test")

    def test_provider_error(self):
        with pytest.raises(ProviderError):
            raise ProviderError("test")

    def test_auth_error(self):
        with pytest.raises(ProviderAuthError):
            raise ProviderAuthError("bad key")

    def test_agent_error(self):
        with pytest.raises(AgentError):
            raise AgentError("agent failed")

    def test_kb_error(self):
        with pytest.raises(KnowledgeBaseError):
            raise KnowledgeBaseError("kb failed")


class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        results = []

        def handler(data):
            results.append(data)

        bus.subscribe("test", handler)
        bus.emit("test", "hello")

        assert "hello" in results

    def test_unsubscribe(self):
        bus = EventBus()
        results = []

        def handler(data):
            results.append(data)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        bus.emit("test", "hello")

        assert len(results) == 0

    def test_listeners(self):
        bus = EventBus()
        assert bus.listeners("test") == 0
        bus.subscribe("test", lambda: None)
        assert bus.listeners("test") == 1


class TestCache:
    def test_set_and_get(self):
        cache = Cache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self):
        cache = Cache()
        assert cache.get("nonexistent") is None

    def test_cache_clear(self):
        cache = Cache()
        cache.set("key1", "value1")
        cache.clear()
        assert cache.get("key1") is None

    def test_cache_invalidation(self):
        cache = Cache()
        cache.set("foo1", "a")
        cache.set("foo2", "b")
        cache.set("bar", "c")
        count = cache.invalidate("foo")
        assert count == 2
        assert cache.get("bar") == "c"

    def test_cache_stats(self):
        cache = Cache()
        cache.set("key", "value")
        cache.get("key")  # hit
        cache.get("missing")  # miss
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestMiddleware:
    def test_chain(self):
        chain = MiddlewareChain()
        chain.add(lambda data: data.strip())
        chain.add(lambda data: data.upper())
        result = chain.process("  hello  ")
        assert result == "HELLO"

    def test_clear(self):
        chain = MiddlewareChain()
        chain.add(lambda x: x)
        chain.clear()
        assert chain.count() == 0

    def test_kwargs(self):
        chain = MiddlewareChain()
        chain.add(lambda data, **kwargs: data + kwargs.get("suffix", ""))
        result = chain.process("hello", suffix=" world")
        assert result == "hello world"
