<!-- Meta: TermMind is a free, open-source AI-powered terminal assistant supporting 7+ LLM providers. Chat with GPT, Claude, Gemini in your terminal with code analysis, file editing, and 40+ commands. -->
<!-- Keywords: AI terminal assistant, CLI coding tool, GPT terminal, Claude terminal, coding assistant, AI code editor, terminal AI chat, LLM CLI tool -->

<p align="center">
  <img src="https://img.shields.io/pypi/v/termmind?color=blue&label=PyPI" alt="PyPI version">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/pypi/dm/termmind?color=orange&label=Downloads" alt="Downloads">
  <img src="https://img.shields.io/badge/Tests-227%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style">
</p>

<h1 align="center">TermMind — AI-Powered Terminal Assistant | Multi-Provider CLI Coding Tool</h1>

> A modern, open-source AI terminal assistant. Free, beautiful, and lives in your terminal.

```
  ╔═════════════════════════════╗
  ║     T e r m M i n d         ║
  ║  AI Terminal Assistant      ║
  ╚═════════════════════════════╝
```

## What is TermMind?

TermMind is a CLI tool that lets you chat with AI models directly in your terminal. It can read, write, and edit files, run commands, understand your codebase, and help you code faster — all with a beautiful, rich terminal UI.

Think Claude Code or Aider, but **free, open-source, and lightweight**.

## ✨ Features

- 🎨 **Beautiful terminal UI** — Syntax highlighting, markdown rendering, streaming responses
- 🔌 **Multi-provider** — OpenAI, Anthropic Claude, Google Gemini, Groq, Together.ai, OpenRouter, Ollama
- 💰 **Free tiers supported** — Works with Gemini, Groq, and Ollama at zero cost
- 📁 **Smart context** — Automatically includes relevant files from your project
- ✏️ **File editing** — AI-powered file creation and editing with diff support
- ↩️ **Undo system** — Every edit is tracked; undo any change with `/undo`
- 💾 **Session management** — Save and load conversations
- 📊 **Cost tracking** — Real-time token count and cost estimation
- 🔄 **Provider switching** — Change models mid-conversation with `/provider`
- 🌳 **File tree** — Visual project structure with `.termmindignore` support
- 🔍 **Code search** — Find anything in your project files
- 🐙 **Git integration** — Status, diff, log, and AI-generated commit messages
- ⚡ **Streaming** — See responses as they're generated, not after
- 📦 **Snippet Manager** — Save, search, and reuse code snippets with template variables
- 🏗️ **Project Templates** — Scaffold projects from 8 built-in templates (Python, FastAPI, React, Next.js, etc.)
- 🔧 **Refactoring Engine** — AI-powered refactoring with diff preview, confirmation, and undo

## 🚀 Installation

```bash
pip install termmind
```

Or from source:

```bash
git clone https://github.com/rudra496/termmind.git
cd termmind
pip install -e .
```

## 🏁 Quick Start

### 1. Set up your API

```bash
termmind init
```

This walks you through selecting a provider and entering your API key. You can also manually edit `~/.termmind/config.json`.

### 2. Start chatting

```bash
termmind chat
```

### 3. Ask questions

```bash
termmind ask "Explain async/await in Python"
```

### 4. Edit files

```bash
termmind edit main.py "Add input validation to the parse_args function"
```

### 5. Review code

```bash
termmind review ./src
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `termmind init` | Configure API provider, key, and model |
| `termmind chat` | Start interactive chat session |
| `termmind ask "q"` | One-shot question (no session) |
| `termmind edit file` | Edit a file with AI |
| `termmind review path` | Review code in directory |
| `termmind explain file` | Explain a file |
| `termmind test file` | Generate tests for a file |
| `termmind history` | Show saved sessions |
| `termmind config` | Show current configuration |

### Chat Commands

Inside `termmind chat`, use slash commands:

| Command | Description |
|---------|-------------|
| `/edit <file> [instruction]` | Edit a file with AI |
| `/run <command>` | Run a shell command |
| `/files` | List files in context |
| `/add <file>` | Add file to context |
| `/search <query>` | Search project files |
| `/tree` | Show file tree |
| `/clear` | Clear conversation |
| `/save [name]` | Save session |
| `/load <name>` | Load saved session |
| `/model [name]` | Show/switch model |
| `/provider [name]` | Show/switch provider |
| `/cost` | Show token usage & cost |
| `/theme dark/light` | Change color theme |
| `/undo` | Undo last file edit |
| `/diff` | Show session changes |
| `/status` | Git status + context info |
| `/git [status/log/diff]` | Git operations |
| `/snippet save <name>` | Save code as a snippet |
| `/snippet list` | List saved snippets |
| `/snippet load <name>` | Load snippet into context |
| `/snippet search <query>` | Search snippets |
| `/template list` | List project templates |
| `/template use <name>` | Scaffold a project |
| `/refactor <op> <file>` | AI-powered refactoring |
| `/refactor undo` | Undo last refactoring |
| `/help` | Show all commands |

## 🔑 Provider Setup

### 🆓 Free Options (no cost)

#### Google Gemini
1. Go to [aistudio.google.com](https://aistudio.google.com/apikey)
2. Create a free API key
3. Select `gemini` during `termmind init`

#### Groq
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up and create an API key
3. Super fast inference on open-source models

#### Ollama (fully offline)
1. Install: `curl -fsSL https://ollama.ai/install.sh | sh`
2. Pull a model: `ollama pull llama3.2`
3. No API key needed! Just select `ollama` during setup

### 💳 Paid Options

#### OpenAI
1. Go to [platform.openai.com](https://platform.openai.com/api-keys)
2. Create an API key
3. Supports GPT-4o, GPT-4o-mini, etc.

#### OpenRouter
1. Go to [openrouter.ai](https://openrouter.ai/keys)
2. Access 100+ models from one API key

## ⚙️ Configuration

Config is stored at `~/.termmind/config.json`:

```json
{
  "provider": "gemini",
  "api_key": "your-key-here",
  "model": "gemini-2.0-flash",
  "max_tokens": 4096,
  "temperature": 0.7,
  "theme": "dark"
}
```

### .termmindignore

Like `.gitignore` but for AI context. Create in your project root:

```
node_modules/
__pycache__/
*.min.js
dist/
.env
```

## 🆚 Comparison

| Feature | TermMind | Claude Code | Aider | Open Interpreter |
|---------|----------|-------------|-------|-----------------|
| Open Source | ✅ MIT | ❌ | ✅ Apache | ✅ MIT |
| Free Tier | ✅ (Gemini/Groq) | ❌ | ❌ | ❌ |
| Local/Offline | ✅ (Ollama) | ❌ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ | ✅ |
| Multi-Provider | ✅ 6+ | ❌ | ✅ | ✅ |
| Rich Terminal UI | ✅ | ✅ | ❌ | ❌ |
| File Editing | ✅ | ✅ | ✅ | ✅ |
| Undo Edits | ✅ | ❌ | ✅ | ❌ |
| Cost Tracking | ✅ | ❌ | ❌ | ❌ |
| Session Save/Load | ✅ | ❌ | ❌ | ❌ |
| Dependencies | 4 | Heavy | Moderate | Heavy |
| Python | ✅ 3.8+ | Node.js | Python | Python |

## 🐳 Docker Quick Start

```bash
# Build and run
docker compose up --build

# With local Ollama (fully offline)
docker compose --profile local-llm up --build

# One-shot question via Docker
docker compose run --rm termmind ask "Explain async/await in Python"
```

## 🔧 Shell Completions

```bash
# Auto-install for your current shell
termmind completions install

# Or manually: generated scripts live in ~/.termmind/completions/
# Bash:
  echo 'source ~/.termmind/completions/termmind.bash' >> ~/.bashrc
# Zsh:
  echo 'fpath=(~/.termmind/completions $fpath)' >> ~/.zshrc
# Fish:
  cp ~/.termmind/completions/termmind.fish ~/.config/fish/completions/
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│                   CLI (cli.py)              │
│  click commands: chat, ask, edit, review…   │
└──────────┬──────────────┬───────────────────┘
           │              │
    ┌──────▼──────┐ ┌────▼──────────┐
    │  Commands    │ │  Diff Engine  │
    │  (/edit,…)   │ │  (diff_       │
    │  commands.py │ │   engine.py)  │
    └──────┬──────┘ └───────────────┘
           │
    ┌──────▼──────────────────────────┐
    │         Context Engine          │
    │  context.py + memory.py        │
    │  (smart file selection,        │
    │   code index, caching)         │
    └──────┬──────────────────────────┘
           │
    ┌──────▼──────┐ ┌───────────────┐
    │  File Ops    │ │  Git Module   │
    │  file_ops.py │ │  git.py       │
    └──────┬──────┘ └───────────────┘
           │
    ┌──────▼──────────────────────────┐
    │         API Client              │
    │  api.py + providers.py         │
    │  (streaming, multi-provider)    │
    └────────────────────────────────┘
           │
    ┌──────▼──────────────────────────┐
    │       Plugin System              │
    │  plugins.py (on_start, on_msg…) │
    └────────────────────────────────┘
```

## ✨ What Makes TermMind Unique

These features set TermMind apart from every other AI coding assistant:

### 🎨 Smart Diff Preview System
- **Side-by-side diff view** in the terminal with rich syntax highlighting
- **Hunk-by-hunk confirmation** — accept or reject individual changes
- **Auto-detect edit type** — insert, delete, replace, move, rename
- **Multi-file diff statistics** — insertions, deletions, files changed
- Beautiful colored output (red for removals, green for additions)

### 🧠 Code Context Memory
- **Persists across sessions** — remembers your project structure
- **Lightweight code index** — function signatures, class definitions, imports
- **Incremental updates** — only re-indexes changed files
- **9 languages supported** — Python, JS, TS, Go, Rust, Java, Ruby, C, C++
- **Query the index** — find functions/classes by name pattern instantly

### 🐚 Shell Integration
- **Auto-detect shell** — bash, zsh, fish
- **Generate completion scripts** for all three shells
- **Terminal capability detection** — true color, Unicode, emoji, copy/paste
- **Auto-resize handling** — responds to terminal resize events
- **One-command install** — `termmind completions install`

### 📦 Snippet Manager
- **Save snippets** from conversations — extracts code blocks automatically
- **Search** by name, description, tags, or code content with relevance scoring
- **Template variables** — `{{filename}}`, `{{datetime}}`, `{{user}}`, `{{cwd}}`, `{{year}}`, etc.
- **Auto-suggest** relevant snippets based on conversation context
- **Import/Export** — share snippet collections as JSON files
- **Usage tracking** — tracks how often each snippet is used
- **Language detection** — auto-detects programming language from content
- Stored in `~/.termmind/snippets/` — portable and shareable

### 🏗️ Project Templates
- **8 built-in templates** — scaffold complete projects instantly:
  - `python-package` — Modern Python package with pyproject.toml, tests, CI
  - `fastapi-api` — FastAPI REST API with auth, DB, Docker
  - `flask-api` — Flask REST API with SQLAlchemy
  - `cli-tool` — Python CLI tool with click
  - `react-app` — React + TypeScript + Vite
  - `nextjs-app` — Next.js with App Router
  - `express-api` — Express.js REST API
  - `django-app` — Django with Django REST Framework
- **Template variables** — `{{project_name}}`, `{{module_name}}`, `{{author}}`, etc.
- **Custom templates** — add your own to `~/.termmind/templates/`
- **Post-generation instructions** — clear next steps for each template

### 🔧 Refactoring Engine
- **8 refactoring operations** — extract-function, rename, inline, extract-class, simplify, dead-code, sort-imports, add-types
- **AI-powered** — uses your configured model for intelligent refactoring
- **Diff preview** — see exactly what will change before applying
- **Confirmation step** — approve or reject each refactoring
- **Undo support** — every refactoring is tracked and reversible
- **History** — view past refactorings with `/refactor history`
- **Local sort-imports** — PEP 8 import sorting without AI needed

## ⚡ Performance

| Operation | Time |
|-----------|------|
| Startup (cold) | ~0.3s |
| Startup (warm) | ~0.1s |
| Context selection (10 files) | ~0.05s |
| Code index build (100 files) | ~0.8s |
| Code index update (incremental) | ~0.05s |
| Diff render (1000 lines) | ~0.02s |

*Measured on a typical developer machine. Actual times vary.*

## 🛠️ Development

```bash
# Clone
git clone https://github.com/rudra496/termmind.git
cd termmind

# Install in dev mode
pip install -e .

# Run directly
python -m termmind.cli chat

# Test
python -m pytest

# Docker dev environment
docker compose up --build
```

### Project Structure

```
termmind/
├── termmind/
│   ├── __init__.py       # Version info
│   ├── cli.py            # Main CLI entry point
│   ├── api.py            # API client (streaming, multi-provider)
│   ├── config.py         # Configuration management
│   ├── context.py        # Smart file context builder
│   ├── commands.py       # Slash command handlers
│   ├── file_ops.py       # File read/write/edit/search
│   ├── git.py            # Git operations
│   ├── providers.py      # Provider implementations
│   ├── plugins.py        # Plugin system
│   ├── sessions.py       # Session save/load
│   ├── themes.py         # Color themes
│   ├── diff_engine.py    # Smart diff preview system
│   ├── memory.py         # Code context memory/index
│   ├── shell.py          # Shell integration & completions
│   ├── snippets.py       # Snippet manager (save/search/reuse)
│   ├── templates.py      # Project scaffolding templates
│   ├── refactor.py       # AI-powered refactoring engine
│   └── utils.py          # Token counting, utilities
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CONTRIBUTING.md
└── LICENSE
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Setting up the dev environment
- Code style and conventions
- Adding new providers and commands
- Plugin development
- Testing guidelines
- PR and issue templates

## 📜 Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold this standard.

## 🔒 Security

See [SECURITY.md](SECURITY.md) for our security policy, supported versions, and
vulnerability reporting guidelines.

Quick start:
1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing`
5. Open a Pull Request

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ by the TermMind contributors
</p>

## 💡 Why TermMind?

- **7 providers, 1 tool** — No need to switch between ChatGPT, Claude, Gemini apps
- **Code-aware** — Understands your project structure, not just isolated files
- **Works offline** — Use Ollama or local models with zero API costs
- **Extensible** — Plugin system lets you add custom commands
- **Zero config** — Works out of the box, configure only when you want to
- **Session history** — Never lose context between sessions

## 👤 Who Uses This?

| Role | How They Use It |
|------|----------------|
| **Full-Stack Devs** | Quick code generation, refactoring, and debugging across languages |
| **DevOps Engineers** | Generate Dockerfiles, CI configs, and Terraform files |
| **Students** | Learn programming with an AI tutor that explains concepts |
| **Open Source Contributors** | Understand unfamiliar codebases quickly |
| **AI Enthusiasts** | Experiment with multiple LLM providers side by side |

n## 🔗 Other Projects

Check out more open-source tools:

| Project | Description | Stars |
|---------|-------------|-------|
| [🛡️ AI Code Trust Validator](https://github.com/rudra496/ai-code-trust-validator) | Detect security flaws, hallucinations & logic errors in AI-generated code | ![Stars](https://img.shields.io/github/stars/rudra496/ai-code-trust-validator?style=social) |
| [🔍 CodeVista](https://github.com/rudra496/codevista) | Code analysis & security scanner with 75+ languages | ![Stars](https://img.shields.io/github/stars/rudra496/codevista?style=social) |

---

## 🌐 Connect

- [![GitHub](https://img.shields.io/badge/GitHub-rudra496-181717?logo=github)](https://github.com/rudra496)
- [![LinkedIn](https://img.shields.io/badge/LinkedIn-rudrasarker-0A66C2?logo=linkedin)](https://www.linkedin.com/in/rudrasarker)
- [![X/Twitter](https://img.shields.io/badge/X-@Rudra496-000000?logo=x)](https://x.com/Rudra496)
- [![Facebook](https://img.shields.io/badge/Facebook-rudrasarker130-1877F2?logo=facebook)](https://www.facebook.com/rudrasarker130)
- [![YouTube](https://img.shields.io/badge/YouTube-@rudrasarker9732-FF0000?logo=youtube)](https://youtube.com/@rudrasarker9732)
- [![Dev.to](https://img.shields.io/badge/Dev.to-rudra__sarker-000000?logo=devdotto)](https://dev.to/rudra_sarker)
- [![ResearchGate](https://img.shields.io/badge/ResearchGate-Rudra_Sarker-00CCBB?logo=researchgate)](https://www.researchgate.net/profile/Rudra-Sarker-3)

---

<p align="center">
  <strong>Built with ❤️ by <a href="https://github.com/rudra496">rudra496</a> · <a href="https://www.linkedin.com/in/rudrasarker">LinkedIn</a></strong><br>
  <sub>MIT License · Free & Open Source Forever</sub>
</p>