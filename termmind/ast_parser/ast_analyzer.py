"""AST based static analysis for python codebase context generation."""

import ast
from pathlib import Path


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.classes: list[dict] = []
        self.functions: list[dict] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        docstring = ast.get_docstring(node)
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": docstring,
            "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        docstring = ast.get_docstring(node)
        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": docstring,
            "args": [arg.arg for arg in node.args.args]
        })
        self.generic_visit(node)

def analyze_file(filepath: str) -> dict:
    """Analyze a Python file and return its semantic graph structure."""
    path = Path(filepath)
    if not path.exists() or not path.name.endswith(".py"):
        return {"error": "Invalid Python file"}

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        analyzer = CodeAnalyzer()
        analyzer.visit(tree)
        return {
            "file": path.name,
            "classes": analyzer.classes,
            "functions": analyzer.functions
        }
    except Exception as e:
        return {"error": str(e)}
