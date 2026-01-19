"""Pricing utilities for cost analysis."""

from typing import Dict, Any, Optional, Tuple


PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI (USD per 1M tokens)
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4.1": {"input": 5.00, "output": 15.00},
    "gpt-4.1-mini": {"input": 0.30, "output": 1.20},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    # Anthropic (USD per 1M tokens)
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}

DEFAULT_INPUT_RATIO = 0.6


def merge_pricing(overrides: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Merge pricing overrides into defaults."""
    pricing = {model: rates.copy() for model, rates in PRICING.items()}
    if not overrides:
        return pricing
    for model, rates in overrides.items():
        if not isinstance(rates, dict):
            continue
        input_rate = rates.get("input")
        output_rate = rates.get("output")
        if input_rate is None and output_rate is None:
            continue
        pricing.setdefault(model, {})
        if input_rate is not None:
            pricing[model]["input"] = float(input_rate)
        if output_rate is not None:
            pricing[model]["output"] = float(output_rate)
    return pricing


def split_tokens(total_tokens: int, input_ratio: float = DEFAULT_INPUT_RATIO) -> Tuple[int, int]:
    """Estimate input/output token split from a total."""
    if total_tokens <= 0:
        return 0, 0
    input_tokens = int(total_tokens * input_ratio)
    output_tokens = max(total_tokens - input_tokens, 0)
    return input_tokens, output_tokens


def calculate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    pricing: Dict[str, float],
) -> float:
    """Calculate cost in USD from token counts and per-1M pricing."""
    input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
    output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
    return input_cost + output_cost
