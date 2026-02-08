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

    def format_per_skill(self, per_skill: list[dict]) -> list[str]:
        """Format per-skill cost bars. Each line fits within 43 chars.

        Format: '  {name:<18} ${cost:>6.2f} {bar}' = 2+18+2+6+1+8 = 37 chars max.
        """
        if not per_skill:
            return []
        max_cost = max(s["cost"] for s in per_skill) if per_skill else 1
        lines = []
        for s in per_skill:
            name = s["name"][:18]
            cost = s["cost"]
            filled = int((cost / max_cost) * 8) if max_cost > 0 else 0
            bar = "\u2588" * filled + "\u2591" * (8 - filled)
            lines.append(f"  {name:<18} ${cost:>6.2f} {bar}")
        return lines

    def format_context(self, context_tokens: int) -> str:
        """Format context window usage display."""
        if context_tokens <= 0:
            return ""
        # Show as thousands with 'k' suffix
        ctx_k = context_tokens / 1000
        max_k = 200  # 200k context window
        filled = min(int((ctx_k / max_k) * 20), 20)
        bar = "\u2588" * filled + "\u2591" * (20 - filled)
        return f"  Context: {ctx_k:>6.1f}k {bar}"

    def format_compactions(self, compactions: list, session_count: int = 1) -> str:
        if not compactions:
            return ""
        full = sum(1 for c in compactions if c.kind == "compaction")
        micro = sum(1 for c in compactions if c.kind == "microcompaction")
        clears = sum(1 for c in compactions if c.kind == "clear")
        parts = []
        if session_count > 1:
            parts.append(f"  Sessions: {session_count}")
        if full:
            parts.append(f"  Context compactions: {full}")
        if micro:
            parts.append(f"  Context resets: {micro}")
        if clears:
            parts.append(f"  Context clears: {clears}")
        return "\n".join(parts)

    def format_compliance(self, skill_count: int, tool_count: int) -> str:
        return f"  Skills: {skill_count}  |  Tools: {tool_count}"

    def update_stats(self, summary: str, per_skill: list[dict], tool_counts: dict[str, int] | None = None, subagent_count: int = 0, compactions: list | None = None, context_tokens: int = 0, session_count: int = 1, skill_count: int = 0):
        parts = [summary, "  " + "\u2500" * 38]

        # Context window usage right after summary
        if context_tokens > 0:
            parts.append(self.format_context(context_tokens))

        # Skill/tool compliance counts
        total_tools = sum(tool_counts.values()) if tool_counts else 0
        if skill_count > 0 or total_tools > 0:
            parts.append(self.format_compliance(skill_count, total_tools))

        # Compactions in high-visibility position, right after summary/context
        if compactions:
            parts.append(self.format_compactions(compactions, session_count=session_count))

        # Per-skill cost bars
        if per_skill:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append("  Per skill:")
            parts.extend(self.format_per_skill(per_skill))

        # Tool usage counts
        if tool_counts:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append("  Tools:")
            sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])
            for name, count in sorted_tools[:8]:
                parts.append(f"    {name:<20} {count:>4}")

        # Subagent count as its own section
        if subagent_count > 0:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append(f"  Subagents: {subagent_count}")

        self.update("\n".join(parts))
