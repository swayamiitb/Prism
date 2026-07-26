"""
Context Brain — eval CLI
========================

  python -m evals wiring   — structural invariants (no LLM, <1s)
  python -m evals          — (behavioral + judges are LLM-driven; see EVALS.md)
"""

from __future__ import annotations

import typer
from evals.wiring import run_all
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Context Brain evaluation harness.", no_args_is_help=True)
console = Console()


@app.command()
def wiring() -> None:
    """Run the structural wiring invariants."""
    from context_brain.contexts import create_context_providers

    create_context_providers()
    results = run_all()
    table = Table(title="Context Brain — Wiring Invariants")
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("name")
    table.add_column("result", justify="center")
    table.add_column("detail", style="dim")
    failures = 0
    for r in results:
        if not r.passed:
            failures += 1
        table.add_row(
            r.id,
            r.name,
            "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]",
            r.detail,
        )
    console.print(table)
    if failures:
        console.print(f"\n[red]{failures} invariant(s) failed.[/red]")
        raise typer.Exit(1)
    console.print(f"\n[green]All {len(results)} invariants passed.[/green]")


@app.command()
def behavioral() -> None:
    """Run behavioral cases (requires live Ollama + Neo4j)."""
    console.print(
        "[yellow]Behavioral + judge tiers need a running stack (Ollama + Neo4j).[/yellow]\n"
        "Start the stack with `docker compose up -d`, then re-run.\n"
        "See docs/EVALS.md for the full methodology."
    )
    raise typer.Exit(2)


if __name__ == "__main__":
    app()
