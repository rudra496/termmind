"""API client for OpenAI-compatible endpoints with streaming support."""

import json
import time
from typing import Any, Dict, Generator, List, Optional

import httpx

from .config import get_provider_info, load_config

USER_AGENT = "TermMind/0.1.0"


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

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _build_messages(
        self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if system_prompt:
            cfg = load_config()
            sp = system_prompt or cfg.get("system_prompt", "")
            if sp:
                out.append({"role": "system", "content": sp})
        out.extend(messages)
        return out

    def chat(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> str:
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
        self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None
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
        collected = ""
        try:
            with httpx.Client(timeout=httpx.Timeout(120, connect=10)) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
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
                                collected += content
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            raise APIError(f"Cannot connect to {self.base_url}. Is the service running?")
        except httpx.TimeoutException:
            raise APIError("Request timed out.")

    def _request(self, body: Dict[str, Any], retries: int = 3) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = self._headers()
        last_err = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=httpx.Timeout(120, connect=10)) as client:
                    resp = client.post(url, json=body, headers=headers)
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
                    time.sleep(2 ** attempt)
                continue
            except APIError:
                raise
            except Exception as e:
                raise APIError(str(e))
        raise APIError(f"Failed after {retries} retries: {last_err}")

    def estimate_tokens(self, text: str) -> int:
        """Rough token count: ~4 chars per token."""
        return len(text) // 4

    def get_cost(self) -> float:
        """Estimate session cost based on usage."""
        info = get_provider_info(self.provider)
        inp = self.usage["prompt_tokens"] / 1000 * info.get("cost_per_1k_input", 0)
        out = self.usage["completion_tokens"] / 1000 * info.get("cost_per_1k_output", 0)
        return inp + out

    def total_tokens(self) -> int:
        return self.usage["prompt_tokens"] + self.usage["completion_tokens"]
