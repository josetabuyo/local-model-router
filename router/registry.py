"""Loads rankings and resolves model strings to (provider, model_id) pairs."""
from pathlib import Path

import yaml

RANKINGS_DIR = Path(__file__).parent.parent / "rankings"

LOCAL_PROVIDERS = {"ollama"}


class Registry:
    def __init__(self):
        self._local = self._load("local.yaml")
        self._cloud = self._load("cloud.yaml")

    def _load(self, filename: str) -> dict:
        with open(RANKINGS_DIR / filename) as f:
            return yaml.safe_load(f) or {}

    # ── Public resolution methods ──────────────────────────────────────────

    def resolve(self, model_str: str) -> tuple[str, str]:
        """Return (provider, model_id). Local preferred over cloud for best:<category>."""
        if model_str.startswith("best:"):
            category = model_str[5:]
            local = self._try_best_local(category)
            if local:
                return local
            cloud = self._try_best_cloud(category)
            if cloud:
                return cloud
            raise ValueError(self._no_category_error(category))
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            return provider, model_id
        raise ValueError(self._format_error(model_str))

    def resolve_local_only(self, model_str: str) -> tuple[str, str]:
        """Resolves only to Ollama models. Raises if the model is cloud-only."""
        if model_str.startswith("best:"):
            category = model_str[5:]
            result = self._try_best_local(category)
            if result is None:
                raise ValueError(
                    f"No local model ranked for category '{category}'. "
                    f"Available categories with local rankings: {self._local_categories()}"
                )
            return result
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            if provider not in LOCAL_PROVIDERS:
                raise ValueError(
                    f"'{model_str}' targets a cloud provider. "
                    "The /local endpoint only accepts 'best:<category>' or 'ollama/<model>'."
                )
            return provider, model_id
        raise ValueError(self._format_error(model_str))

    def resolve_cloud_only(self, model_str: str) -> tuple[str, str]:
        """Resolves only to cloud models. Raises if the model is local-only."""
        if model_str.startswith("best:"):
            category = model_str[5:]
            result = self._try_best_cloud(category)
            if result is None:
                raise ValueError(
                    f"No cloud model ranked for category '{category}'. "
                    f"Available categories with cloud rankings: {self._cloud_categories()}"
                )
            return result
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            if provider in LOCAL_PROVIDERS:
                raise ValueError(
                    f"'{model_str}' is a local model. "
                    "The /cloud endpoint only accepts 'best:<category>' or a cloud provider prefix "
                    "(e.g. 'groq/llama-3.3-70b-versatile')."
                )
            return provider, model_id
        raise ValueError(self._format_error(model_str))

    def resolve_chain(self, model_str: str, strategy: str = "local-first") -> list[tuple[str, str]]:
        """Return an ordered list of (provider, model_id) to try in sequence.

        Fallback only applies to best:<category> requests. Explicit provider/model
        requests always return a single-element list (no automatic fallback).

        strategy:
          'local-first'  — try local (Ollama), fall back to cloud
          'cloud-first'  — try cloud (Groq/OpenRouter), fall back to local
        """
        if not model_str.startswith("best:"):
            return [self.resolve(model_str)]

        category = model_str[5:]
        local = self._try_best_local(category)
        cloud = self._try_best_cloud(category)

        if strategy == "local-first":
            ordered = [x for x in [local, cloud] if x is not None]
        else:
            ordered = [x for x in [cloud, local] if x is not None]

        if not ordered:
            raise ValueError(self._no_category_error(category))
        return ordered

    # ── Introspection helpers ──────────────────────────────────────────────

    def categories(self) -> list[str]:
        cats = set(self._local.get("categories", {}).keys())
        cats |= set(self._cloud.get("categories", {}).keys())
        return sorted(cats)

    def list_models(self) -> list[str]:
        models: set[str] = set()
        for category in self.categories():
            models.add(f"best:{category}")
        for entries in self._local.get("categories", {}).values():
            for e in entries:
                models.add(f"ollama/{e['model']}")
        for entries in self._cloud.get("categories", {}).values():
            for e in entries:
                provider = e.get("provider", "groq")
                models.add(f"{provider}/{e['model']}")
        return sorted(models)

    def describe(self, category: str) -> list[dict]:
        """Return the full ranked list for a category (local entries first, then cloud)."""
        local = [{"provider": "ollama", **e} for e in self._local.get("categories", {}).get(category, [])]
        cloud = list(self._cloud.get("categories", {}).get(category, []))
        return local + cloud

    # ── Private helpers ────────────────────────────────────────────────────

    def _try_best_local(self, category: str) -> tuple[str, str] | None:
        entries = self._local.get("categories", {}).get(category, [])
        if entries:
            return "ollama", entries[0]["model"]
        return None

    def _try_best_cloud(self, category: str) -> tuple[str, str] | None:
        entries = self._cloud.get("categories", {}).get(category, [])
        if entries:
            e = entries[0]
            return e.get("provider", "groq"), e["model"]
        return None

    def _local_categories(self) -> list[str]:
        return sorted(self._local.get("categories", {}).keys())

    def _cloud_categories(self) -> list[str]:
        return sorted(self._cloud.get("categories", {}).keys())

    def _no_category_error(self, category: str) -> str:
        return (
            f"No model ranked for category '{category}'. "
            f"Available categories: {self.categories()}"
        )

    def _format_error(self, model_str: str) -> str:
        return (
            f"Unknown model format '{model_str}'. "
            "Use 'best:<category>' or '<provider>/<model_id>' "
            "(e.g. 'best:coding', 'ollama/qwen2.5:7b', 'groq/llama-3.3-70b-versatile')"
        )
