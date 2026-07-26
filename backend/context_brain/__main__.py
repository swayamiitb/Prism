"""
Context Brain CLI
=================

``python -m context_brain`` — interactive chat with the Brain.
``python -m context_brain providers`` — list provider status.
``python -m context_brain graph-stats`` — knowledge-graph summary.
``python -m context_brain skills`` — list exported executable skills.
``python -m context_brain clear-graph`` — wipe the graph (prompts).
``python -m context_brain pull-models`` — reminder to pull Ollama models.

Run from ``backend/`` so ``context_brain`` and ``app`` are importable, or set
``PYTHONPATH=backend``.
"""

from __future__ import annotations

import asyncio
import sys

import typer
from context_brain.contexts import create_context_providers, provider_status_rows
from context_brain.settings import get_settings
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Context Brain — an AI that understands how a company works.", no_args_is_help=True)
console = Console()


@app.command()
def chat() -> None:
    """Start an interactive chat session with the Brain."""
    from context_brain.agent import ainvoke

    create_context_providers()
    console.print(
        Panel.fit(
            "[bold cyan]Context Brain[/bold cyan] — ask how the company works.\n"
            "e.g. 'how do we handle refunds over $500?'\nCtrl+C or 'exit' to quit.",
            border_style="cyan",
        )
    )
    while True:
        try:
            user_input = console.input("\n[bold green]you>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return
        if not user_input or user_input.lower() in {"exit", "quit", ":q"}:
            console.print("[dim]bye[/dim]")
            return
        with console.status("[cyan]thinking…[/cyan]", spinner="dots"):
            result = asyncio.run(ainvoke(user_input))
        if result["tool_calls"]:
            console.print(f"[dim]tools: {', '.join(result['tool_calls'])}[/dim]")
        console.print(f"\n[bold cyan]brain>[/bold cyan] {result['content']}")


@app.command(name="providers")
def providers_cmd() -> None:
    """List registered context providers and their status."""
    create_context_providers()
    rows = provider_status_rows()
    table = Table(title="Context Brain — Context Providers", show_lines=False)
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("name")
    table.add_column("status", justify="center")
    table.add_column("writable", justify="center")
    table.add_column("detail", style="dim")
    for r in rows:
        ok = bool(r["ok"])
        table.add_row(
            str(r["id"]),
            str(r["name"]),
            "[green]✓[/green]" if ok else "[red]✗[/red]",
            "yes" if r.get("writable") else "read-only",
            str(r["detail"]),
        )
    console.print(table)


@app.command(name="graph-stats")
def graph_stats_cmd() -> None:
    """Print knowledge-graph statistics."""
    from context_brain.graph_schema import stats

    try:
        s = stats()
    except Exception as exc:
        console.print(f"[red]cannot reach Neo4j:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[bold]nodes:[/bold] {s.node_count}   [bold]edges:[/bold] {s.edge_count}")
    if s.by_label:
        t = Table(title="By node label")
        t.add_column("label", style="cyan")
        t.add_column("count", justify="right")
        for k, v in s.by_label.items():
            t.add_row(k, str(v))
        console.print(t)
    if s.by_edge:
        t = Table(title="By edge type")
        t.add_column("type", style="magenta")
        t.add_column("count", justify="right")
        for k, v in s.by_edge.items():
            t.add_row(k, str(v))
        console.print(t)


@app.command(name="skills")
def skills_cmd() -> None:
    """List exported executable skill files."""
    from context_brain.skills_engine import list_exported_skills

    skills = list_exported_skills()
    if not skills:
        console.print("[dim]No skills exported yet. Ask the Brain to synthesize a process.[/dim]")
        return
    table = Table(title="Exported Skills")
    table.add_column("file", style="cyan")
    table.add_column("name")
    table.add_column("process")
    table.add_column("steps", justify="right")
    table.add_column("owner", style="dim")
    for s in skills:
        table.add_row(
            s.get("file", ""), s.get("name", ""), s.get("process", ""), str(s.get("steps", 0)), s.get("owner", "")
        )
    console.print(table)


@app.command(name="clear-graph")
def clear_graph_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete every node + edge in the knowledge graph."""
    from context_brain.graph_schema import clear_graph

    if not yes:
        confirm = typer.confirm("This deletes ALL nodes and edges. Continue?", default=False)
        if not confirm:
            console.print("[dim]aborted[/dim]")
            raise typer.Exit()
    result = clear_graph()
    console.print(f"[green]deleted {result['deleted']} node(s)[/green]")


@app.command(name="pull-models")
def pull_models_cmd() -> None:
    """Print the command to pull the required Ollama models."""
    s = get_settings()
    console.print(
        Panel.fit(
            f"Run:\n  [cyan]ollama pull {s.ollama_chat_model}[/cyan]\n  [cyan]ollama pull {s.ollama_embed_model}[/cyan]\n\n"
            "Or, if the stack is up under Docker:\n  [cyan]./scripts/ollama_pull.sh[/cyan]",
            title="Pull local models",
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.insert(1, "chat")
    app()
