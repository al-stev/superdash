"""Stats panel widget showing session costs, tools, and context resets."""
from __future__ import annotations
from textual.widgets import Static


def format_cache_ratio(cache_read: int, total_input: int) -> str:
    if total_input == 0:
        return "0%"
    return f"{int(cache_read / total_input * 100)}%"


class StatsWidget(Static):
    """Displays session stats: costs, tool usage, subagents, context resets."""

    def format_summary(self, total_cost: float, input_tokens: int, output_tokens: int, cache_read_tokens: int) -> str:
        total_input = input_tokens + cache_read_tokens
        ratio = format_cache_ratio(cache_read_tokens, total_input)
        return (
            f"  This session:  ${total_cost:.2f}\n"
            f"  Tokens in:     {input_tokens:,}\n"
            f"    ({ratio} cached)\n"
            f"  Tokens out:    {output_tokens:,}"
        )

    def format_compactions(self, compactions: list) -> str:
        if not compactions:
            return ""
        full = sum(1 for c in compactions if c.kind == "compaction")
        micro = sum(1 for c in compactions if c.kind == "microcompaction")
        parts = []
        if full:
            parts.append(f"  Context compactions: {full}")
        if micro:
            parts.append(f"  Context resets: {micro}")
        return "\n".join(parts)

    def update_stats(self, summary: str, per_skill: list[dict], tool_counts: dict[str, int] | None = None, subagent_count: int = 0, compactions: list | None = None):
        parts = [summary, "  " + "\u2500" * 38]
        if per_skill:
            parts.append("  Per skill:")
            max_cost = max(s["cost"] for s in per_skill) if per_skill else 1
            for s in per_skill:
                filled = int((s["cost"] / max_cost) * 10) if max_cost > 0 else 0
                bar = "\u2588" * filled + "\u2591" * (10 - filled)
                parts.append(f"  {s['name']:<28} ${s['cost']:.2f}  {bar}")

        if tool_counts:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append("  Tools:")
            sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])
            for name, count in sorted_tools[:8]:
                parts.append(f"    {name:<20} {count:>4}")

        if subagent_count > 0 or compactions:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            if subagent_count > 0:
                parts.append(f"  Subagents: {subagent_count}")
            if compactions:
                parts.append(self.format_compactions(compactions))

        self.update("\n".join(parts))
