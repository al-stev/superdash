"""Main Textual application — layout, themes, file watching."""
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.theme import Theme
from textual.widgets import Header, Footer, Static

from superpowers_dashboard.config import load_config
from superpowers_dashboard.registry import SkillRegistry
from superpowers_dashboard.watcher import SessionParser, find_latest_session
from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.widgets.skill_list import SkillListWidget
from superpowers_dashboard.widgets.workflow import WorkflowWidget
from superpowers_dashboard.widgets.costs_panel import CostsWidget
from superpowers_dashboard.widgets.activity import ActivityLogWidget


TERMINAL_THEME = Theme(
    name="terminal",
    primary="#ffffff",
    secondary="#aaaaaa",
    accent="#ffffff",
    foreground="#ffffff",
    background="#000000",
    surface="#111111",
    panel="#222222",
    dark=True,
)

MAINFRAME_THEME = Theme(
    name="mainframe",
    primary="#33ff33",
    secondary="#00cc00",
    accent="#66ff66",
    foreground="#33ff33",
    background="#000000",
    surface="#001100",
    panel="#002200",
    dark=True,
)

# Default superpowers plugin path
DEFAULT_SKILLS_DIR = (
    Path.home() / ".claude" / "plugins" / "cache"
    / "claude-plugins-official" / "superpowers"
)


def _find_skills_dir() -> Path | None:
    """Find the superpowers skills directory (latest version)."""
    if not DEFAULT_SKILLS_DIR.exists():
        return None
    versions = sorted(DEFAULT_SKILLS_DIR.iterdir(), reverse=True)
    for v in versions:
        skills = v / "skills"
        if skills.exists():
            return skills
    return None


class SuperpowersDashboard(App):
    """Terminal dashboard for Claude Code Superpowers skills."""

    TITLE = "SUPERPOWERS DASHBOARD"
    CSS = """
    #top-row { height: 1fr; }
    #bottom-row { height: 1fr; }
    #skills-panel { width: 30; border: solid $primary-darken-2; }
    #workflow-panel { width: 1fr; border: solid $primary-darken-2; }
    #costs-panel { width: 30; border: solid $primary-darken-2; }
    #activity-panel { width: 1fr; border: solid $primary-darken-2; }
    .panel-title { text-style: bold; padding: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "toggle_theme", "Theme"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.parser = SessionParser()
        self._current_theme = "terminal"
        self._session_path: Path | None = None
        self._file_pos = 0

        # Load skill registry
        skills_dir = _find_skills_dir()
        self.registry = SkillRegistry(skills_dir) if skills_dir else SkillRegistry(Path("/nonexistent"))

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-row"):
            with Vertical(id="skills-panel"):
                yield Static("SKILLS", classes="panel-title")
                yield SkillListWidget(id="skill-list")
            with Vertical(id="workflow-panel"):
                yield Static("WORKFLOW", classes="panel-title")
                yield WorkflowWidget(id="workflow")
        with Horizontal(id="bottom-row"):
            with Vertical(id="costs-panel"):
                yield Static("COSTS", classes="panel-title")
                yield CostsWidget(id="costs")
            with Vertical(id="activity-panel"):
                yield Static("ACTIVITY LOG", classes="panel-title")
                yield ActivityLogWidget(id="activity")
        yield Footer()

    def on_mount(self):
        self.register_theme(TERMINAL_THEME)
        self.register_theme(MAINFRAME_THEME)
        self.theme = "terminal"

        # Find session and start watching
        self._session_path = find_latest_session()
        if self._session_path:
            self._load_existing_session()
            self.set_interval(0.5, self._poll_session)
        self._refresh_ui()

    def _load_existing_session(self):
        """Parse existing session file content."""
        if not self._session_path or not self._session_path.exists():
            return
        with open(self._session_path) as f:
            for line in f:
                self.parser.process_line(line.strip())
            self._file_pos = f.tell()

    def _poll_session(self):
        """Check for new lines in the session file."""
        if not self._session_path or not self._session_path.exists():
            return
        with open(self._session_path) as f:
            f.seek(self._file_pos)
            new_lines = f.readlines()
            self._file_pos = f.tell()
        if new_lines:
            for line in new_lines:
                self.parser.process_line(line.strip())
            self._refresh_ui()

    def _refresh_ui(self):
        """Update all widgets from parser state."""
        all_skill_names = sorted(self.registry.skills.keys())
        pricing = self.config["pricing"]

        # Update skill list
        skill_list = self.query_one("#skill-list", SkillListWidget)
        skill_list.update_skills(all_skill_names, self.parser.active_skill, self.parser.used_skills)

        # Build workflow entries
        entries = []
        for i, event in enumerate(self.parser.skill_events):
            total_tokens = event.input_tokens + event.output_tokens + event.cache_read_tokens + event.cache_write_tokens
            # Calculate cost using primary model
            model = next(iter(event.models), "claude-opus-4-6")
            cost = calculate_cost(model, event.input_tokens, event.output_tokens, event.cache_read_tokens, event.cache_write_tokens, pricing)
            # Duration
            duration = 0.0
            if i + 1 < len(self.parser.skill_events):
                next_event = self.parser.skill_events[i + 1]
                duration = (next_event.start_time - event.start_time).total_seconds()
            elif event.skill_name == self.parser.active_skill:
                duration = (datetime.now(timezone.utc) - event.start_time).total_seconds()

            entries.append({
                "skill_name": event.skill_name,
                "args": event.args,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_seconds": duration,
                "is_active": event.skill_name == self.parser.active_skill and i == len(self.parser.skill_events) - 1,
            })

        workflow = self.query_one("#workflow", WorkflowWidget)
        workflow.update_timeline(entries)

        # Update costs
        total_input = sum(e.input_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["input"]
        total_output = sum(e.output_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["output"]
        total_cache_read = sum(e.cache_read_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["cache_read"]
        total_cost = sum(e["cost"] for e in entries)

        costs_widget = self.query_one("#costs", CostsWidget)
        summary = costs_widget.format_summary(total_cost, total_input, total_output, total_cache_read)

        # Per-skill aggregation
        per_skill: dict[str, float] = {}
        for e in entries:
            name = e["skill_name"]
            per_skill[name] = per_skill.get(name, 0) + e["cost"]
        per_skill_list = [{"name": k, "cost": v} for k, v in sorted(per_skill.items(), key=lambda x: -x[1])]
        costs_widget.update_costs(summary, per_skill_list)

        # Update activity log
        activity = self.query_one("#activity", ActivityLogWidget)
        activity.clear()
        for event in self.parser.skill_events:
            activity.add_skill_event(event.timestamp, event.skill_name, event.args)

        # Update header with session info and total cost
        session_id = self._session_path.stem[:6] if self._session_path else "none"
        self.sub_title = f"session: {session_id}  ${total_cost:.2f}"

    def action_toggle_theme(self):
        if self._current_theme == "terminal":
            self.theme = "mainframe"
            self._current_theme = "mainframe"
        else:
            self.theme = "terminal"
            self._current_theme = "terminal"
