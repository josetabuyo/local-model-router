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
            chain = self._local_chain(category) or self._cloud_chain(category)
            if chain:
                return chain[0]
            raise ValueError(self._no_category_error(category))
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            return provider, model_id
        raise ValueError(self._format_error(model_str))

    def resolve_local_chain(self, model_str: str) -> list[tuple[str, str]]:
        """Return all local entries in ranked order. Raises if none or if model is cloud-only."""
        if model_str.startswith("best:"):
            category = model_str[5:]
            chain = self._local_chain(category)
            if not chain:
                raise ValueError(
                    f"No local model ranked for category '{category}'. "
                    f"Available categories with local rankings: {self._local_categories()}"
                )
            return chain
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            if provider not in LOCAL_PROVIDERS:
                raise ValueError(
                    f"'{model_str}' targets a cloud provider. "
                    "The /local endpoint only accepts 'best:<category>' or 'ollama/<model>'."
                )
            return [(provider, model_id)]
        raise ValueError(self._format_error(model_str))

    def resolve_cloud_chain(self, model_str: str) -> list[tuple[str, str]]:
        """Return all cloud entries in ranked order. Raises if none or if model is local-only."""
        if model_str.startswith("best:"):
            category = model_str[5:]
            chain = self._cloud_chain(category)
            if not chain:
                raise ValueError(
                    f"No cloud model ranked for category '{category}'. "
                    f"Available categories with cloud rankings: {self._cloud_categories()}"
                )
            return chain
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            if provider in LOCAL_PROVIDERS:
                raise ValueError(
                    f"'{model_str}' is a local model. "
                    "The /cloud endpoint only accepts 'best:<category>' or a cloud provider prefix "
                    "(e.g. 'nvidia/deepseek-ai/deepseek-v4-pro', 'groq/qwen/qwen3.6-27b')."
                )
            return [(provider, model_id)]
        raise ValueError(self._format_error(model_str))

    def resolve_chain(self, model_str: str, strategy: str = "local-first") -> list[tuple[str, str]]:
        """Return full ordered cascade chain to try in sequence.

        For best:<category>: all local entries then all cloud entries (or reversed for cloud-first).
        For explicit provider/model: single-element list, no fallback.

        strategy:
          'local-first'  — all local entries, then all cloud entries (NVIDIA → Groq → OpenRouter)
          'cloud-first'  — all cloud entries, then all local entries
        """
        if not model_str.startswith("best:"):
            return [self.resolve(model_str)]

        category = model_str[5:]
        local_chain = self._local_chain(category)
        cloud_chain = self._cloud_chain(category)

        if strategy == "local-first":
            full_chain = local_chain + cloud_chain
        else:
            full_chain = cloud_chain + local_chain

        if not full_chain:
            raise ValueError(self._no_category_error(category))
        return full_chain

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

    def _local_chain(self, category: str) -> list[tuple[str, str]]:
        entries = self._local.get("categories", {}).get(category, [])
        return [("ollama", e["model"]) for e in entries]

    def _cloud_chain(self, category: str) -> list[tuple[str, str]]:
        entries = self._cloud.get("categories", {}).get(category, [])
        return [(e.get("provider", "groq"), e["model"]) for e in entries]

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
            "(e.g. 'best:coding', 'ollama/qwen2.5:7b', 'nvidia/deepseek-ai/deepseek-v4-pro')"
        )
