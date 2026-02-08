"""Workflow timeline widget showing skill invocation history."""
from textual.widgets import Static

def format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)

def format_duration_minutes(seconds: float) -> str:
    if seconds < 60:
        return "<1m"
    minutes = int(seconds // 60)
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    return f"{minutes}m"

def _cost_bar(cost: float, max_cost: float, width: int = 14) -> str:
    if max_cost <= 0:
        return "\u2591" * width
    filled = int((cost / max_cost) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)

class WorkflowWidget(Static):
    """Displays vertical timeline of skill invocations."""

    def format_entry(self, index: int, skill_name: str, args: str, total_tokens: int, cost: float, duration_seconds: float, max_cost: float, is_active: bool) -> str:
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        bar = _cost_bar(cost, max_cost)
        active_marker = " \u25cf" if is_active else ""
        args_display = f'"{args[:30]}..."' if len(args) > 30 else f'"{args}"' if args else ""
        num = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469"
        idx_char = num[index - 1] if 1 <= index <= 10 else f"({index})"
        result = f"{idx_char} {skill_name:<24} {tok_str:>6} tok  ${cost:.2f}\n"
        if args_display:
            result += f"   \u2503  {args_display}\n"
        result += f"   \u2503  {bar}  {dur_str}{active_marker}"
        return result

    def format_overhead(self, input_tokens: int, output_tokens: int, cost: float, duration_seconds: float, tool_summary: str) -> str:
        """Render an overhead segment (work done without any skill active)."""
        total_tokens = input_tokens + output_tokens
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        result = f"   \u2500\u2500 no skill \u2500\u2500        {tok_str:>6} tok  ${cost:.2f}\n"
        if tool_summary:
            result += f"   \u2503  {tool_summary}\n"
        result += f"   \u2503  {dur_str}"
        return result

    def update_timeline(self, entries: list[dict]):
        if not entries:
            self.update("  No skills invoked yet.")
            return
        max_cost = max(e.get("cost", 0) for e in entries)
        parts = []
        skill_index = 0
        for e in entries:
            kind = e.get("kind", "skill")
            if kind == "overhead":
                text = self.format_overhead(
                    input_tokens=e.get("input_tokens", 0),
                    output_tokens=e.get("output_tokens", 0),
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    tool_summary=e.get("tool_summary", ""),
                )
            else:
                skill_index += 1
                text = self.format_entry(index=skill_index, skill_name=e["skill_name"], args=e.get("args", ""), total_tokens=e.get("total_tokens", 0), cost=e.get("cost", 0), duration_seconds=e.get("duration_seconds", 0), max_cost=max_cost, is_active=e.get("is_active", False))
            parts.append(text)
        separator = "\n   \u25bc\n"
        self.update(separator.join(parts))
