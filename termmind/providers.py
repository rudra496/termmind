"""Provider implementations for TermMind API client."""

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional

import httpx

from .config import load_config, get_provider_info

USER_AGENT = "TermMind/1.0.0"
_TIMEOUT = httpx.Timeout(120, connect=10)
_STREAM_TIMEOUT = httpx.Timeout(120, connect=10)
_OLLAMA_TIMEOUT = httpx.Timeout(300, connect=10)

_shared_client: Optional[httpx.Client] = None


def _get_shared_client(timeout: httpx.Timeout = _TIMEOUT) -> httpx.Client:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.Client(timeout=timeout)
    return _shared_client


def _close_shared_client() -> None:
    global _shared_client
    if _shared_client is not None:
        _shared_client.close()
        _shared_client = None


class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    name: str = "base"
    base_url: str = ""
    requires_key: bool = True

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @abstractmethod
    def send_message(
        self, messages: List[Dict[str, str]], stream: bool = False, **kwargs: Any
    ) -> Generator[str, None, None]:
        """Send messages and yield content chunks (or one chunk if not streaming)."""
        ...

    @abstractmethod
    def list_models(self) -> List[str]:
        """Return available model names."""
        ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for given token counts."""
        ...

    @abstractmethod
    def validate_connection(self, timeout: float = 10.0) -> bool:
        """Test if connection works. Returns True on success."""
        ...

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            h.update(extra)
        return h


class OpenAICompatibleProvider(BaseProvider):
    """Shared base for providers using the OpenAI chat completions API.

    Subclasses only need to set: name, requires_key, _costs, _models, base_url, model.
    The streaming and non-streaming logic is handled here.
    """

    _costs: Dict[str, tuple] = {}
    _models: List[str] = []
    _timeout: httpx.Timeout = _TIMEOUT

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")

    def send_message(self, messages: List[Dict[str, str]], stream: bool = False, **kw: Any) -> Generator[str, None, None]:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kw.get("max_tokens", 4096),
            "temperature": kw.get("temperature", 0.7),
            "stream": stream,
        }
        url = f"{self.base_url}/chat/completions"
        headers = self._headers()

        if not stream:
            resp = _retry_request(lambda: _get_shared_client(self._timeout).post(url, json=body, headers=headers))
            if resp.status_code != 200:
                raise Exception(f"{self.name.title()} error {resp.status_code}: {resp.text}")
            yield resp.json()["choices"][0]["message"]["content"]
            return

        with httpx.Client(timeout=self._timeout) as client:
            with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    raise Exception(f"{self.name.title()} error {resp.status_code}: {resp.read().decode()}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        delta = json.loads(data).get("choices", [{}])[0].get("delta", {})
                        c = delta.get("content", "")
                        if c:
                            yield c
                    except json.JSONDecodeError:
                        continue

    def list_models(self) -> List[str]:
        return list(self._models)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        if not self._costs:
            return 0.0
        costs = self._costs.get(self.model, (0.0, 0.0))
        return (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])

    def validate_connection(self, timeout: float = 10.0) -> bool:
        if self.requires_key and not self.api_key:
            return False
        try:
            resp = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False


def _retry_request(func, max_retries: int = 3, retry_on: Optional[List[int]] = None) -> Any:
    """Execute func with exponential backoff on retryable status codes."""
    retry_on = retry_on or [429, 500, 502, 503]
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = func()
            if hasattr(resp, "status_code") and resp.status_code in retry_on:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    if last_err:
        raise last_err
    return None


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API provider."""

    name = "openai"
    requires_key = True
    _costs = {
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-4": (0.03, 0.06),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "o1": (0.015, 0.06),
        "o1-mini": (0.003, 0.012),
        "o3-mini": (0.00110, 0.00440),
    }
    _models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"]

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://api.openai.com/v1"
        self.model = self.model or "gpt-4o-mini"


class AnthropicProvider(BaseProvider):
    """Anthropic (Claude) API provider."""

    name = "anthropic"
    requires_key = True
    _costs = {
        "claude-sonnet-4-20250514": (0.003, 0.015),
        "claude-3-5-sonnet-20241022": (0.003, 0.015),
        "claude-3-5-haiku-20241022": (0.001, 0.005),
        "claude-3-haiku-20240307": (0.00025, 0.00125),
        "claude-3-opus-20240229": (0.015, 0.075),
    }
    _models = list(_costs.keys())

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://api.anthropic.com"
        self.model = self.model or "claude-sonnet-4-20250514"

    def _anthropic_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }

    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple:
        """Convert OpenAI-style messages to Anthropic format. Returns (system, anthropic_messages)."""
        system = ""
        anth_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anth_messages.append({"role": msg["role"], "content": msg["content"]})
        return system, anth_messages

    def send_message(self, messages: List[Dict[str, str]], stream: bool = False, **kw: Any) -> Generator[str, None, None]:
        system, anth_messages = self._convert_messages(messages)
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": anth_messages,
            "max_tokens": kw.get("max_tokens", 4096),
            "temperature": kw.get("temperature", 0.7),
            "stream": stream,
        }
        if system:
            body["system"] = system
        url = f"{self.base_url}/v1/messages"
        headers = self._anthropic_headers()

        if not stream:
            def do_req():
                return _get_shared_client().post(url, json=body, headers=headers)
            resp = _retry_request(do_req)
            if resp.status_code != 200:
                raise Exception(f"Anthropic error {resp.status_code}: {resp.text}")
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    yield block["text"]
            return

        with httpx.Client(timeout=_TIMEOUT) as client:
            with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    raise Exception(f"Anthropic error {resp.status_code}: {resp.read().decode()}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") == "content_block_delta":
                            text = parsed.get("delta", {}).get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue

    def list_models(self) -> List[str]:
        return list(self._models)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        costs = self._costs.get(self.model, (0.003, 0.015))
        return (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])

    def validate_connection(self, timeout: float = 10.0) -> bool:
        if not self.api_key:
            return False
        try:
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._anthropic_headers(),
                timeout=timeout,
            )
            return resp.status_code in (200, 403)
        except Exception:
            return False


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini API via OpenAI-compatible endpoint."""

    name = "gemini"
    requires_key = True
    _costs = {
        "gemini-2.0-flash": (0.0, 0.0),
        "gemini-1.5-pro": (0.0, 0.0),
        "gemini-1.5-flash": (0.0, 0.0),
    }
    _models = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
        self.model = self.model or "gemini-2.0-flash"

    def validate_connection(self, timeout: float = 10.0) -> bool:
        if not self.api_key:
            return False
        try:
            resp = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}",
                timeout=timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False


class GroqProvider(OpenAICompatibleProvider):
    """Groq API provider (OpenAI-compatible)."""

    name = "groq"
    requires_key = True
    _costs = {
        "llama-3.3-70b-versatile": (0.0, 0.0),
        "llama-3.1-8b-instant": (0.0, 0.0),
        "mixtral-8x7b-32768": (0.0, 0.0),
        "llama3-70b-8192": (0.0, 0.0),
        "llama3-8b-8192": (0.0, 0.0),
        "gemma2-9b-it": (0.0, 0.0),
    }
    _models = list(_costs.keys())

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://api.groq.com/openai/v1"
        self.model = self.model or "llama-3.3-70b-versatile"


class TogetherProvider(OpenAICompatibleProvider):
    """Together.ai API provider (OpenAI-compatible)."""

    name = "together"
    requires_key = True
    _costs = {
        "meta-llama/Llama-3-70b-chat-hf": (0.00088, 0.00088),
        "mistralai/Mixtral-8x7B-Instruct-v0.1": (0.0006, 0.0006),
        "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.00088, 0.00088),
    }
    _models = list(_costs.keys())

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://api.together.xyz/v1"
        self.model = self.model or "meta-llama/Llama-3-70b-chat-hf"


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter API provider."""

    name = "openrouter"
    requires_key = True

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "https://openrouter.ai/api/v1"
        self.model = self.model or "openai/gpt-4o-mini"

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = super()._headers(extra)
        h["HTTP-Referer"] = "https://github.com/rudra496/termmind"
        h["X-Title"] = "TermMind"
        return h

    def list_models(self) -> List[str]:
        return ["*"]


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama local API provider (OpenAI-compatible endpoint)."""

    name = "ollama"
    requires_key = False
    _timeout = _OLLAMA_TIMEOUT

    def __init__(self, **kw: Any):
        super().__init__(**kw)
        self.base_url = self.base_url or "http://localhost:11434/v1"
        self.model = self.model or "llama3.2"

    def list_models(self) -> List[str]:
        try:
            resp = httpx.get(f"{self.base_url.replace('/v1', '')}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return ["llama3.2", "codellama", "mistral", "qwen2.5-coder"]

    def validate_connection(self, timeout: float = 10.0) -> bool:
        try:
            resp = httpx.get(f"{self.base_url.replace('/v1', '')}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def send_message(self, messages: List[Dict[str, str]], stream: bool = False, **kw: Any) -> Generator[str, None, None]:
        kw["max_tokens"] = kw.get("max_tokens", 4096)
        return super().send_message(messages, stream, **kw)


# Provider registry
PROVIDERS: Dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "together": TogetherProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, **kwargs: Any) -> BaseProvider:
    """Instantiate a provider by name."""
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return cls(**kwargs)
