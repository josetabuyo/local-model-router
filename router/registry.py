"""Loads rankings and resolves model strings to (provider, model_id) pairs."""
from pathlib import Path

import yaml

RANKINGS_DIR = Path(__file__).parent.parent / "rankings"

LOCAL_PROVIDERS = {"ollama"}

# Model-string prefixes that select a category, and how to order that
# category's ranked entries. 'best' is the curated quality order already in
# the yaml. 'cheapest' and 'fastest' re-sort the same entries by cost/speed.
_MODES = ("best", "cheapest", "fastest")

# Base speed ranking per provider (lower = faster), used by 'fastest:<category>'.
# Groq's LPU hardware beats NVIDIA NIM and OpenRouter's proxied backends on
# every model we've measured — see rankings/cloud.yaml multilingual notes
# (Groq 2-8s vs NVIDIA 40-60s for comparable quality tiers).
_PROVIDER_SPEED_RANK: dict[str, int] = {"groq": 0, "nvidia": 2, "openrouter": 3}

# Per-model overrides where we have documented actual throughput/latency
# (see rankings/cloud.yaml notes) that contradicts the provider default —
# e.g. a specific NIM model known to be much slower than typical NIM latency.
_SPEED_OVERRIDES: dict[tuple[str, str], int] = {
    ("groq", "openai/gpt-oss-20b"): -1,      # replaces llama-3.1-8b-instant (Groq EOL 2026-08-16); smallest active Groq model, fastest in the cascade
    ("groq", "openai/gpt-oss-120b"): 0,      # ~500 tok/s, per Groq's own deprecation notice benchmarks
    # qwen/qwen3.5-397b-a17b override removed 2026-08-22 (model-scout audit):
    # EOL 2026-07-27, no longer referenced anywhere in rankings/cloud.yaml.
}


def _blended_cost(entry: dict) -> float:
    """Average of $/Mtok in and out. 0 for free-tier entries (the common case)."""
    return (entry.get("cost_per_mtok_in", 0.0) + entry.get("cost_per_mtok_out", 0.0)) / 2


def _speed_rank(entry: dict) -> int:
    provider = entry.get("provider", "groq")
    override = _SPEED_OVERRIDES.get((provider, entry["model"]))
    if override is not None:
        return override
    return _PROVIDER_SPEED_RANK.get(provider, 9)


class Registry:
    def __init__(self):
        self._local = self._load("local.yaml")
        self._cloud = self._load("cloud.yaml")

    def _load(self, filename: str) -> dict:
        with open(RANKINGS_DIR / filename) as f:
            return yaml.safe_load(f) or {}

    # ── Public resolution methods ──────────────────────────────────────────

    def resolve(self, model_str: str) -> tuple[str, str]:
        """Return (provider, model_id). Local preferred over cloud for <mode>:<category>."""
        mode, category = self._parse(model_str)
        if mode is not None:
            chain = self._local_chain(category, mode) or self._cloud_chain(category, mode)
            if chain:
                return chain[0]
            raise ValueError(self._no_category_error(category))
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
            return provider, model_id
        raise ValueError(self._format_error(model_str))

    def resolve_local_chain(self, model_str: str) -> list[tuple[str, str]]:
        """Return all local entries in ranked order. Raises if none or if model is cloud-only."""
        mode, category = self._parse(model_str)
        if mode is not None:
            chain = self._local_chain(category, mode)
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
                    "The /local endpoint only accepts '<best|cheapest|fastest>:<category>' or 'ollama/<model>'."
                )
            return [(provider, model_id)]
        raise ValueError(self._format_error(model_str))

    def resolve_cloud_chain(self, model_str: str) -> list[tuple[str, str]]:
        """Return all cloud entries in ranked order. Raises if none or if model is local-only."""
        mode, category = self._parse(model_str)
        if mode is not None:
            chain = self._cloud_chain(category, mode)
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
                    "The /cloud endpoint only accepts '<best|cheapest|fastest>:<category>' or a cloud provider prefix "
                    "(e.g. 'nvidia/deepseek-ai/deepseek-v4-pro', 'groq/qwen/qwen3.6-27b')."
                )
            return [(provider, model_id)]
        raise ValueError(self._format_error(model_str))

    def resolve_chain(self, model_str: str, strategy: str = "local-first") -> list[tuple[str, str]]:
        """Return full ordered cascade chain to try in sequence.

        For <mode>:<category>: all local entries then all cloud entries (or reversed for cloud-first),
        each tier ordered per 'mode' (best/cheapest/fastest — see _local_chain/_cloud_chain).
        For explicit provider/model: single-element list, no fallback.

        strategy:
          'local-first'  — all local entries, then all cloud entries (NVIDIA → Groq → OpenRouter)
          'cloud-first'  — all cloud entries, then all local entries
        """
        mode, category = self._parse(model_str)
        if mode is None:
            return [self.resolve(model_str)]

        local_chain = self._local_chain(category, mode)
        cloud_chain = self._cloud_chain(category, mode)

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
            for mode in _MODES:
                models.add(f"{mode}:{category}")
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

    def _parse(self, model_str: str) -> tuple[str | None, str | None]:
        """Split '<mode>:<category>' into (mode, category), or (None, None) if not that shape."""
        for mode in _MODES:
            prefix = f"{mode}:"
            if model_str.startswith(prefix):
                return mode, model_str[len(prefix):]
        return None, None

    def _local_chain(self, category: str, mode: str = "best") -> list[tuple[str, str]]:
        # Local (Ollama) entries have no pricing tiers and speed depends entirely
        # on the user's own hardware — mode doesn't reorder this tier, only
        # whether it's tried at all (it always is, for every mode).
        entries = self._local.get("categories", {}).get(category, [])
        return [("ollama", e["model"]) for e in entries]

    def _cloud_chain(self, category: str, mode: str = "best") -> list[tuple[str, str]]:
        entries = self._cloud.get("categories", {}).get(category, [])
        if mode == "cheapest":
            entries = self._sort_cheapest(entries)
        elif mode == "fastest":
            entries = self._sort_fastest(entries)
        else:
            # 'best' (curated quality order) never touches paid fallback entries
            # automatically — those only surface via 'cheapest:<category>'.
            entries = [e for e in entries if not e.get("paid")]
        return [(e.get("provider", "groq"), e["model"]) for e in entries]

    def _sort_cheapest(self, entries: list[dict]) -> list[dict]:
        """Free entries first (stable, curated order), then paid entries ascending by $/Mtok."""
        free = [e for e in entries if not e.get("paid")]
        paid = sorted((e for e in entries if e.get("paid")), key=_blended_cost)
        return free + paid

    def _sort_fastest(self, entries: list[dict]) -> list[dict]:
        """Free-tier entries only, reordered by measured/known provider speed (fastest first)."""
        free = [e for e in entries if not e.get("paid")]
        return sorted(free, key=_speed_rank)

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
