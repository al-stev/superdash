"""Activity log widget showing chronological skill invocation feed."""
from datetime import datetime
from textual.widgets import RichLog

def format_log_entry(timestamp: str, skill_name: str, args: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        time_str = "??:??:??"
    args_display = args[:40] + "..." if len(args) > 40 else args
    line = f"  {time_str}  {skill_name}"
    if args_display:
        line += f'\n           args: "{args_display}"'
    return line

class ActivityLogWidget(RichLog):
    """Scrollable chronological log of skill invocations."""
    def add_skill_event(self, timestamp: str, skill_name: str, args: str):
        text = format_log_entry(timestamp, skill_name, args)
        self.write(text)
