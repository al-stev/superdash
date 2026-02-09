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

    def format_subagent_stats(self, count: int, skills_used: int, total_cost: float, total_tokens: int) -> str:
        """Format aggregate subagent metrics.

        Example output:
          Subagents:       8
            Skills used:   2/8
            Total cost:    $3.42
            Total tokens:  142k
        """
        if total_tokens >= 1000:
            tok_value = total_tokens / 1000
            tok_formatted = f"{tok_value:.1f}"
            if tok_formatted.endswith(".0"):
                tok_formatted = tok_formatted[:-2]
            tok_str = f"{tok_formatted}k"
        else:
            tok_str = str(total_tokens)

        return (
            f"  Subagents:       {count}\n"
            f"    Skills used:   {skills_used}/{count}\n"
            f"    Total cost:    ${total_cost:.2f}\n"
            f"    Total tokens:  {tok_str}"
        )

    def format_model_usage(self, model_stats: list[dict]) -> str:
        """Format per-model token and cost breakdown.

        Each entry: {"model": str, "input_tokens": int, "output_tokens": int, "cost": float}
        """
        if not model_stats:
            return ""
        lines = ["  Models:"]
        for m in model_stats:
            total_tok = m["input_tokens"] + m["output_tokens"]
            if total_tok >= 1000:
                tok_str = f"{total_tok / 1000:.1f}k"
                if tok_str.endswith(".0k"):
                    tok_str = tok_str[:-3] + "k"
            else:
                tok_str = str(total_tok)
            lines.append(f"    {m['model']:<14} {tok_str:>6} tok ${m['cost']:>7.2f}")
        return "\n".join(lines)

    def update_stats(self, summary: str, per_skill: list[dict], tool_counts: dict[str, int] | None = None, subagent_count: int = 0, compactions: list | None = None, context_tokens: int = 0, session_count: int = 1, skill_count: int = 0, subagent_details: list | None = None, model_stats: list[dict] | None = None):
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

        # Subagent stats section
        if subagent_details:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            agg_count = len(subagent_details)
            agg_skills = sum(1 for d in subagent_details if d.skills_invoked)
            agg_cost = sum(d.cost for d in subagent_details)
            agg_tokens = sum(d.input_tokens + d.output_tokens for d in subagent_details)
            parts.append(self.format_subagent_stats(agg_count, agg_skills, agg_cost, agg_tokens))
        elif subagent_count > 0:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append(f"  Subagents: {subagent_count}")

        # Per-model usage section
        if model_stats:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append(self.format_model_usage(model_stats))

        self.update("\n".join(parts))
