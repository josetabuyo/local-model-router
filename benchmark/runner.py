"""Benchmark orchestrator — runs tasks across all configured models."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Callable

from benchmark.metrics import Result
from benchmark.providers.base import BaseProvider
from benchmark.providers.ollama_provider import OllamaProvider
from benchmark.tasks import Task, TASKS


def run_benchmark(
    providers: list[tuple[BaseProvider, list[str]]],
    tasks: list[Task] | None = None,
    on_result: Callable[[Result], None] | None = None,
    task_delay: float = 0.5,
) -> list[Result]:
    """
    providers: list of (provider, [model_id, ...]) pairs
    tasks: subset of TASKS to run (default: all)
    on_result: callback invoked after each Result is collected
    task_delay: seconds to breathe between tasks (reduces system load)
    """
    tasks = tasks or TASKS
    results: list[Result] = []

    for provider, model_ids in providers:
        for model_id in model_ids:
            for i, task in enumerate(tasks):
                result = provider.run(model_id, task)
                results.append(result)
                if on_result:
                    on_result(result)
                # breathe between tasks — skip after last task per model
                if task_delay > 0 and i < len(tasks) - 1:
                    time.sleep(task_delay)

            # unload local models from RAM immediately after all their tasks
            if isinstance(provider, OllamaProvider):
                provider.unload(model_id)

    return results


def save_results(results: list[Result], output_dir: str = "results") -> Path:
    Path(output_dir).mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"benchmark_{ts}.json"
    path.write_text(json.dumps([r.as_dict() for r in results], indent=2))
    return path
