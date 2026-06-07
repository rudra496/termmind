"""Knowledge base CLI commands."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from termmind.api import APIClient
from termmind.config import load_config
from termmind.knowledge.rag import DocumentLoader, RAGPipeline, VectorStore

console = Console()


@click.group(name="kb")
def kb_cmd():
    """Knowledge base commands."""
    pass


@kb_cmd.command("init")
@click.option("--name", "-n", default="default", help="Collection name")
def kb_init(name):
    """Initialize a knowledge base."""
    store = VectorStore(collection_name=name)
    path = Path.home() / ".termmind" / "kb" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    store.save(str(path))
    console.print(f"[green]Knowledge base '{name}' initialized.[/green]")
    console.print(f"[dim]Saved to {path}[/dim]")


@kb_cmd.command("add")
@click.argument("path")
@click.option("--collection", "-c", default="default", help="Collection name")
@click.option("--recursive", "-r", is_flag=True, help="Add recursively")
@click.option("--pattern", "-p", default="*.md", help="File pattern")
def kb_add(path, collection, recursive, pattern):
    """Add documents to knowledge base.

    Example: termmind kb add ./docs --recursive
    """
    store_path = Path.home() / ".termmind" / "kb" / f"{collection}.json"

    store = VectorStore(collection_name=collection)
    if store_path.exists():
        store.load(str(store_path))

    target = Path(path)
    if target.is_file():
        docs = [DocumentLoader.from_file(str(target))]
    elif target.is_dir() and recursive:
        docs = DocumentLoader.from_directory(str(target), pattern)
    else:
        console.print(f"[red]Invalid path: {path}[/red]")
        return

    for i, doc in enumerate(docs):
        store.add(f"doc_{store.count() + i}", doc)

    store.save(str(store_path))
    console.print(f"[green]Added {len(docs)} documents to '{collection}'.[/green]")
    console.print(f"[dim]Total: {store.count()} documents[/dim]")


@kb_cmd.command("query")
@click.argument("query")
@click.option("--collection", "-c", default="default", help="Collection name")
@click.option("--top-k", "-k", default=5, type=int, help="Number of documents")
@click.option("--provider", "-p", default="", help="Override provider")
@click.option("--model", "-m", default="", help="Override model")
def kb_query(query, collection, top_k, provider, model):
    """Query knowledge base with RAG.

    Example: termmind kb query "What is RAG?"
    """
    store_path = Path.home() / ".termmind" / "kb" / f"{collection}.json"

    if not store_path.exists():
        console.print(f"[red]Knowledge base '{collection}' not found.[/red]")
        return

    store = VectorStore(collection_name=collection)
    store.load(str(store_path))

    cfg = load_config()
    client = APIClient(
        provider=provider or cfg.get("provider", "ollama"),
        api_key=cfg.get("api_key", ""),
        model=model or cfg.get("model", ""),
    )

    rag = RAGPipeline(store, client)

    console.print(f"[dim]Querying {store.count()} documents...[/dim]\n")
    answer = rag.query(query, top_k=top_k)

    console.print("[bold green]Answer:[/bold green]")
    console.print(answer)


@kb_cmd.command("list")
@click.option("--collection", "-c", default="default", help="Collection name")
def kb_list(collection):
    """List documents in knowledge base."""
    store_path = Path.home() / ".termmind" / "kb" / f"{collection}.json"

    if not store_path.exists():
        console.print(f"[red]Knowledge base '{collection}' not found.[/red]")
        return

    store = VectorStore(collection_name=collection)
    store.load(str(store_path))

    ids = store.list()
    table = Table(title=f"Documents in '{collection}'", border_style="cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Source")
    table.add_column("Type")

    for doc_id in ids[:50]:
        doc = store.get(doc_id)
        if doc:
            table.add_row(
                doc_id,
                doc.metadata.get("source", "unknown"),
                doc.metadata.get("type", "text")
            )

    console.print(table)
    console.print(f"[dim]Total: {len(ids)} documents[/dim]")


@kb_cmd.command("stats")
@click.option("--collection", "-c", default="default", help="Collection name")
def kb_stats(collection):
    """Show knowledge base statistics."""
    store_path = Path.home() / ".termmind" / "kb" / f"{collection}.json"

    if not store_path.exists():
        console.print(f"[red]Knowledge base '{collection}' not found.[/red]")
        return

    store = VectorStore(collection_name=collection)
    store.load(str(store_path))

    total_size = 0
    for doc_id in store.list():
        doc = store.get(doc_id)
        if doc:
            total_size += len(doc.content)

    table = Table(title=f"Stats for '{collection}'", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Documents", str(store.count()))
    table.add_row("Total size", f"{total_size:,} chars")
    table.add_row("Avg size", f"{total_size // store.count() if store.count() else 0:,} chars")

    console.print(table)
