# Superdash Polish & Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Polish the existing superdash TUI with bar alignment fixes, CWD-scoped session discovery, context window indicator, /clear detection, and a README.

**Architecture:** Modifications to existing modules — stats panel layout overhaul, watcher enhancements for context tracking and /clear detection, session discovery rewrite, and new README with zshrc integration tip.

**Tech Stack:** Python 3.11+, Textual, existing test infrastructure (pytest)

---

### Task 0: Commit Existing Uncommitted Changes

The working tree has uncommitted changes from the previous session (turn_duration tracking, compaction display improvements). These must be committed before new work begins.

**Step 1: Review and commit**

```bash
cd /Users/al/Documents/gitstuff/superpowers-tui
uv run pytest tests/ -q
git add src/superpowers_dashboard/app.py src/superpowers_dashboard/watcher.py src/superpowers_dashboard/widgets/costs_panel.py tests/test_watcher.py tests/test_widget_costs.py
git commit -m "feat: add turn_duration tracking and compaction count display"
```

Expected: 44 tests pass, clean commit.

---

### Task 1: Fix Stats Panel Bar Alignment & Layout

The per-skill cost bars in the stats panel overflow the 45-char panel width, causing text wrapping. Each skill entry currently takes 2 lines instead of 1, pushing tools/compactions off-screen.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/costs_panel.py`
- Modify: `tests/test_widget_costs.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_costs.py`:

```python
def test_per_skill_bar_fits_in_panel():
    """Each per-skill line must fit within 43 chars (45 panel - 2 border)."""
    w = StatsWidget()
    # Simulate update_stats and capture output
    per_skill = [
        {"name": "subagent-driven-development", "cost": 28.56},
        {"name": "test-driven-development", "cost": 9.25},
        {"name": "brainstorming", "cost": 4.20},
    ]
    lines = w.format_per_skill(per_skill)
    for line in lines:
        assert len(line) <= 43, f"Line too wide ({len(line)} chars): {line!r}"


def test_per_skill_bars_are_aligned():
    """All bar characters should start at the same column."""
    w = StatsWidget()
    per_skill = [
        {"name": "subagent-driven-development", "cost": 28.56},
        {"name": "brainstorming", "cost": 4.20},
    ]
    lines = w.format_per_skill(per_skill)
    # Find the column where the block char starts
    bar_starts = []
    for line in lines:
        for i, ch in enumerate(line):
            if ch in ("\u2588", "\u2591"):
                bar_starts.append(i)
                break
    assert len(set(bar_starts)) == 1, f"Bars start at different columns: {bar_starts}"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_costs.py::test_per_skill_bar_fits_in_panel -v`
Expected: FAIL — `format_per_skill` doesn't exist yet.

**Step 3: Implement the fix**

In `src/superpowers_dashboard/widgets/costs_panel.py`, extract `format_per_skill` as a testable method and fix the formatting:

```python
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
        clears = sum(1 for c in compactions if c.kind == "clear")
        parts = []
        if full:
            parts.append(f"  Compactions:      {full}")
        if micro:
            parts.append(f"  Micro-compactions: {micro}")
        if clears:
            parts.append(f"  Context clears:   {clears}")
        return "\n".join(parts)

    def format_context(self, context_tokens: int, max_tokens: int = 200_000) -> str:
        """Format context window usage bar."""
        if context_tokens == 0:
            return ""
        used_k = context_tokens / 1000
        max_k = max_tokens / 1000
        pct = min(context_tokens / max_tokens, 1.0)
        bar_width = 20
        filled = int(pct * bar_width)
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        return f"  Context: {used_k:.0f}k / {max_k:.0f}k\n  {bar}"

    def format_per_skill(self, per_skill: list[dict]) -> list[str]:
        """Format per-skill cost lines. Each line must fit in 43 chars."""
        if not per_skill:
            return []
        max_cost = max(s["cost"] for s in per_skill)
        lines = []
        for s in per_skill:
            # Truncate name to 18 chars, right-align cost, 8-char bar
            name = s["name"][:18]
            filled = int((s["cost"] / max_cost) * 8) if max_cost > 0 else 0
            bar = "\u2588" * filled + "\u2591" * (8 - filled)
            lines.append(f"  {name:<18} ${s['cost']:>6.2f} {bar}")
        return lines

    def update_stats(self, summary: str, per_skill: list[dict], tool_counts: dict[str, int] | None = None, subagent_count: int = 0, compactions: list | None = None, context_tokens: int = 0):
        parts = [summary]

        # Context window (right after summary)
        ctx = self.format_context(context_tokens)
        if ctx:
            parts.append(ctx)

        # Compactions (high visibility, near top)
        if compactions:
            parts.append("  " + "\u2500" * 38)
            parts.append(self.format_compactions(compactions))

        # Per-skill breakdown
        if per_skill:
            parts.append("  " + "\u2500" * 38)
            parts.append("  Per skill:")
            parts.extend(self.format_per_skill(per_skill))

        # Tools
        if tool_counts:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append("  Tools:")
            sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])
            for name, count in sorted_tools[:8]:
                parts.append(f"    {name:<20} {count:>4}")

        # Subagents
        if subagent_count > 0:
            parts.append("")
            parts.append("  " + "\u2500" * 38)
            parts.append(f"  Subagents: {subagent_count}")

        self.update("\n".join(parts))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_widget_costs.py -v`
Expected: All tests pass (existing + 2 new).

**Step 5: Make stats panel scrollable**

In `src/superpowers_dashboard/app.py`, change the stats panel container from `Vertical` to `VerticalScroll`:

Change line ~124:
```python
# Before:
        with Vertical(id="stats-panel"):
# After:
        with VerticalScroll(id="stats-panel"):
```

**Step 6: Pass context_tokens to update_stats**

In `src/superpowers_dashboard/app.py` `_refresh_ui()`, track and pass the latest context usage. Add to `SessionParser` or compute in `_refresh_ui`:

After the `total_cost` calculation, add:
```python
        # Context window usage: latest turn's total input represents context consumed
        context_tokens = self.parser.last_context_tokens
```

And pass to `update_stats`:
```python
        stats_widget.update_stats(
            summary, per_skill_list,
            tool_counts=self.parser.tool_counts,
            subagent_count=len(self.parser.subagents),
            compactions=self.parser.compactions or None,
            context_tokens=context_tokens,
        )
```

**Step 7: Run all tests**

Run: `uv run pytest tests/ -q`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add src/superpowers_dashboard/widgets/costs_panel.py src/superpowers_dashboard/app.py tests/test_widget_costs.py
git commit -m "fix: align stats panel bars, add context indicator, make scrollable"
```

---

### Task 2: Context Window Tracking in Parser

The parser needs to track the latest context window usage (total input tokens from the most recent assistant message) so the stats panel can show how much context remains.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Modify: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_tracks_last_context_tokens():
    """last_context_tokens should reflect the most recent turn's total input."""
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # The skill invocation assistant message has input_tokens=100, cache_read=200
    # So last_context_tokens should be 300
    assert parser.last_context_tokens == 300

    # Another assistant message updates it
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 5000, "output_tokens": 200, "cache_read_input_tokens": 45000, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    assert parser.last_context_tokens == 50000
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parser_tracks_last_context_tokens -v`
Expected: FAIL — `last_context_tokens` attribute doesn't exist.

**Step 3: Implement**

In `src/superpowers_dashboard/watcher.py`, add to `SessionParser.__init__`:

```python
        self.last_context_tokens: int = 0
```

In `_process_assistant`, after the existing usage extraction, add tracking of total input:

```python
        # Track context window usage (total input for latest turn)
        total_input = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        if total_input > 0:
            self.last_context_tokens = total_input
```

Add this right before the `self._accumulate_tokens(usage, model)` call.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_watcher.py -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: track context window usage from latest turn input tokens"
```

---

### Task 3: Session Scoping by Working Directory

Currently `find_project_sessions()` finds sessions from whichever project has the most recent activity. It should instead find sessions for the project matching the directory where `superdash` was launched.

Claude Code stores sessions under `~/.claude/projects/<path-with-slashes-replaced-by-dashes>/`. For example:
- `/Users/al/Documents/gitstuff/superpowers-tui`
- becomes `-Users-al-Documents-gitstuff-superpowers-tui`

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Modify: `tests/test_watcher.py`
- Modify: `src/superpowers_dashboard/app.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_find_project_sessions_by_cwd(tmp_path):
    """Sessions should be found by matching CWD to Claude's directory naming."""
    from superpowers_dashboard.watcher import find_project_sessions
    # Simulate Claude's directory structure
    project_dir = tmp_path / "-Users-al-myproject"
    project_dir.mkdir()
    session1 = project_dir / "session1.jsonl"
    session2 = project_dir / "session2.jsonl"
    session1.write_text('{"type":"user"}\n')
    session2.write_text('{"type":"user"}\n')

    # Other project (should not be found)
    other_dir = tmp_path / "-Users-al-other"
    other_dir.mkdir()
    other_session = other_dir / "other.jsonl"
    other_session.write_text('{"type":"user"}\n')

    sessions = find_project_sessions(
        base_dir=tmp_path,
        project_cwd="/Users/al/myproject",
    )
    assert len(sessions) == 2
    assert all(s.parent == project_dir for s in sessions)


def test_find_project_sessions_no_match(tmp_path):
    """Return empty list when no sessions match the CWD."""
    from superpowers_dashboard.watcher import find_project_sessions
    project_dir = tmp_path / "-Users-al-other"
    project_dir.mkdir()
    (project_dir / "s.jsonl").write_text('{"type":"user"}\n')

    sessions = find_project_sessions(
        base_dir=tmp_path,
        project_cwd="/Users/al/myproject",
    )
    assert sessions == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_find_project_sessions_by_cwd -v`
Expected: FAIL — `find_project_sessions` doesn't accept `project_cwd` parameter.

**Step 3: Implement**

Replace `find_project_sessions` in `src/superpowers_dashboard/watcher.py`:

```python
def _cwd_to_project_dir_name(cwd: str) -> str:
    """Convert a working directory path to Claude's project directory name.

    Claude Code uses the path with '/' replaced by '-':
      /Users/al/Documents/gitstuff/superpowers-tui
      -> -Users-al-Documents-gitstuff-superpowers-tui
    """
    return cwd.replace("/", "-")


def find_project_sessions(base_dir: Path | None = None, project_cwd: str | None = None) -> list[Path]:
    """Find all session JSONL files for the given project directory.

    Matches CWD to Claude's project directory naming convention.
    Returns sessions sorted oldest-first.
    """
    if base_dir is None:
        base_dir = Path.home() / ".claude" / "projects"
    if not base_dir.exists():
        return []
    if project_cwd is None:
        project_cwd = str(Path.cwd())

    dir_name = _cwd_to_project_dir_name(project_cwd)
    project_dir = base_dir / dir_name
    if not project_dir.exists():
        return []

    sessions = list(project_dir.glob("*.jsonl"))
    sessions = [s for s in sessions if "subagents" not in s.parts]
    sessions.sort(key=lambda p: p.stat().st_mtime)
    return sessions
```

Also keep `find_latest_session` but it's no longer used by the app — it can stay for backwards compatibility or be removed.

**Step 4: Update app.py to pass CWD**

In `src/superpowers_dashboard/app.py` `on_mount()`, change:

```python
        project_sessions = find_project_sessions()
```

This works because `find_project_sessions` now defaults `project_cwd` to `Path.cwd()`.

If the app receives a `--project-dir` CLI argument, pass it through. Update `__main__.py`:

```python
"""Entry point for superpowers-dashboard."""
import argparse
from superpowers_dashboard.app import SuperpowersDashboard


def main():
    parser = argparse.ArgumentParser(description="Superpowers Dashboard")
    parser.add_argument("--project-dir", default=None, help="Project directory to monitor (defaults to CWD)")
    args = parser.parse_args()
    app = SuperpowersDashboard(project_dir=args.project_dir)
    app.run()


if __name__ == "__main__":
    main()
```

And update `SuperpowersDashboard.__init__` to accept and store `project_dir`:

```python
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
```

And in `on_mount()`:

```python
        project_sessions = find_project_sessions(project_cwd=self._project_dir)
```

**Step 5: Run all tests**

Run: `uv run pytest tests/ -q`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/superpowers_dashboard/watcher.py src/superpowers_dashboard/app.py src/superpowers_dashboard/__main__.py tests/test_watcher.py
git commit -m "feat: scope session discovery to launch directory using CWD"
```

---

### Task 4: Detect /clear Commands

`/clear` commands appear in JSONL as `local_command` system entries:
```json
{"type": "system", "subtype": "local_command", "content": "<command-name>/clear</command-name>..."}
```

Note: In practice, `/clear` may not appear in JSONL at all (it may start a new session file). We add detection anyway so it works if/when the event is present.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Modify: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_detects_clear_command():
    """A /clear local_command should be tracked as a clear event."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "local_command",
        "content": '<command-name>/clear</command-name>\n            <command-message>clear</command-message>\n            <command-args></command-args>',
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.compactions) == 1
    assert parser.compactions[0].kind == "clear"
    assert parser.compactions[0].timestamp == "2026-02-07T12:00:00.000Z"


def test_parser_ignores_non_clear_local_commands():
    """Other local commands like /model should not be tracked as clears."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "local_command",
        "content": '<command-name>/model</command-name>\n            <command-message>model</command-message>\n            <command-args></command-args>',
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.compactions) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parser_detects_clear_command -v`
Expected: FAIL — parser doesn't handle `local_command`.

**Step 3: Implement**

In `src/superpowers_dashboard/watcher.py`, add to `_process_system`:

```python
        elif subtype == "local_command":
            content = entry.get("content", "")
            if "<command-name>/clear</command-name>" in content:
                self.compactions.append(CompactionEvent(
                    timestamp=entry.get("timestamp", ""),
                    pre_tokens=0,
                    trigger="manual",
                    kind="clear",
                ))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_watcher.py -v`
Expected: All tests pass.

**Step 5: Update compactions label test**

Update `tests/test_widget_costs.py` to verify the "Context clears" label:

```python
def test_stats_widget_shows_clear_counts():
    """Stats should show clear count separately."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="t1", pre_tokens=169162, trigger="auto", kind="compaction"),
        CompactionEvent(timestamp="t2", pre_tokens=0, trigger="manual", kind="clear"),
    ]
    text = w.format_compactions(compactions)
    assert "Compactions:" in text
    assert "Context clears:" in text
```

**Step 6: Run all tests**

Run: `uv run pytest tests/ -q`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py tests/test_widget_costs.py
git commit -m "feat: detect /clear commands and show in stats panel"
```

---

### Task 5: README and zshrc Integration

**Files:**
- Create: `README.md`
- Create: `.gitignore`

**Step 1: Create .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.venv/
```

**Step 2: Create README.md**

```markdown
# superdash

Terminal dashboard for monitoring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions with [Superpowers](https://github.com/anthropics/claude-code-plugins/tree/main/superpowers) skills.

Read-only. No hooks, no configuration required. Just run it alongside Claude Code.

## Install

```bash
uv tool install .
```

Or for development:

```bash
git clone <repo-url>
cd superpowers-tui
uv sync
uv run superdash
```

## Usage

```bash
# Monitor sessions for the current directory
superdash

# Monitor a specific project
superdash --project-dir /path/to/project
```

### Panels

| Panel | Location | Shows |
|-------|----------|-------|
| **Skills** | Top-left | All registered skills with active/used/available status |
| **Workflow** | Top-right | Timeline of skill invocations with tokens, cost, duration |
| **Stats** | Bottom-left | Session cost, context usage, compactions, tool counts |
| **Activity Log** | Bottom-right | Chronological event feed |

### Keybindings

- `q` — Quit
- `t` — Toggle theme (Terminal / Mainframe)

## Auto-launch with Claude Code

Add to your `~/.zshrc`:

**Terminal.app:**
```bash
claude-dash() {
  osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && superdash\""
  claude "$@"
}
```

**iTerm2:**
```bash
claude-dash() {
  osascript -e "tell application \"iTerm2\" to create window with default profile command \"cd $(pwd) && superdash\""
  claude "$@"
}
```

Then use `claude-dash` instead of `claude` to launch both together.

## How It Works

Superdash reads Claude Code session files (`~/.claude/projects/<project>/*.jsonl`) and polls for new data every 500ms. It detects skill invocations, token usage, compactions, and subagent dispatches from the JSONL stream.

Session files are matched to the current working directory — each `superdash` instance only shows data for its own project.
```

**Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: add README with usage, panels, and zshrc integration"
```

---

### Task 6: Integration Test

**Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 2: Launch the dashboard**

Run: `uv run superdash`

Verify:
- Stats panel shows compactions near the top (below session summary)
- Per-skill bars are aligned on one line each
- Context usage bar appears
- Tools and subagent counts are visible (scroll if needed)
- Only sessions for the current project directory are shown

**Step 3: Test --project-dir flag**

Run: `uv run superdash --project-dir /Users/al/Documents/gitstuff/superpowers-tui`
Expected: Same sessions as default (since that's the CWD).

Run: `uv run superdash --project-dir /nonexistent`
Expected: Dashboard launches with "No skills invoked yet" (no sessions found).

---

## Summary

| Task | Description | Tests Added |
|------|-------------|-------------|
| 0 | Commit existing uncommitted changes | 0 (existing 44 pass) |
| 1 | Fix stats panel bars, context indicator, VerticalScroll | 2 |
| 2 | Context window tracking in parser | 1 |
| 3 | Session scoping by CWD | 2 |
| 4 | /clear detection | 3 |
| 5 | README and .gitignore | 0 |
| 6 | Integration test (manual) | 0 |

**Total: 7 tasks, 8 new tests (52 total), ~6 files modified, ~2 files created**
