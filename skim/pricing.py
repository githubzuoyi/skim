"""Pricing helpers for skim analytics and inline savings hints."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_PRICING_MODEL = "gpt-5.4"


@dataclass(frozen=True)
class PricingModel:
    """Input/output token pricing for a model family."""

    key: str
    display_name: str
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float


_PRICING_MODELS: dict[str, PricingModel] = {
    "gpt-5.4": PricingModel(
        key="gpt-5.4",
        display_name="GPT-5.4",
        input_per_million=2.50,
        cached_input_per_million=0.25,
        output_per_million=15.00,
    ),
    "gpt-5.4 mini": PricingModel(
        key="gpt-5.4 mini",
        display_name="GPT-5.4 mini",
        input_per_million=0.75,
        cached_input_per_million=0.075,
        output_per_million=4.50,
    ),
}


def resolve_pricing_model(model: str | None = None) -> PricingModel:
    """Resolve the active pricing model, defaulting to GPT-5.4 input pricing."""

    requested = (model or os.environ.get("SKIM_PRICING_MODEL") or DEFAULT_PRICING_MODEL)
    key = requested.strip().lower()
    return _PRICING_MODELS.get(key, _PRICING_MODELS[DEFAULT_PRICING_MODEL])


def estimate_input_cost(tokens: int, model: str | None = None) -> float:
    """Estimate prompt-side API cost for a token count."""

    pricing = resolve_pricing_model(model)
    return (tokens / 1_000_000) * pricing.input_per_million


def savings_pct(input_tokens: int, output_tokens: int) -> int:
    """Return savings percentage relative to the original input size."""

    if input_tokens <= 0:
        return 0
    return round((1 - (output_tokens / input_tokens)) * 100)


def format_usd(amount: float) -> str:
    """Format USD values with enough precision for tiny per-read savings."""

    if amount >= 1:
        return f"${amount:.2f}"
    if amount >= 0.1:
        return f"${amount:.3f}"
    if amount >= 0.01:
        return f"${amount:.4f}"
    if amount >= 0.001:
        return f"${amount:.5f}"
    return f"${amount:.6f}"