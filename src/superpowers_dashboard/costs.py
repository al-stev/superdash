"""Cost calculation from token counts and pricing config."""

# Map short model names used in subagent dispatches to full pricing keys
MODEL_ALIASES = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-5-20250929",
    "haiku": "claude-haiku-4-5-20251001",
}


def resolve_model(model: str) -> str:
    """Resolve a model name to its full pricing key."""
    if not model or model == "inherit":
        return "claude-opus-4-6"
    return MODEL_ALIASES.get(model, model)


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    pricing: dict,
) -> float:
    """Calculate dollar cost for token usage."""
    if model not in pricing:
        return 0.0

    rates = pricing[model]
    cost = (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
        + (cache_read_tokens / 1_000_000) * rates["cache_read"]
        + (cache_write_tokens / 1_000_000) * rates["cache_write"]
    )
    return round(cost, 6)
