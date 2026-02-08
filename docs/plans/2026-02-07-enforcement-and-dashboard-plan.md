# Skill Enforcement & Dashboard Augmentation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add layered skill enforcement (hooks + CLAUDE.md), fix cost/session bugs, and expand the dashboard with subagent visibility, hook config, and skill compliance tracking.

**Architecture:** Enforcement lives outside the dashboard (user-level hooks + CLAUDE.md). Dashboard changes are all in-process: new data models in watcher.py, new widgets, and augmented existing panels. All state flows through SessionParser.

**Tech Stack:** Python 3.11+, Textual TUI framework, JSONL parsing, shell scripts for hooks.

**Test runner:** `uv run pytest tests/ -x -v`

**Design doc:** `docs/plans/2026-02-07-enforcement-and-dashboard-design.md`

---

### Task 1: Fix overhead cost calculation bug

The dashboard only sums costs from skill events, ignoring overhead tokens (work done without any skill active). This is likely the source of the $20 discrepancy observed.

**Files:**
- Modify: `src/superpowers_dashboard/app.py:200-203`
- Test: `tests/test_app_cost.py` (new)

**Step 1: Write the failing test**

Create `tests/test_app_cost.py`:

```python
"""Tests for overhead cost calculation in the app refresh logic."""
import json
from superpowers_dashboard.watcher import SessionParser
from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.config import DEFAULT_PRICING


def _compute_total_cost(parser: SessionParser, pricing: dict = None) -> float:
    """Replicate the app's cost calculation logic."""
    if pricing is None:
        pricing = DEFAULT_PRICING

    # Skill event costs
    skill_cost = 0.0
    for event in parser.skill_events:
        model = next(iter(event.models), "claude-opus-4-6")
        skill_cost += calculate_cost(
            model, event.input_tokens, event.output_tokens,
            event.cache_read_tokens, event.cache_write_tokens, pricing,
        )

    # Overhead cost
    overhead_cost = calculate_cost(
        "claude-opus-4-6",
        parser.overhead_tokens["input"],
        parser.overhead_tokens["output"],
        parser.overhead_tokens["cache_read"],
        parser.overhead_tokens.get("cache_write", 0),
        pricing,
    )

    return skill_cost + overhead_cost


def test_overhead_tokens_are_costed():
    """Overhead tokens (no skill active) must be included in total cost."""
    parser = SessionParser()
    # Simulate work without any skill invocation
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 10000, "output_tokens": 5000,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))

    assert parser.overhead_tokens["input"] == 10000
    assert parser.overhead_tokens["output"] == 5000
    total = _compute_total_cost(parser)
    # 10k input @ $5/M = $0.05, 5k output @ $25/M = $0.125
    assert total > 0.0
    expected = (10000 / 1_000_000) * 5.0 + (5000 / 1_000_000) * 25.0
    assert abs(total - expected) < 0.001


def test_total_cost_includes_both_skill_and_overhead():
    """Total cost should sum skill event costs AND overhead costs."""
    parser = SessionParser()
    # Overhead before skill
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "overhead work"}],
            "usage": {"input_tokens": 5000, "output_tokens": 2000,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))

    # Skill invocation
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": "t1", "name": "Skill",
                         "input": {"skill": "superpowers:brainstorming"}}],
            "usage": {"input_tokens": 100, "output_tokens": 50,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:01:00.000Z",
    }))
    parser.process_line(json.dumps({
        "type": "user", "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": "skill content"}]},
        "timestamp": "2026-02-07T10:01:00.000Z",
    }))

    total = _compute_total_cost(parser)
    overhead_only = calculate_cost("claude-opus-4-6", 5000, 2000, 0, 0, DEFAULT_PRICING)
    skill_only = calculate_cost("claude-opus-4-6", 100, 50, 0, 0, DEFAULT_PRICING)
    assert abs(total - (overhead_only + skill_only)) < 0.001
    assert total > skill_only  # overhead must contribute
```

**Step 2: Run test to verify it passes (this tests the calculation helper, not the app bug itself)**

Run: `uv run pytest tests/test_app_cost.py -v`
Expected: PASS (we're testing the correct calculation logic that we'll apply to app.py)

**Step 3: Apply the fix in app.py**

In `src/superpowers_dashboard/app.py`, replace the `total_cost` line in `_refresh_ui()`:

Replace:
```python
        total_cost = sum(e["cost"] for e in entries)
```

With:
```python
        # Include overhead cost (work done without any skill active)
        overhead_cost = calculate_cost(
            "claude-opus-4-6",
            self.parser.overhead_tokens["input"],
            self.parser.overhead_tokens["output"],
            self.parser.overhead_tokens["cache_read"],
            self.parser.overhead_tokens.get("cache_write", 0),
            pricing,
        )
        total_cost = sum(e["cost"] for e in entries) + overhead_cost
```

**Step 4: Run all tests to verify nothing broke**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tests/test_app_cost.py src/superpowers_dashboard/app.py
git commit -m "fix: include overhead tokens in total cost calculation"
```

---

### Task 2: Add overhead segment tracking to watcher

Track overhead work as distinct segments between skill events, so the workflow panel can show gaps.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Test: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_tracks_overhead_segments():
    """Overhead work between skills should be tracked as segments."""
    parser = SessionParser()

    # Overhead before first skill
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/foo"}}],
            "usage": {"input_tokens": 5000, "output_tokens": 2000,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))

    # Skill invocation
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1", timestamp="2026-02-07T10:05:00.000Z"):
        parser.process_line(line)

    assert len(parser.overhead_segments) >= 1
    seg = parser.overhead_segments[0]
    assert seg.input_tokens == 5000
    assert seg.output_tokens == 2000
    assert seg.tool_count == 1


def test_parser_overhead_segment_between_skills():
    """Overhead gap between two skills should be a separate segment."""
    parser = SessionParser()

    # First skill
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1", timestamp="2026-02-07T10:00:00.000Z"):
        parser.process_line(line)

    # Overhead between skills
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "tool_use", "id": "e1", "name": "Edit", "input": {}},
                {"type": "tool_use", "id": "e2", "name": "Write", "input": {}},
            ],
            "usage": {"input_tokens": 8000, "output_tokens": 3000,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:10:00.000Z",
    }))

    # Second skill — this should finalize the overhead segment
    for line in _make_skill_invocation("writing-plans", tool_use_id="t2", timestamp="2026-02-07T10:15:00.000Z"):
        parser.process_line(line)

    # Should have at least one overhead segment between the two skills
    assert len(parser.overhead_segments) >= 1
    # Find the segment between skills (not before the first skill)
    between = [s for s in parser.overhead_segments if s.tool_count == 2]
    assert len(between) == 1
    assert between[0].input_tokens == 8000


def test_parser_no_overhead_segment_when_skill_active():
    """No overhead segment created while a skill is active."""
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)

    # Work under active skill
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "work under skill"}],
            "usage": {"input_tokens": 1000, "output_tokens": 500,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:05:00.000Z",
    }))

    assert len(parser.overhead_segments) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parser_tracks_overhead_segments -v`
Expected: FAIL with `AttributeError: 'SessionParser' has no attribute 'overhead_segments'`

**Step 3: Implement OverheadSegment and tracking**

Add to `src/superpowers_dashboard/watcher.py`:

Add the dataclass after `SubagentEvent`:

```python
@dataclass
class OverheadSegment:
    """A segment of work done without any skill active."""
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int = 0
    tool_count: int = 0
```

In `SessionParser.__init__`, add:
```python
        self.overhead_segments: list[OverheadSegment] = []
        self._current_overhead: OverheadSegment | None = None
```

Modify `_accumulate_tokens` to track overhead segments:

```python
    def _accumulate_tokens(self, usage: dict, model: str):
        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)

        if self.skill_events and self.active_skill:
            event = self.skill_events[-1]
            event.input_tokens += input_tok
            event.output_tokens += output_tok
            event.cache_read_tokens += cache_read
            event.cache_write_tokens += cache_write
            if model:
                event.models.add(model)
        else:
            self.overhead_tokens["input"] += input_tok
            self.overhead_tokens["output"] += output_tok
            self.overhead_tokens["cache_read"] += cache_read
            self.overhead_tokens["cache_write"] += cache_write
            # Track as overhead segment
            if self._current_overhead is None:
                self._current_overhead = OverheadSegment(timestamp="")
            if not self._current_overhead.timestamp:
                self._current_overhead.timestamp = ""  # will be set from entry
            self._current_overhead.input_tokens += input_tok
            self._current_overhead.output_tokens += output_tok
            self._current_overhead.cache_read_tokens += cache_read
            self._current_overhead.cache_write_tokens += cache_write
```

Track tool counts in overhead segments — modify `_process_assistant` to count tools in the current overhead segment when no skill is active. Also finalize the overhead segment when a new skill starts.

In `_process_assistant`, after the tool_use loop, before `_accumulate_tokens`:
```python
        # Count tools for overhead segment tracking
        if not (self.skill_events and self.active_skill):
            tool_count = sum(1 for item in content if item.get("type") == "tool_use")
            if tool_count > 0 and self._current_overhead is None:
                self._current_overhead = OverheadSegment(timestamp=entry.get("timestamp", ""))
            if tool_count > 0 and self._current_overhead is not None:
                self._current_overhead.tool_count += tool_count
                if not self._current_overhead.timestamp:
                    self._current_overhead.timestamp = entry.get("timestamp", "")
```

In `_process_user`, when a skill is confirmed (before creating the SkillEvent), finalize any current overhead segment:
```python
        if entry.get("isMeta") and self._pending_skill:
            # Finalize current overhead segment
            if self._current_overhead is not None and (self._current_overhead.input_tokens > 0 or self._current_overhead.tool_count > 0):
                self.overhead_segments.append(self._current_overhead)
            self._current_overhead = None
            # ... existing skill event creation code
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_watcher.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: track overhead segments between skill invocations"
```

---

### Task 3: Show overhead gaps in workflow panel

Render overhead segments as visible gaps between skill events in the workflow timeline.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/workflow.py`
- Modify: `src/superpowers_dashboard/app.py` (pass overhead data to workflow)
- Test: `tests/test_widget_workflow.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_workflow.py`:

```python
def test_workflow_format_overhead():
    """Overhead segments should render with tool summary."""
    w = WorkflowWidget()
    text = w.format_overhead(
        input_tokens=18500, output_tokens=4200,
        cost=4.20, duration_seconds=120, tool_summary="Edit(3) Read(5)",
    )
    assert "no skill" in text.lower() or "overhead" in text.lower()
    assert "18.5k" in text
    assert "$4.20" in text


def test_workflow_timeline_with_overhead():
    """Timeline should interleave skills and overhead segments."""
    w = WorkflowWidget()
    entries = [
        {"kind": "skill", "skill_name": "brainstorming", "args": "", "total_tokens": 1200, "cost": 0.52, "duration_seconds": 120, "is_active": False},
        {"kind": "overhead", "total_tokens": 18500, "cost": 4.20, "duration_seconds": 60, "tool_summary": "Edit(3) Read(5)"},
        {"kind": "skill", "skill_name": "test-driven-dev", "args": "", "total_tokens": 3100, "cost": 1.10, "duration_seconds": 240, "is_active": True},
    ]
    w.update_timeline(entries)
    content = str(w.renderable)
    assert "brainstorming" in content
    assert "test-driven-dev" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_workflow.py::test_workflow_format_overhead -v`
Expected: FAIL with `AttributeError: 'WorkflowWidget' has no attribute 'format_overhead'`

**Step 3: Implement overhead rendering**

Add to `src/superpowers_dashboard/widgets/workflow.py`:

```python
    def format_overhead(self, input_tokens: int, output_tokens: int, cost: float, duration_seconds: float, tool_summary: str) -> str:
        total_tokens = input_tokens + output_tokens
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        result = f"   \u2500\u2500 no skill \u2500\u2500        {tok_str:>6} tok  ${cost:.2f}\n"
        if tool_summary:
            result += f"   \u2503  {tool_summary}\n"
        result += f"   \u2503  {dur_str}"
        return result
```

Update `update_timeline` to handle mixed entries:

```python
    def update_timeline(self, entries: list[dict]):
        if not entries:
            self.update("  No skills invoked yet.")
            return
        max_cost = max(e.get("cost", 0) for e in entries) if entries else 1
        parts = []
        skill_index = 0
        for e in entries:
            if e.get("kind") == "overhead":
                text = self.format_overhead(
                    input_tokens=e.get("total_tokens", 0),
                    output_tokens=0,
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    tool_summary=e.get("tool_summary", ""),
                )
                parts.append(text)
            else:
                skill_index += 1
                text = self.format_entry(
                    index=skill_index,
                    skill_name=e["skill_name"], args=e.get("args", ""),
                    total_tokens=e.get("total_tokens", 0), cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    max_cost=max_cost, is_active=e.get("is_active", False),
                )
                parts.append(text)
        separator = "\n   \u25bc\n"
        self.update(separator.join(parts))
```

Update `_refresh_ui` in `app.py` to build the mixed entries list with overhead segments interleaved. Build entries by iterating skill events and overhead segments together, sorted by timestamp.

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py src/superpowers_dashboard/app.py tests/test_widget_workflow.py
git commit -m "feat: show overhead gaps between skills in workflow timeline"
```

---

### Task 4: Add new session detection to polling loop

The dashboard only watches the session file found at startup. New sessions are missed entirely.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py` (add `session_count`)
- Modify: `src/superpowers_dashboard/app.py` (detect new session files)
- Test: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_has_session_count():
    """SessionParser should track session count."""
    parser = SessionParser()
    assert parser.session_count == 1  # starts at 1 (current session)


def test_find_project_sessions_excludes_subagents(tmp_path):
    """Subagent JSONL files must be excluded from session list."""
    from superpowers_dashboard.watcher import find_project_sessions
    project_dir = tmp_path / "-Users-al-myproject"
    project_dir.mkdir()
    session = project_dir / "abc123.jsonl"
    session.write_text('{"type":"user"}\n')

    # Create subagent file
    subagent_dir = project_dir / "abc123" / "subagents"
    subagent_dir.mkdir(parents=True)
    (subagent_dir / "agent-xyz.jsonl").write_text('{"type":"user"}\n')

    sessions = find_project_sessions(base_dir=tmp_path, project_cwd="/Users/al/myproject")
    assert len(sessions) == 1
    assert "subagents" not in str(sessions[0])
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parser_has_session_count -v`
Expected: FAIL with `AttributeError: 'SessionParser' has no attribute 'session_count'`

**Step 3: Implement session count and new session detection**

In `src/superpowers_dashboard/watcher.py`, add to `SessionParser.__init__`:
```python
        self.session_count: int = 1
```

In `src/superpowers_dashboard/app.py`, modify `_poll_session`:

```python
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
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py src/superpowers_dashboard/app.py tests/test_watcher.py
git commit -m "feat: detect new sessions during polling and track session count"
```

---

### Task 5: Add session count and skill compliance to stats panel

Show session count alongside compactions, and show skill vs tool counts.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/costs_panel.py`
- Modify: `src/superpowers_dashboard/app.py` (pass new data)
- Test: `tests/test_widget_costs.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_costs.py`:

```python
def test_stats_widget_shows_session_count():
    """Stats should show session count alongside compactions."""
    w = StatsWidget()
    text = w.format_compactions([], session_count=3)
    assert "Sessions: 3" in text


def test_stats_widget_shows_skill_compliance():
    """Stats should show skill and tool counts."""
    w = StatsWidget()
    text = w.format_compliance(skill_count=3, tool_count=28)
    assert "Skills: 3" in text
    assert "Tools: 28" in text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_costs.py::test_stats_widget_shows_session_count -v`
Expected: FAIL (format_compactions doesn't accept session_count)

**Step 3: Implement session count and compliance display**

In `src/superpowers_dashboard/widgets/costs_panel.py`:

Update `format_compactions` signature to accept `session_count`:

```python
    def format_compactions(self, compactions: list, session_count: int = 1) -> str:
        parts = []
        if session_count > 1:
            parts.append(f"  Sessions: {session_count}")
        if not compactions and not parts:
            return ""
        full = sum(1 for c in compactions if c.kind == "compaction")
        micro = sum(1 for c in compactions if c.kind == "microcompaction")
        clears = sum(1 for c in compactions if c.kind == "clear")
        if full:
            parts.append(f"  Context compactions: {full}")
        if micro:
            parts.append(f"  Context resets: {micro}")
        if clears:
            parts.append(f"  Context clears: {clears}")
        return "\n".join(parts)
```

Add `format_compliance` method:

```python
    def format_compliance(self, skill_count: int, tool_count: int) -> str:
        return f"  Skills: {skill_count}  |  Tools: {tool_count}"
```

Update `update_stats` to accept and display compliance data:

```python
    def update_stats(self, summary: str, per_skill: list[dict],
                     tool_counts: dict[str, int] | None = None,
                     subagent_count: int = 0,
                     compactions: list | None = None,
                     context_tokens: int = 0,
                     session_count: int = 1,
                     skill_count: int = 0):
```

Add compliance display after the context bar, before compactions:

```python
        # Skill compliance
        total_tools = sum(tool_counts.values()) if tool_counts else 0
        if skill_count > 0 or total_tools > 0:
            parts.append(self.format_compliance(skill_count, total_tools))
```

Pass `session_count` to `format_compactions`:

```python
        if compactions or session_count > 1:
            parts.append(self.format_compactions(compactions or [], session_count))
```

Update `_refresh_ui` in `app.py` to pass the new arguments:

```python
        stats_widget.update_stats(
            summary, per_skill_list,
            tool_counts=self.parser.tool_counts,
            subagent_count=len(self.parser.subagents),
            compactions=self.parser.compactions or None,
            context_tokens=context_tokens,
            session_count=self.parser.session_count,
            skill_count=len(self.parser.skill_events),
        )
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/costs_panel.py src/superpowers_dashboard/app.py tests/test_widget_costs.py
git commit -m "feat: show session count and skill compliance in stats panel"
```

---

### Task 6: Create enforcement hooks and CLAUDE.md files

Create the hook scripts and configuration files for skill enforcement. These are config files outside the dashboard project.

**Files:**
- Create: `~/.claude/hooks/skill-check.sh`
- Create: `~/.claude/hooks/warn-no-skill.sh`
- Create: `~/.claude/hooks/subagent-skill-check.sh`
- Modify: `~/.claude/settings.json`
- Create: `~/.claude/CLAUDE.md`
- Create: `/Users/al/Documents/gitstuff/superpowers-tui/CLAUDE.md`

**Step 1: Create hooks directory and scripts**

```bash
mkdir -p ~/.claude/hooks
```

Create `~/.claude/hooks/skill-check.sh`:
```bash
#!/usr/bin/env bash
cat <<'EOF'
{
  "hookSpecificOutput": {
    "additionalContext": "Before responding, check if any available skills apply to this task. If there is even a 1% chance a skill applies, invoke it with the Skill tool BEFORE any other action including clarifying questions."
  }
}
EOF
exit 0
```

Create `~/.claude/hooks/warn-no-skill.sh`:
```bash
#!/usr/bin/env bash
cat <<'EOF'
{
  "hookSpecificOutput": {
    "additionalContext": "You are about to modify code or run a command. If no skill has been invoked this session, consider whether one should apply first (brainstorming, test-driven-development, systematic-debugging, writing-plans)."
  }
}
EOF
exit 0
```

Create `~/.claude/hooks/subagent-skill-check.sh`:
```bash
#!/usr/bin/env bash
cat <<'EOF'
{
  "hookSpecificOutput": {
    "additionalContext": "Before starting work, check if any available skills apply. If there is even a 1% chance, invoke it first."
  }
}
EOF
exit 0
```

Make all executable:
```bash
chmod +x ~/.claude/hooks/skill-check.sh ~/.claude/hooks/warn-no-skill.sh ~/.claude/hooks/subagent-skill-check.sh
```

**Step 2: Update settings.json**

Read current `~/.claude/settings.json` and merge hooks into it:

```json
{
  "model": "opus",
  "enabledPlugins": {
    "frontend-design@claude-code-plugins": true,
    "superpowers@claude-plugins-official": true
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/skill-check.sh"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/warn-no-skill.sh"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/subagent-skill-check.sh"
          }
        ]
      }
    ]
  }
}
```

**Step 3: Create global CLAUDE.md**

Create `~/.claude/CLAUDE.md`:
```markdown
# Workflow
- Before any action, check if a superpowers skill applies. If even 1% chance, invoke it.
- Subagents: check available skills before starting work.
- Use test-driven-development for any code changes.
- Use systematic-debugging for any bug investigation.
- Use brainstorming before any creative/design work.
```

**Step 4: Create project CLAUDE.md**

Create `/Users/al/Documents/gitstuff/superpowers-tui/CLAUDE.md`:
```markdown
# superpowers-tui

Terminal dashboard for monitoring Claude Code superpowers skill usage.

## Commands
- `uv run python -m superpowers_dashboard` — run the dashboard
- `uv run pytest` — run tests
- `uv run pytest tests/test_file.py -x` — run a specific test file

## Architecture
- `src/superpowers_dashboard/` — all source code
- `watcher.py` — JSONL parser and session discovery (the data layer)
- `app.py` — Textual app, layout, polling loop, UI refresh
- `widgets/` — individual panel widgets (skill_list, workflow, costs_panel, activity, hooks_panel)
- `registry.py` — reads skill definitions from superpowers plugin
- `costs.py` — token-to-cost calculation
- `config.py` — pricing config with TOML override

## Key Patterns
- SessionParser processes JSONL lines incrementally (streaming, not batch)
- Polling is 500ms interval on the latest session file
- All state lives in SessionParser; widgets are stateless renderers
- Subagent JSONL files are at {session-id}/subagents/agent-{id}.jsonl

## Gotchas
- Token accumulation attributes to active skill or overhead — no skill means overhead
- Claude's project dir naming: replaces / with - in the CWD path
- Skill confirmation requires an isMeta user entry after the Skill tool_use
```

**Step 5: Verify hooks work**

```bash
bash ~/.claude/hooks/skill-check.sh
# Expected: JSON output with additionalContext
bash ~/.claude/hooks/warn-no-skill.sh
# Expected: JSON output with additionalContext
bash ~/.claude/hooks/subagent-skill-check.sh
# Expected: JSON output with additionalContext
```

**Step 6: Commit project CLAUDE.md (not user-level files)**

```bash
git add CLAUDE.md
git commit -m "docs: add project CLAUDE.md with commands and architecture"
```

---

### Task 7: Add hook configuration viewer panel

New widget that reads and displays all configured hooks.

**Files:**
- Create: `src/superpowers_dashboard/widgets/hooks_panel.py`
- Modify: `src/superpowers_dashboard/app.py` (layout change + data)
- Test: `tests/test_widget_hooks.py` (new)

**Step 1: Write the failing test**

Create `tests/test_widget_hooks.py`:

```python
"""Tests for the hooks configuration viewer panel."""
from superpowers_dashboard.widgets.hooks_panel import HooksWidget, parse_hooks_config


def test_parse_hooks_config_from_dict():
    """Parse hooks from a settings.json-style dict."""
    config = {
        "UserPromptSubmit": [
            {"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/hooks/skill-check.sh"}]}
        ],
        "PreToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "~/.claude/hooks/warn.sh"}]}
        ],
    }
    hooks = parse_hooks_config(config, source="user config")
    assert len(hooks) == 2
    assert hooks[0]["event"] == "UserPromptSubmit"
    assert hooks[0]["source"] == "user config"
    assert "skill-check.sh" in hooks[0]["command"]
    assert hooks[1]["matcher"] == "Edit|Write"


def test_parse_hooks_config_empty():
    """Empty config returns empty list."""
    hooks = parse_hooks_config({}, source="test")
    assert hooks == []


def test_hooks_widget_format():
    """Widget should format hooks for display."""
    w = HooksWidget()
    hooks = [
        {"event": "SessionStart", "matcher": "", "command": "session-start.sh", "source": "superpowers"},
        {"event": "UserPromptSubmit", "matcher": "", "command": "skill-check.sh", "source": "user config"},
    ]
    w.update_hooks(hooks)
    content = str(w.renderable)
    assert "SessionStart" in content
    assert "UserPromptSubmit" in content
    assert "superpowers" in content


def test_hooks_widget_no_hooks():
    """Widget should handle no hooks gracefully."""
    w = HooksWidget()
    w.update_hooks([])
    content = str(w.renderable)
    assert "none" in content.lower() or "no hooks" in content.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'superpowers_dashboard.widgets.hooks_panel'`

**Step 3: Implement hooks panel**

Create `src/superpowers_dashboard/widgets/hooks_panel.py`:

```python
"""Hook configuration viewer widget."""
import json
from pathlib import Path
from textual.widgets import Static


def parse_hooks_config(hooks_dict: dict, source: str) -> list[dict]:
    """Parse hooks from a config dict into display-friendly format."""
    result = []
    for event_type, entries in hooks_dict.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            matcher = entry.get("matcher", "")
            for hook in entry.get("hooks", []):
                command = hook.get("command", "")
                # Extract just the script name
                script_name = Path(command).name if command else str(hook.get("type", ""))
                result.append({
                    "event": event_type,
                    "matcher": matcher,
                    "command": script_name,
                    "source": source,
                })
    return result


def load_all_hooks(
    settings_path: Path | None = None,
    plugin_dirs: list[Path] | None = None,
) -> list[dict]:
    """Load hooks from all sources: user settings and plugin hooks.json files."""
    all_hooks = []

    # User-level settings
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            config = json.loads(settings_path.read_text())
            hooks = config.get("hooks", {})
            all_hooks.extend(parse_hooks_config(hooks, source="user config"))
        except (json.JSONDecodeError, KeyError):
            pass

    # Plugin hooks
    if plugin_dirs:
        for plugin_dir in plugin_dirs:
            hooks_file = plugin_dir / "hooks" / "hooks.json"
            if hooks_file.exists():
                try:
                    config = json.loads(hooks_file.read_text())
                    hooks = config.get("hooks", {})
                    plugin_name = plugin_dir.parent.name  # e.g., "superpowers"
                    all_hooks.extend(parse_hooks_config(hooks, source=plugin_name))
                except (json.JSONDecodeError, KeyError):
                    pass

    return all_hooks


class HooksWidget(Static):
    """Displays configured hooks from all sources."""

    def update_hooks(self, hooks: list[dict]):
        if not hooks:
            self.update("  No hooks configured")
            return
        lines = []
        for h in hooks:
            matcher_str = f" [{h['matcher']}]" if h.get("matcher") else ""
            lines.append(f"  \u26a1 {h['event']}{matcher_str}")
            lines.append(f"    {h['source']} \u2192 {h['command']}")
        self.update("\n".join(lines))
```

**Step 4: Update app.py layout**

In `app.py`, change the CSS to support 3-row left column:

```css
    #top-row { height: 1fr; }
    #bottom-row { height: 1fr; }
    #left-top { width: 45; }
    #skills-panel { border: tall $border; }
    #hooks-panel { border: tall $border; }
    #workflow-panel { width: 1fr; border: tall $border; }
    #stats-panel { width: 45; border: tall $border; }
    #activity-panel { width: 1fr; border: tall $border; }
```

Update `compose()` to include hooks panel:

```python
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-row"):
            with Vertical(id="left-top"):
                with Vertical(id="skills-panel"):
                    yield Static("SKILLS", classes="panel-title")
                    yield SkillListWidget(id="skill-list")
                with Vertical(id="hooks-panel"):
                    yield Static("HOOKS", classes="panel-title")
                    yield HooksWidget(id="hooks")
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
```

In `on_mount`, load and display hooks:

```python
        # Load hook configuration
        plugin_dirs = []
        skills_dir = _find_skills_dir()
        if skills_dir:
            plugin_dirs.append(skills_dir.parent)  # plugin root
        hooks_widget = self.query_one("#hooks", HooksWidget)
        hooks_data = load_all_hooks(plugin_dirs=plugin_dirs)
        hooks_widget.update_hooks(hooks_data)
```

**Step 5: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/superpowers_dashboard/widgets/hooks_panel.py tests/test_widget_hooks.py src/superpowers_dashboard/app.py
git commit -m "feat: add hook configuration viewer panel"
```

---

### Task 8: Add subagent transcript parsing

Parse subagent JSONL files to extract skills, tools, tokens, and costs.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Test: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
import re
from superpowers_dashboard.watcher import SubagentDetail, parse_subagent_transcript


def test_parse_subagent_transcript(tmp_path):
    """Parse a subagent JSONL file and extract metrics."""
    subagent_file = tmp_path / "agent-abc123.jsonl"
    lines = [
        json.dumps({
            "type": "user", "agentId": "abc123", "sessionId": "sess1",
            "message": {"role": "user", "content": "Do research"},
            "timestamp": "2026-02-07T10:00:00.000Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-5-20250929",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/foo"}},
                    {"type": "tool_use", "id": "t2", "name": "Grep", "input": {"pattern": "bar"}},
                ],
                "usage": {"input_tokens": 5000, "output_tokens": 2000,
                          "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 0},
            },
            "timestamp": "2026-02-07T10:00:05.000Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-5-20250929",
                "content": [{"type": "text", "text": "Done"}],
                "usage": {"input_tokens": 8000, "output_tokens": 1000,
                          "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 0},
            },
            "timestamp": "2026-02-07T10:00:10.000Z",
        }),
    ]
    subagent_file.write_text("\n".join(lines))

    detail = parse_subagent_transcript(subagent_file)
    assert detail.agent_id == "abc123"
    assert detail.input_tokens == 13000  # 5000 + 8000
    assert detail.output_tokens == 3000  # 2000 + 1000
    assert detail.cache_read_tokens == 3000  # 1000 + 2000
    assert detail.tool_counts["Read"] == 1
    assert detail.tool_counts["Grep"] == 1
    assert len(detail.skills_invoked) == 0


def test_parse_subagent_with_skill(tmp_path):
    """Subagent that invokes a skill should track it."""
    subagent_file = tmp_path / "agent-def456.jsonl"
    lines = [
        json.dumps({
            "type": "user", "agentId": "def456",
            "message": {"role": "user", "content": "Implement feature"},
            "timestamp": "2026-02-07T10:00:00.000Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "content": [{"type": "tool_use", "id": "s1", "name": "Skill",
                             "input": {"skill": "superpowers:test-driven-development"}}],
                "usage": {"input_tokens": 100, "output_tokens": 50,
                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            },
            "timestamp": "2026-02-07T10:00:05.000Z",
        }),
    ]
    subagent_file.write_text("\n".join(lines))

    detail = parse_subagent_transcript(subagent_file)
    assert "test-driven-development" in detail.skills_invoked


def test_extract_agent_id_from_tool_result():
    """Extract agentId from Task tool_result text."""
    from superpowers_dashboard.watcher import extract_agent_id
    text = "agentId: a82030d (for resuming)\n<usage>total_tokens: 18488</usage>"
    assert extract_agent_id(text) == "a82030d"


def test_extract_agent_id_no_match():
    """Return None when no agentId found."""
    from superpowers_dashboard.watcher import extract_agent_id
    assert extract_agent_id("no agent id here") is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parse_subagent_transcript -v`
Expected: FAIL with `ImportError: cannot import name 'SubagentDetail'`

**Step 3: Implement SubagentDetail and parsing**

Add to `src/superpowers_dashboard/watcher.py`:

```python
@dataclass
class SubagentDetail:
    """Parsed metrics from a subagent's JSONL transcript."""
    agent_id: str
    skills_invoked: list[str] = field(default_factory=list)
    tool_counts: dict[str, int] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int = 0


def extract_agent_id(text: str) -> str | None:
    """Extract agentId from a Task tool_result text."""
    import re
    match = re.search(r"agentId:\s*([a-f0-9]+)", text)
    return match.group(1) if match else None


def parse_subagent_transcript(path: Path) -> SubagentDetail:
    """Parse a subagent JSONL file and extract metrics."""
    agent_id = path.stem.replace("agent-", "")
    detail = SubagentDetail(agent_id=agent_id)

    with open(path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "assistant":
                msg = entry.get("message", {})
                usage = msg.get("usage", {})
                detail.input_tokens += usage.get("input_tokens", 0)
                detail.output_tokens += usage.get("output_tokens", 0)
                detail.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                detail.cache_write_tokens += usage.get("cache_creation_input_tokens", 0)

                for item in msg.get("content", []):
                    if item.get("type") == "tool_use":
                        tool_name = item.get("name", "")
                        if tool_name:
                            detail.tool_counts[tool_name] = detail.tool_counts.get(tool_name, 0) + 1
                        if tool_name == "Skill":
                            skill_input = item.get("input", {})
                            skill_full = skill_input.get("skill", "")
                            skill_name = skill_full.split(":")[-1] if ":" in skill_full else skill_full
                            if skill_name and skill_name not in detail.skills_invoked:
                                detail.skills_invoked.append(skill_name)

            elif entry.get("type") == "system" and entry.get("subtype") == "turn_duration":
                detail.duration_ms += entry.get("durationMs", 0)

    return detail
```

Update `SubagentEvent` to hold optional detail:

```python
@dataclass
class SubagentEvent:
    """A subagent dispatch event."""
    timestamp: str
    description: str
    subagent_type: str
    model: str
    tool_use_id: str = ""
    detail: SubagentDetail | None = None
```

In `_process_assistant`, capture `tool_use_id` for Task dispatches:

```python
            if tool_name == "Task":
                task_input = item.get("input", {})
                self.subagents.append(SubagentEvent(
                    timestamp=entry.get("timestamp", ""),
                    description=task_input.get("description", ""),
                    subagent_type=task_input.get("subagent_type", ""),
                    model=task_input.get("model", "inherit"),
                    tool_use_id=item.get("id", ""),
                ))
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_watcher.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: add subagent transcript parsing with skill/tool/token extraction"
```

---

### Task 9: Wire subagent transcript parsing into app polling

Detect completed subagents, find their transcript files, parse them, and attach detail to SubagentEvent.

**Files:**
- Modify: `src/superpowers_dashboard/app.py`
- Modify: `src/superpowers_dashboard/watcher.py` (add helper for subagent file paths)
- Test: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_find_subagent_file(tmp_path):
    """Find a subagent JSONL file by session ID and agent ID."""
    from superpowers_dashboard.watcher import find_subagent_file
    session_id = "abc-123"
    agent_id = "def456"
    subagent_dir = tmp_path / "-Users-al-project" / session_id / "subagents"
    subagent_dir.mkdir(parents=True)
    expected = subagent_dir / f"agent-{agent_id}.jsonl"
    expected.write_text('{"type":"user"}\n')

    result = find_subagent_file(tmp_path / "-Users-al-project", session_id, agent_id)
    assert result == expected


def test_find_subagent_file_missing(tmp_path):
    """Return None when subagent file doesn't exist."""
    from superpowers_dashboard.watcher import find_subagent_file
    result = find_subagent_file(tmp_path, "sess1", "nope")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_find_subagent_file -v`
Expected: FAIL with `ImportError: cannot import name 'find_subagent_file'`

**Step 3: Implement**

Add to `src/superpowers_dashboard/watcher.py`:

```python
def find_subagent_file(project_dir: Path, session_id: str, agent_id: str) -> Path | None:
    """Find a subagent JSONL file by session ID and agent ID."""
    path = project_dir / session_id / "subagents" / f"agent-{agent_id}.jsonl"
    return path if path.exists() else None
```

In `app.py`, add a method to resolve subagent details and call it from `_poll_session` or `_refresh_ui`:

```python
    def _resolve_subagent_details(self):
        """Parse transcript files for completed subagents that lack detail."""
        if not self._session_path:
            return
        project_dir = self._session_path.parent
        session_id = self._session_path.stem

        for event in self.parser.subagents:
            if event.detail is not None:
                continue  # already parsed
            if not event.tool_use_id:
                continue
            # Try to find the agent ID from the matching tool_result
            # (extracted during JSONL processing - needs _pending_agent_ids)
            agent_id = self._agent_id_map.get(event.tool_use_id)
            if not agent_id:
                continue
            subagent_path = find_subagent_file(project_dir, session_id, agent_id)
            if subagent_path:
                event.detail = parse_subagent_transcript(subagent_path)
```

Also need to track agent IDs from tool_results. Add `_agent_id_map: dict[str, str]` to the app and populate it by processing tool_result entries in the watcher. Add to `SessionParser`:

```python
        self.agent_id_map: dict[str, str] = {}  # tool_use_id -> agent_id
```

In `_process_user`, detect tool_result entries and extract agent IDs:

```python
        # Extract agent IDs from Task tool_results
        message = entry.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    tool_use_id = item.get("tool_use_id", "")
                    result_text = ""
                    result_content = item.get("content", "")
                    if isinstance(result_content, str):
                        result_text = result_content
                    elif isinstance(result_content, list):
                        result_text = " ".join(
                            c.get("text", "") for c in result_content if isinstance(c, dict)
                        )
                    agent_id = extract_agent_id(result_text)
                    if agent_id and tool_use_id:
                        self.agent_id_map[tool_use_id] = agent_id
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py src/superpowers_dashboard/app.py tests/test_watcher.py
git commit -m "feat: wire subagent transcript parsing into polling loop"
```

---

### Task 10: Display subagent details in activity log and stats

Show parsed subagent information (tools, tokens, skills, cost) in the activity log and aggregate metrics in the stats panel.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/activity.py`
- Modify: `src/superpowers_dashboard/widgets/costs_panel.py`
- Modify: `src/superpowers_dashboard/app.py` (pass subagent data)
- Test: `tests/test_widget_activity.py`
- Test: `tests/test_widget_costs.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_activity.py`:

```python
from superpowers_dashboard.widgets.activity import format_subagent_detail_entry


def test_format_subagent_detail_entry():
    """Subagent detail should show tools, tokens, and status."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Research TUI",
        subagent_type="Explore",
        model="sonnet",
        tool_counts={"Read": 8, "Grep": 4},
        input_tokens=18500,
        output_tokens=4200,
        cost=0.42,
        skills_invoked=[],
        status="complete",
    )
    assert "Research TUI" in text
    assert "Read(8)" in text
    assert "Grep(4)" in text
    assert "$0.42" in text
    assert "complete" in text.lower() or "\u2713" in text


def test_format_subagent_detail_with_skills():
    """Subagent that used skills should show them."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Implement feature",
        subagent_type="general-purpose",
        model="opus",
        tool_counts={"Edit": 3},
        input_tokens=24000,
        output_tokens=8000,
        cost=1.20,
        skills_invoked=["test-driven-development"],
        status="complete",
    )
    assert "test-driven-development" in text
```

Add to `tests/test_widget_costs.py`:

```python
def test_stats_widget_shows_subagent_aggregate():
    """Stats should show aggregate subagent metrics."""
    w = StatsWidget()
    text = w.format_subagent_stats(
        count=8, skills_used=2, total_cost=3.42, total_tokens=142000
    )
    assert "8" in text
    assert "2/8" in text or "2" in text
    assert "$3.42" in text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_activity.py::test_format_subagent_detail_entry -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

Add to `src/superpowers_dashboard/widgets/activity.py`:

```python
def format_subagent_detail_entry(
    timestamp: str, description: str, subagent_type: str, model: str,
    tool_counts: dict[str, int], input_tokens: int, output_tokens: int,
    cost: float, skills_invoked: list[str], status: str,
) -> str:
    time_str = _parse_time(timestamp)
    model_str = f"/{model}" if model and model != "inherit" else ""
    status_icon = "\u2713" if status == "complete" else "\u25d0"

    lines = [f"  {time_str}  \u25b6 Subagent: {description} [{subagent_type}{model_str}]"]

    if skills_invoked:
        lines.append(f"           \u251c Skills: {', '.join(skills_invoked)}")

    if tool_counts:
        top_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:5]
        tool_str = " ".join(f"{name}({count})" for name, count in top_tools)
        lines.append(f"           \u251c Tools: {tool_str}")

    tok_in = f"{input_tokens/1000:.1f}k" if input_tokens >= 1000 else str(input_tokens)
    tok_out = f"{output_tokens/1000:.1f}k" if output_tokens >= 1000 else str(output_tokens)
    lines.append(f"           \u2514 Tokens: {tok_in} in / {tok_out} out  ${cost:.2f}  {status_icon} {status}")

    return "\n".join(lines)
```

Add to `ActivityLogWidget`:

```python
    def add_subagent_detail(self, timestamp: str, description: str, subagent_type: str,
                            model: str, tool_counts: dict, input_tokens: int,
                            output_tokens: int, cost: float, skills_invoked: list,
                            status: str):
        text = format_subagent_detail_entry(
            timestamp, description, subagent_type, model, tool_counts,
            input_tokens, output_tokens, cost, skills_invoked, status,
        )
        self.write(text)
```

Add to `src/superpowers_dashboard/widgets/costs_panel.py`:

```python
    def format_subagent_stats(self, count: int, skills_used: int, total_cost: float, total_tokens: int) -> str:
        tok_str = f"{total_tokens/1000:.0f}k" if total_tokens >= 1000 else str(total_tokens)
        lines = [
            f"  Subagents:       {count}",
            f"    Skills used:   {skills_used}/{count}",
            f"    Total cost:    ${total_cost:.2f}",
            f"    Total tokens:  {tok_str}",
        ]
        return "\n".join(lines)
```

Update `update_stats` to use `format_subagent_stats` instead of the simple count.

Update `_refresh_ui` in `app.py` to pass subagent detail data when rendering activity events.

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/activity.py src/superpowers_dashboard/widgets/costs_panel.py src/superpowers_dashboard/app.py tests/test_widget_activity.py tests/test_widget_costs.py
git commit -m "feat: show subagent details in activity log and aggregate stats"
```

---

### Task 11: Show subagent dispatches in workflow panel

Display subagent dispatches inline in the workflow timeline, with nested skill info if available.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/workflow.py`
- Modify: `src/superpowers_dashboard/app.py` (build mixed timeline)
- Test: `tests/test_widget_workflow.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_workflow.py`:

```python
def test_workflow_format_subagent():
    """Subagent dispatches should render with nested skill info."""
    w = WorkflowWidget()
    text = w.format_subagent_entry(
        description="Research TUI",
        total_tokens=18500,
        cost=0.42,
        skills_invoked=[],
    )
    assert "Research TUI" in text
    assert "18.5k" in text
    assert "no skills" in text.lower()


def test_workflow_format_subagent_with_skills():
    """Subagent with skills should show them nested."""
    w = WorkflowWidget()
    text = w.format_subagent_entry(
        description="Implement feature",
        total_tokens=24000,
        cost=1.20,
        skills_invoked=["test-driven-development"],
    )
    assert "Implement feature" in text
    assert "test-driven-development" in text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_workflow.py::test_workflow_format_subagent -v`
Expected: FAIL with `AttributeError`

**Step 3: Implement**

Add to `WorkflowWidget`:

```python
    def format_subagent_entry(self, description: str, total_tokens: int, cost: float, skills_invoked: list[str]) -> str:
        tok_str = format_tokens(total_tokens)
        desc = description[:24]
        result = f"\u25b6 {desc:<24} {tok_str:>6} tok  ${cost:.2f}\n"
        if skills_invoked:
            result += f"  \u2514 {', '.join(skills_invoked)}"
        else:
            result += f"  \u2514 (no skills)"
        return result
```

Update `update_timeline` to handle subagent entries (kind == "subagent"):

```python
            elif e.get("kind") == "subagent":
                text = self.format_subagent_entry(
                    description=e.get("description", ""),
                    total_tokens=e.get("total_tokens", 0),
                    cost=e.get("cost", 0),
                    skills_invoked=e.get("skills_invoked", []),
                )
                parts.append(text)
```

Update `_refresh_ui` in `app.py` to build the mixed timeline with skill events, overhead segments, and subagent dispatches all interleaved by timestamp.

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py src/superpowers_dashboard/app.py tests/test_widget_workflow.py
git commit -m "feat: show subagent dispatches in workflow timeline"
```

---

### Task 12: Add hook activity detection

Parse JSONL entries for evidence of hooks firing and surface them in the activity log.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Modify: `src/superpowers_dashboard/widgets/activity.py`
- Modify: `src/superpowers_dashboard/app.py`
- Test: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_detects_hook_events():
    """Parser should detect hook-related entries in JSONL."""
    parser = SessionParser()
    # Hook progress entries appear during hook execution
    parser.process_line(json.dumps({
        "type": "progress",
        "data": {"type": "hook_progress", "hookEventName": "UserPromptSubmit", "hookType": "command"},
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))
    assert len(parser.hook_events) == 1
    assert parser.hook_events[0]["event"] == "UserPromptSubmit"


def test_parser_detects_pretooluse_hook():
    """Parser should detect PreToolUse hook events."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "progress",
        "data": {"type": "hook_progress", "hookEventName": "PreToolUse", "hookType": "command"},
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))
    assert len(parser.hook_events) == 1
    assert parser.hook_events[0]["event"] == "PreToolUse"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_parser_detects_hook_events -v`
Expected: FAIL with `AttributeError: 'SessionParser' has no attribute 'hook_events'`

**Step 3: Implement**

Add to `SessionParser.__init__`:
```python
        self.hook_events: list[dict] = []
```

In `process_line`, add handling for progress entries:
```python
        elif entry_type == "progress":
            self._process_progress(entry)
```

Add method:
```python
    def _process_progress(self, entry: dict):
        data = entry.get("data", {})
        if data.get("type") == "hook_progress":
            self.hook_events.append({
                "event": data.get("hookEventName", ""),
                "hook_type": data.get("hookType", ""),
                "timestamp": entry.get("timestamp", ""),
            })
```

Add to `activity.py`:

```python
def format_hook_entry(timestamp: str, event: str) -> str:
    time_str = _parse_time(timestamp)
    return f"  {time_str}  \u26a1 Hook: {event}"
```

Add to `ActivityLogWidget`:
```python
    def add_hook_event(self, timestamp: str, event: str):
        text = format_hook_entry(timestamp, event)
        self.write(text)
```

Update `_refresh_ui` in `app.py` to include hook events in the chronological activity feed.

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py src/superpowers_dashboard/widgets/activity.py src/superpowers_dashboard/app.py tests/test_watcher.py
git commit -m "feat: detect and display hook activity in activity log"
```

---

### Task 13: Final integration test and cleanup

Run the full test suite, verify the dashboard launches, and clean up any issues.

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 2: Launch dashboard to verify visually**

Run: `uv run python -m superpowers_dashboard`
Expected: Dashboard launches with the new 3-row left layout (Skills, Hooks, Stats), overhead gaps in workflow, and subagent details in activity log.

**Step 3: Verify hooks are working**

Start a new Claude session and check that:
- UserPromptSubmit hook fires on every message
- PreToolUse hook fires before Edit/Write/Bash
- The dashboard shows hook activity in the activity log

**Step 4: Commit any remaining fixes**

```bash
git add -A
git commit -m "chore: integration fixes and cleanup"
```
