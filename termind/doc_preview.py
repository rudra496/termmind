"""Inline Doc Preview — extract and display docstrings/signatures for project symbols.

Commands:
    /docs <name>              — Show docstring for a function/method
    /docs <Class.method>      — Show docstring for a class method
    /docs <module.Class.method> — Dotted path lookup
    /docs --file <path>       — List all documented symbols in a file
    /docs --update            — Re-scan and cache docstrings from source
    /docs --suggest <prefix>  — Fuzzy-suggest matching symbols

Supports: Python, JavaScript, TypeScript, Go, Rust, Java.
"""

import ast
import os
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .file_ops import find_files, read_file
from .memory import build_index, load_index, query_functions, query_classes


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DocEntry:
    """A parsed documentation entry for one symbol."""
    name: str
    kind: str            # "function", "method", "class"
    signature: str       # e.g. "parse(path: str, encoding: str = 'utf-8') -> dict"
    return_type: str = ""
    docstring: str = ""
    file: str = ""
    line: int = 0
    params: List[Dict[str, str]] = field(default_factory=list)
    language: str = ""
    parent_class: str = ""
    module: str = ""


# ---------------------------------------------------------------------------
# Per-language docstring extractors
# ---------------------------------------------------------------------------

def _extract_python_docstring(filepath: str, content: str) -> List[DocEntry]:
    """Parse a Python file with ast and extract docstrings."""
    entries: List[DocEntry] = []
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return entries

    def _params_str(func_node: ast.FunctionDef) -> Tuple[str, List[Dict[str, str]], str]:
        """Build signature parts from an AST function node."""
        import inspect
        params = []
        for arg in func_node.args.args:
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            default = ""
            defaults_offset = len(func_node.args.args) - len(func_node.args.defaults)
            idx = func_node.args.args.index(arg)
            if idx >= defaults_offset:
                d = func_node.args.defaults[idx - defaults_offset]
                default = f" = {ast.unparse(d)}"
            params.append({"name": arg.arg, "type": annotation, "default": default})

        if func_node.args.vararg:
            va_type = ast.unparse(func_node.args.vararg.annotation) if func_node.args.vararg.annotation else ""
            params.append({"name": f"*{func_node.args.vararg.arg}", "type": va_type, "default": ""})
        if func_node.args.kwarg:
            kw_type = ast.unparse(func_node.args.kwarg.annotation) if func_node.args.kwarg.annotation else ""
            params.append({"name": f"**{func_node.args.kwarg.arg}", "type": kw_type, "default": ""})

        sig_parts = []
        for p in params:
            part = p["name"]
            if p["type"]:
                part += f": {p['type']}"
            part += p["default"]
            sig_parts.append(part)

        ret = ast.unparse(func_node.returns) if func_node.returns else ""
        return ", ".join(sig_parts), params, ret

    def _decorators(func_node: ast.FunctionDef) -> str:
        decs = []
        for d in func_node.decorator_list:
            decs.append(ast.unparse(d))
        prefix = ""
        if "staticmethod" in decs:
            prefix = "@staticmethod "
        elif "classmethod" in decs:
            prefix = "@classmethod "
        elif decs:
            prefix = "@" + ", @".join(decs) + " "
        return prefix

    # Module-level docstring
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        mod_doc = tree.body[0].value.value
        if isinstance(mod_doc, str) and mod_doc.strip():
            entries.append(DocEntry(
                name=Path(filepath).stem, kind="module",
                signature="module", docstring=mod_doc.strip(),
                file=filepath, line=1, language="python",
            ))

    # Classes
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            continue

        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            entries.append(DocEntry(
                name=node.name, kind="class",
                signature=f"class {node.name}({bases})" if bases else f"class {node.name}",
                docstring=doc.strip() if doc else "",
                file=filepath, line=node.lineno, language="python",
            ))

        elif isinstance(node, ast.FunctionDef):
            # Determine if it's a method (direct child of a class)
            parent = ""
            for class_node in ast.walk(tree):
                if isinstance(class_node, ast.ClassDef):
                    for item in class_node.body:
                        if item is node:
                            parent = class_node.name
                            break
            kind = "method" if parent else "function"
            sig_params, params, ret = _params_str(node)
            full_sig = f"{node.name}({sig_params})"
            if ret:
                full_sig += f" -> {ret}"
            doc = ast.get_docstring(node) or ""
            dec_prefix = _decorators(node)
            entries.append(DocEntry(
                name=node.name, kind=kind,
                signature=dec_prefix + full_sig if dec_prefix else full_sig,
                return_type=ret, docstring=doc.strip() if doc else "",
                file=filepath, line=node.lineno, params=params,
                language="python", parent_class=parent,
            ))

    return entries


def _extract_js_ts_docstring(filepath: str, content: str) -> List[DocEntry]:
    """Extract JSDoc comments for JS/TS functions and classes."""
    entries: List[DocEntry] = []
    lines = content.splitlines()
    ext = Path(filepath).suffix.lower()
    lang = "typescript" if ext in (".ts", ".tsx") else "javascript"

    # JSDoc pattern: /** ... */ immediately before a function/class
    jsdoc_re = re.compile(
        r"/\*\*[\s\S]*?\*/\s*"
        r"((?:export\s+)?(?:default\s+)?(?:async\s+)?"
        r"(?:function\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
        r"(?:\s*:\s*([^,{\s]+))?|"
        r"class\s+(\w+)(?:<[^>]*>)?(?:\s+extends\s+(\w+))?"
        r"(?:\s+implements\s+[^{]*)?))",
    )

    for match in jsdoc_re.finditer(content):
        full = match.group(0)
        doc_block = re.search(r"/\*\*([\s\S]*?)\*/", full)
        doc_text = ""
        if doc_block:
            raw = doc_block.group(1)
            doc_text = "\n".join(
                line.strip().lstrip("*").strip()
                for line in raw.splitlines()
            ).strip()

        func_name = match.group(2)
        if func_name:
            params_str = match.group(3) or ""
            ret = (match.group(4) or "").strip()
            sig = f"function {func_name}({params_str})"
            if ret:
                sig += f": {ret}"

            params = _parse_js_params(params_str)
            entries.append(DocEntry(
                name=func_name, kind="function", signature=sig,
                return_type=ret, docstring=doc_text,
                file=filepath, line=content[:match.start()].count("\n") + 1,
                params=params, language=lang,
            ))
        else:
            cls_name = match.group(5)
            if cls_name:
                extends = match.group(6) or ""
                sig = f"class {cls_name}"
                if extends:
                    sig += f" extends {extends}"
                entries.append(DocEntry(
                    name=cls_name, kind="class", signature=sig,
                    docstring=doc_text,
                    file=filepath, line=content[:match.start()].count("\n") + 1,
                    language=lang,
                ))

    # Also extract non-JSDoc functions (for signatures even without docs)
    func_re = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
        r"(?:\s*:\s*([^,{\s]+))?",
    )
    seen_names = {e.name for e in entries}
    for match in func_re.finditer(content):
        name = match.group(1)
        if name in seen_names:
            continue
        params_str = match.group(2) or ""
        ret = (match.group(3) or "").strip()
        sig = f"function {name}({params_str})"
        if ret:
            sig += f": {ret}"
        params = _parse_js_params(params_str)
        entries.append(DocEntry(
            name=name, kind="function", signature=sig,
            return_type=ret, docstring="",
            file=filepath, line=content[:match.start()].count("\n") + 1,
            params=params, language=lang,
        ))

    return entries


def _parse_js_params(params_str: str) -> List[Dict[str, str]]:
    """Parse JS/TS function parameters into structured list."""
    params = []
    if not params_str.strip():
        return params
    # Simple split — doesn't handle complex destructuring but covers common cases
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        name = p
        ptype = ""
        default = ""
        # Handle type annotation: name: Type = default
        m = re.match(r"(\w+)(?:\s*:\s*([^=]+?))?(?:\s*=\s*(.+))?$", p)
        if m:
            name = m.group(1)
            ptype = (m.group(2) or "").strip()
            default = f" = {m.group(3)}" if m.group(3) else ""
        # Spread: ...args
        if p.startswith("..."):
            name = p
            ptype = ""
            default = ""
        params.append({"name": name, "type": ptype, "default": default})
    return params


def _extract_go_docstring(filepath: str, content: str) -> List[DocEntry]:
    """Extract Go doc comments for functions and types."""
    entries: List[DocEntry] = []
    lines = content.splitlines()

    # Go convention: doc comment is the comment block immediately preceding the declaration
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Function: func (receiver) Name(params) (returns)
        func_match = re.match(
            r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(([^)]*)\)(?:\s*\(([^)]*)\))?",
            stripped,
        )
        if func_match:
            name = func_match.group(1)
            params_str = func_match.group(2)
            return_str = func_match.group(3) or ""

            doc = _go_doc_above(lines, i)
            sig = f"func {name}({params_str})"
            if return_str:
                sig += f" ({return_str})"

            params = []
            for p in (params_str or "").split(","):
                p = p.strip()
                if not p:
                    continue
                parts = p.split()
                pname = parts[-1] if parts else p
                ptype = " ".join(parts[:-1]) if len(parts) > 1 else ""
                params.append({"name": pname, "type": ptype, "default": ""})

            entries.append(DocEntry(
                name=name, kind="function", signature=sig,
                return_type=return_str.strip(), docstring=doc,
                file=filepath, line=i + 1, params=params, language="go",
            ))
            continue

        # Type: type Name struct
        type_match = re.match(r"type\s+(\w+)\s+struct\s*\{", stripped)
        if type_match:
            name = type_match.group(1)
            doc = _go_doc_above(lines, i)
            entries.append(DocEntry(
                name=name, kind="class", signature=f"type {name} struct",
                docstring=doc, file=filepath, line=i + 1, language="go",
            ))

    return entries


def _go_doc_above(lines: List[str], idx: int) -> str:
    """Collect Go doc comment block above line idx."""
    doc_lines = []
    i = idx - 1
    while i >= 0 and lines[i].strip().startswith("//"):
        doc_lines.append(lines[i].strip().lstrip("/").strip())
        i -= 1
    doc_lines.reverse()
    return "\n".join(doc_lines).strip()


def _extract_rust_docstring(filepath: str, content: str) -> List[DocEntry]:
    """Extract Rust doc comments (/// and //!) for functions and structs."""
    entries: List[DocEntry] = []
    lines = content.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Function: pub fn name<T>(params) -> Ret
        func_match = re.match(
            r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)(?:<[^>]*>)?\s*\(([^)]*)\)"
            r"(?:\s*->\s*([^,{]+))?",
            stripped,
        )
        if func_match:
            name = func_match.group(1)
            params_str = func_match.group(2)
            ret = (func_match.group(3) or "").strip()
            doc = _rust_doc_above(lines, i)
            sig = f"fn {name}({params_str})"
            if ret:
                sig += f" -> {ret}"

            params = _parse_rust_params(params_str)
            entries.append(DocEntry(
                name=name, kind="function", signature=sig,
                return_type=ret, docstring=doc,
                file=filepath, line=i + 1, params=params, language="rust",
            ))
            continue

        # Struct: pub struct Name { ... }
        struct_match = re.match(r"(?:pub\s+)?struct\s+(\w+)(?:<[^>]*>)?", stripped)
        if struct_match:
            name = struct_match.group(1)
            doc = _rust_doc_above(lines, i)
            entries.append(DocEntry(
                name=name, kind="class", signature=f"struct {name}",
                docstring=doc, file=filepath, line=i + 1, language="rust",
            ))
            continue

        # Impl block methods (simple: fn name inside impl)
        impl_match = re.match(r"impl\s+", stripped)
        if impl_match:
            # Scan forward for methods
            j = i + 1
            while j < len(lines):
                l = lines[j].strip()
                if l.startswith("}"):
                    break
                m = re.match(
                    r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)(?:<[^>]*>)?\s*\(([^)]*)\)"
                    r"(?:\s*->\s*([^,{]+))?",
                    l,
                )
                if m:
                    mname = m.group(1)
                    mparams = m.group(2)
                    mret = (m.group(3) or "").strip()
                    mdoc = _rust_doc_above(lines, j)
                    msig = f"fn {mname}({mparams})"
                    if mret:
                        msig += f" -> {mret}"
                    entries.append(DocEntry(
                        name=mname, kind="method", signature=msig,
                        return_type=mret, docstring=mdoc,
                        file=filepath, line=j + 1,
                        params=_parse_rust_params(mparams), language="rust",
                    ))
                j += 1

    return entries


def _rust_doc_above(lines: List[str], idx: int) -> str:
    """Collect Rust doc comments (///) above line idx."""
    doc_lines = []
    i = idx - 1
    while i >= 0 and lines[i].strip().startswith("///"):
        doc_lines.append(lines[i].strip().lstrip("/").strip())
        i -= 1
    doc_lines.reverse()
    return "\n".join(doc_lines).strip()


def _parse_rust_params(params_str: str) -> List[Dict[str, str]]:
    """Parse Rust function parameters."""
    params = []
    if not params_str.strip():
        return params
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        # Rust: name: Type or mut name: Type or self or &self or &mut self
        if p in ("self", "&self", "&mut self", "mut self"):
            params.append({"name": p, "type": "", "default": ""})
            continue
        # name: Type or mut name: Type
        m = re.match(r"(?:mut\s+)?(\w+)\s*:\s*(.+)", p)
        if m:
            params.append({"name": m.group(1), "type": m.group(2).strip(), "default": ""})
        else:
            params.append({"name": p, "type": "", "default": ""})
    return params


def _extract_java_docstring(filepath: str, content: str) -> List[DocEntry]:
    """Extract Javadoc for Java methods and classes."""
    entries: List[DocEntry] = []

    # Match Javadoc /** ... */ followed by class or method
    pattern = re.compile(
        r"/\*\*[\s\S]*?\*/\s*"
        r"((?:public|private|protected|static|\s)+"
        r"(?:(?:abstract|final|static|synchronized|native)\s+)*"
        r"(?:class|interface|enum|@?\w[\w<>]*?)\s+(\w+)"
        r"(?:<[^>]*>)?(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?"
        r"|"
        r"(?:public|private|protected|static|\s)+"
        r"(?:(?:abstract|final|static|synchronized|native)\s+)*"
        r"[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\))",
    )

    for match in pattern.finditer(content):
        doc_block = re.search(r"/\*\*([\s\S]*?)\*/", match.group(0))
        doc_text = ""
        if doc_block:
            raw = doc_block.group(1)
            doc_text = "\n".join(
                line.strip().lstrip("*").strip()
                for line in raw.splitlines()
            ).strip()

        line_num = content[:match.start()].count("\n") + 1

        cls_name = match.group(2)
        if cls_name:
            entries.append(DocEntry(
                name=cls_name, kind="class",
                signature=f"class {cls_name}",
                docstring=doc_text,
                file=filepath, line=line_num, language="java",
            ))
            continue

        method_name = match.group(3)
        params_str = match.group(4) or ""
        if method_name:
            params = _parse_java_params(params_str)
            sig = f"{method_name}({params_str})"
            entries.append(DocEntry(
                name=method_name, kind="function", signature=sig,
                docstring=doc_text,
                file=filepath, line=line_num, params=params, language="java",
            ))

    return entries


def _parse_java_params(params_str: str) -> List[Dict[str, str]]:
    """Parse Java method parameters: Type name, Type name, ..."""
    params = []
    if not params_str.strip():
        return params
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        parts = p.rsplit(None, 1)
        if len(parts) == 2:
            params.append({"name": parts[1], "type": parts[0], "default": ""})
        else:
            params.append({"name": p, "type": "", "default": ""})
    return params


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXTRACTORS = {
    ".py": _extract_python_docstring,
    ".js": _extract_js_ts_docstring,
    ".jsx": _extract_js_ts_docstring,
    ".ts": _extract_js_ts_docstring,
    ".tsx": _extract_js_ts_docstring,
    ".go": _extract_go_docstring,
    ".rs": _extract_rust_docstring,
    ".java": _extract_java_docstring,
}


def extract_docs(filepath: str, content: Optional[str] = None) -> List[DocEntry]:
    """Extract all doc entries from a file."""
    if content is None:
        content = read_file(filepath)
    if content is None:
        return []

    ext = Path(filepath).suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor:
        return extractor(filepath, content)

    # Fallback: try to get basic function info from the code index
    return []


def extract_all_docs(project_root: str) -> List[DocEntry]:
    """Extract docs from all supported files in the project."""
    all_entries: List[DocEntry] = []
    files = find_files(project_root, max_depth=8)
    for filepath in files:
        ext = Path(filepath).suffix.lower()
        if ext in _EXTRACTORS:
            all_entries.extend(extract_docs(filepath))
    return all_entries


# ---------------------------------------------------------------------------
# Query & lookup
# ---------------------------------------------------------------------------

def lookup_symbol(project_root: str, query: str) -> List[DocEntry]:
    """Look up a symbol by name. Supports dotted paths like 'module.Class.method'."""
    # Try to load cached index; fall back to fresh extract
    entries = extract_all_docs(project_root)

    parts = query.strip().split(".")

    # Direct name match
    matches = [e for e in entries if e.name == query.strip()]

    if not matches and len(parts) == 1:
        # Fuzzy: prefix match
        matches = [e for e in entries if e.name.startswith(parts[0])]

    if not matches and len(parts) == 2:
        # ClassName.method
        cls_name, method_name = parts
        matches = [
            e for e in entries
            if e.parent_class == cls_name and e.name == method_name
        ]
        if not matches:
            # Also check module.Class
            matches = [
                e for e in entries
                if e.name == cls_name and e.kind == "class"
            ]
            # If class found, also grab its methods
            if matches:
                cls = matches[0]
                matches.extend(
                    e for e in entries
                    if e.parent_class == cls_name
                )

    if not matches and len(parts) >= 3:
        # module.Class.method
        method_name = parts[-1]
        cls_name = parts[-2]
        module = ".".join(parts[:-2])
        matches = [
            e for e in entries
            if e.name == method_name and e.parent_class == cls_name
        ]
        # If module specified, filter by file path containing module
        if matches and module:
            matches = [e for e in matches if module in e.file.replace("/", ".")]

    if not matches:
        # Broader fuzzy: substring match
        q_lower = query.lower()
        matches = [e for e in entries if q_lower in e.name.lower()]

    # Deduplicate by (name, file, line)
    seen = set()
    unique = []
    for e in matches:
        key = (e.name, e.file, e.line)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique[:10]


def list_file_docs(project_root: str, filepath: str) -> List[DocEntry]:
    """List all documented symbols in a specific file."""
    full_path = filepath
    if not os.path.isabs(full_path):
        full_path = os.path.join(project_root, filepath)
    return extract_docs(full_path)


def suggest_symbols(project_root: str, prefix: str) -> List[DocEntry]:
    """Suggest symbols matching a prefix (for autocomplete)."""
    entries = extract_all_docs(project_root)
    prefix_lower = prefix.lower()
    return [
        e for e in entries
        if e.name.lower().startswith(prefix_lower)
           or prefix_lower in e.name.lower()
    ][:15]


# ---------------------------------------------------------------------------
# Rich rendering
# ---------------------------------------------------------------------------

def render_doc_entry(entry: DocEntry, console: Console) -> None:
    """Render a single DocEntry as a Rich panel."""
    # Build header
    kind_icon = {
        "function": "λ", "method": "ƒ", "class": "◆", "module": "📦",
    }.get(entry.kind, "•")

    kind_label = entry.kind.capitalize()
    header = f"{kind_icon}  [bold cyan]{entry.name}[/bold cyan]  [dim]{kind_label}[/dim]"

    if entry.parent_class:
        header += f"  [dim]← {entry.parent_class}[/dim]"

    # Build body
    body_parts = []

    # Signature
    sig_text = Text(entry.signature)
    lang = entry.language or "python"
    body_parts.append(Panel(sig_text, title="[bold]Signature[/bold]", border_style="blue", expand=False))

    # Location
    rel = os.path.relpath(entry.file, ".") if os.path.exists(entry.file) else entry.file
    loc = f"[dim]{rel}:{entry.line}[/dim]"
    if entry.language:
        loc += f"  [dim]({entry.language})[/dim]"
    body_parts.append(loc)

    # Return type
    if entry.return_type:
        body_parts.append(f"[bold]Returns:[/bold] [green]{entry.return_type}[/green]")

    # Parameters table
    if entry.params:
        table = Table(show_header=True, header_style="bold", border_style="dim")
        table.add_column("Parameter", style="cyan", min_width=15)
        table.add_column("Type", style="green", min_width=10)
        table.add_column("Default", style="yellow")
        for p in entry.params:
            table.add_row(p["name"], p["type"] or "[dim]—[/dim]", p["default"] or "")
        body_parts.append(table)

    # Docstring
    if entry.docstring:
        # Clean up docstring
        doc = entry.docstring.strip()
        if len(doc) > 800:
            doc = doc[:800] + "\n[dim]... (truncated)[/dim]"

        # Try syntax highlighting
        try:
            syn = Syntax(doc, "markdown", theme="monokai", word_wrap=True)
            body_parts.append(Panel(syn, title="[bold]Docstring[/bold]", border_style="green", expand=False))
        except Exception:
            body_parts.append(Panel(doc, title="[bold]Docstring[/bold]", border_style="green", expand=False))
    else:
        body_parts.append("[dim yellow]No docstring found.[/dim yellow]")

    # Compose final panel
    inner = "\n\n".join(str(p) for p in body_parts)
    console.print(Panel(inner, title=header, border_style="cyan", expand=False, padding=(1, 2)))


def render_doc_list(entries: List[DocEntry], console: Console, title: str = "Documentation") -> None:
    """Render a list of DocEntries as a table."""
    if not entries:
        console.print("[dim]No documentation entries found.[/dim]")
        return

    table = Table(title=title, border_style="dim", show_lines=True)
    table.add_column("Name", style="bold cyan", min_width=20)
    table.add_column("Kind", style="dim", justify="center", width=8)
    table.add_column("Signature", min_width=30)
    table.add_column("Doc", max_width=40, no_wrap=False)
    table.add_column("Location", style="dim", max_width=30)

    for entry in entries:
        doc_preview = entry.docstring.split("\n")[0][:40] if entry.docstring else "[dim]—[/dim]"
        rel = os.path.relpath(entry.file, ".") if os.path.exists(entry.file) else entry.file
        loc = f"{rel}:{entry.line}"
        if entry.parent_class:
            loc += f"\n[dim]← {entry.parent_class}[/dim]"
        table.add_row(
            entry.name, entry.kind, entry.signature, doc_preview, loc,
        )

    console.print(table)
    console.print(f"[dim]Found {len(entries)} entries.[/dim]")


#