"""Multi-agent orchestration system."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from termmind.api import APIClient


@dataclass
class AgentPersona:
    """Agent persona definition."""
    name: str
    role: str
    system_prompt: str
    capabilities: List[str] = field(default_factory=list)
    max_turns: int = 10


class Agent:
    """Single agent instance."""
    
    def __init__(self, persona: AgentPersona, client: APIClient) -> None:
        self.persona = persona
        self.client = client
        self.state: Dict[str, Any] = {}
        self.memory: List[Dict[str, str]] = []
        self.turns = 0
    
    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute a task with this agent."""
        if self.turns >= self.persona.max_turns:
            return f"[{self.persona.name}] Max turns reached."
        
        messages = [
            {"role": "system", "content": self.persona.system_prompt},
        ]
        
        if context:
            ctx_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            messages.append({"role": "user", "content": f"Context:\n{ctx_str}\n\nTask: {task}"})
        else:
            messages.append({"role": "user", "content": task})
        
        self.turns += 1
        
        # Use the client's chat method
        try:
            response = self.client.chat(messages)
            self.memory.append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            return f"[{self.persona.name}] Error: {e}"
    
    def remember(self, key: str, value: Any) -> None:
        """Store something in agent memory."""
        self.state[key] = value
    
    def recall(self, key: str) -> Any:
        """Recall from agent memory."""
        return self.state.get(key)
    
    def reset(self) -> None:
        """Reset agent state."""
        self.turns = 0
        self.state.clear()
        self.memory.clear()


class WorkflowEngine:
    """Orchestrates multi-agent workflows."""
    
    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self._workflows: Dict[str, List[str]] = {}
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent."""
        self._agents[agent.persona.name] = agent
    
    def define_workflow(self, name: str, steps: List[str]) -> None:
        """Define a workflow as a sequence of agent names."""
        self._workflows[name] = steps
    
    def run_workflow(self, name: str, task: str, **kwargs: Any) -> Dict[str, Any]:
        """Run a defined workflow."""
        if name not in self._workflows:
            raise ValueError(f"Workflow {name} not defined")
        
        steps = self._workflows[name]
        results = {}
        context = {}
        
        for step_name in steps:
            agent = self._agents.get(step_name)
            if not agent:
                raise ValueError(f"Agent {step_name} not found")
            
            result = agent.run(task, context=context)
            results[step_name] = result
            context[f"{step_name}_output"] = result
        
        return {
            "workflow": name,
            "task": task,
            "results": results,
            "final_output": results.get(steps[-1], "")
        }
    
    def list_agents(self) -> List[str]:
        """List all registered agents."""
        return list(self._agents.keys())
    
    def list_workflows(self) -> List[str]:
        """List all defined workflows."""
        return list(self._workflows.keys())
    
    def save_state(self, path: str) -> None:
        """Save workflow state to JSON."""
        import json
        state = {
            "agents": [a.persona.name for a in self._agents.values()],
            "workflows": self._workflows,
        }
        Path(path).write_text(json.dumps(state, indent=2))
    
    def load_state(self, path: str) -> None:
        """Load workflow state from JSON."""
        import json
        data = json.loads(Path(path).read_text())
        self._workflows = data.get("workflows", {})


# Built-in personas
RESEARCHER = AgentPersona(
    name="researcher",
    role="Information gathering and analysis",
    system_prompt="You are a research agent. Gather information, summarize findings, and provide structured analysis.",
    capabilities=["web_search", "summarization", "analysis"]
)

CODER = AgentPersona(
    name="coder",
    role="Code implementation",
    system_prompt="You are a coding agent. Write clean, efficient, well-documented code. Follow best practices.",
    capabilities=["code_generation", "debugging", "refactoring", "testing"]
)

REVIEWER = AgentPersona(
    name="reviewer",
    role="Quality assurance",
    system_prompt="You are a code review agent. Identify bugs, security issues, performance problems, and suggest improvements.",
    capabilities=["code_review", "security_audit", "performance_analysis"]
)

WRITER = AgentPersona(
    name="writer",
    role="Documentation",
    system_prompt="You are a technical writing agent. Create clear, comprehensive documentation.",
    capabilities=["documentation", "comments", "README_generation"]
)

ARCHITECT = AgentPersona(
    name="architect",
    role="System design",
    system_prompt="You are a system architect. Design scalable, maintainable systems.",
    capabilities=["architecture", "patterns", "diagrams"]
)

__all__ = [
    "Agent", "AgentPersona", "WorkflowEngine",
    "RESEARCHER", "CODER", "REVIEWER", "WRITER", "ARCHITECT"
]
