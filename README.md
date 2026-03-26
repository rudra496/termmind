# TermMind 🧠

> A modern, open-source AI terminal assistant. Free, beautiful, and lives in your terminal.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/CLI-Terminal-purple.svg" alt="CLI">
</p>

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
- 🔌 **Multi-provider** — OpenAI, Google Gemini, Groq, Together.ai, OpenRouter, Ollama
- 💰 **Free tiers supported** — Works with Gemini, Groq, and Ollama at zero cost
- 📁 **Smart context** — Automatically includes relevant files from your project
- ✏️ **File editing** — AI-powered file creation and editing with diff support
- ↩️ **Undo system** — Every edit is tracked; undo any change with `/undo`
- 💾 **Session management** — Save and load conversations
- 📊 **Cost tracking** — Real-time token count and cost estimation
- 🔄 **Provider switching** — Change models mid-conversation with `/provider`
- 🌳 **File tree** — Visual project structure with `.termindignore` support
- 🔍 **Code search** — Find anything in your project files
- 🐙 **Git integration** — Status, diff, log, and AI-generated commit messages
- ⚡ **Streaming** — See responses as they're generated, not after

## 🚀 Installation

```bash
pip install termind
```

Or from source:

```bash
git clone https://github.com/nicepkg/termmind.git
cd termmind
pip install -e .
```

## 🏁 Quick Start

### 1. Set up your API

```bash
termind init
```

This walks you through selecting a provider and entering your API key. You can also manually edit `~/.termind/config.json`.

### 2. Start chatting

```bash
termind chat
```

### 3. Ask questions

```bash
termind ask "Explain async/await in Python"
```

### 4. Edit files

```bash
termind edit main.py "Add input validation to the parse_args function"
```

### 5. Review code

```bash
termind review ./src
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `termind init` | Configure API provider, key, and model |
| `termind chat` | Start interactive chat session |
| `termind ask "q"` | One-shot question (no session) |
| `termind edit file` | Edit a file with AI |
| `termind review path` | Review code in directory |
| `termind explain file` | Explain a file |
| `termind test file` | Generate tests for a file |
| `termind history` | Show saved sessions |
| `termind config` | Show current configuration |

### Chat Commands

Inside `termind chat`, use slash commands:

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
| `/help` | Show all commands |

## 🔑 Provider Setup

### 🆓 Free Options (no cost)

#### Google Gemini
1. Go to [aistudio.google.com](https://aistudio.google.com/apikey)
2. Create a free API key
3. Select `gemini` during `termind init`

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

Config is stored at `~/.termind/config.json`:

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

### .termindignore

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

## 🛠️ Development

```bash
# Clone
git clone https://github.com/nicepkg/termmind.git
cd termmind

# Install in dev mode
pip install -e .

# Run directly
python -m termind.cli chat

# Test
python -m pytest
```

### Project Structure

```
termmind/
├── termind/
│   ├── __init__.py      # Version info
│   ├── cli.py           # Main CLI entry point
│   ├── api.py           # API client (streaming, multi-provider)
│   ├── config.py        # Configuration management
│   ├── context.py       # Smart file context builder
│   ├── commands.py      # Slash command handlers
│   ├── file_ops.py      # File read/write/edit/search
│   ├── git.py           # Git operations
│   ├── themes.py        # Color themes
│   └── utils.py         # Token counting, utilities
├── pyproject.toml
├── README.md
└── LICENSE
```

## 🤝 Contributing

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
