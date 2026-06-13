"""Prompt library — pre-built prompt templates for common tasks."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

LIBRARY_DIR = Path.home() / ".termmind" / "prompts"


@dataclass
class PromptTemplate:
    """A reusable prompt template."""

    name: str
    category: str
    description: str
    system_prompt: str = ""
    user_prompt: str = ""
    tags: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)

    def render(self, **kwargs: str) -> dict[str, str]:
        """Render the template with variable substitutions."""
        system = self.system_prompt
        user = self.user_prompt
        for key, value in kwargs.items():
            system = system.replace(f"{{{key}}}", value)
            user = user.replace(f"{{{key}}}", value)
        return {"system": system, "user": user}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PromptTemplate":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# Built-in prompt templates
BUILTIN_TEMPLATES: list[PromptTemplate] = [
    PromptTemplate(
        name="code-review",
        category="Code Quality",
        description="Comprehensive code review with actionable feedback",
        system_prompt="You are a senior code reviewer. Be constructive, specific, and prioritize issues by severity.",
        user_prompt="""Review this code thoroughly. Check for:
- Bugs and logic errors
- Security vulnerabilities
- Performance issues
- Code style and best practices
- Error handling gaps
- Documentation needs

```
{code}
```

Provide feedback organized by severity (critical, high, medium, low).""",
        tags=["review", "quality", "security"],
        variables=["code"],
    ),
    PromptTemplate(
        name="explain-code",
        category="Understanding",
        description="Explain code in plain English with examples",
        system_prompt="You are a patient coding teacher. Explain clearly with examples.",
        user_prompt="""Explain this code step by step:
1. What does it do overall?
2. Break down each function/block
3. Explain any complex patterns
4. Give a simple usage example

```
{code}
```""",
        tags=["explain", "learn", "understand"],
        variables=["code"],
    ),
    PromptTemplate(
        name="optimize",
        category="Performance",
        description="Optimize code for better performance",
        system_prompt="You are a performance optimization expert. Focus on measurable improvements.",
        user_prompt="""Optimize this code for performance. For each change:
1. Explain the bottleneck
2. Show the optimized version
3. Estimate the improvement

```
{code}
```

Also suggest algorithmic improvements if applicable.""",
        tags=["optimize", "performance", "speed"],
        variables=["code"],
    ),
    PromptTemplate(
        name="add-types",
        category="Code Quality",
        description="Add comprehensive type hints to Python code",
        system_prompt="You are a Python typing expert. Add precise type annotations.",
        user_prompt="""Add comprehensive type hints to this Python code:
- Use typing module (Optional, Union, etc.)
- Add return types
- Use TypeVar for generics where appropriate
- Add TypeAlias for complex types

```python
{code}
```

Output the complete file with type hints added.""",
        tags=["types", "python", "typing"],
        variables=["code"],
    ),
    PromptTemplate(
        name="write-docs",
        category="Documentation",
        description="Generate comprehensive documentation for code",
        system_prompt="You are a technical writer. Write clear, comprehensive documentation.",
        user_prompt="""Generate documentation for this code:
1. Module-level docstring
2. Function/class docstrings (Google style)
3. Inline comments for complex logic
4. Usage examples in docstrings

```
{code}
```""",
        tags=["docs", "documentation", "docstring"],
        variables=["code"],
    ),
    PromptTemplate(
        name="debug-error",
        category="Debugging",
        description="Debug an error with stack trace analysis",
        system_prompt="You are a debugging expert. Analyze errors systematically.",
        user_prompt="""Help me debug this error:

Error/Traceback:
```
{error}
```

Code:
```
{code}
```

1. Identify the root cause
2. Explain why it happens
3. Provide the fix
4. Suggest how to prevent similar issues""",
        tags=["debug", "error", "fix", "traceback"],
        variables=["error", "code"],
    ),
    PromptTemplate(
        name="api-design",
        category="Architecture",
        description="Design a RESTful API with best practices",
        system_prompt="You are an API architect. Design clean, RESTful APIs following best practices.",
        user_prompt="""Design a REST API for: {description}

Include:
1. Endpoint definitions (method, path, params)
2. Request/response schemas
3. Error handling strategy
4. Authentication approach
5. Pagination strategy
6. Rate limiting recommendations""",
        tags=["api", "rest", "design", "architecture"],
        variables=["description"],
    ),
    PromptTemplate(
        name="refactor-pattern",
        category="Refactoring",
        description="Refactor code using a specific design pattern",
        system_prompt="You are a design patterns expert. Apply patterns correctly and idiomatically.",
        user_prompt="""Refactor this code using the {pattern} design pattern:

```
{code}
```

1. Explain why this pattern fits
2. Show the refactored code
3. Highlight the benefits
4. Show before/after comparison""",
        tags=["refactor", "pattern", "design-pattern", "oop"],
        variables=["pattern", "code"],
    ),
    PromptTemplate(
        name="git-commit",
        category="Workflow",
        description="Generate a descriptive git commit message",
        system_prompt="You write excellent git commit messages following Conventional Commits.",
        user_prompt="""Generate a git commit message for these changes:

```diff
{diff}
```

Follow Conventional Commits format:
- type(scope): description
- Include body for complex changes
- Reference issues if applicable""",
        tags=["git", "commit", "workflow"],
        variables=["diff"],
    ),
    PromptTemplate(
        name="summarize",
        category="Understanding",
        description="Summarize a large codebase or file",
        system_prompt="You are a code analyst. Provide clear, structured summaries.",
        user_prompt="""Summarize this code in a structured format:

```
{code}
```

Provide:
1. One-line summary
2. Key components and their roles
3. Dependencies and imports
4. Public API surface
5. Potential improvements""",
        tags=["summarize", "analyze", "overview"],
        variables=["code"],
    ),
    PromptTemplate(
        name="security-audit",
        category="Security",
        description="Perform a security audit on code",
        system_prompt="You are a security auditor. Be thorough and prioritize findings by risk.",
        user_prompt="""Perform a security audit on this code:

```
{code}
```

Check for:
1. Injection vulnerabilities (SQL, XSS, command)
2. Authentication/authorization issues
3. Data exposure risks
4. Insecure configurations
5. Cryptographic weaknesses
6. OWASP Top 10 compliance""",
        tags=["security", "audit", "vulnerability"],
        variables=["code"],
    ),
    PromptTemplate(
        name="migration-plan",
        category="Architecture",
        description="Plan a code migration or upgrade",
        system_prompt="You are a migration specialist. Plan thorough, safe migrations.",
        user_prompt="""Create a migration plan to move from {source} to {target}.

Current code:
```
{code}
```

Include:
1. Step-by-step migration plan
2. Breaking changes to watch for
3. Compatibility shims
4. Testing strategy
5. Rollback plan""",
        tags=["migration", "upgrade", "refactor"],
        variables=["source", "target", "code"],
    ),
]


def _ensure_dir() -> None:
    """Ensure the prompt library directory exists."""
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def list_templates(category: str = "", tag: str = "") -> list[PromptTemplate]:
    """List available prompt templates, optionally filtered by category or tag."""
    all_templates = list(BUILTIN_TEMPLATES)

    # Load user templates
    _ensure_dir()
    for f in LIBRARY_DIR.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, list):
                for d in data:
                    all_templates.append(PromptTemplate.from_dict(d))
            else:
                all_templates.append(PromptTemplate.from_dict(data))
        except (json.JSONDecodeError, OSError, KeyError):
            continue

    if category:
        all_templates = [t for t in all_templates if t.category.lower() == category.lower()]
    if tag:
        all_templates = [t for t in all_templates if tag.lower() in [tg.lower() for tg in t.tags]]

    return all_templates


def get_template(name: str) -> Optional[PromptTemplate]:
    """Get a specific template by name."""
    for t in list_templates():
        if t.name == name:
            return t
    return None


def save_template(template: PromptTemplate) -> str:
    """Save a custom template to the user library."""
    _ensure_dir()
    filepath = LIBRARY_DIR / f"{template.name}.json"
    with open(filepath, "w") as f:
        json.dump(template.to_dict(), f, indent=2)
    return str(filepath)


def delete_template(name: str) -> bool:
    """Delete a custom template."""
    filepath = LIBRARY_DIR / f"{name}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False


def list_categories() -> list[str]:
    """List all unique categories."""
    return sorted(set(t.category for t in list_templates()))


def render_template(name: str, **kwargs: str) -> Optional[dict[str, str]]:
    """Render a template by name with variable substitutions."""
    template = get_template(name)
    if not template:
        return None
    return template.render(**kwargs)
