# Architecture

TermMind is a modular CLI application built with Click and Rich.

## Core Flow

```
User Input (prompt_toolkit)
       │
       ▼
   CLI (cli.py)
       │
       ├── Slash Command ──► commands.py
       │
       └── AI Query ──► context.py (build file context)
                            │
                            ▼
                       providers.py (select provider)
                            │
                            ▼
                        api.py (HTTP streaming)
                            │
                            ▼
                       Rich rendering
```

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Click CLI definition, interactive chat loop, banner, key bindings |
| `api.py` | HTTP client for OpenAI-compatible endpoints, streaming, retry, cost tracking |
| `providers.py` | 7 LLM provider implementations (OpenAI, Anthropic, Gemini, Groq, Together, OpenRouter, Ollama) |
| `config.py` | Configuration loading/saving, provider presets, default settings |
| `commands.py` | 30+ slash command handlers |
| `context.py` | Smart file relevance scoring, automatic context building with caching |
| `file_ops.py` | File read/write/edit/search/diff/undo operations |
| `git.py` | Git operations and AI-generated commit messages |
| `memory.py` | AST-based code index for 9 languages |
| `diff_engine.py` | Diff parsing, inline and side-by-side rendering |
| `refactor.py` | 8 AI-powered refactoring operations |
| `snippets.py` | Snippet save/load/search/import/export |
| `templates.py` | 8 project scaffolding templates |
| `recorder.py` | Session recording and HTML export |
| `cost_optimizer.py` | Token usage tracking, cost estimation, budget alerts |
| `doc_preview.py` | Inline docstring preview for Python, JS, Go, Rust, Java |
| `voice.py` | Text-to-speech via pyttsx3 (optional) |
| `eli5.py` | Simplified explanation mode |
| `plugins.py` | Plugin system with ABC and dynamic discovery |
| `sessions.py` | Session save/load/export |
| `themes.py` | 5 color themes |
| `shell.py` | Shell detection, completions, capabilities |
| `utils.py` | Token counting, cost calculation, language detection |

## Provider Architecture

All providers inherit from `BaseProvider` (providers.py). OpenAI-compatible providers (OpenAI, Groq, Together, OpenRouter, Gemini) share a common implementation. Anthropic and Ollama have custom implementations due to API differences.

```
BaseProvider (ABC)
    ├── OpenAIProvider
    ├── AnthropicProvider
    ├── GeminiProvider
    ├── GroqProvider
    ├── TogetherProvider
    ├── OpenRouterProvider
    └── OllamaProvider
```

## Plugin System

Plugins extend TermMind by hooking into session lifecycle events:

```
BasePlugin (ABC)
    ├── on_start(session)
    ├── on_message(message, role)
    ├── on_response(response)
    ├── on_edit(filepath, old, new)
    ├── on_command(command, args)
    └── on_exit()
```

Plugins are discovered from `~/.termmind/plugins/` and registered at startup.

## Configuration

Config is stored at `~/.termmind/config.json` and loaded via `config.py`. Provider presets define default models and endpoints for each provider.

## Testing

Tests are in `tests/` using pytest. All external API calls are mocked — no provider connection needed to run tests.
