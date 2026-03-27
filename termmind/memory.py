"""Code Context Memory — project structure cache across sessions."""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .file_ops import find_files, read_file, _is_ignored

# Storage layout:
#   ~/.termmind/memory/<project-hash>/index.json
#   ~/.termmind/memory/<project-hash>/meta.json

MEMORY_DIR = Path.home() / ".termmind" / "memory"

# Supported languages and their comment/definition patterns
LANG_PATTERNS: Dict[str, Dict[str, Any]] = {
    ".py": {
        "functions": re.compile(
            r"^\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?",
            re.MULTILINE,
        ),
        "classes": re.compile(
            r"^\s*class\s+(\w+)(?:\(([^)]*)\))?", re.MULTILINE,
        ),
        "imports": re.compile(
            r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))", re.MULTILINE,
        ),
        "decorators": re.compile(r"^\s*@(\w+)", re.MULTILINE),
    },
    ".js": {
        "functions": re.compile(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
            re.MULTILINE,
        ),
        "classes": re.compile(r"(?:export\s+)?class\s+(\w+)", re.MULTILINE),
        "imports": re.compile(
            r"(?:import\s+.+\s+from\s+['\"]([^'\"]+)|require\s*\(\s*['\"]([^'\"]+))",
            re.MULTILINE,
        ),
        "decorators": re.compile(r"^\s*@(\w+)", re.MULTILINE),
    },
    ".ts": {
        "functions": re.compile(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
            r"(?:\s*:\s*([^,{]+))?",
            re.MULTILINE,
        ),
        "classes": re.compile(
            r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]*>)?(?:\s+extends\s+(\w+))?",
            re.MULTILINE,
        ),
        "imports": re.compile(
            r"(?:import\s+.+\s+from\s+['\"]([^'\"]+)|require\s*\(\s*['\"]([^'\"]+))",
            re.MULTILINE,
        ),
        "decorators": re.compile(r"^\s*@(\w+)", re.MULTILINE),
    },
    ".go": {
        "functions": re.compile(
            r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(([^)]*)\)",
            re.MULTILINE,
        ),
        "classes": re.compile(r"type\s+(\w+)\s+struct\s*\{", re.MULTILINE),
        "imports": re.compile(r'import\s+\(?["\']([^"\']+)', re.MULTILINE),
        "decorators": re.compile(r"//\s*@\w+", re.MULTILINE),
    },
    ".rs": {
        "functions": re.compile(
            r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
            r"(?:\s*->\s*([^,{]+))?",
            re.MULTILINE,
        ),
        "classes": re.compile(
            r"(?:pub\s+)?struct\s+(\w+)", re.MULTILINE,
        ),
        "imports": re.compile(
            r"use\s+([\w:]+)::", re.MULTILINE,
        ),
        "decorators": re.compile(r"#\[(\w+)", re.MULTILINE),
    },
    ".java": {
        "functions": re.compile(
            r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)",
            re.MULTILINE,
        ),
        "classes": re.compile(
            r"(?:public|private|protected)?\s*(?:abstract|final)?\s*class\s+(\w+)",
            re.MULTILINE,
        ),
        "imports": re.compile(r"import\s+([\w.]+);", re.MULTILINE),
        "decorators": re.compile(r"@\w+", re.MULTILINE),
    },
    ".rb": {
        "functions": re.compile(
            r"def\s+(\w+)(?:\s*\(([^)]*)\))?", re.MULTILINE,
        ),
        "classes": re.compile(r"class\s+(\w+)", re.MULTILINE),
        "imports": re.compile(r"require\s+['\"]([^'\"]+)", re.MULTILINE),
        "decorators": re.compile(r"^\s*(?:before|after|around)_\w+", re.MULTILINE),
    },
    ".c": {
        "functions": re.compile(
            r"(?:static\s+)?[\w*]+\s+(\w+)\s*\(([^)]*)\)\s*\{", re.MULTILINE,
        ),
        "classes": re.compile(r"", re.MULTILINE),
        "imports": re.compile(r"#include\s+[<\"]([^>\"]+)", re.MULTILINE),
        "decorators": re.compile(r"", re.MULTILINE),
    },
    ".cpp": {
        "functions": re.compile(
            r"(?:(?:static|virtual|inline|const|template\s*<[^>]*>)\s+)*"
            r"[\w:*<>]+\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE,
        ),
        "classes": re.compile(r"class\s+(\w+)", re.MULTILINE),
        "imports": re.compile(r"#include\s+[<\"]([^>\"]+)", re.MULTILINE),
        "decorators": re.compile(r"", re.MULTILINE),
    },
}


@dataclass
class FunctionInfo:
    """Information about a single function/method."""
    name: str
    signature: str
    return_type: str = ""
    line: int = 0
    decorators: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a single class."""
    name: str
    bases: List[str] = field(default_factory=list)
    line: int = 0
    methods: List[str] = field(default_factory=list)


@dataclass
class FileIndex:
    """Parsed index for a single file."""
    path: str = ""
    mtime: float = 0.0
    hash: str = ""
    language: str = ""
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    line_count: int = 0
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "mtime": self.mtime,
            "hash": self.hash,
            "language": self.language,
            "functions": self.functions,
            "classes": self.classes,
            "imports": self.imports,
            "line_count": self.line_count,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FileIndex":
        fi = cls()
        fi.path = d.get("path", "")
        fi.mtime = d.get("mtime", 0.0)
        fi.hash = d.get("hash", "")
        fi.language = d.get("language", "")
        fi.functions = d.get("functions", [])
        fi.classes = d.get("classes", [])
        fi.imports = d.get("imports", [])
        fi.line_count = d.get("line_count", 0)
        fi.size_bytes = d.get("size_bytes", 0)
        return fi


@dataclass
class ProjectIndex:
    """Complete index for a project."""
    project_hash: str = ""
    project_root: str = ""
    files: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    indexed_at: float = 0.0
    total_files: int = 0
    total_functions: int = 0
    total_classes: int = 0
    file_hash_map: Dict[str, str] = field(default_factory=dict)  # path -> content hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_hash": self.project_hash,
            "project_root": self.project_root,
            "files": self.files,
            "indexed_at": self.indexed_at,
            "total_files": self.total_files,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "file_hash_map": self.file_hash_map,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProjectIndex":
        pi = cls()
        pi.project_hash = d.get("project_hash", "")
        pi.project_root = d.get("project_root", "")
        pi.files = d.get("files", {})
        pi.indexed_at = d.get("indexed_at", 0.0)
        pi.total_files = d.get("total_files", 0)
        pi.total_functions = d.get("total_functions", 0)
        pi.total_classes = d.get("total_classes", 0)
        pi.file_hash_map = d.get("file_hash_map", {})
        return pi


def _project_hash(project_root: str) -> str:
    """Generate a stable hash for a project directory."""
    abs_path = os.path.abspath(project_root)
    return hashlib.sha256(abs_path.encode()).hexdigest()[:16]


def _content_hash(content: str) -> str:
    """Generate a quick hash of file content."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _file_hash_fast(filepath: str) -> str:
    """Generate hash from first ~8KB of file content (fast, for change detection)."""
    try:
        with open(filepath, "rb") as f:
            head = f.read(8192)
        return hashlib.md5(head).hexdigest()[:12]
    except OSError:
        return ""


def _get_language(ext: str) -> str:
    """Map file extension to language name."""
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
        ".jsx": "javascript", ".tsx": "typescript",
        ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
        ".lua": "lua", ".php": "php", ".cs": "csharp",
    }
    return lang_map.get(ext.lower(), "")


def _parse_file(filepath: str, content: str) -> FileIndex:
    """Parse a single file and extract structure information."""
    ext = Path(filepath).suffix.lower()
    patterns = LANG_PATTERNS.get(ext)
    if not patterns:
        return FileIndex(
            path=filepath, mtime=0, hash=_content_hash(content),
            language=_get_language(ext),
            line_count=len(content.splitlines()),
            size_bytes=len(content.encode("utf-8")),
        )

    file_index = FileIndex(
        path=filepath, mtime=0, hash=_content_hash(content),
        language=_get_language(ext),
        line_count=len(content.splitlines()),
        size_bytes=len(content.encode("utf-8")),
    )

    lines = content.splitlines()

    # Extract functions
    func_pattern = patterns["functions"]
    if func_pattern.pattern:  # not empty
        for match in func_pattern.finditer(content):
            name = match.group(1)
            params = match.group(2) or ""
            ret = match.group(3) or ""
            line_num = content[:match.start()].count("\n") + 1
            sig = f"{name}({params})"
            if ret:
                sig += f" -> {ret}"
            file_index.functions.append({
                "name": name,
                "signature": sig,
                "params": params.strip(),
                "return_type": ret.strip(),
                "line": line_num,
            })

    # Extract classes
    class_pattern = patterns["classes"]
    if class_pattern.pattern:
        for match in class_pattern.finditer(content):
            name = match.group(1)
            bases = [b.strip() for b in (match.group(2) or "").split(",") if b.strip()]
            line_num = content[:match.start()].count("\n") + 1
            file_index.classes.append({
                "name": name,
                "bases": bases,
                "line": line_num,
            })

    # Extract imports
    import_pattern = patterns["imports"]
    if import_pattern.pattern:
        for match in import_pattern.finditer(content):
            module = match.group(1) or match.group(2) or ""
            module = module.strip().split(".")[0] if module else ""
            if module and module not in file_index.imports:
                file_index.imports.append(module)

    # Extract decorators/annotations
    dec_pattern = patterns.get("decorators")
    if dec_pattern and dec_pattern.pattern:
        for match in dec_pattern.finditer(content):
            dec_name = match.group(1)
            # Attach to nearest function/class below
            if file_index.functions:
                file_index.functions[-1].setdefault("decorators", []).append(dec_name)

    return file_index


def _get_memory_dir(project_root: str) -> Path:
    """Get the memory directory for a project."""
    phash = _project_hash(project_root)
    return MEMORY_DIR / phash


def _index_path(project_root: str) -> Path:
    """Get the path to the index file for a project."""
    return _get_memory_dir(project_root) / "index.json"


def _meta_path(project_root: str) -> Path:
    """Get the path to the meta file for a project."""
    return _get_memory_dir(project_root) / "meta.json"


def load_index(project_root: str) -> Optional[ProjectIndex]:
    """Load a project index from disk. Returns None if not found or invalid."""
    ipath = _index_path(project_root)
    if not ipath.exists():
        return None
    try:
        with open(ipath, "r") as f:
            data = json.load(f)
        return ProjectIndex.from_dict(data)
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def save_index(project_index: ProjectIndex, project_root: str) -> None:
    """Save a project index to disk."""
    mdir = _get_memory_dir(project_root)
    mdir.mkdir(parents=True, exist_ok=True)
    with open(_index_path(project_root), "w") as f:
        json.dump(project_index.to_dict(), f, indent=2)


def build_index(project_root: str, force: bool = False) -> ProjectIndex:
    """Build or update the project index.

    Args:
        project_root: Path to the project root directory.
        force: If True, rebuild from scratch. Otherwise, incrementally update.

    Returns:
        The updated ProjectIndex.
    """
    start_time = time.time()
    project_root = os.path.abspath(project_root)
    phash = _project_hash(project_root)

    if not force:
        existing = load_index(project_root)
        if existing and existing.project_root == project_root:
            return _incremental_update(existing, project_root)

    # Full build
    project_index = ProjectIndex(
        project_hash=phash,
        project_root=project_root,
        indexed_at=time.time(),
    )

    files = find_files(project_root, max_depth=8)
    supported_exts = set(LANG_PATTERNS.keys())

    total_funcs = 0
    total_classes = 0

    for filepath in files:
        ext = Path(filepath).suffix.lower()
        # Also index files without patterns for basic info
        try:
            fast_hash = _file_hash_fast(filepath)
        except OSError:
            continue

        if ext in supported_exts:
            content = read_file(filepath)
            if content is None:
                continue
            fi = _parse_file(filepath, content)
            fi.mtime = os.path.getmtime(filepath)
            total_funcs += len(fi.functions)
            total_classes += len(fi.classes)
            project_index.files[filepath] = fi.to_dict()
        else:
            # Basic info for unsupported types
            try:
                st = os.stat(filepath)
                project_index.files[filepath] = {
                    "path": filepath,
                    "mtime": st.st_mtime,
                    "hash": fast_hash,
                    "language": _get_language(ext),
                    "functions": [],
                    "classes": [],
                    "imports": [],
                    "line_count": 0,
                    "size_bytes": st.st_size,
                }
            except OSError:
                continue
        project_index.file_hash_map[filepath] = fast_hash

    project_index.total_files = len(project_index.files)
    project_index.total_functions = total_funcs
    project_index.total_classes = total_classes

    save_index(project_index, project_root)

    # Save meta
    mdir = _get_memory_dir(project_root)
    mdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "project_root": project_root,
        "project_hash": phash,
        "last_indexed": time.time(),
        "index_duration_ms": (time.time() - start_time) * 1000,
        "files_indexed": project_index.total_files,
    }
    with open(_meta_path(project_root), "w") as f:
        json.dump(meta, f, indent=2)

    return project_index


def _incremental_update(existing: ProjectIndex, project_root: str) -> ProjectIndex:
    """Incrementally update an existing index by checking for changed files."""
    start_time = time.time()
    current_files = find_files(project_root, max_depth=8)
    current_set = set(current_files)
    indexed_set = set(existing.files.keys())

    new_files = current_set - indexed_set
    deleted_files = indexed_set - current_set
    possibly_changed = current_set & indexed_set

    changed_files: Set[str] = set()
    for filepath in possibly_changed:
        try:
            current_hash = _file_hash_fast(filepath)
        except OSError:
            deleted_files.add(filepath)
            continue
        old_hash = existing.file_hash_map.get(filepath, "")
        if current_hash != old_hash:
            changed_files.add(filepath)

    files_to_update = new_files | changed_files
    supported_exts = set(LANG_PATTERNS.keys())

    for filepath in deleted_files:
        existing.files.pop(filepath, None)
        existing.file_hash_map.pop(filepath, None)

    total_funcs = existing.total_functions
    total_classes = existing.total_classes

    for filepath in files_to_update:
        ext = Path(filepath).suffix.lower()
        try:
            fast_hash = _file_hash_fast(filepath)
        except OSError:
            continue

        # Remove old counts if re-indexing
        old_data = existing.files.get(filepath, {})
        total_funcs -= len(old_data.get("functions", []))
        total_classes -= len(old_data.get("classes", []))

        if ext in supported_exts:
            content = read_file(filepath)
            if content is None:
                continue
            fi = _parse_file(filepath, content)
            fi.mtime = os.path.getmtime(filepath)
            total_funcs += len(fi.functions)
            total_classes += len(fi.classes)
            existing.files[filepath] = fi.to_dict()
        else:
            try:
                st = os.stat(filepath)
                existing.files[filepath] = {
                    "path": filepath, "mtime": st.st_mtime, "hash": fast_hash,
                    "language": _get_language(ext), "functions": [], "classes": [],
                    "imports": [], "line_count": 0, "size_bytes": st.st_size,
                }
            except OSError:
                continue
        existing.file_hash_map[filepath] = fast_hash

    existing.total_files = len(existing.files)
    existing.total_functions = total_funcs
    existing.total_classes = total_classes
    existing.indexed_at = time.time()

    save_index(existing, project_root)

    meta = {
        "project_root": project_root,
        "project_hash": existing.project_hash,
        "last_indexed": time.time(),
        "index_duration_ms": (time.time() - start_time) * 1000,
        "files_indexed": existing.total_files,
        "incremental": True,
        "files_updated": len(files_to_update),
        "files_deleted": len(deleted_files),
    }
    mdir = _get_memory_dir(project_root)
    mdir.mkdir(parents=True, exist_ok=True)
    with open(_meta_path(project_root), "w") as f:
        json.dump(meta, f, indent=2)

    return existing


def query_functions(project_root: str, name_pattern: str = "",
                    filepath: str = "") -> List[Dict[str, Any]]:
    """Query functions in the project index.

    Args:
        project_root: Project root directory.
        name_pattern: Optional regex pattern to filter function names.
        filepath: Optional filepath to restrict search to a single file.

    Returns:
        List of function info dicts.
    """
    index = load_index(project_root)
    if not index:
        index = build_index(project_root)

    results = []
    files_to_search = {filepath} if filepath else set(index.files.keys())

    regex = re.compile(name_pattern, re.IGNORECASE) if name_pattern else None

    for fpath in files_to_search:
        fdata = index.files.get(fpath)
        if not fdata:
            continue
        for func in fdata.get("functions", []):
            if regex and not regex.search(func["name"]):
                continue
            func_copy = dict(func)
            func_copy["file"] = fpath
            results.append(func_copy)

    return results


def query_classes(project_root: str, name_pattern: str = "") -> List[Dict[str, Any]]:
    """Query classes in the project index."""
    index = load_index(project_root)
    if not index:
        index = build_index(project_root)

    results = []
    regex = re.compile(name_pattern, re.IGNORECASE) if name_pattern else None

    for fpath, fdata in index.files.items():
        for cls in fdata.get("classes", []):
            if regex and not regex.search(cls["name"]):
                continue
            cls_copy = dict(cls)
            cls_copy["file"] = fpath
            results.append(cls_copy)

    return results


def query_imports(project_root: str, module: str = "") -> List[Dict[str, str]]:
    """Query which files import a given module."""
    index = load_index(project_root)
    if not index:
        index = build_index(project_root)

    results = []
    module_lower = module.lower() if module else ""

    for fpath, fdata in index.files.items():
        for imp in fdata.get("imports", []):
            if module_lower and module_lower not in imp.lower():
                continue
            results.append({"file": fpath, "module": imp})

    return results


def get_project_summary(project_root: str) -> Dict[str, Any]:
    """Get a summary of the project index for display."""
    index = load_index(project_root)
    if not index:
        index = build_index(project_root)

    # Count by language
    lang_counts: Dict[str, int] = {}
    for fdata in index.files.values():
        lang = fdata.get("language", "unknown")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    return {
        "project_root": index.project_root,
        "total_files": index.total_files,
        "total_functions": index.total_functions,
        "total_classes": index.total_classes,
        "languages": lang_counts,
        "indexed_at": index.indexed_at,
    }


def get_context_for_query(project_root: str, query: str) -> str:
    """Build a context string from the index relevant to a query.

    Searches function/class names for keywords in the query and returns
    signatures and locations of matches.
    """
    index = load_index(project_root)
    if not index:
        index = build_index(project_root)

    query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
    if not query_words:
        return ""

    scored_entries: List[Tuple[float, str]] = []
    seen_files: Set[str] = set()

    for fpath, fdata in index.files.items():
        fname = Path(fpath).stem.lower()

        for func in fdata.get("functions", []):
            name_lower = func["name"].lower()
            score = 0.0
            for word in query_words:
                if word in name_lower:
                    score += 2.0
                if word in fname:
                    score += 0.5
            if score > 0:
                rel = os.path.relpath(fpath, project_root)
                entry = f"  {func['name']}({func.get('params', '')}) → {rel}:{func.get('line', 0)}"
                if func.get("return_type"):
                    entry += f" → {func['return_type']}"
                scored_entries.append((score, entry))
                seen_files.add(rel)

        for cls in fdata.get("classes", []):
            name_lower = cls["name"].lower()
            score = 0.0
            for word in query_words:
                if word in name_lower:
                    score += 2.0
            if score > 0:
                rel = os.path.relpath(fpath, project_root)
                bases = ", ".join(cls.get("bases", []))
                entry = f"  class {cls['name']}({bases}) → {rel}:{cls.get('line', 0)}"
                scored_entries.append((score, entry))
                seen_files.add(rel)

    if not scored_entries:
        return ""

    scored_entries.sort(key=lambda x: x[0], reverse=True)
    parts = [f"## Code Index ({len(scored_entries)} matches)"]
    for score, entry in scored_entries[:30]:
        parts.append(entry)

    if len(scored_entries) > 30:
        parts.append(f"  ... and {len(scored_entries) - 30} more matches")

    return "\n".join(parts)


def invalidate_file(project_root: str, filepath: str) -> None:
    """Remove a file from the index (e.g., after deletion)."""
    index = load_index(project_root)
    if not index:
        return
    index.files.pop(filepath, None)
    index.file_hash_map.pop(filepath, None)
    index.total_files = len(index.files)
    save_index(index, project_root)


def clear_project_index(project_root: str) -> None:
    """Delete the entire index for a project."""
    mdir = _get_memory_dir(project_root)
    if mdir.exists():
        import shutil
        shutil.rmtree(mdir, ignore_errors=True)
