"""Result dataclass and cost estimation."""
from dataclasses import dataclass, field
from typing import Optional


ELECTRICITY_COST_PER_KWH = 0.15  # USD, US average
MAC_POWER_WATTS = 30.0            # MacBook M-series under LLM load


@dataclass
class Result:
    model_id: str
    provider: str
    task_id: str
    task_name: str
    ttft_s: Optional[float]       # time to first token
    total_s: float                # total wall time
    prompt_tokens: int
    output_tokens: int
    tokens_per_sec: float
    cost_usd: float               # 0 for local
    response: str
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def local_cost_usd(total_s: float) -> float:
    """Electricity cost for running the model for total_s seconds."""
    hours = total_s / 3600
    return hours * MAC_POWER_WATTS / 1000 * ELECTRICITY_COST_PER_KWH


# Cloud pricing per 1M tokens (input + output blended, free-tier = 0)
CLOUD_PRICES: dict[str, float] = {
    # Groq — free tier (rate-limited but $0)
    "groq/llama-3.1-8b-instant": 0.0,
    "groq/llama3-8b-8192": 0.0,
    "groq/gemma2-9b-it": 0.0,
    "groq/mixtral-8x7b-32768": 0.0,
    # OpenRouter free models
    "openrouter/google/gemma-4-31b-it:free": 0.0,
    "openrouter/openai/gpt-oss-20b:free": 0.0,
    "openrouter/nvidia/nemotron-nano-9b-v2:free": 0.0,
}


def cloud_cost_usd(model_key: str, total_tokens: int) -> float:
    price_per_m = CLOUD_PRICES.get(model_key, 0.0)
    return price_per_m * total_tokens / 1_000_000
