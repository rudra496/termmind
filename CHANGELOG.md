# Changelog

All notable changes to TermMind are documented in this file.

## [2.0.0] - 2026-06-05

### Added
- **2 New LLM Providers**: Mistral AI (Mistral Large, Codestral) and Cohere (Command R+, Command R) — now 9 providers total
- **Security Scanner**: Built-in vulnerability detection with 15+ rules
  - Hardcoded secrets, SQL injection, command injection detection
  - Insecure cryptography, path traversal, CORS misconfigurations
  - Weak hash algorithms, debug mode, SSL verification warnings
  - AI-powered deep security review mode (`--ai` flag)
  - Both file and directory scanning support
- **AI Code Generation**: Generate code from natural language descriptions
  - 10 built-in templates: api, class, cli, test, docker, config, script, regex, migration, model
  - Framework-specific generation (FastAPI, Flask, pytest, etc.)
  - Save generated code directly to file with `--output`
- **Prompt Library**: 12+ built-in prompt templates for common tasks
  - Code review, explain code, optimize, add types, write docs
  - Debug errors, API design, refactor patterns, git commit messages
  - Security audit, migration planning, code summarization
  - Save and load custom prompt templates
  - Category and tag-based filtering
- **Smart Autocomplete**: Context-aware suggestions for files, commands, and actions
  - Fuzzy file matching with relevance scoring
  - Contextual action suggestions based on message content
  - Smart command completion
- **Pipe Support**: Process stdin input with AI (`cat error.log | termmind pipe`)
- **New CLI Commands**:
  - `termmind scan <path>` — Security vulnerability scanning
  - `termmind generate <type> "description"` — AI code generation
  - `termmind pipe` — Process piped stdin
  - `termmind prompts [list|categories|use]` — Prompt library management
- **New Slash Commands** (interactive mode):
  - `/scan [path]` — Quick security scan
  - `/scan ai <file>` — AI deep security review
  - `/generate <type> "desc"` — Generate code
  - `/prompt list|use|save|categories` — Prompt library
  - `/suggest` — Get contextual action suggestions
- **Landing Page Overhaul**: Comprehensive SEO-optimized website
  - Structured data (JSON-LD) for software, FAQ, and HowTo schemas
  - Open Graph and Twitter Card meta tags
  - Provider comparison table
  - Feature comparison with competitors
  - FAQ section with expandable answers
  - Testimonials section
  - Intersection Observer animations
  - Responsive design with dark theme

### Changed
- Updated banner to show "9 Providers • Security • Generate"
- Expanded provider registry from 7 to 9 providers
- Added Mistral and Cohere to config presets
- Updated sitemap.xml with section-level URLs
- Enhanced robots.txt with disallow rules for source directories

## [1.0.0] - 2025-01-15

### Added
- Initial release of TermMind
- 7 LLM provider support: OpenAI, Anthropic, Gemini, Groq, Together, OpenRouter, Ollama
- Interactive chat mode with streaming responses
- File editing with diff preview and undo
- Code review, test generation, and 8 refactoring operations
- Smart code context with automatic file relevance scoring
- AST-based code index supporting 9 languages
- Git integration (status, diff, commit, branch management)
- Session management (save, load, export)
- Snippet manager (save, search, import/export)
- Project templates (8 scaffolding templates)
- Plugin system with ABC-based discovery
- Cost tracking with budget alerts and provider comparison
- 5 color themes (Dark, Light, Solarized, Dracula, Monokai)
- Shell completions (Bash, Zsh, Fish)
- Session recording with HTML export
- ELI5 mode for simplified explanations
- Voice mode (text-to-speech via pyttsx3)
- Docker support
- CI pipeline with lint, test matrix (Python 3.9-3.13), and build verification
