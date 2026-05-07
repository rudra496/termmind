"""Basic TermMind usage example.

This script demonstrates how to use TermMind's Python API
to validate configuration and check provider connectivity.
"""

import json
import sys


def main() -> None:
    try:
        from termmind.config import load_config, PROVIDER_PRESETS
        from termmind.utils import estimate_tokens
    except ImportError:
        print("Install termmind first: pip install -e .")
        sys.exit(1)

    # Load configuration
    cfg = load_config()
    provider = cfg.get("provider", "ollama")
    model = cfg.get("model", "llama3.2")

    print(f"Provider: {provider}")
    print(f"Model:    {model}")

    # Show available providers
    print(f"\nAvailable providers: {', '.join(PROVIDER_PRESETS.keys())}")

    # Estimate tokens for a sample prompt
    sample = "Explain how Python decorators work"
    tokens = estimate_tokens(sample)
    print(f"\nSample prompt: {sample!r}")
    print(f"Estimated tokens: {tokens}")


if __name__ == "__main__":
    main()
