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


def format_subagent_entry(timestamp: str, description: str, subagent_type: str, model: str) -> str:
    time_str = _parse_time(timestamp)
    model_str = f" [{model}]" if model and model != "inherit" else ""
    return f"  {time_str}  Subagent: {description}{model_str}\n           type: {subagent_type}"


class ActivityLogWidget(RichLog):
    """Scrollable chronological log of skill invocations."""

    def add_skill_event(self, timestamp: str, skill_name: str, args: str):
        text = format_log_entry(timestamp, skill_name, args)
        self.write(text)

    def add_compaction(self, timestamp: str, kind: str, pre_tokens: int):
        text = format_compaction_entry(timestamp, kind, pre_tokens)
        self.write(text)

    def add_subagent(self, timestamp: str, description: str, subagent_type: str, model: str):
        text = format_subagent_entry(timestamp, description, subagent_type, model)
        self.write(text)
