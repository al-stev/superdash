# Superpowers Dashboard — Design Document

## Problem

When using Claude Code with Superpowers skills, it's hard to know:
- Which skills exist and what they do
- Which skill is currently active
- What skills have been used this session and in what order
- How much each skill invocation cost in tokens and time

This is a situational awareness problem. The dashboard is a heads-up display, not a launcher.

## Solution

A terminal dashboard (Python + Textual) that observes Claude Code session JSONL files in real-time and displays skill status, workflow history, and cost data.

Read-only. No hooks to install, no Claude Code configuration needed.

## Architecture

```
~/.claude/projects/*/*.jsonl
         |
         v
   +-------------+     +----------------+
   | JSONL Watcher|     | Skill Registry |
   | (tail+parse) |     | (reads SKILL.md)|
   +------+------+     +-------+--------+
          |                     |
          v                     v
   +--------------------------------------+
   |         Textual App (TUI)            |
   |                                      |
   |  +------------+  +---------------+   |
   |  | Skill List |  |   Workflow    |   |
   |  |  (status)  |  |   Timeline   |   |
   |  +------------+  +---------------+   |
   |  | Costs      |  |  Activity    |   |
   |  |            |  |  Log         |   |
   |  +------------+  +---------------+   |
   +--------------------------------------+
```

### Components

**JSONL Watcher** — Finds the most recent session `.jsonl` file under `~/.claude/projects/`. Polls file size every 500ms via asyncio, parses new lines. Emits events into the Textual app via its message system.

**Skill Registry** — On startup, reads all `SKILL.md` files from the superpowers plugin directory. Extracts name and description from YAML frontmatter. Static reference data.

**Textual App** — Four-panel layout. Widgets react to watcher events.

## UI Layout

```
+--------------------------------------------------------------+
|  SUPERPOWERS DASHBOARD           session: a3f2c1  $0.42      |
+---------------------+------------------------------------+
|  SKILLS             |  WORKFLOW                              |
|  -----              |  --------                              |
|  * brainstorming    |  1. brainstorming    12.8k tok  $0.31  |
|  # writing-plans    |     "Terminal UI for superpowers"      |
|  o executing-plans  |     ############--  29m                |
|  o test-driven-dev  |     v                                  |
|  o systematic-debug |  2. writing-plans     8.2k tok  $0.19  |
|  o using-worktrees  |     "from design doc"                  |
|  o dispatching-...  |     ########------  13m                |
|  o subagent-driven  |     v                                  |
|  o finishing-branch |  3. executing-plans  45.1k tok  $1.02  |
|  o code-review-req  |     "step 1 of 4"                     |
|  o code-review-rec  |     ##############  43m                |
|  o verification     |                                        |
|  o writing-skills   |                                        |
|  o using-superpow.. |                                        |
+---------------------+------------------------------------+
|  COSTS              |  ACTIVITY LOG                          |
|  -----              |  ------------                          |
|  This session: $0.42|  22:16:03  Skill: brainstorming        |
|  Tokens in: 12,847  |           args: "Terminal UI for s..." |
|    (68% cached)     |  22:18:47  Skill: writing-plans        |
|  Tokens out:  3,291 |           args: "from design doc"      |
|  ---------------    |  22:24:12  Skill: executing-plans      |
|  Per skill:         |           args: "step 1 of 4"          |
|  brainstorming $0.31|                                        |
|  writing-plan  $0.11|                                        |
+---------------------+------------------------------------+
```

### Panel Details

**Skills (top-left):** All skills from the registry with three states:
- Active (currently running) — bright indicator
- Used (completed this session) — dimmer indicator
- Available (not yet used) — grey indicator

Selecting a skill shows its one-line description.

**Workflow (top-right):** Vertical timeline of actual skill invocations this session. Each entry shows:
- Skill name and invocation number
- Args passed (truncated)
- Token count and cost
- Proportional cost bar
- Duration in minutes (active skill shows a live counter)

Skills used multiple times appear multiple times. This is the actual session history, not an idealized pipeline.

**Costs (bottom-left):** Session totals:
- Total cost
- Tokens in/out with cache hit ratio
- Per-skill cost breakdown with proportional bars

**Activity Log (bottom-right):** Chronological feed of skill invocations with timestamps and arguments. Scrollable.

## Skill State Detection

Source: Claude Code session JSONL files.

Every skill invocation follows a three-step pattern in the JSONL:
1. `assistant` message with `tool_use` where `name === "Skill"`
2. `user` message with `tool_result` confirming launch
3. `user` message with `isMeta: true` containing full skill instructions

State rules:
- **Available**: In skill registry, no `isMeta` event for this skill in session
- **Active**: Most recent skill to have an `isMeta` event
- **Used**: Had `isMeta` event earlier, but a different skill was invoked after

No heuristic timeouts. A skill stays active until displaced by another skill invocation.

### Token and Cost Attribution

Every `assistant` message in JSONL contains:
- `message.model` — which model (e.g. `claude-opus-4-6`)
- `message.usage.input_tokens`
- `message.usage.output_tokens`
- `message.usage.cache_read_input_tokens`
- `message.usage.cache_creation_input_tokens`

Tokens are attributed to whichever skill was most recently activated. Tokens before any skill invocation go into an "overhead" bucket.

### Session Discovery

On startup, find the most recent `.jsonl` file under `~/.claude/projects/`. Watch for new files appearing (new session started).

## Configuration

```toml
# ~/.config/superpowers-dashboard/config.toml

[pricing]
# Per million tokens

[pricing."claude-opus-4-6"]
input = 5.0
output = 25.0
cache_read = 0.5
cache_write = 6.25

[pricing."claude-sonnet-4-5-20250929"]
input = 3.0
output = 15.0
cache_read = 0.3
cache_write = 3.75

[pricing."claude-haiku-4-5-20251001"]
input = 1.0
output = 5.0
cache_read = 0.1
cache_write = 1.25
```

Created on first run with current defaults. Users can edit to match their rates.

## Themes

Two built-in themes, toggled with `t` keybinding:

**Terminal (default):** Clean black and white.

**Mainframe:** Green phosphor CRT aesthetic (#33FF33 on #000000).

## Tech Stack

- Python 3.11+
- Textual (TUI framework)
- tomllib / tomli (config parsing)
- No other dependencies

Installable via `uvx` or `pip`.

## File Structure

```
superpowers-tui/
  pyproject.toml
  src/
    superpowers_dashboard/
      __init__.py
      app.py           # Textual app, layout, themes
      watcher.py       # JSONL file watcher + parser
      registry.py      # Skill registry (reads SKILL.md files)
      config.py        # Config loading (pricing, paths)
      widgets/
        __init__.py
        skill_list.py  # Skills panel
        workflow.py    # Workflow timeline panel
        costs.py       # Costs panel
        activity.py    # Activity log panel
  docs/
    plans/
      2026-02-06-superpowers-dashboard-design.md
```

Estimated size: 500-750 lines of code across ~10 files.

## What's Out of Scope

- "What's next" skill suggestions (Claude handles skill selection)
- File rendering or IDE features
- Multi-session management
- Browser mode (free via `textual serve` but not a design goal)
- Multi-project tracking
