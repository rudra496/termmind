# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in TermMind,
please report it responsibly.

### How to Report

1. **Do NOT** open a public issue for security vulnerabilities.
2. Email your report to: [INSERT SECURITY EMAIL]
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

### What to Expect

- We will acknowledge receipt within 48 hours
- We will provide an initial assessment within 7 days
- We will keep you informed of progress
- We will credit you in the release notes (unless you prefer anonymity)

### Disclosure Policy

- We will disclose the vulnerability publicly after a fix is released
- We aim to resolve critical vulnerabilities within 7 days
- We aim to resolve high-severity vulnerabilities within 30 days

## Security Best Practices for Users

- **API Keys**: Store your API keys in `~/.termmind/config.json` with restrictive
  file permissions (`chmod 600`). Never commit API keys to version control.
- **File Operations**: Review file changes before applying edits. Use `/undo`
  to revert unwanted changes.
- **Shell Commands**: Review commands before running with `/run`. TermMind can
  execute arbitrary shell commands.
- **Providers**: Use local models (Ollama) for sensitive code to avoid sending
  code to external APIs.
- **Configuration**: Review `~/.termmind/config.json` and ensure sensitive values
  are not exposed.

## Known Security Considerations

- TermMind sends code to configured AI providers for analysis. Use local models
  for proprietary or sensitive code.
- The `/run` command can execute arbitrary shell commands — use with caution.
- Session data is stored in plain text in `~/.termmind/sessions/`.
- Snippet data is stored in plain text in `~/.termmind/snippets/`.
