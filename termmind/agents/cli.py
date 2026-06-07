"""Agent CLI commands."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from termmind.agents.engine import Agent, WorkflowEngine, RESEARCHER, CODER, REVIEWER, WRITER, ARCHITECT
from termmind.api import APIClient
from termmind.config import load_config

console = Console()
PERSONAS = {
    "researcher": RESEARCHER,
    "coder": CODER,
    "reviewer": REVIEWER,
    "writer": WRITER,
    "architect": ARCHITECT,
}


@click.group(name="agent")
def agent_cmd():
    """Multi-agent workflow commands."""
    pass


@agent_cmd.command("list")
def agent_list():
    """List available agent personas."""
    table = Table(title="Agent Personas", border_style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Role")
    table.add_column("Capabilities")
    
    for name, persona in PERSONAS.items():
        table.add_row(name, persona.role, ", ".join(persona.capabilities))
    
    console.print(table)


@agent_cmd.command("run")
@click.argument("workflow")
@click.argument("task")
@click.option("--agents", "-a", default="researcher,coder,reviewer", help="Comma-separated agent names")
@click.option("--provider", "-p", default="", help="Override provider")
@click.option("--model", "-m", default="", help="Override model")
@click.option("--save", "-s", is_flag=True, help="Save workflow state")
@click.option("--output", "-o", help="Output file for results")
def agent_run(workflow, task, agents, provider, model, save, output):
    """Run a multi-agent workflow.
    
    Example: termmind agent run "research-code" "Build a REST API"
    """
    cfg = load_config()
    
    client = APIClient(
        provider=provider or cfg.get("provider", "ollama"),
        api_key=cfg.get("api_key", ""),
        model=model or cfg.get("model", ""),
    )
    
    engine = WorkflowEngine()
    
    # Register requested agents
    for name in agents.split(","):
        name = name.strip()
        if name not in PERSONAS:
            console.print(f"[red]Unknown agent: {name}[/red]")
            continue
        agent = Agent(PERSONAS[name], client)
        engine.register_agent(agent)
    
    # Define workflow
    step_names = [n.strip() for n in agents.split(",")]
    engine.define_workflow(workflow, step_names)
    
    console.print(f"[bold]Running workflow: {workflow}[/bold]")
    console.print(f"[dim]Agents: {', '.join(step_names)}[/dim]")
    console.print(f"[dim]Task: {task}[/dim]\n")
    
    result = engine.run_workflow(workflow, task)
    
    # Display results
    for agent_name, response in result["results"].items():
        console.print(f"[bold cyan]{agent_name}:[/bold cyan]")
        console.print(response[:500] + "..." if len(response) > 500 else response)
        console.print()
    
    console.print(f"[bold green]Final Output:[/bold green]")
    console.print(result["final_output"][:500] + "..." if len(result["final_output"]) > 500 else result["final_output"])
    
    # Save if requested
    if save:
        state_path = Path.home() / ".termmind" / "workflows" / f"{workflow}.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        engine.save_state(str(state_path))
        console.print(f"\n[dim]Workflow state saved to {state_path}[/dim]")
    
    if output:
        Path(output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        console.print(f"[dim]Results saved to {output}[/dim]")


@agent_cmd.command("chat")
@click.argument("persona_name")
@click.argument("message")
@click.option("--provider", "-p", default="", help="Override provider")
@click.option("--model", "-m", default="", help="Override model")
def agent_chat(persona_name, message, provider, model):
    """Chat with a specific agent persona.
    
    Example: termmind agent chat researcher "Explain quantum computing"
    """
    if persona_name not in PERSONAS:
        console.print(f"[red]Unknown persona: {persona_name}[/red]")
        return
    
    cfg = load_config()
    client = APIClient(
        provider=provider or cfg.get("provider", "ollama"),
        api_key=cfg.get("api_key", ""),
        model=model or cfg.get("model", ""),
    )
    
    agent = Agent(PERSONAS[persona_name], client)
    response = agent.run(message)
    
    console.print(f"[bold cyan]{persona_name}:[/bold cyan]")
    console.print(response)
