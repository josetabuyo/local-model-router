"""Rich terminal report for benchmark results."""
from __future__ import annotations
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich import box

from benchmark.metrics import Result

console = Console()


def print_summary(results: list[Result]) -> None:
    """Print per-task tables and an overall cost summary."""
    if not results:
        console.print("[yellow]No results to display.[/yellow]")
        return

    task_ids = list(dict.fromkeys(r.task_id for r in results))

    for tid in task_ids:
        task_results = [r for r in results if r.task_id == tid]
        task_name = task_results[0].task_name

        table = Table(
            title=f"[bold cyan]{task_name}[/bold cyan]",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Provider", style="dim")
        table.add_column("Model", style="bold")
        table.add_column("Time (s)", justify="right")
        table.add_column("Tok/s", justify="right")
        table.add_column("Out tokens", justify="right")
        table.add_column("Cost (USD)", justify="right")
        table.add_column("Status")

        for r in task_results:
            status = "[red]ERROR[/red]" if r.error else "[green]OK[/green]"
            cost_str = f"${r.cost_usd:.6f}" if r.cost_usd else "$0.000000"
            table.add_row(
                r.provider,
                _short_model(r.model_id),
                f"{r.total_s:.2f}",
                f"{r.tokens_per_sec:.1f}",
                str(r.output_tokens),
                cost_str,
                status,
            )

        console.print(table)
        console.print()

    _print_cost_summary(results)
    _print_response_samples(results)


def _print_cost_summary(results: list[Result]) -> None:
    total_by_model: dict[str, float] = defaultdict(float)
    time_by_model: dict[str, float] = defaultdict(float)
    for r in results:
        key = f"{r.provider}/{_short_model(r.model_id)}"
        total_by_model[key] += r.cost_usd
        time_by_model[key] += r.total_s

    table = Table(title="[bold yellow]Cost Summary[/bold yellow]", box=box.SIMPLE_HEAVY)
    table.add_column("Model")
    table.add_column("Total time (s)", justify="right")
    table.add_column("Total cost (USD)", justify="right")
    table.add_column("Note")

    for key in sorted(total_by_model):
        provider = key.split("/")[0]
        note = "local electricity" if provider == "ollama" else "cloud API"
        table.add_row(
            key,
            f"{time_by_model[key]:.1f}",
            f"${total_by_model[key]:.6f}",
            note,
        )

    console.print(table)
    console.print()


def _print_response_samples(results: list[Result]) -> None:
    """Show one sample response per model for the instruction-following task."""
    samples = [r for r in results if r.task_id == "instruction" and not r.error]
    if not samples:
        return

    console.rule("[bold]Instruction-Following Responses[/bold]")
    for r in samples:
        console.print(f"[dim]{r.provider}[/dim] / [bold]{_short_model(r.model_id)}[/bold]")
        console.print(f"  {(r.response or '').strip()[:200]}")
    console.print()


def print_result_live(r: Result) -> None:
    """Called after each result is collected; prints a one-liner."""
    status = f"[red]ERR[/red] {r.error[:60]}" if r.error else f"[green]OK[/green] {r.tokens_per_sec:.0f} tok/s  {r.total_s:.1f}s"
    console.print(f"  {r.provider}/{_short_model(r.model_id)}  [{r.task_name}]  {status}")


def _short_model(model_id: str) -> str:
    return model_id.split("/")[-1][:40]
