"""ReAct loop for the autonomous agent."""

import json
from typing import Any, Callable, Dict, List, Optional

from termmind.agents.core.tools import default_registry

class AgentLoop:
    """Executes a Reasoning and Action (ReAct) loop."""
    
    def __init__(self, provider, max_steps: int = 10):
        """
        Initialize the loop with an LLM provider.
        Provider must have a 'send_message' method that returns a string or generator.
        """
        self.provider = provider
        self.max_steps = max_steps
        self.history: List[Dict[str, str]] = []

    def execute(self, prompt: str) -> str:
        """Run the loop given an initial prompt."""
        self.history.append({"role": "user", "content": prompt})
        
        tools_schema = default_registry.get_tool_schemas()
        
        # In a real implementation we would pass `tools=tools_schema` 
        # to the provider API. For now, we inject the schema into the system prompt.
        system_prompt = (
            "You are an autonomous AI agent capable of using tools.\n"
            "You must use the following tools when necessary:\n"
            f"{json.dumps(tools_schema, indent=2)}\n\n"
            "To use a tool, respond ONLY with a JSON object in this format:\n"
            '{"tool_call": {"name": "tool_name", "arguments": {"arg1": "val1"}}}\n'
            "When you have the final answer, just respond with the answer as text."
        )

        for step in range(self.max_steps):
            # Send message to LLM
            response_text = ""
            try:
                if hasattr(self.provider, "chat"):
                    # Using TermMind APIClient
                    response_text = self.provider.chat(self.history, system_prompt=system_prompt)
                else:
                    # Using raw provider
                    response_gen = self.provider.send_message(self.history, stream=False)
                    response_text = "".join(response_gen) if not isinstance(response_gen, str) else response_gen
            except Exception as e:
                return f"Error communicating with LLM: {e}"

            self.history.append({"role": "assistant", "content": response_text})

            # Check if LLM wants to call a tool
            try:
                # Naive JSON parsing for tool calls.
                # In production, providers have native tool-calling features.
                if '{"tool_call"' in response_text:
                    start = response_text.find('{"tool_call"')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                    data = json.loads(json_str)
                    
                    tool_call = data.get("tool_call", {})
                    name = tool_call.get("name")
                    args = tool_call.get("arguments", {})
                    
                    # Execute tool
                    tool_result = default_registry.execute(name, args)
                    
                    self.history.append({
                        "role": "user", 
                        "content": f"Tool {name} result:\n{tool_result}"
                    })
                else:
                    # No tool call, final answer
                    return response_text
            except json.JSONDecodeError:
                # It wasn't a valid JSON tool call, assume it's just chatting
                return response_text

        return "Error: Agent reached maximum steps without completing the task."
