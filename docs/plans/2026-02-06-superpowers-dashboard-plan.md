# Superpowers Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Textual TUI dashboard that observes Claude Code session JSONL files in real-time and displays superpowers skill status, workflow history, and cost data.

**Architecture:** A Python Textual app with four panels (Skills, Workflow, Costs, Activity Log). A JSONL watcher tails session files and emits events. A skill registry reads SKILL.md frontmatter. Two themes (Terminal, Mainframe) toggled with `t`.

**Tech Stack:** Python 3.11+, Textual, tomllib, PyYAML (for SKILL.md frontmatter), asyncio

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/superpowers_dashboard/__init__.py`
- Create: `src/superpowers_dashboard/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "superpowers-dashboard"
version = "0.1.0"
description = "Terminal dashboard for Claude Code Superpowers skills"
requires-python = ">=3.11"
dependencies = [
    "textual>=3.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
superpowers-dashboard = "superpowers_dashboard.__main__:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 2: Create __init__.py**

```python
"""Superpowers Dashboard — Terminal HUD for Claude Code skills."""
```

**Step 3: Create __main__.py**

```python
"""Entry point for superpowers-dashboard."""
from superpowers_dashboard.app import SuperpowersDashboard


def main():
    app = SuperpowersDashboard()
    app.run()


if __name__ == "__main__":
    main()
```

**Step 4: Create tests/__init__.py and tests/conftest.py**

```python
# tests/__init__.py
```

```python
# tests/conftest.py
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
```

**Step 5: Install in dev mode and verify**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv init --no-readme && rm hello.py && uv add textual pyyaml && uv add --dev pytest pytest-asyncio`
Expected: Clean install, no errors.

Note: We'll manually adjust pyproject.toml after `uv init` sets up the structure.

**Step 6: Commit**

```bash
git add pyproject.toml src/ tests/ uv.lock .python-version
git commit -m "feat: project scaffolding with Textual and pytest"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/superpowers_dashboard/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
from superpowers_dashboard.config import load_config, DEFAULT_PRICING


def test_default_pricing_has_opus():
    assert "claude-opus-4-6" in DEFAULT_PRICING
    pricing = DEFAULT_PRICING["claude-opus-4-6"]
    assert pricing["input"] == 5.0
    assert pricing["output"] == 25.0
    assert pricing["cache_read"] == 0.5
    assert pricing["cache_write"] == 6.25


def test_load_config_returns_defaults_when_no_file(tmp_path):
    config = load_config(config_path=tmp_path / "nonexistent.toml")
    assert config["pricing"] == DEFAULT_PRICING


def test_load_config_reads_toml_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[pricing."claude-opus-4-6"]
input = 10.0
output = 50.0
cache_read = 1.0
cache_write = 12.5
''')
    config = load_config(config_path=config_file)
    assert config["pricing"]["claude-opus-4-6"]["input"] == 10.0


def test_load_config_merges_with_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[pricing."claude-opus-4-6"]
input = 10.0
output = 50.0
cache_read = 1.0
cache_write = 12.5
''')
    config = load_config(config_path=config_file)
    # Custom opus pricing applied
    assert config["pricing"]["claude-opus-4-6"]["input"] == 10.0
    # Default sonnet pricing still present
    assert "claude-sonnet-4-5-20250929" in config["pricing"]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/config.py
"""Configuration loading for superpowers-dashboard."""
import tomllib
from pathlib import Path

DEFAULT_PRICING = {
    "claude-opus-4-6": {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.5,
        "cache_write": 6.25,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
}

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "superpowers-dashboard" / "config.toml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load config from TOML file, falling back to defaults."""
    config = {"pricing": dict(DEFAULT_PRICING)}

    if config_path.exists():
        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)
        if "pricing" in user_config:
            config["pricing"].update(user_config["pricing"])

    return config
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_config.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/config.py tests/test_config.py
git commit -m "feat: config module with configurable pricing defaults"
```

---

### Task 3: Skill Registry

**Files:**
- Create: `src/superpowers_dashboard/registry.py`
- Create: `tests/test_registry.py`
- Create: `tests/fixtures/skills/brainstorming/SKILL.md`
- Create: `tests/fixtures/skills/writing-plans/SKILL.md`

**Step 1: Create test fixtures**

```markdown
<!-- tests/fixtures/skills/brainstorming/SKILL.md -->
---
name: brainstorming
description: "Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

Content here...
```

```markdown
<!-- tests/fixtures/skills/writing-plans/SKILL.md -->
---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task
---

# Writing Plans

Content here...
```

**Step 2: Write the failing test**

```python
# tests/test_registry.py
from pathlib import Path
from superpowers_dashboard.registry import SkillRegistry


def test_load_skills_from_directory(fixtures_dir):
    registry = SkillRegistry(fixtures_dir / "skills")
    skills = registry.skills
    assert len(skills) == 2
    assert "brainstorming" in skills
    assert "writing-plans" in skills


def test_skill_has_name_and_description(fixtures_dir):
    registry = SkillRegistry(fixtures_dir / "skills")
    skill = registry.skills["brainstorming"]
    assert skill["name"] == "brainstorming"
    assert "intent" in skill["description"].lower() or "design" in skill["description"].lower()


def test_empty_directory(tmp_path):
    registry = SkillRegistry(tmp_path)
    assert registry.skills == {}


def test_nonexistent_directory(tmp_path):
    registry = SkillRegistry(tmp_path / "nope")
    assert registry.skills == {}
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_registry.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Write minimal implementation**

```python
# src/superpowers_dashboard/registry.py
"""Skill registry — reads SKILL.md frontmatter from superpowers plugin directory."""
import yaml
from pathlib import Path


class SkillRegistry:
    """Loads skill metadata from SKILL.md files."""

    def __init__(self, skills_dir: Path):
        self.skills: dict[str, dict] = {}
        self._load(skills_dir)

    def _load(self, skills_dir: Path):
        if not skills_dir.exists():
            return
        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            meta = self._parse_frontmatter(skill_file)
            if meta and "name" in meta:
                self.skills[meta["name"]] = meta

    def _parse_frontmatter(self, path: Path) -> dict | None:
        text = path.read_text()
        if not text.startswith("---"):
            return None
        end = text.index("---", 3)
        frontmatter = text[3:end].strip()
        return yaml.safe_load(frontmatter)
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_registry.py -v`
Expected: 4 passed

**Step 6: Commit**

```bash
git add src/superpowers_dashboard/registry.py tests/test_registry.py tests/fixtures/
git commit -m "feat: skill registry reads SKILL.md frontmatter"
```

---

### Task 4: JSONL Watcher and Parser

**Files:**
- Create: `src/superpowers_dashboard/watcher.py`
- Create: `tests/test_watcher.py`
- Create: `tests/fixtures/session.jsonl`

**Step 1: Create test fixture**

Create `tests/fixtures/session.jsonl` with realistic entries extracted from actual session data. Include:
- A `progress` entry (hook event)
- A `user` entry (user message)
- An `assistant` entry with text content and usage
- An `assistant` entry with `tool_use` for `Skill` invocation
- A `user` entry with `tool_result` for skill launch
- A `user` entry with `isMeta: true` for skill activation
- A second skill invocation to test state transitions

The fixture should use the exact JSONL structure observed in real sessions. Key fields per entry type:

For assistant messages:
```json
{"type": "assistant", "message": {"model": "claude-opus-4-6", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "superpowers:brainstorming", "args": "test"}}], "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 300}}, "timestamp": "2026-02-06T22:16:50.558Z"}
```

For isMeta activation:
```json
{"type": "user", "isMeta": true, "message": {"role": "user", "content": [{"type": "text", "text": "...skill content..."}]}, "timestamp": "2026-02-06T22:16:50.572Z", "sourceToolUseID": "toolu_abc123"}
```

**Step 2: Write the failing test**

```python
# tests/test_watcher.py
import json
from pathlib import Path
from superpowers_dashboard.watcher import SessionParser, SkillEvent


def _make_skill_invocation(skill_name: str, args: str = "", timestamp: str = "2026-02-06T22:16:50.558Z", tool_use_id: str = "toolu_abc") -> list[str]:
    """Generate the 3-line JSONL sequence for a skill invocation."""
    lines = []
    # Step 1: assistant tool_use
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": tool_use_id, "name": "Skill", "input": {"skill": f"superpowers:{skill_name}", "args": args}}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0},
        },
        "timestamp": timestamp,
    }))
    # Step 2: tool_result
    lines.append(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": f"Launching skill: superpowers:{skill_name}"}]},
        "toolUseResult": {"success": True, "commandName": f"superpowers:{skill_name}"},
        "timestamp": timestamp,
    }))
    # Step 3: isMeta
    lines.append(json.dumps({
        "type": "user",
        "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": f"# {skill_name}\n\nSkill content..."}]},
        "timestamp": timestamp,
        "sourceToolUseID": tool_use_id,
    }))
    return lines


def test_parser_detects_skill_invocation():
    parser = SessionParser()
    lines = _make_skill_invocation("brainstorming", args="test idea")
    for line in lines:
        parser.process_line(line)
    assert len(parser.skill_events) == 1
    event = parser.skill_events[0]
    assert event.skill_name == "brainstorming"
    assert event.args == "test idea"


def test_parser_tracks_active_skill():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", timestamp="2026-02-06T22:00:00.000Z"):
        parser.process_line(line)
    assert parser.active_skill == "brainstorming"


def test_parser_transitions_active_to_used():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", timestamp="2026-02-06T22:00:00.000Z", tool_use_id="t1"):
        parser.process_line(line)
    for line in _make_skill_invocation("writing-plans", timestamp="2026-02-06T22:30:00.000Z", tool_use_id="t2"):
        parser.process_line(line)
    assert parser.active_skill == "writing-plans"
    assert "brainstorming" in parser.used_skills


def test_parser_accumulates_tokens():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # Add an assistant message with tokens (attributed to brainstorming)
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 500, "output_tokens": 200, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    event = parser.skill_events[0]
    # 100 from invocation + 500 from response
    assert event.input_tokens == 600
    assert event.output_tokens == 250


def test_parser_handles_non_skill_lines():
    parser = SessionParser()
    parser.process_line(json.dumps({"type": "progress", "data": {"type": "hook_progress"}, "timestamp": "2026-02-06T22:00:00.000Z"}))
    assert len(parser.skill_events) == 0
    assert parser.active_skill is None
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_watcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Write minimal implementation**

```python
# src/superpowers_dashboard/watcher.py
"""JSONL session watcher and parser for skill invocation detection."""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SkillEvent:
    """A single skill invocation with accumulated metrics."""
    skill_name: str
    args: str
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    models: set = field(default_factory=set)

    @property
    def start_time(self) -> datetime:
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


class SessionParser:
    """Parses JSONL lines and tracks skill state."""

    def __init__(self):
        self.skill_events: list[SkillEvent] = []
        self.active_skill: str | None = None
        self.used_skills: set[str] = set()
        self.overhead_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        self._pending_skill: dict | None = None  # skill tool_use waiting for isMeta

    def process_line(self, line: str):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return

        entry_type = entry.get("type")

        if entry_type == "assistant":
            self._process_assistant(entry)
        elif entry_type == "user":
            self._process_user(entry)

    def _process_assistant(self, entry: dict):
        message = entry.get("message", {})
        content = message.get("content", [])
        usage = message.get("usage", {})
        model = message.get("model", "")

        # Check for Skill tool_use
        for item in content:
            if item.get("type") == "tool_use" and item.get("name") == "Skill":
                skill_input = item.get("input", {})
                skill_full = skill_input.get("skill", "")
                # Strip "superpowers:" prefix
                skill_name = skill_full.split(":")[-1] if ":" in skill_full else skill_full
                self._pending_skill = {
                    "skill_name": skill_name,
                    "args": skill_input.get("args", ""),
                    "timestamp": entry.get("timestamp", ""),
                    "tool_use_id": item.get("id", ""),
                }

        # Accumulate tokens to current active skill
        self._accumulate_tokens(usage, model)

    def _process_user(self, entry: dict):
        if entry.get("isMeta") and self._pending_skill:
            # Skill is now active
            if self.active_skill:
                self.used_skills.add(self.active_skill)
            skill = self._pending_skill
            event = SkillEvent(
                skill_name=skill["skill_name"],
                args=skill["args"],
                timestamp=skill["timestamp"],
            )
            self.skill_events.append(event)
            self.active_skill = skill["skill_name"]
            self._pending_skill = None

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


def find_latest_session(base_dir: Path | None = None) -> Path | None:
    """Find the most recently modified session JSONL file."""
    if base_dir is None:
        base_dir = Path.home() / ".claude" / "projects"
    if not base_dir.exists():
        return None
    sessions = list(base_dir.glob("*/*.jsonl"))
    # Exclude subagent files
    sessions = [s for s in sessions if "subagents" not in s.parts]
    if not sessions:
        return None
    return max(sessions, key=lambda p: p.stat().st_mtime)
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_watcher.py -v`
Expected: 6 passed

**Step 6: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: JSONL parser with skill state detection and token tracking"
```

---

### Task 5: Cost Calculator

**Files:**
- Create: `src/superpowers_dashboard/costs.py`
- Create: `tests/test_costs.py`

**Step 1: Write the failing test**

```python
# tests/test_costs.py
from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.config import DEFAULT_PRICING


def test_calculate_cost_opus():
    cost = calculate_cost(
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 30.0  # $5 input + $25 output


def test_calculate_cost_with_cache():
    cost = calculate_cost(
        model="claude-opus-4-6",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 6.75  # $0.50 read + $6.25 write


def test_calculate_cost_unknown_model():
    cost = calculate_cost(
        model="unknown-model",
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        pricing=DEFAULT_PRICING,
    )
    assert cost == 0.0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_costs.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/costs.py
"""Cost calculation from token counts and pricing config."""


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    pricing: dict,
) -> float:
    """Calculate dollar cost for token usage."""
    if model not in pricing:
        return 0.0

    rates = pricing[model]
    cost = (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
        + (cache_read_tokens / 1_000_000) * rates["cache_read"]
        + (cache_write_tokens / 1_000_000) * rates["cache_write"]
    )
    return round(cost, 6)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_costs.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/costs.py tests/test_costs.py
git commit -m "feat: cost calculator with configurable per-model pricing"
```

---

### Task 6: Skill List Widget

**Files:**
- Create: `src/superpowers_dashboard/widgets/__init__.py`
- Create: `src/superpowers_dashboard/widgets/skill_list.py`
- Create: `tests/test_widget_skill_list.py`

**Step 1: Write the failing test**

```python
# tests/test_widget_skill_list.py
from superpowers_dashboard.widgets.skill_list import SkillListWidget


def test_skill_list_format_available():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "available")
    assert "brainstorming" in line
    assert "\u25cb" in line  # ○


def test_skill_list_format_active():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "active")
    assert "\u25c6" in line  # ◆


def test_skill_list_format_used():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "used")
    assert "\u25cf" in line  # ●
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_skill_list.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/widgets/__init__.py
```

```python
# src/superpowers_dashboard/widgets/skill_list.py
"""Skill list widget showing all skills with status indicators."""
from textual.widgets import Static
from textual.reactive import reactive


STATE_ICONS = {
    "active": "\u25c6",   # ◆
    "used": "\u25cf",      # ●
    "available": "\u25cb", # ○
}


class SkillListWidget(Static):
    """Displays all skills with active/used/available status."""

    skills_data: reactive[dict] = reactive(dict)

    def format_skill(self, name: str, state: str) -> str:
        icon = STATE_ICONS.get(state, "\u25cb")
        return f"  {icon} {name}"

    def update_skills(self, all_skills: list[str], active: str | None, used: set[str]):
        lines = []
        for name in all_skills:
            if name == active:
                state = "active"
            elif name in used:
                state = "used"
            else:
                state = "available"
            lines.append(self.format_skill(name, state))
        self.skills_data = {"lines": lines, "active": active, "used": used}
        self.update("\n".join(lines))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_skill_list.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/ tests/test_widget_skill_list.py
git commit -m "feat: skill list widget with active/used/available indicators"
```

---

### Task 7: Workflow Timeline Widget

**Files:**
- Create: `src/superpowers_dashboard/widgets/workflow.py`
- Create: `tests/test_widget_workflow.py`

**Step 1: Write the failing test**

```python
# tests/test_widget_workflow.py
from superpowers_dashboard.widgets.workflow import WorkflowWidget, format_tokens, format_duration_minutes


def test_format_tokens_small():
    assert format_tokens(500) == "500"


def test_format_tokens_thousands():
    assert format_tokens(12847) == "12.8k"


def test_format_tokens_millions():
    assert format_tokens(1_200_000) == "1.2M"


def test_format_duration_minutes():
    assert format_duration_minutes(1740) == "29m"  # 29 minutes


def test_format_duration_seconds():
    assert format_duration_minutes(45) == "<1m"


def test_format_duration_hours():
    assert format_duration_minutes(7200) == "2h 0m"


def test_workflow_format_entry():
    w = WorkflowWidget()
    text = w.format_entry(
        index=1,
        skill_name="brainstorming",
        args="Terminal UI for superpowers",
        total_tokens=12847,
        cost=0.31,
        duration_seconds=1740,
        max_cost=1.02,
        is_active=False,
    )
    assert "brainstorming" in text
    assert "12.8k" in text
    assert "$0.31" in text
    assert "29m" in text
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_workflow.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/widgets/workflow.py
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

    def format_entry(
        self,
        index: int,
        skill_name: str,
        args: str,
        total_tokens: int,
        cost: float,
        duration_seconds: float,
        max_cost: float,
        is_active: bool,
    ) -> str:
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        bar = _cost_bar(cost, max_cost)
        active_marker = " \u25cf" if is_active else ""
        args_display = f'"{args[:30]}..."' if len(args) > 30 else f'"{args}"' if args else ""

        lines = [
            f"\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469"[index - 1] if index <= 10 else f"({index})",
        ]
        # Build as single formatted block
        num = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469"
        idx_char = num[index - 1] if 1 <= index <= 10 else f"({index})"
        result = f"{idx_char} {skill_name:<24} {tok_str:>6} tok  ${cost:.2f}\n"
        if args_display:
            result += f"   \u2503  {args_display}\n"
        result += f"   \u2503  {bar}  {dur_str}{active_marker}"
        return result

    def update_timeline(self, entries: list[dict]):
        if not entries:
            self.update("  No skills invoked yet.")
            return
        max_cost = max(e.get("cost", 0) for e in entries)
        parts = []
        for i, e in enumerate(entries):
            text = self.format_entry(
                index=i + 1,
                skill_name=e["skill_name"],
                args=e.get("args", ""),
                total_tokens=e.get("total_tokens", 0),
                cost=e.get("cost", 0),
                duration_seconds=e.get("duration_seconds", 0),
                max_cost=max_cost,
                is_active=e.get("is_active", False),
            )
            parts.append(text)
        separator = "\n   \u25bc\n"
        self.update(separator.join(parts))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_workflow.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py tests/test_widget_workflow.py
git commit -m "feat: workflow timeline widget with tokens, cost, and duration"
```

---

### Task 8: Costs Widget

**Files:**
- Create: `src/superpowers_dashboard/widgets/costs_panel.py`
- Create: `tests/test_widget_costs.py`

**Step 1: Write the failing test**

```python
# tests/test_widget_costs.py
from superpowers_dashboard.widgets.costs_panel import CostsWidget, format_cache_ratio


def test_format_cache_ratio():
    assert format_cache_ratio(680, 1000) == "68%"


def test_format_cache_ratio_zero():
    assert format_cache_ratio(0, 0) == "0%"


def test_costs_widget_format_summary():
    w = CostsWidget()
    text = w.format_summary(
        total_cost=0.42,
        input_tokens=12847,
        output_tokens=3291,
        cache_read_tokens=8700,
    )
    assert "$0.42" in text
    assert "12,847" in text
    assert "3,291" in text
    assert "68%" in text
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_costs.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/widgets/costs_panel.py
"""Costs panel widget showing session totals and per-skill breakdown."""
from textual.widgets import Static


def format_cache_ratio(cache_read: int, total_input: int) -> str:
    if total_input == 0:
        return "0%"
    return f"{int(cache_read / total_input * 100)}%"


class CostsWidget(Static):
    """Displays session cost totals and per-skill breakdown."""

    def format_summary(
        self,
        total_cost: float,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
    ) -> str:
        total_input = input_tokens + cache_read_tokens
        ratio = format_cache_ratio(cache_read_tokens, total_input)
        return (
            f"  This session:  ${total_cost:.2f}\n"
            f"  Tokens in:     {input_tokens:,}\n"
            f"    ({ratio} cached)\n"
            f"  Tokens out:    {output_tokens:,}"
        )

    def update_costs(self, summary: str, per_skill: list[dict]):
        parts = [summary, "  \u2500" * 20]
        if per_skill:
            parts.append("  Per skill:")
            max_cost = max(s["cost"] for s in per_skill) if per_skill else 1
            for s in per_skill:
                filled = int((s["cost"] / max_cost) * 10) if max_cost > 0 else 0
                bar = "\u2588" * filled + "\u2591" * (10 - filled)
                parts.append(f"  {s['name']:<18} ${s['cost']:.2f}  {bar}")
        self.update("\n".join(parts))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_costs.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/costs_panel.py tests/test_widget_costs.py
git commit -m "feat: costs panel widget with session totals and cache ratio"
```

---

### Task 9: Activity Log Widget

**Files:**
- Create: `src/superpowers_dashboard/widgets/activity.py`
- Create: `tests/test_widget_activity.py`

**Step 1: Write the failing test**

```python
# tests/test_widget_activity.py
from superpowers_dashboard.widgets.activity import ActivityLogWidget, format_log_entry


def test_format_log_entry():
    text = format_log_entry(
        timestamp="2026-02-06T22:16:50.558Z",
        skill_name="brainstorming",
        args="Terminal UI for superpowers",
    )
    assert "22:16:03" in text or "22:16" in text
    assert "brainstorming" in text


def test_format_log_entry_truncates_args():
    text = format_log_entry(
        timestamp="2026-02-06T22:16:50.558Z",
        skill_name="brainstorming",
        args="A" * 100,
    )
    assert "..." in text
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_activity.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/widgets/activity.py
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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/test_widget_activity.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/activity.py tests/test_widget_activity.py
git commit -m "feat: activity log widget with timestamp and args display"
```

---

### Task 10: Main App — Layout, Themes, and Keybindings

**Files:**
- Create: `src/superpowers_dashboard/app.py`

**Step 1: Write the app**

```python
# src/superpowers_dashboard/app.py
"""Main Textual application — layout, themes, file watching."""
import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.theme import Theme
from textual.widgets import Header, Footer, Static

from superpowers_dashboard.config import load_config, DEFAULT_PRICING
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
                from datetime import datetime, timezone
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
        total_cost = sum(e.get("cost", 0) for e in entries)

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
```

**Step 2: Run a quick smoke test**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run python -c "from superpowers_dashboard.app import SuperpowersDashboard; print('Import OK')"`
Expected: "Import OK"

**Step 3: Commit**

```bash
git add src/superpowers_dashboard/app.py src/superpowers_dashboard/__main__.py
git commit -m "feat: main app with four-panel layout, themes, and session polling"
```

---

### Task 11: Integration Test — Run Against Live Data

**Step 1: Run the dashboard**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run superpowers-dashboard`

Expected: Dashboard launches showing:
- Left panel: all 14 skills with brainstorming and writing-plans marked as used/active
- Right panel: workflow timeline showing the skill invocations from this session
- Bottom left: cost totals
- Bottom right: activity log with timestamps

**Step 2: Test theme toggle**

Press `t` — should switch between black/white Terminal and green Mainframe themes.

**Step 3: Test live updates**

In the Claude Code session (other terminal), invoke a new skill. The dashboard should update within 500ms.

**Step 4: Run full test suite**

Run: `cd /Users/al/Documents/gitstuff/superpowers-tui && uv run pytest tests/ -v`
Expected: All tests pass

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: superpowers dashboard v0.1.0 — complete four-panel TUI"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Project scaffolding | - |
| 2 | Config module | 4 |
| 3 | Skill registry | 4 |
| 4 | JSONL watcher/parser | 6 |
| 5 | Cost calculator | 3 |
| 6 | Skill list widget | 3 |
| 7 | Workflow timeline widget | 7 |
| 8 | Costs panel widget | 3 |
| 9 | Activity log widget | 2 |
| 10 | Main app (layout, themes, polling) | 1 smoke |
| 11 | Integration test with live data | manual |

**Total: ~11 tasks, ~33 automated tests, ~10 files, ~650 lines of code**
