# Tree View and Subagent Role Tagging Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the flat workflow timeline with a nested tree that groups subagents by task number and shows their roles (implementer, spec-reviewer, code-reviewer).

**Architecture:** Pure grouping logic in a new module, rendering changes in the workflow widget, wiring in app.py. The parser stays unchanged — grouping is a view concern.

**Tech Stack:** Python dataclasses, regex for task number extraction, box-drawing characters for tree rendering.

---

## Data Model

### SubagentEvent Change

Add `role: str = ""` field to `SubagentEvent` in `watcher.py`. Populated during `_refresh_ui`, not during parsing.

### New: grouping.py

```python
@dataclass
class TaskGroup:
    task_number: int
    label: str              # e.g. "Fix overhead cost"
    parent_skill: str       # e.g. "subagent-driven-development"
    subagents: list[dict]   # ordered: implementers, spec-reviewers, code-reviewers
```

### Role Classification

```python
def classify_role(description: str, subagent_type: str) -> str:
    desc_lower = description.lower()
    if desc_lower.startswith("implement task"):
        return "implementer"
    if "spec compliance" in desc_lower:
        return "spec-reviewer"
    if "code-reviewer" in subagent_type or "code review" in desc_lower:
        return "code-reviewer"
    if subagent_type == "Explore":
        return "explorer"
    return "other"
```

### Task Number Extraction

Regex `Task (\d+)` on description. Returns `int | None`.

### Group Building

`build_task_groups(subagent_entries, skill_entries)` returns:
- `dict[int, TaskGroup]` — task number to group mapping
- `list[dict]` — ungrouped subagent entries (no task number, or explorers)

Algorithm:
1. Classify each subagent's role
2. Extract task numbers
3. Group by task number
4. For each group, determine parent skill (the active skill at the implementer's timestamp)
5. Order within group: implementers, then spec-reviewers, then code-reviewers (by timestamp)
6. Return groups and ungrouped remainder

## Tree Rendering

### Three Levels

**Level 1 — Top-level skills and overhead gaps:**
```
 ① brainstorming                      12.8k tok  $0.31
    ┃  "Terminal UI for superpowers"
    ┃  ██████████████  29m
    ▼
 ② subagent-driven-development              $4.82 ●
```

Skills without task groups render exactly as today.

**Level 2 — Task groups (indented under parent skill):**
```
    ┣━ Task 1: Fix overhead cost             $0.18
    ┃    ├ implement    4.2k tok  $0.12  ✓
    ┃    ├ spec-review  1.1k tok  $0.03  ✓
    ┃    └ quality      2.8k tok  $0.03  ✓
```

**Level 3 — Subagent rows:**

Each shows: role label, tokens, cost, status icon.

### Status Icons

- `✓` — complete (has transcript with results)
- `●` — in progress (dispatched, no result yet)
- `○` — pending (not yet dispatched)
- `✗` — failed/needs-refix (for future use)

### Subagent Status Detection

- **Complete:** `detail is not None` (transcript parsed, has token counts)
- **In progress:** `detail is None` and `tool_use_id` exists (dispatched but no result yet)
- **Pending:** Not yet dispatched. Inferred from group — if implementer exists but spec-reviewer doesn't, spec-reviewer is pending.

### Ungrouped Subagents

Explorers, researchers, and subagents without a "Task N" pattern render inline at their timeline position using the existing `▶` format. This is the graceful fallback.

### Overhead Gaps

Always shown between top-level entries, same as today. Orchestrator overhead between task dispatches appears as normal overhead segments.

## Edge Cases

- **Re-reviews:** Multiple implementer + reviewer dispatches for same task number. All shown in order — the tree naturally shows the retry cycle.
- **Final code review:** No task number, classified as code-reviewer. Renders inline as ungrouped.
- **No task numbers:** Subagents without "Task N" in description render ungrouped — fallback to current behavior.
- **Mixed sessions:** Brainstorming (no subagents) renders as simple skill entry. Subagent-driven renders as tree.
- **Explore subagents:** Render inline at timeline position, not grouped.

## File Changes

**New:**
- `src/superpowers_dashboard/grouping.py` — classify_role, extract_task_number, build_task_groups
- `tests/test_grouping.py` — all grouping logic tests

**Modified:**
- `src/superpowers_dashboard/watcher.py` — add `role: str = ""` to SubagentEvent
- `src/superpowers_dashboard/widgets/workflow.py` — format_task_group, format_subagent_row, updated update_timeline
- `src/superpowers_dashboard/app.py` — call build_task_groups in _refresh_ui, pass to workflow
- `tests/test_widget_workflow.py` — tree rendering tests

**Unchanged:**
- hooks_panel.py, costs_panel.py, activity.py, registry.py, config.py, costs.py
- SessionParser internals
- Enforcement hooks
