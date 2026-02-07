"""Costs panel widget showing session totals and per-skill breakdown."""
from textual.widgets import Static

def format_cache_ratio(cache_read: int, total_input: int) -> str:
    if total_input == 0:
        return "0%"
    return f"{int(cache_read / total_input * 100)}%"

class CostsWidget(Static):
    """Displays session cost totals and per-skill breakdown."""

    def format_summary(self, total_cost: float, input_tokens: int, output_tokens: int, cache_read_tokens: int) -> str:
        total_input = input_tokens + cache_read_tokens
        ratio = format_cache_ratio(cache_read_tokens, total_input)
        return (
            f"  This session:  ${total_cost:.2f}\n"
            f"  Tokens in:     {input_tokens:,}\n"
            f"    ({ratio} cached)\n"
            f"  Tokens out:    {output_tokens:,}"
        )

    def update_costs(self, summary: str, per_skill: list[dict]):
        parts = [summary, "  \u2500" * 20]
        if per_skill:
            parts.append("  Per skill:")
            max_cost = max(s["cost"] for s in per_skill) if per_skill else 1
            for s in per_skill:
                filled = int((s["cost"] / max_cost) * 10) if max_cost > 0 else 0
                bar = "\u2588" * filled + "\u2591" * (10 - filled)
                parts.append(f"  {s['name']:<18} ${s['cost']:.2f}  {bar}")
        self.update("\n".join(parts))
