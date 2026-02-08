"""Hook configuration viewer panel."""
import json
from pathlib import Path

from rich.text import Text
from textual.widgets import Static


def parse_hooks_config(hooks_dict: dict, source: str) -> list[dict]:
    """Parse hooks from a settings.json-style dict.

    For each hook event type, extract entries and return a list of dicts
    with keys: event, matcher, command (just the script filename), source.
    """
    result = []
    for event, entries in hooks_dict.items():
        for entry in entries:
            matcher = entry.get("matcher", "")
            for hook in entry.get("hooks", []):
                command_path = hook.get("command", "")
                # Extract just the filename from the full path
                command = Path(command_path).name if command_path else ""
                result.append({
                    "event": event,
                    "matcher": matcher,
                    "command": command,
                    "source": source,
                })
    return result


def load_all_hooks(
    settings_path: Path | None = None,
    plugin_dirs: list[Path] | None = None,
) -> list[dict]:
    """Load hooks from user settings.json and plugin hooks.json files.

    Args:
        settings_path: Path to user settings.json. Defaults to ~/.claude/settings.json.
        plugin_dirs: List of plugin root directories to scan for hooks/hooks.json.

    Returns:
        Combined list of hook dicts.
    """
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"
    if plugin_dirs is None:
        plugin_dirs = []

    all_hooks: list[dict] = []

    # Load from user settings
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            hooks_dict = settings.get("hooks", {})
            all_hooks.extend(parse_hooks_config(hooks_dict, source="user config"))
        except (json.JSONDecodeError, OSError):
            pass

    # Load from plugin hooks.json files
    for plugin_dir in plugin_dirs:
        hooks_file = plugin_dir / "hooks" / "hooks.json"
        if hooks_file.exists():
            try:
                with open(hooks_file) as f:
                    data = json.load(f)
                hooks_dict = data.get("hooks", {})
                # Use plugin directory name as source
                source = plugin_dir.parent.name if plugin_dir.parent else plugin_dir.name
                all_hooks.extend(parse_hooks_config(hooks_dict, source=source))
            except (json.JSONDecodeError, OSError):
                pass

    return all_hooks


class HooksWidget(Static):
    """Displays configured hooks from settings and plugins."""

    def format_hooks(self, hooks: list[dict]) -> str:
        """Format hooks list as plain text (for testing)."""
        if not hooks:
            return "  No hooks configured"

        lines = []
        for hook in hooks:
            lines.append(f"  \u26a1 {hook['event']}")
            lines.append(f"    {hook['source']} \u2192 {hook['command']}")
            lines.append("")
        return "\n".join(lines)

    def update_hooks(self, hooks: list[dict]) -> None:
        """Render hooks for display with Rich styling."""
        if not hooks:
            self.update(Text("  No hooks configured", style="dim"))
            return

        text = Text()
        for i, hook in enumerate(hooks):
            if i > 0:
                text.append("\n")
            text.append(f"  \u26a1 {hook['event']}\n", style="bold")
            text.append(f"    {hook['source']} \u2192 {hook['command']}", style="dim")
        self.update(text)
