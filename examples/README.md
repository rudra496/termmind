# Examples

Runnable examples demonstrating TermMind features.

## Prerequisites

```bash
pip install -e .
# Configure a provider first
termmind init
```

## Usage Examples

### Chat with Ollama (free, local)

```bash
# Make sure Ollama is running, then:
termmind chat
# Inside the chat:
❯ /provider ollama
❯ Explain how Python decorators work
```

### One-shot question

```bash
termmind ask "What is the time complexity of binary search?"
```

### Code review

```bash
termmind review src/
```

### Edit a file with AI

```bash
termmind edit main.py "Add input validation to the parse_args function"
```

### Generate tests

```bash
termmind test utils.py --framework pytest
```

### Explain a file

```bash
termmind explain cli.py
```

### Add docstrings

```bash
termmind docstring module.py
```

### Git integration

```bash
# Start chat in a git repo
termmind chat
# Inside the chat:
❯ /git status
❯ /git diff
❯ /git commit
```

## CLI Pipe Usage

```bash
# Pipe file content for analysis
cat error.log | termmind ask "What caused this error?"

# Generate commit messages
git diff | termmind ask "Write a concise commit message for these changes"
```
