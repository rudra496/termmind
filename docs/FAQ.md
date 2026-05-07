# FAQ

## General

**What is TermMind?**
TermMind is an AI-powered terminal assistant that lets you chat with LLMs (GPT, Claude, Gemini, etc.) directly in your terminal. It includes code analysis, file editing, and 40+ commands.

**Is TermMind free?**
Yes, TermMind is open source (MIT license). You can use it for free with local models via Ollama or free-tier providers like Groq and Gemini.

## Setup

**How do I get started?**
```bash
pip install termmind
termmind init
termmind chat
```

**Which provider should I use?**
- For free local usage: Ollama (requires Ollama installed)
- For free cloud usage: Groq or Gemini (requires API key)
- For best quality: OpenAI or Anthropic (paid)

**Do I need an API key?**
Only for cloud providers. Ollama works without any API key.

## Usage

**Can I switch providers mid-conversation?**
Yes, use `/provider <name>` to switch at any time.

**How do I include files in context?**
TermMind automatically detects relevant files. You can also use `/add <file>` to manually add files, or `/files` to see what's included.

**Can I undo edits?**
Yes, use `/undo` to revert the last edit, or `/undo --all` to revert all edits in the session.

## Troubleshooting

**"Cannot connect to Ollama"**
Make sure Ollama is running: `ollama serve` or start the Ollama application.

**"API key not configured"**
Run `termmind init` to set up your API key, or manually edit `~/.termmind/config.json`.

**Responses are slow**
Try switching to a faster model with `/model`, or use Groq for low-latency responses.
