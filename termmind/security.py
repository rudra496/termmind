"""Security scanner — detect common vulnerabilities in code."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .file_ops import find_files, read_file


@dataclass
class SecurityIssue:
    """A single security issue found in code."""
    severity: str  # critical, high, medium, low, info
    category: str
    title: str
    description: str
    file: str
    line: int
    code_snippet: str
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "file": self.file,
            "line": self.line,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
        }


@dataclass
class ScanResult:
    """Results from a security scan."""
    files_scanned: int = 0
    issues: list[SecurityIssue] = field(default_factory=list)
    scan_time_ms: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "medium")

    @property
    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "low")

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.issues),
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": self.medium_count,
            "low": self.low_count,
        }


# Pattern-based security rules
_SECURITY_RULES: list[dict[str, Any]] = [
    # Hardcoded secrets
    {
        "pattern": re.compile(
            r"""(?:password|passwd|pwd|secret|api_key|apikey|access_token|auth_token|private_key|token)\s*=\s*['\"][^'\"]{8,}['\"]""",
            re.IGNORECASE,
        ),
        "severity": "critical",
        "category": "Hardcoded Secrets",
        "title": "Hardcoded credential or secret",
        "description": "Secrets should not be hardcoded in source code. Use environment variables or a secrets manager.",
        "recommendation": "Use os.environ, python-dotenv, or a vault (e.g., HashiCorp Vault, AWS Secrets Manager).",
    },
    # SQL injection
    {
        "pattern": re.compile(
            r"""(?:execute|cursor\.execute|query|raw)\s*\(\s*(?:f['\"]|['\"].*%s|['\"].*\+|['\"].*\.format)""",
            re.IGNORECASE,
        ),
        "severity": "critical",
        "category": "SQL Injection",
        "title": "Potential SQL injection vulnerability",
        "description": "String formatting or concatenation in SQL queries can lead to SQL injection attacks.",
        "recommendation": "Use parameterized queries or an ORM (e.g., SQLAlchemy).",
    },
    # Eval/exec usage
    {
        "pattern": re.compile(r"""\b(?:eval|exec)\s*\(""", re.IGNORECASE),
        "severity": "high",
        "category": "Code Injection",
        "title": "Use of eval() or exec()",
        "description": "eval/exec with untrusted input allows arbitrary code execution.",
        "recommendation": "Avoid eval/exec. Use ast.literal_eval() for safe evaluation of literals.",
    },
    # Pickle deserialization
    {
        "pattern": re.compile(r"""pickle\.(?:loads?|Unpickler)\s*\(""", re.IGNORECASE),
        "severity": "high",
        "category": "Deserialization",
        "title": "Unsafe pickle deserialization",
        "description": "Unpickling untrusted data can execute arbitrary code.",
        "recommendation": "Use JSON, msgpack, or signed data instead of pickle for untrusted input.",
    },
    # Insecure random
    {
        "pattern": re.compile(r"""random\.(?:random|randint|choice|randrange)\s*\(""", re.IGNORECASE),
        "severity": "medium",
        "category": "Cryptography",
        "title": "Use of non-cryptographic random",
        "description": "The random module is not suitable for security-sensitive contexts.",
        "recommendation": "Use secrets module for security: secrets.token_hex(), secrets.choice().",
        "exclude_files": ["test_", "tests/", "conftest"],
    },
    # Shell injection
    {
        "pattern": re.compile(
            r"""(?:os\.system|os\.popen|subprocess\.(?:call|run|Popen))\s*\(\s*(?:f['\"]|['\"].*%|['\"].*\+|['\"].*\.format)""",
            re.IGNORECASE,
        ),
        "severity": "high",
        "category": "Command Injection",
        "title": "Potential command injection",
        "description": "Passing formatted strings to shell commands can allow command injection.",
        "recommendation": "Use subprocess with a list of arguments and shell=False.",
    },
    # Insecure HTTP
    {
        "pattern": re.compile(r"""https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)[:/]""", re.IGNORECASE),
        "severity": "low",
        "category": "Network",
        "title": "Insecure local HTTP connection",
        "description": "Using HTTP instead of HTTPS for local connections.",
        "recommendation": "Use HTTPS in production; HTTP for local dev only.",
        "exclude_files": ["test_", "tests/"],
    },
    # TODO/FIXME with security keywords
    {
        "pattern": re.compile(
            r"""#\s*(?:TODO|FIXME|HACK|XXX)\b.*(?:secur|auth|vuln|exploit|inject|xss|csrf)""",
            re.IGNORECASE,
        ),
        "severity": "medium",
        "category": "Code Quality",
        "title": "Security-related TODO/FIXME",
        "description": "A TODO or FIXME comment mentions a security concern that needs attention.",
        "recommendation": "Address security TODOs before deploying to production.",
    },
    # Path traversal
    {
        "pattern": re.compile(
            r"""(?:open|Path)\s*\(\s*(?:.*(?:request|params|args|input|query|user))""",
            re.IGNORECASE,
        ),
        "severity": "high",
        "category": "Path Traversal",
        "title": "Potential path traversal vulnerability",
        "description": "Using user input directly in file paths can allow directory traversal attacks.",
        "recommendation": "Validate and sanitize file paths. Use os.path.realpath() and check against allowed directories.",
    },
    # Weak hashing
    {
        "pattern": re.compile(r"""(?:hashlib\.)?(?:md5|sha1)\s*\(""", re.IGNORECASE),
        "severity": "medium",
        "category": "Cryptography",
        "title": "Use of weak hash algorithm",
        "description": "MD5 and SHA1 are considered cryptographically broken for security purposes.",
        "recommendation": "Use SHA-256 or stronger: hashlib.sha256(). For passwords, use bcrypt or argon2.",
    },
    # CORS wildcard
    {
        "pattern": re.compile(r"""(?:Access-Control-Allow-Origin|CORS_ORIGINS|allow_origin)\s*[:=]\s*['\"]?\*['\"]?"""),
        "severity": "medium",
        "category": "Web Security",
        "title": "Wildcard CORS configuration",
        "description": "Allowing all origins (*) in CORS can expose your API to cross-site attacks.",
        "recommendation": "Restrict CORS to specific trusted origins.",
    },
    # Debug mode in production
    {
        "pattern": re.compile(r"""(?:DEBUG|debug)\s*=\s*True"""),
        "severity": "low",
        "category": "Configuration",
        "title": "Debug mode enabled",
        "description": "Debug mode should be disabled in production environments.",
        "recommendation": "Use environment variables: DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'.",
    },
    # Insecure SSL
    {
        "pattern": re.compile(r"""(?:verify\s*=\s*False|CERT_NONE|ssl\._create_unverified_context)"""),
        "severity": "high",
        "category": "Network Security",
        "title": "SSL verification disabled",
        "description": "Disabling SSL verification makes connections vulnerable to man-in-the-middle attacks.",
        "recommendation": "Always verify SSL certificates. Fix certificate issues instead of disabling verification.",
    },
]


def _should_exclude(rule: dict, filepath: str) -> bool:
    """Check if file should be excluded based on rule's exclude_files."""
    excludes = rule.get("exclude_files", [])
    for exc in excludes:
        if exc in filepath:
            return True
    return False


def scan_file(filepath: str, content: Optional[str] = None) -> list[SecurityIssue]:
    """Scan a single file for security issues."""
    if content is None:
        content = read_file(filepath)
    if not content:
        return []

    issues: list[SecurityIssue] = []
    lines = content.splitlines()

    for rule in _SECURITY_RULES:
        if _should_exclude(rule, filepath):
            continue

        for match in rule["pattern"].finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            issues.append(SecurityIssue(
                severity=rule["severity"],
                category=rule["category"],
                title=rule["title"],
                description=rule["description"],
                file=filepath,
                line=line_num,
                code_snippet=snippet[:120],
                recommendation=rule.get("recommendation", ""),
            ))

    return issues


def scan_directory(directory: str, max_depth: int = 6) -> ScanResult:
    """Scan a directory for security issues."""
    import time
    start = time.time()

    result = ScanResult()
    files = find_files(directory, max_depth=max_depth)

    # Filter to source files
    source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".c", ".cpp", ".yaml", ".yml", ".toml", ".json"}
    source_files = [f for f in files if Path(f).suffix.lower() in source_exts]

    result.files_scanned = len(source_files)

    for filepath in source_files:
        issues = scan_file(filepath)
        result.issues.extend(issues)

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    result.issues.sort(key=lambda i: severity_order.get(i.severity, 5))
    result.scan_time_ms = (time.time() - start) * 1000

    return result


def ai_security_review(client: Any, filepath: str, content: str) -> str:
    """Use AI to do a deeper security review of a file."""
    prompt = f"""Perform a thorough security review of this code. Identify:
- Authentication and authorization issues
- Input validation gaps
- Data exposure risks
- Injection vulnerabilities (SQL, XSS, command)
- Insecure configurations
- Cryptographic weaknesses
- Race conditions or TOCTOU issues

For each issue found, explain:
1. The vulnerability
2. The risk level (critical/high/medium/low)
3. How to fix it

File: {filepath}
```
{content}
```"""
    messages = [{"role": "user", "content": prompt}]
    response = ""
    for chunk in client.chat_stream(messages):
        response += chunk
    return response
