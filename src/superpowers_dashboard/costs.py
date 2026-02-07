"""Cost calculation from token counts and pricing config."""


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
