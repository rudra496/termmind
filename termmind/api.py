"""API client for OpenAI-compatible endpoints with streaming support."""

import json
import time
from collections.abc import Generator
from typing import Any, Optional

import httpx

from .config import get_provider_info, load_config

USER_AGENT = "TermMind/1.0.0"
_TIMEOUT = httpx.Timeout(120, connect=10)

_shared_client: Optional[httpx.Client] = None


def _get_shared_client() -> httpx.Client:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.Client(timeout=_TIMEOUT)
    return _shared_client


def close_client() -> None:
    """Close the shared HTTP client."""
    global _shared_client
    if _shared_client is not None:
        _shared_client.close()
        _shared_client = None


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """Lightweight client for OpenAI-compatible chat completions."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        cfg = load_config()
        info = get_provider_info(provider)
        self.provider = provider or cfg.get("provider", "ollama")
        self.api_key = api_key if api_key is not None else cfg.get("api_key", "")
        self.model = model or cfg.get("model", info["default_model"])
        self.base_url = (base_url or info["base_url"]).rstrip("/")
        self.max_tokens = max_tokens or cfg.get("max_tokens", 4096)
        self.temperature = temperature if temperature is not None else cfg.get("temperature", 0.7)
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _build_messages(
        self, messages: list[dict[str, str]], system_prompt: Optional[str] = None
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        else:
            cfg = load_config()
            sp = cfg.get("system_prompt", "")
            if sp:
                out.append({"role": "system", "content": sp})
        out.extend(messages)
        return out

    def chat(self, messages: list[dict[str, str]], system_prompt: Optional[str] = None) -> str:
        """Non-streaming chat completion."""
        body = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        resp = self._request(body)
        if not resp:
            return ""
        return resp.strip()

    def chat_stream(
        self, messages: list[dict[str, str]], system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Streaming chat completion — yields content deltas."""
        body = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        url = f"{self.base_url}/chat/completions"
        headers = self._headers()
        try:
            with (
                httpx.Client(timeout=_TIMEOUT) as client,
                client.stream("POST", url, json=body, headers=headers) as resp,
            ):
                if resp.status_code != 200:
                    err = resp.read().decode(errors="replace")
                    raise APIError(f"API error {resp.status_code}: {err}", resp.status_code)
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        except APIError:
            raise
        except httpx.ConnectError:
            raise APIError(f"Cannot connect to {self.base_url}. Is the service running?") from None
        except httpx.TimeoutException:
            raise APIError("Request timed out.") from None

    def _request(self, body: dict[str, Any], retries: int = 3) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = self._headers()
        last_err = None
        for attempt in range(retries):
            try:
                resp = _get_shared_client().post(url, json=body, headers=headers)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    raise APIError(f"API error {resp.status_code}: {resp.text}", resp.status_code)
                data = resp.json()
                usage = data.get("usage", {})
                self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"]
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue
            except APIError:
                raise
            except Exception as e:
                raise APIError(str(e)) from None
        raise APIError(f"Failed after {retries} retries: {last_err}")

    def get_cost(self) -> float:
        """Estimate session cost based on usage."""
        info = get_provider_info(self.provider)
        inp = self.usage["prompt_tokens"] / 1000 * info.get("cost_per_1k_input", 0)
        out = self.usage["completion_tokens"] / 1000 * info.get("cost_per_1k_output", 0)
        return inp + out

    def total_tokens(self) -> int:
        return self.usage["prompt_tokens"] + self.usage["completion_tokens"]

    def embed(self, text: str) -> list[float]:
        """Generate vector embedding for a given text using the provider's /embeddings endpoint."""
        url = f"{self.base_url}/embeddings"
        headers = self._headers()

        # Determine the model to use for embeddings based on provider
        model = self.model
        if self.provider == "openai":
            model = "text-embedding-3-small"
        elif self.provider == "gemini":
            model = "text-embedding-004"
        elif self.provider == "together":
            model = "togethercomputer/mxbai-embed-large-v1"
        elif self.provider == "cohere":
            model = "embed-english-v3.0"

        body = {"model": model, "input": text}

        try:
            resp = _get_shared_client().post(url, json=body, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0].get("embedding")
                    if embedding:
                        return [float(x) for x in embedding]
        except Exception:
            pass
        return []
