# tests/test_costs.py
from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.config import DEFAULT_PRICING


def test_calculate_cost_opus():
    cost = calculate_cost(
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 30.0  # $5 input + $25 output


def test_calculate_cost_with_cache():
    cost = calculate_cost(
        model="claude-opus-4-6",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 6.75  # $0.50 read + $6.25 write


def test_calculate_cost_unknown_model():
    cost = calculate_cost(
        model="unknown-model",
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 0.0
