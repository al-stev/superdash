"""Activity log widget showing chronological skill invocation feed."""
from datetime import datetime
from textual.widgets import RichLog


def _parse_time(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return "??:??:??"


def format_log_entry(timestamp: str, skill_name: str, args: str) -> str:
    time_str = _parse_time(timestamp)
    args_display = args[:40] + "..." if len(args) > 40 else args
    line = f"  {time_str}  Skill: {skill_name}"
    if args_display:
        line += f'\n           args: "{args_display}"'
    return line


def format_compaction_entry(timestamp: str, kind: str, pre_tokens: int) -> str:
    time_str = _parse_time(timestamp)
    label = "MICROCOMPACTION" if kind == "microcompaction" else "COMPACTION"
    return f"  {time_str}  {label}  {pre_tokens:,} tok"


def format_hook_entry(timestamp: str, event: str) -> str:
    time_str = _parse_time(timestamp)
    return f"  {time_str}  \u26a1 Hook: {event}"


def format_subagent_entry(timestamp: str, description: str, subagent_type: str, model: str) -> str:
    time_str = _parse_time(timestamp)
    model_str = f" [{model}]" if model and model != "inherit" else ""
    return f"  {time_str}  Subagent: {description}{model_str}\n           type: {subagent_type}"


def _format_tokens(count: int) -> str:
    """Format token count with k suffix when >= 1000."""
    if count >= 1000:
        value = count / 1000
        # Use .1f but strip trailing zero for clean display
        formatted = f"{value:.1f}"
        if formatted.endswith(".0"):
            formatted = formatted[:-2]
        return f"{formatted}k"
    return str(count)


def format_subagent_detail_entry(
    timestamp: str,
    description: str,
    subagent_type: str,
    model: str,
    tool_counts: dict[str, int],
    input_tokens: int,
    output_tokens: int,
    cost: float,
    skills_invoked: list[str],
    status: str,
) -> str:
    """Format a subagent with its internal details in tree format.

    Example output:
      10:00:00  > Subagent: Research TUI [Explore/sonnet]
                 | Skills: test-driven-development
                 | Tools: Read(8) Grep(4) Glob(3)
                 + Tokens: 18.5k in / 4.2k out  $0.42  checkmark complete
    """
    time_str = _parse_time(timestamp)
    model_str = f" [{subagent_type}/{model}]" if model and model != "inherit" else f" [{subagent_type}]"
    status_icon = "\u2713" if status == "complete" else "\u25d0"

    lines = [f"  {time_str}  \u25b6 Subagent: {description}{model_str}"]

    # Determine tree connectors based on what lines will follow
    detail_lines = []

    if skills_invoked:
        skills_str = ", ".join(skills_invoked)
        detail_lines.append(f"Skills: {skills_str}")

    # Top 5 tools sorted by count descending
    if tool_counts:
        sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:5]
        tools_str = " ".join(f"{name}({count})" for name, count in sorted_tools)
        detail_lines.append(f"Tools: {tools_str}")

    # Token/cost/status line (always present)
    in_str = _format_tokens(input_tokens)
    out_str = _format_tokens(output_tokens)
    detail_lines.append(f"Tokens: {in_str} in / {out_str} out  ${cost:.2f}  {status_icon} {status}")

    # Add tree connectors
    pad = "             "
    for i, detail in enumerate(detail_lines):
        if i < len(detail_lines) - 1:
            lines.append(f"{pad}\u251c {detail}")
        else:
            lines.append(f"{pad}\u2514 {detail}")

    return "\n".join(lines)


def should_show_activity(kind: str) -> bool:
    """Return whether an activity event kind should appear in the feed."""
    return kind != "hook"


class ActivityLogWidget(RichLog):
    """Scrollable chronological log of skill invocations."""

    def add_skill_event(self, timestamp: str, skill_name: str, args: str):
        text = format_log_entry(timestamp, skill_name, args)
        self.write(text)

    def add_hook_event(self, timestamp: str, event: str):
        text = format_hook_entry(timestamp, event)
        self.write(text)

    def add_compaction(self, timestamp: str, kind: str, pre_tokens: int):
        text = format_compaction_entry(timestamp, kind, pre_tokens)
        self.write(text)

    def add_subagent(self, timestamp: str, description: str, subagent_type: str, model: str):
        text = format_subagent_entry(timestamp, description, subagent_type, model)
        self.write(text)

    def add_subagent_detail(
        self,
        timestamp: str,
        description: str,
        subagent_type: str,
        model: str,
        tool_counts: dict[str, int],
        input_tokens: int,
        output_tokens: int,
        cost: float,
        skills_invoked: list[str],
        status: str,
    ):
        text = format_subagent_detail_entry(
            timestamp, description, subagent_type, model,
            tool_counts, input_tokens, output_tokens, cost,
            skills_invoked, status,
        )
        self.write(text)
