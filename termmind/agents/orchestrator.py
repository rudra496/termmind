"""Supervisor orchestrator for TermMind agents."""

from termmind.agents.core.loop import AgentLoop
from termmind.api import APIClient

class Orchestrator:
    """Orchestrates tasks using sub-agents."""

    def __init__(self):
        self.client = APIClient()

    def run_task(self, task_description: str) -> str:
        """Run a complex task via the agent loop."""
        print(f"[Orchestrator] Starting task: {task_description}")
        agent = AgentLoop(provider=self.client, max_steps=15)
        
        # In a multi-agent setup, the orchestrator might break this down
        # and spawn multiple AgentLoops (e.g. Coder, Reviewer).
        result = agent.execute(task_description)
        return result
