"""Tool registry for the autonomous agent."""

import subprocess
from typing import Callable


class ToolRegistry:
    """Registry for autonomous tools."""

    def __init__(self):
        self.tools = {}

    def register(self, name: str, description: str, parameters: dict, func: Callable):
        self.tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
            "executable": func
        }

    def get_tool_schemas(self) -> list[dict]:
        return [{"type": "function", "function": t["function"]} for t in self.tools.values()]

    def execute(self, name: str, kwargs: dict) -> str:
        if name not in self.tools:
            return f"Error: Tool {name} not found."
        try:
            return str(self.tools[name]["executable"](**kwargs))
        except Exception as e:
            return f"Error executing {name}: {e}"


# Default Registry
default_registry = ToolRegistry()

def read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return str(e)

default_registry.register(
    name="read_file",
    description="Read the contents of a file from the local filesystem.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative path to the file."}
        },
        "required": ["path"]
    },
    func=read_file
)

def run_command(command: str) -> str:
    """Run a shell command safely."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return str(e)

default_registry.register(
    name="run_command",
    description="Execute a shell command.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash/shell command to execute."}
        },
        "required": ["command"]
    },
    func=run_command
)
