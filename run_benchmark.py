#!/usr/bin/env python3
"""
LLM Benchmark Harness
Usage:
  uv run run_benchmark.py                        # local models, all tasks
  uv run run_benchmark.py --provider all         # local + Groq
  uv run run_benchmark.py --provider groq        # Groq only
  uv run run_benchmark.py --task coding          # single task
  uv run run_benchmark.py --models qwen2.5:7b    # specific model(s)
  uv run run_benchmark.py --throttle             # low-impact mode (slower, less CPU)
  uv run run_benchmark.py --threads 2            # limit CPU threads (default: 4)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

load_dotenv(Path(__file__).parent / ".env")

from benchmark.providers.ollama_provider import OllamaProvider
from benchmark.providers.groq_provider import GroqProvider, FREE_MODELS as GROQ_MODELS
from benchmark.providers.openrouter_provider import OpenRouterProvider, FREE_MODELS as OR_MODELS
from benchmark.runner import run_benchmark, save_results
from benchmark.report import print_result_live, print_summary
from benchmark.tasks import TASKS

console = Console()


def build_providers(args: argparse.Namespace):
    pairs = []
    ollama = OllamaProvider()

    if args.provider in ("ollama", "local", "all", None):
        local_models = ollama.list_models()
        if args.models:
            requested = [m.strip() for m in args.models.split(",")]
            local_models = [m for m in local_models if m in requested]
        if local_models:
            pairs.append((ollama, local_models))
        else:
            console.print("[yellow]No local Ollama models found.[/yellow]")

    if args.provider in ("groq", "cloud", "all"):
        key = os.getenv("GROQ_API_KEY")
        if not key:
            console.print("[yellow]GROQ_API_KEY not set — skipping Groq.[/yellow]")
        else:
            models = GROQ_MODELS if args.all_cloud else GROQ_MODELS[:2]
            pairs.append((GroqProvider(key), models))

    if args.provider in ("openrouter", "cloud", "all"):
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            console.print("[yellow]OPENROUTER_API_KEY not set — skipping OpenRouter.[/yellow]")
        else:
            models = OR_MODELS if args.all_cloud else OR_MODELS[:2]
            pairs.append((OpenRouterProvider(key), models))

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Benchmark Harness")
    parser.add_argument(
        "--provider", choices=["ollama", "local", "groq", "openrouter", "cloud", "all"],
        default=None,
    )
    parser.add_argument("--task", choices=[t.id for t in TASKS], default=None)
    parser.add_argument("--models", default=None, help="Comma-separated Ollama model names")
    parser.add_argument("--all-cloud", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument(
        "--throttle", action="store_true",
        help="Low-impact mode: 2s delay between tasks, 2 CPU threads",
    )
    parser.add_argument(
        "--threads", type=int, default=None,
        help="CPU threads for Ollama (default: 4, use 2 for light mode)",
    )
    args = parser.parse_args()

    # configure resource limits
    if args.throttle:
        task_delay = 2.0
        os.environ.setdefault("OLLAMA_NUM_THREAD", "2")
    else:
        task_delay = 0.5
    if args.threads:
        os.environ["OLLAMA_NUM_THREAD"] = str(args.threads)

    # lower own process priority so the OS stays responsive
    try:
        os.nice(10)
    except (AttributeError, PermissionError):
        pass

    if args.provider is None and args.models is None:
        args.provider = "ollama"

    tasks = [t for t in TASKS if t.id == args.task] if args.task else TASKS
    providers = build_providers(args)

    if not providers:
        console.print("[red]No providers available. Exiting.[/red]")
        sys.exit(1)

    total = sum(len(models) for _, models in providers) * len(tasks)
    mode = "[yellow]throttle[/yellow]" if args.throttle else "normal"
    console.rule(f"[bold]Running {total} benchmark(s)[/bold] ({mode})")

    results = run_benchmark(providers, tasks, on_result=print_result_live, task_delay=task_delay)

    console.rule("[bold]Results[/bold]")
    print_summary(results)

    if not args.no_save:
        path = save_results(results)
        console.print(f"[dim]Results saved → {path}[/dim]")


if __name__ == "__main__":
    main()
