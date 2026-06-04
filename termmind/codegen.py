"""Code generator — generate code from natural language descriptions."""

from typing import Any, Optional

from .file_ops import write_file

# Templates for common generation tasks
_GENERATION_TEMPLATES: dict[str, dict[str, str]] = {
    "api": {
        "system": "You are an expert API developer. Generate clean, well-structured REST API code.",
        "prompt": """Generate a {framework} REST API with the following endpoints:
{description}

Requirements:
- Proper error handling and status codes
- Input validation
- Clean route organization
- Include type hints where applicable
- Add docstrings for endpoints""",
    },
    "class": {
        "system": "You are an expert OOP developer. Generate clean, well-designed class hierarchies.",
        "prompt": """Generate a Python class for: {description}

Requirements:
- Use dataclasses or attrs where appropriate
- Include type hints
- Add comprehensive docstrings
- Include __repr__ and __eq__ methods
- Follow SOLID principles""",
    },
    "cli": {
        "system": "You are an expert CLI developer. Generate clean command-line tools.",
        "prompt": """Generate a CLI tool using {framework} for: {description}

Requirements:
- Proper argument parsing with help text
- Colored output using rich
- Error handling with meaningful messages
- Include --version and --help""",
    },
    "test": {
        "system": "You are an expert test engineer. Generate comprehensive test suites.",
        "prompt": """Generate a {framework} test suite for the following code:
```
{description}
```

Requirements:
- Test happy paths, edge cases, and error conditions
- Use fixtures and parametrize where appropriate
- Include setup and teardown
- Aim for >90% coverage
- Use clear test names that describe what is being tested""",
    },
    "docker": {
        "system": "You are an expert DevOps engineer. Generate optimized Dockerfiles.",
        "prompt": """Generate a production-ready Dockerfile for: {description}

Requirements:
- Multi-stage build where applicable
- Minimal base image (alpine/slim)
- Non-root user
- Proper .dockerignore
- Health check
- Labels and metadata""",
    },
    "config": {
        "system": "You are an expert systems developer. Generate clean configuration files.",
        "prompt": """Generate a {format} configuration file for: {description}

Requirements:
- Well-commented
- Sensible defaults
- Environment variable support
- Validation schema if applicable""",
    },
    "script": {
        "system": "You are an expert Python developer. Generate clean, efficient scripts.",
        "prompt": """Generate a Python script that: {description}

Requirements:
- Type hints
- Docstrings
- Error handling
- Command-line arguments if needed
- Logging instead of print""",
    },
    "regex": {
        "system": "You are a regex expert. Generate precise regular expressions.",
        "prompt": """Generate a regular expression that matches: {description}

Provide:
1. The regex pattern
2. Explanation of each part
3. Test cases (matches and non-matches)
4. Python usage example with re module""",
    },
    "migration": {
        "system": "You are a database expert. Generate clean migration scripts.",
        "prompt": """Generate a {framework} database migration for: {description}

Requirements:
- Include both up and down migrations
- Add indexes for performance
- Include foreign key constraints
- Handle edge cases (empty tables, existing data)""",
    },
    "model": {
        "system": "You are a database expert. Generate clean ORM models.",
        "prompt": """Generate a {framework} model for: {description}

Requirements:
- Type hints and validators
- Relationships defined
- Indexes for queried fields
- String representation
- Created/updated timestamps""",
    },
}


def get_generation_template(template_type: str) -> dict[str, str]:
    """Get a generation template by type."""
    return _GENERATION_TEMPLATES.get(template_type, _GENERATION_TEMPLATES["script"])


def list_template_types() -> list[str]:
    """List available generation template types."""
    return list(_GENERATION_TEMPLATES.keys())


def generate_code(
    client: Any,
    description: str,
    template_type: str = "script",
    framework: str = "",
    extra_context: str = "",
) -> str:
    """Generate code using AI based on a description and template."""
    template = get_generation_template(template_type)
    prompt = template["prompt"].format(
        description=description,
        framework=framework or "Python",
        format=framework or "TOML",
    )
    if extra_context:
        prompt += f"\n\nAdditional context:\n{extra_context}"

    messages = [{"role": "user", "content": prompt}]
    system_prompt = template["system"]

    response = ""
    for chunk in client.chat_stream(messages, system_prompt=system_prompt):
        response += chunk
    return response


def generate_and_save(
    client: Any,
    description: str,
    output_file: str,
    template_type: str = "script",
    framework: str = "",
) -> str:
    """Generate code and save to a file."""
    response = generate_code(client, description, template_type, framework)

    # Extract code from markdown fences if present
    clean = response.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines)

    write_file(output_file, clean)
    return response
