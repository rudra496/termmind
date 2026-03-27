"""Configuration management for TermMind."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".termmind"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"],
        "default_model": "gpt-4o-mini",
        "cost_per_1k_input": 0.005,
        "cost_per_1k_output": 0.015,
        "requires_key": True,
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"],
        "default_model": "claude-sonnet-4-20250514",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "requires_key": True,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "default_model": "gemini-2.0-flash",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "requires_key": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "default_model": "llama-3.3-70b-versatile",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "requires_key": True,
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "models": ["meta-llama/Llama-3-70b-chat-hf", "mistralai/Mixtral-8x7B-Instruct-v0.1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"],
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "cost_per_1k_input": 0.00088,
        "cost_per_1k_output": 0.00088,
        "requires_key": True,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3-haiku", "meta-llama/llama-3-70b-instruct", "*"],
        "default_model": "openai/gpt-4o-mini",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "requires_key": True,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.2", "codellama", "mistral", "qwen2.5-coder"],
        "default_model": "llama3.2",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "requires_key": False,
    },
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "ollama",
    "api_key": "",
    "model": "",
    "max_tokens": 4096,
    "temperature": 0.7,
    "theme": "dark",
    "editor": "vim",
    "system_prompt": "You are TermMind, a helpful AI assistant in the terminal. "
        "You help with coding, file operations, and general questions. "
        "Be concise and practical. When showing code, use markdown code blocks with language hints.",
    "auto_context": True,
    "max_context_files": 20,
    "max_context_tokens": 100000,
    "confirm_edits": True,
    "confirm_runs": True,
    "stream": True,
    "history_size": 100,
    "sessions_dir": "~/.termmind/sessions",
    "custom_instructions": "",
    "providers": {},
}


def _ensure_dirs() -> None:
    """Create config and sessions directories if they don't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration from disk, merging with defaults."""
    _ensure_dirs()
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                stored = json.load(f)
            cfg.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    # Resolve model from provider preset if not set
    if not cfg["model"] and cfg["provider"] in PROVIDER_PRESETS:
        cfg["model"] = PROVIDER_PRESETS[cfg["provider"]]["default_model"]
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Save configuration to disk."""
    _ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_provider_info(provider: Optional[str] = None) -> Dict[str, Any]:
    """Get provider preset info."""
    cfg = load_config()
    name = provider or cfg.get("provider", "ollama")
    return PROVIDER_PRESETS.get(name, PROVIDER_PRESETS["ollama"])


def update_config(key: str, value: Any) -> Dict[str, Any]:
    """Update a single config key and save."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    return cfg
