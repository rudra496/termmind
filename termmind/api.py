"""API client for OpenAI-compatible endpoints with streaming support."""

from collections.abc import Generator
from typing import Optional

from .config import get_provider_info, load_config
from .providers import _get_shared_client, get_provider


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """Lightweight client for chat completions, wrapping providers.py."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = 4096,
        temperature: Optional[float] = 0.7,
    ):
        cfg = load_config()
        self.provider_name = provider or cfg.get("provider", "ollama")
        info = get_provider_info(self.provider_name)

        self.api_key = api_key if api_key is not None else cfg.get("api_key", "")
        self.model = model or cfg.get("model", info.get("default_model", ""))
        self.base_url = (base_url or info.get("base_url", "")).rstrip("/")
        self.max_tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 4096)
        self.temperature = temperature if temperature is not None else cfg.get("temperature", 0.7)
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

        try:
            self._impl = get_provider(
                self.provider_name,
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
            )
        except ValueError as e:
            raise APIError(str(e)) from e

    @property
    def provider(self) -> str:
        return self.provider_name

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

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _update_usage(self, prompt_text: str, completion_text: str) -> None:
        self.usage["prompt_tokens"] += self._estimate_tokens(prompt_text)
        self.usage["completion_tokens"] += self._estimate_tokens(completion_text)

    def chat(self, messages: list[dict[str, str]], system_prompt: Optional[str] = None) -> str:
        """Non-streaming chat completion."""
        built_msgs = self._build_messages(messages, system_prompt)
        prompt_text = "".join(m.get("content", "") for m in built_msgs)
        try:
            gen = self._impl.send_message(
                built_msgs,
                stream=False,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            response = "".join(list(gen))
            self._update_usage(prompt_text, response)
            return response.strip()
        except Exception as e:
            raise APIError(str(e)) from e

    def chat_stream(
        self, messages: list[dict[str, str]], system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Streaming chat completion — yields content deltas."""
        built_msgs = self._build_messages(messages, system_prompt)
        prompt_text = "".join(m.get("content", "") for m in built_msgs)
        response_text = ""
        try:
            gen = self._impl.send_message(
                built_msgs,
                stream=True,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            for chunk in gen:
                response_text += chunk
                yield chunk
            self._update_usage(prompt_text, response_text)
        except Exception as e:
            raise APIError(str(e)) from e

    def get_cost(self) -> float:
        """Estimate session cost based on usage."""
        return self._impl.estimate_cost(
            self.usage["prompt_tokens"],
            self.usage["completion_tokens"]
        )

    def total_tokens(self) -> int:
        return self.usage["prompt_tokens"] + self.usage["completion_tokens"]

    def embed(self, text: str) -> list[float]:
        """Generate vector embedding for a given text."""
        url = f"{self.base_url}/embeddings"
        headers = self._impl._headers() if hasattr(self._impl, "_headers") else {}

        # Determine the model to use for embeddings based on provider
        model = self.model
        if self.provider_name == "openai":
            model = "text-embedding-3-small"
        elif self.provider_name == "gemini":
            model = "text-embedding-004"
        elif self.provider_name == "together":
            model = "togethercomputer/mxbai-embed-large-v1"
        elif self.provider_name == "cohere":
            model = "embed-english-v3.0"

        body = {"model": model, "input": text}

        try:
            client = _get_shared_client()
            resp = client.post(url, json=body, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0].get("embedding")
                    if embedding:
                        return [float(x) for x in embedding]
        except Exception:
            pass
        return []

