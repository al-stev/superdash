"""Main Textual application — layout, themes, file watching."""
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import Header, Footer, Static

from superpowers_dashboard.config import load_config
from superpowers_dashboard.registry import SkillRegistry
from superpowers_dashboard.watcher import SessionParser, find_project_sessions
from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.widgets.skill_list import SkillListWidget
from superpowers_dashboard.widgets.workflow import WorkflowWidget
from superpowers_dashboard.widgets.costs_panel import StatsWidget
from superpowers_dashboard.widgets.activity import ActivityLogWidget


TERMINAL_THEME = Theme(
    name="terminal",
    primary="#ffffff",
    secondary="#333333",
    accent="#ffffff",
    foreground="#ffffff",
    background="#000000",
    surface="#000000",
    panel="#000000",
    dark=True,
    variables={
        "border": "#333333",
        "border-blurred": "#333333",
        "scrollbar": "#333333",
        "scrollbar-background": "#000000",
    },
)

MAINFRAME_THEME = Theme(
    name="mainframe",
    primary="#33ff33",
    secondary="#000000",
    accent="#33ff33",
    foreground="#33ff33",
    background="#000000",
    surface="#000000",
    panel="#000000",
    dark=True,
    variables={
        "footer-foreground": "#1a7a1a",
        "footer-background": "#000000",
        "footer-key-foreground": "#33ff33",
        "footer-description-foreground": "#1a7a1a",
        "border": "#0a1f0a",
        "border-blurred": "#0a1f0a",
        "scrollbar": "#0a1f0a",
        "scrollbar-background": "#000000",
    },
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

    TITLE = "SUPERDASH"
    CSS = """
    Screen { background: #000000; }
    * { background: transparent; }
    #top-row { height: 1fr; }
    #bottom-row { height: 1fr; }
    #skills-panel { width: 45; border: tall $border; }
    #workflow-panel { width: 1fr; border: tall $border; }
    #stats-panel { width: 45; border: tall $border; }
    #activity-panel { width: 1fr; border: tall $border; }
    .panel-title { text-style: bold; padding: 0 1; }
    Header { background: #000000; color: $foreground; }
    Footer { background: #000000; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "toggle_theme", "Theme"),
    ]

    def __init__(self, project_dir: str | None = None):
        super().__init__()
        self.config = load_config()
        self.parser = SessionParser()
        self._current_theme = "terminal"
        self._session_path: Path | None = None
        self._file_pos = 0
        self._last_activity_count = 0
        self._project_dir = project_dir

        # Load skill registry
        skills_dir = _find_skills_dir()
        self.registry = SkillRegistry(skills_dir) if skills_dir else SkillRegistry(Path("/nonexistent"))

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-row"):
            with Vertical(id="skills-panel"):
                yield Static("SKILLS", classes="panel-title")
                yield SkillListWidget(id="skill-list")
            with VerticalScroll(id="workflow-panel"):
                yield Static("WORKFLOW", classes="panel-title")
                yield WorkflowWidget(id="workflow")
        with Horizontal(id="bottom-row"):
            with VerticalScroll(id="stats-panel"):
                yield Static("STATS", classes="panel-title")
                yield StatsWidget(id="stats")
            with Vertical(id="activity-panel"):
                yield Static("ACTIVITY LOG", classes="panel-title")
                yield ActivityLogWidget(id="activity")
        yield Footer()

    def on_mount(self):
        self.register_theme(TERMINAL_THEME)
        self.register_theme(MAINFRAME_THEME)
        self.theme = "terminal"

        # Find all sessions for this project and parse them
        project_sessions = find_project_sessions(project_cwd=self._project_dir)
        if project_sessions:
            self._session_path = project_sessions[-1]  # latest for polling
            self._load_all_sessions(project_sessions)
            self.set_interval(0.5, self._poll_session)
        self._refresh_ui()

    def _load_all_sessions(self, session_paths: list[Path]):
        """Parse all session files in chronological order."""
        for path in session_paths:
            if not path.exists():
                continue
            with open(path) as f:
                for line in f:
                    self.parser.process_line(line.strip())
                if path == session_paths[-1]:
                    self._file_pos = f.tell()

    def _poll_session(self):
        """Check for new lines in the session file, and detect new sessions."""
        # Check for new session files
        current_sessions = find_project_sessions(project_cwd=self._project_dir)
        if current_sessions and current_sessions[-1] != self._session_path:
            new_path = current_sessions[-1]
            with open(new_path) as f:
                for line in f:
                    self.parser.process_line(line.strip())
                self._file_pos = f.tell()
            self._session_path = new_path
            self.parser.session_count += 1
            self._refresh_ui()
            return

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

        # Build workflow entries (skills)
        entries = []
        for i, event in enumerate(self.parser.skill_events):
            total_tokens = event.input_tokens + event.output_tokens + event.cache_read_tokens + event.cache_write_tokens
            # Calculate cost using primary model
            model = next(iter(event.models), "claude-opus-4-6")
            cost = calculate_cost(model, event.input_tokens, event.output_tokens, event.cache_read_tokens, event.cache_write_tokens, pricing)
            entries.append({
                "kind": "skill",
                "timestamp": event.timestamp,
                "skill_name": event.skill_name,
                "args": event.args,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_seconds": event.duration_ms / 1000.0,
                "is_active": event.skill_name == self.parser.active_skill and i == len(self.parser.skill_events) - 1,
            })

        # Add overhead segments
        for seg in self.parser.overhead_segments:
            seg_cost = calculate_cost(
                "claude-opus-4-6",
                seg.input_tokens, seg.output_tokens,
                seg.cache_read_tokens, seg.cache_write_tokens,
                pricing,
            )
            tool_summary = f"tools({seg.tool_count})" if seg.tool_count else ""
            entries.append({
                "kind": "overhead",
                "timestamp": seg.timestamp,
                "input_tokens": seg.input_tokens,
                "output_tokens": seg.output_tokens,
                "cost": seg_cost,
                "duration_seconds": seg.duration_ms / 1000.0,
                "tool_summary": tool_summary,
            })

        # Sort all entries by timestamp
        entries.sort(key=lambda e: e.get("timestamp", ""))

        workflow = self.query_one("#workflow", WorkflowWidget)
        workflow.update_timeline(entries)

        # Update costs
        total_input = sum(e.input_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["input"]
        total_output = sum(e.output_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["output"]
        total_cache_read = sum(e.cache_read_tokens for e in self.parser.skill_events) + self.parser.overhead_tokens["cache_read"]
        overhead_cost = calculate_cost(
            "claude-opus-4-6",
            self.parser.overhead_tokens["input"],
            self.parser.overhead_tokens["output"],
            self.parser.overhead_tokens["cache_read"],
            self.parser.overhead_tokens.get("cache_write", 0),
            pricing,
        )
        skill_entries = [e for e in entries if e.get("kind", "skill") == "skill"]
        total_cost = sum(e["cost"] for e in skill_entries) + overhead_cost

        stats_widget = self.query_one("#stats", StatsWidget)
        summary = stats_widget.format_summary(total_cost, total_input, total_output, total_cache_read)

        # Per-skill aggregation
        per_skill: dict[str, float] = {}
        for e in skill_entries:
            name = e["skill_name"]
            per_skill[name] = per_skill.get(name, 0) + e["cost"]
        per_skill_list = [{"name": k, "cost": v} for k, v in sorted(per_skill.items(), key=lambda x: -x[1])]
        context_tokens = self.parser.last_context_tokens
        stats_widget.update_stats(
            summary, per_skill_list,
            tool_counts=self.parser.tool_counts,
            subagent_count=len(self.parser.subagents),
            compactions=self.parser.compactions or None,
            context_tokens=context_tokens,
            session_count=self.parser.session_count,
            skill_count=len(self.parser.skill_events),
        )

        # Build chronological activity feed from all event types
        all_activity = []
        for event in self.parser.skill_events:
            all_activity.append(("skill", event.timestamp, event))
        for c in self.parser.compactions:
            all_activity.append(("compaction", c.timestamp, c))
        for s in self.parser.subagents:
            all_activity.append(("subagent", s.timestamp, s))
        all_activity.sort(key=lambda x: x[1])

        # Append only new events
        activity = self.query_one("#activity", ActivityLogWidget)
        for item in all_activity[self._last_activity_count:]:
            kind, _, data = item
            if kind == "skill":
                activity.add_skill_event(data.timestamp, data.skill_name, data.args)
            elif kind == "compaction":
                activity.add_compaction(data.timestamp, data.kind, data.pre_tokens)
            elif kind == "subagent":
                activity.add_subagent(data.timestamp, data.description, data.subagent_type, data.model)
        self._last_activity_count = len(all_activity)

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
