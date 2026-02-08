# Skill Enforcement & Dashboard Augmentation Design

## Problem

Claude Code with the superpowers plugin does not reliably invoke skills proactively. The current enforcement mechanism (a SessionStart hook injecting the `using-superpowers` skill) fires once and fades. Skills are skipped entirely unless the user explicitly requests them. Subagents receive no enforcement context at all. The dashboard doesn't surface these gaps, painting an incomplete picture of what's happening.

## Goals

1. Make skill invocation reliable through layered enforcement (hooks + CLAUDE.md)
2. Fix existing bugs: new session detection, overhead cost calculation, overhead workflow gaps
3. Expand the dashboard to show hooks, subagent internals, session boundaries, and skill compliance
4. Make the dashboard an educational tool that reveals how the Claude Code machinery works

## Non-Goals

- OTEL integration
- Educational tooltips/help panel
- Contributing changes upstream to superpowers (may do later)

---

## Part 1: Enforcement

### 1A. UserPromptSubmit Hook

**Location:** `~/.claude/settings.json` + `~/.claude/hooks/skill-check.sh`

On every user message, inject a reminder into the conversation context.

**settings.json addition:**
```json
{
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
    ]
  }
}
```

**skill-check.sh:**
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

### 1B. PreToolUse Warning Hook

**Location:** Same settings.json + `~/.claude/hooks/warn-no-skill.sh`

On Edit, Write, or Bash tool calls, inject a warning nudge (not a block).

**settings.json addition (merged into same hooks object):**
```json
{
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
  ]
}
```

**warn-no-skill.sh:**
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

### 1C. SubagentStart Hook

**Location:** Same settings.json + `~/.claude/hooks/subagent-skill-check.sh`

Inject skill discipline context into subagents, since they don't receive SessionStart hook output.

**settings.json addition:**
```json
{
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
```

**subagent-skill-check.sh:**
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

### 1D. CLAUDE.md Files

**`~/.claude/CLAUDE.md` (global, ~10 lines):**
```markdown
# Workflow
- Before any action, check if a superpowers skill applies. If even 1% chance, invoke it.
- Subagents: check available skills before starting work.
- Use test-driven-development for any code changes.
- Use systematic-debugging for any bug investigation.
- Use brainstorming before any creative/design work.
```

**`./CLAUDE.md` (superpowers-tui project, ~35 lines):**
```markdown
# superpowers-tui

Terminal dashboard for monitoring Claude Code superpowers skill usage.

## Commands
- `uv run python -m superpowers_dashboard` — run the dashboard
- `uv run pytest` — run tests
- `uv run pytest tests/test_watcher.py -x` — run a specific test file

## Architecture
- `src/superpowers_dashboard/` — all source code
- `watcher.py` — JSONL parser and session discovery (the data layer)
- `app.py` — Textual app, layout, polling loop, UI refresh
- `widgets/` — individual panel widgets (skill_list, workflow, costs_panel, activity)
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

---

## Part 2: Bug Fixes

### 2A. New Session Detection

**File:** `app.py`

The polling loop currently only watches one file. Fix: on each poll interval, also check for new JSONL files in the project directory. When a new file appears, start polling it instead.

```python
def _poll_session(self):
    # Check for new session files
    current_sessions = find_project_sessions(project_cwd=self._project_dir)
    if current_sessions and current_sessions[-1] != self._session_path:
        # New session detected — parse it and switch polling target
        new_path = current_sessions[-1]
        with open(new_path) as f:
            for line in f:
                self.parser.process_line(line.strip())
            self._file_pos = f.tell()
        self._session_path = new_path
        self.parser.session_count += 1
        # ... emit session boundary event
        self._refresh_ui()
        return
    # ... existing polling logic
```

Add `session_count` to `SessionParser` to track session boundaries. Emit as an event alongside compactions and clears.

### 2B. Overhead Cost Calculation

**File:** `app.py` `_refresh_ui()`

Currently `total_cost` only sums skill event costs. Fix: also calculate and add overhead cost.

```python
overhead_model = "claude-opus-4-6"  # default
overhead_cost = calculate_cost(
    overhead_model,
    self.parser.overhead_tokens["input"],
    self.parser.overhead_tokens["output"],
    self.parser.overhead_tokens["cache_read"],
    self.parser.overhead_tokens.get("cache_write", 0),
    pricing,
)
total_cost = sum(e["cost"] for e in entries) + overhead_cost
```

### 2C. Overhead Gaps in Workflow

**File:** `widgets/workflow.py` and `app.py`

Interleave overhead segments between skill events in the workflow timeline. The watcher already tracks overhead tokens — we need to segment them by time (between skill events) and display them.

Add overhead tracking per-segment in `watcher.py`:
```python
@dataclass
class OverheadSegment:
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int = 0
    tool_count: int = 0
```

In the workflow, render as:
```
① brainstorming          1.2k tok  $0.52
   ┃  ████░░░░░░░░░░  2m
   ▼
   ── no skill ──       18.5k tok  $4.20
   ┃  Edit(3) Read(5)
   ▼
② test-driven-dev        3.1k tok  $1.10
```

---

## Part 3: Dashboard New Features

### 3A. Session Boundary Tracking

**Files:** `watcher.py`, `costs_panel.py`

Add `session_count: int` to `SessionParser`. Increment when a new session file is detected. Display in stats panel alongside compactions and clears:

```
Sessions: 3  Compactions: 2  μCompactions: 1  Clears: 0
```

### 3B. Hook Activity Detection

**Files:** `watcher.py`, `activity.py`

Hook-injected context appears in JSONL entries. Detect patterns:
- `UserPromptSubmit` hooks appear as additional context in user entries
- `PreToolUse` hooks appear as context before tool results
- `SessionStart` hooks appear in early session entries

Parse and surface as events in the activity log:
```
22:43:59  ⚡ Hook: UserPromptSubmit → skill-check
22:44:01  ⚡ Hook: PreToolUse [Edit] → warn-no-skill
```

Detection approach: look for the `hookSpecificOutput` or `additionalContext` patterns in JSONL entries that indicate hook injection. This is heuristic — the JSONL format may include hook context in different ways depending on Claude Code version.

### 3C. Skill Compliance Display

**File:** `costs_panel.py`

Show skill and tool counts side by side in the stats panel:

```
Skills: 3  |  Tools: 28
```

Data already tracked: `len(self.parser.skill_events)` and `sum(self.parser.tool_counts.values())`.

### 3D. Subagent Transcript Parsing

**File:** `watcher.py`

New data model:
```python
@dataclass
class SubagentDetail:
    agent_id: str
    description: str
    subagent_type: str
    model: str
    status: str  # "running" | "complete"
    skills_invoked: list[str]
    tool_counts: dict[str, int]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    duration_ms: int
```

Correlation mechanism:
1. When Task tool_use is found, record the `tool_use_id`
2. When tool_result comes back, extract `agentId` via regex from the result text
3. Construct path: `{session-id}/subagents/agent-{id}.jsonl`
4. Parse using a lightweight version of SessionParser

Polling strategy:
- **Running subagents** (Task dispatch seen but no tool_result yet): poll their JSONL file on the same 500ms interval
- **Completed subagents** (tool_result received): parse once, cache result

Update `SubagentEvent` to include an optional `SubagentDetail` field.

### 3E. Per-Subagent Display

**Files:** `activity.py`, `workflow.py`, `costs_panel.py`

**Activity log** — show subagent lifecycle with internal details:
```
22:44:01  ▶ Subagent: Research TUI [Explore/sonnet]
            ├ Tools: Read(8) Grep(4) Glob(3) WebSearch(2)
            ├ Tokens: 18.5k in / 4.2k out  $0.42
            └ Duration: 29s ✓ complete
```

For running subagents, show live-updating status:
```
22:46:10  ▶ Subagent: Implement feature [general-purpose/opus]
            ├ Skills: test-driven-development
            ├ Tools: Read(3) Edit(1)... ◐ running
```

**Workflow panel** — show subagent dispatches inline:
```
③ brainstorming       1.2k tok  $0.52
     ▼
④ ▶ Research TUI      18.5k tok  $0.42
  └ (no skills)
     ▼
⑤ ▶ Implement feat    24k tok  $1.20
  └ test-driven-dev
```

**Stats panel** — aggregate subagent metrics:
```
Subagents:         8
  Skills used:     2/8
  Total cost:      $3.42
  Total tokens:    142k
```

### 3F. Hook Configuration Viewer Panel

**File:** New `widgets/hooks_panel.py`, `app.py` layout change

New panel in the left column between Skills and Stats. Reads hook configs on mount (not polled).

**Data sources:**
- `~/.claude/settings.json` → user-level hooks
- Each enabled plugin's `hooks/hooks.json` → plugin hooks
- `.claude/settings.json` → project-level hooks (if they exist)

**Display format:**
```
HOOKS
──────────────────────────────────
⚡ SessionStart
  superpowers → session-start.sh

⚡ UserPromptSubmit
  user config → skill-check.sh

⚡ PreToolUse [Edit|Write|Bash]
  user config → warn-no-skill.sh

⚡ SubagentStart
  user config → subagent-skill-check.sh
```

**Layout change** — left column becomes 3-row stack:
```
┌──────────────────┬──────────────────────────────┐
│ SKILLS (45 cols) │ WORKFLOW (flex)               │
│                  │                               │
├──────────────────┤                               │
│ HOOKS  (45 cols) │                               │
│                  │                               │
├──────────────────┼──────────────────────────────┤
│ STATS  (45 cols) │ ACTIVITY LOG (flex)           │
│                  │                               │
└──────────────────┴──────────────────────────────┘
```

CSS change: split left column into 3 rows. Skills and Hooks get `height: auto` (shrink to content), Stats gets `height: 1fr` (takes remaining space).

---

## Implementation Order

Ordered by dependency and value:

1. **Bug fixes first** (2A, 2B, 2C) — fix new session detection, overhead costing, and workflow gaps. Foundation for everything else.
2. **Enforcement hooks** (1A, 1B, 1C, 1D) — create hook scripts, update settings.json, write CLAUDE.md files. Independent of dashboard work.
3. **Session boundaries + skill compliance** (3A, 3C) — quick wins that enhance stats panel.
4. **Hook config viewer** (3F) — new panel, layout change. Independent of subagent work.
5. **Hook activity detection** (3B) — parse hook evidence from JSONL.
6. **Subagent transcript parsing** (3D) — the data layer for subagent visibility.
7. **Per-subagent display** (3E) — render subagent data in activity, workflow, and stats.

## Estimated Scope

| Component | Lines | Files |
|-----------|-------|-------|
| Bug fixes (2A, 2B, 2C) | ~80 | `app.py`, `watcher.py`, `workflow.py` |
| Enforcement (1A-1D) | ~50 | 3 new shell scripts, `settings.json`, 2 CLAUDE.md files |
| Session + compliance (3A, 3C) | ~30 | `watcher.py`, `costs_panel.py` |
| Hook config viewer (3F) | ~70 | New `hooks_panel.py`, `app.py` |
| Hook activity (3B) | ~40 | `watcher.py`, `activity.py` |
| Subagent parsing (3D) | ~100 | `watcher.py` |
| Per-subagent display (3E) | ~100 | `activity.py`, `workflow.py`, `costs_panel.py` |
| **Total** | **~470** | 4 new files + ~7 modified |

Current codebase: 827 lines. This adds ~57%.
