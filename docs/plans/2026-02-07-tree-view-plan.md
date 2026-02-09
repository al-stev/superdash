# Tree View and Subagent Role Tagging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the flat workflow timeline with a nested tree showing skill chains, task groups, and subagent roles.

**Architecture:** New `grouping.py` module with pure functions for role classification and task grouping. Workflow widget updated with tree rendering methods. App wiring builds groups from entries before passing to widget.

**Tech Stack:** Python dataclasses, regex, box-drawing characters for tree rendering.

---

### Task 1: Role Classification

**Files:**
- Create: `src/superpowers_dashboard/grouping.py`
- Create: `tests/test_grouping.py`

**Step 1: Write the failing tests**

```python
# tests/test_grouping.py
from superpowers_dashboard.grouping import classify_role


def test_classify_implementer():
    assert classify_role("Implement Task 1: Fix cost bug", "general-purpose") == "implementer"


def test_classify_implementer_case_insensitive():
    assert classify_role("implement task 3: overhead", "general-purpose") == "implementer"


def test_classify_spec_reviewer():
    assert classify_role("Review spec compliance Task 1", "general-purpose") == "spec-reviewer"


def test_classify_code_reviewer_by_type():
    assert classify_role("Final code review", "superpowers:code-reviewer") == "code-reviewer"


def test_classify_code_reviewer_by_description():
    assert classify_role("Final code review of all changes", "general-purpose") == "code-reviewer"


def test_classify_explorer():
    assert classify_role("Explore superpowers skills", "Explore") == "explorer"


def test_classify_other():
    assert classify_role("Calculate budget", "Bash") == "other"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grouping.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'superpowers_dashboard.grouping'"

**Step 3: Write minimal implementation**

```python
# src/superpowers_dashboard/grouping.py
"""Subagent role classification and task grouping."""
import re
from dataclasses import dataclass, field


def classify_role(description: str, subagent_type: str) -> str:
    """Classify a subagent's role from its description and type."""
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

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grouping.py -v`
Expected: 7 PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/grouping.py tests/test_grouping.py
git commit -m "feat: add subagent role classification"
```

---

### Task 2: Task Number Extraction

**Files:**
- Modify: `src/superpowers_dashboard/grouping.py`
- Modify: `tests/test_grouping.py`

**Step 1: Write the failing tests**

```python
# append to tests/test_grouping.py
from superpowers_dashboard.grouping import classify_role, extract_task_number


def test_extract_task_number():
    assert extract_task_number("Implement Task 3: Workflow gaps") == 3


def test_extract_task_number_spec_review():
    assert extract_task_number("Review spec compliance Task 7") == 7


def test_extract_task_number_none():
    assert extract_task_number("Final code review of all changes") is None


def test_extract_task_number_no_match():
    assert extract_task_number("Explore superpowers skills") is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grouping.py::test_extract_task_number -v`
Expected: FAIL with "ImportError: cannot import name 'extract_task_number'"

**Step 3: Write minimal implementation**

```python
# Add to src/superpowers_dashboard/grouping.py

def extract_task_number(description: str) -> int | None:
    """Extract task number from a description like 'Implement Task 3: ...'."""
    m = re.search(r"[Tt]ask\s+(\d+)", description)
    return int(m.group(1)) if m else None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grouping.py -v`
Expected: 11 PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/grouping.py tests/test_grouping.py
git commit -m "feat: add task number extraction from subagent descriptions"
```

---

### Task 3: Task Group Building

**Files:**
- Modify: `src/superpowers_dashboard/grouping.py`
- Modify: `tests/test_grouping.py`

**Step 1: Write the failing tests**

```python
# append to tests/test_grouping.py
from superpowers_dashboard.grouping import classify_role, extract_task_number, build_task_groups, TaskGroup


def test_build_task_groups_basic():
    """Three subagents for one task get grouped together."""
    subagent_entries = [
        {"description": "Implement Task 1: Fix bug", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:00:00Z", "total_tokens": 4000, "cost": 0.12, "skills_invoked": ["test-driven-development"]},
        {"description": "Review spec compliance Task 1", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:05:00Z", "total_tokens": 1100, "cost": 0.03, "skills_invoked": []},
        {"description": "Code review Task 1", "subagent_type": "superpowers:code-reviewer",
         "timestamp": "2026-02-07T10:08:00Z", "total_tokens": 2800, "cost": 0.08, "skills_invoked": []},
    ]
    groups, ungrouped = build_task_groups(subagent_entries)
    assert len(groups) == 1
    assert 1 in groups
    group = groups[1]
    assert group.task_number == 1
    assert group.label == "Fix bug"
    assert len(group.subagents) == 3
    assert group.subagents[0]["role"] == "implementer"
    assert group.subagents[1]["role"] == "spec-reviewer"
    assert group.subagents[2]["role"] == "code-reviewer"
    assert len(ungrouped) == 0


def test_build_task_groups_ungrouped():
    """Subagents without task numbers stay ungrouped."""
    subagent_entries = [
        {"description": "Explore skills system", "subagent_type": "Explore",
         "timestamp": "2026-02-07T09:00:00Z", "total_tokens": 8000, "cost": 0.20, "skills_invoked": []},
        {"description": "Implement Task 1: Fix bug", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:00:00Z", "total_tokens": 4000, "cost": 0.12, "skills_invoked": []},
    ]
    groups, ungrouped = build_task_groups(subagent_entries)
    assert len(groups) == 1
    assert len(ungrouped) == 1
    assert ungrouped[0]["role"] == "explorer"


def test_build_task_groups_multiple_tasks():
    """Multiple tasks get separate groups."""
    subagent_entries = [
        {"description": "Implement Task 1: Fix bug", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:00:00Z", "total_tokens": 4000, "cost": 0.12, "skills_invoked": []},
        {"description": "Review spec compliance Task 1", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:05:00Z", "total_tokens": 1100, "cost": 0.03, "skills_invoked": []},
        {"description": "Implement Task 2: Add feature", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:10:00Z", "total_tokens": 6000, "cost": 0.18, "skills_invoked": []},
    ]
    groups, ungrouped = build_task_groups(subagent_entries)
    assert len(groups) == 2
    assert groups[1].label == "Fix bug"
    assert groups[2].label == "Add feature"
    assert len(ungrouped) == 0


def test_build_task_groups_cost_aggregation():
    """Group cost sums all subagent costs."""
    subagent_entries = [
        {"description": "Implement Task 1: Fix bug", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:00:00Z", "total_tokens": 4000, "cost": 0.12, "skills_invoked": []},
        {"description": "Review spec compliance Task 1", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:05:00Z", "total_tokens": 1100, "cost": 0.03, "skills_invoked": []},
    ]
    groups, _ = build_task_groups(subagent_entries)
    assert abs(groups[1].total_cost - 0.15) < 0.001
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grouping.py::test_build_task_groups_basic -v`
Expected: FAIL with "ImportError: cannot import name 'build_task_groups'"

**Step 3: Write minimal implementation**

```python
# Add to src/superpowers_dashboard/grouping.py

@dataclass
class TaskGroup:
    """A group of subagents working on the same task."""
    task_number: int
    label: str
    subagents: list[dict] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(s.get("cost", 0) for s in self.subagents)


def build_task_groups(
    subagent_entries: list[dict],
) -> tuple[dict[int, TaskGroup], list[dict]]:
    """Group subagent entries by task number.

    Returns:
        (groups, ungrouped) where groups is {task_number: TaskGroup}
        and ungrouped is a list of entries without a task number.
    """
    groups: dict[int, TaskGroup] = {}
    ungrouped: list[dict] = []

    for entry in subagent_entries:
        desc = entry.get("description", "")
        stype = entry.get("subagent_type", "")
        role = classify_role(desc, stype)
        entry_with_role = {**entry, "role": role}

        task_num = extract_task_number(desc)
        if task_num is None:
            ungrouped.append(entry_with_role)
            continue

        if task_num not in groups:
            # Extract label: everything after "Task N: " or "Task N"
            label_match = re.search(r"[Tt]ask\s+\d+:\s*(.*)", desc)
            label = label_match.group(1).strip() if label_match else desc
            groups[task_num] = TaskGroup(task_number=task_num, label=label)

        groups[task_num].subagents.append(entry_with_role)

    return groups, ungrouped
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grouping.py -v`
Expected: 15 PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/grouping.py tests/test_grouping.py
git commit -m "feat: add task group building from subagent entries"
```

---

### Task 4: Tree Rendering — Task Group and Subagent Rows

**Files:**
- Modify: `src/superpowers_dashboard/widgets/workflow.py`
- Modify: `tests/test_widget_workflow.py`

**Step 1: Write the failing tests**

```python
# append to tests/test_widget_workflow.py
from superpowers_dashboard.grouping import TaskGroup


def test_workflow_format_task_group_complete():
    """format_task_group renders a completed task with all three subagent rows."""
    w = WorkflowWidget()
    group = TaskGroup(task_number=1, label="Fix overhead cost", subagents=[
        {"role": "implementer", "total_tokens": 4200, "cost": 0.12, "status": "complete"},
        {"role": "spec-reviewer", "total_tokens": 1100, "cost": 0.03, "status": "complete"},
        {"role": "code-reviewer", "total_tokens": 2800, "cost": 0.08, "status": "complete"},
    ])
    text = w.format_task_group(group, is_last=False)
    assert "Task 1" in text
    assert "Fix overhead cost" in text
    assert "$0.23" in text  # total cost
    assert "implement" in text
    assert "spec-review" in text
    assert "quality" in text
    assert "\u2713" in text  # ✓


def test_workflow_format_task_group_in_progress():
    """format_task_group shows pending subagents with ○ icon."""
    w = WorkflowWidget()
    group = TaskGroup(task_number=3, label="Workflow gaps", subagents=[
        {"role": "implementer", "total_tokens": 3100, "cost": 0.09, "status": "running"},
    ])
    text = w.format_task_group(group, is_last=True)
    assert "Task 3" in text
    assert "\u25cf" in text  # ● running
    assert "\u25cb" in text  # ○ pending (spec and quality not dispatched)


def test_workflow_format_subagent_row_complete():
    """format_subagent_row renders a complete subagent with tokens and cost."""
    w = WorkflowWidget()
    text = w.format_subagent_row(
        role="implementer", total_tokens=4200, cost=0.12, status="complete", connector="\u251c"
    )
    assert "implement" in text
    assert "4.2k" in text
    assert "$0.12" in text
    assert "\u2713" in text  # ✓


def test_workflow_format_subagent_row_pending():
    """format_subagent_row renders a pending subagent without tokens."""
    w = WorkflowWidget()
    text = w.format_subagent_row(
        role="spec-reviewer", total_tokens=0, cost=0, status="pending", connector="\u251c"
    )
    assert "spec-review" in text
    assert "\u25cb" in text  # ○
    assert "tok" not in text  # no tokens shown for pending
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_widget_workflow.py::test_workflow_format_task_group_complete -v`
Expected: FAIL with "AttributeError: 'WorkflowWidget' object has no attribute 'format_task_group'"

**Step 3: Write minimal implementation**

Add these methods to `WorkflowWidget` in `src/superpowers_dashboard/widgets/workflow.py`:

```python
    # Role display labels
    _ROLE_LABELS = {
        "implementer": "implement",
        "spec-reviewer": "spec-review",
        "code-reviewer": "quality",
        "explorer": "explore",
        "other": "agent",
    }

    # Expected roles in a complete task group
    _EXPECTED_ROLES = ["implementer", "spec-reviewer", "code-reviewer"]

    def format_subagent_row(self, role: str, total_tokens: int, cost: float, status: str, connector: str) -> str:
        """Render a single subagent row within a task group."""
        label = self._ROLE_LABELS.get(role, role)
        if status == "complete":
            icon = "\u2713"  # ✓
            tok_str = format_tokens(total_tokens)
            return f"   \u2503    {connector} {label:<12} {tok_str:>6} tok  ${cost:.2f}  {icon}"
        elif status == "running":
            icon = "\u25cf"  # ●
            tok_str = format_tokens(total_tokens) if total_tokens > 0 else ""
            cost_str = f"${cost:.2f}" if cost > 0 else ""
            return f"   \u2503    {connector} {label:<12} {tok_str:>6}      {cost_str}  {icon}"
        else:  # pending
            icon = "\u25cb"  # ○
            return f"   \u2503    {connector} {label:<12}                    {icon}"

    def format_task_group(self, group, is_last: bool = False) -> str:
        """Render a task group with its subagent rows."""
        from superpowers_dashboard.grouping import TaskGroup
        branch = "\u2517\u2501" if is_last else "\u2523\u2501"  # ┗━ or ┣━
        total_cost = group.total_cost
        lines = [f"   {branch} Task {group.task_number}: {group.label:<20} ${total_cost:.2f}"]

        # Build rows for existing subagents + pending placeholders
        existing_roles = [s["role"] for s in group.subagents]
        all_rows = list(group.subagents)

        # Add pending placeholders for expected roles not yet dispatched
        for expected_role in self._EXPECTED_ROLES:
            if expected_role not in existing_roles:
                all_rows.append({"role": expected_role, "total_tokens": 0, "cost": 0, "status": "pending"})

        for i, sa in enumerate(all_rows):
            is_last_row = i == len(all_rows) - 1
            connector = "\u2514" if is_last_row else "\u251c"  # └ or ├
            status = sa.get("status", "complete")
            lines.append(self.format_subagent_row(
                role=sa["role"],
                total_tokens=sa.get("total_tokens", 0),
                cost=sa.get("cost", 0),
                status=status,
                connector=connector,
            ))

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_widget_workflow.py -v`
Expected: All PASS (existing + 4 new)

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py tests/test_widget_workflow.py
git commit -m "feat: add tree rendering for task groups and subagent rows"
```

---

### Task 5: Update Workflow Timeline to Render Groups

**Files:**
- Modify: `src/superpowers_dashboard/widgets/workflow.py`
- Modify: `tests/test_widget_workflow.py`

**Step 1: Write the failing test**

```python
# append to tests/test_widget_workflow.py

def test_workflow_timeline_with_task_groups():
    """update_timeline renders task groups nested under skill entries."""
    w = WorkflowWidget()
    entries = [
        {
            "kind": "skill",
            "skill_name": "subagent-driven-development",
            "args": "",
            "total_tokens": 2000,
            "cost": 0.05,
            "duration_seconds": 60,
            "is_active": True,
            "task_groups": {
                1: TaskGroup(task_number=1, label="Fix bug", subagents=[
                    {"role": "implementer", "total_tokens": 4200, "cost": 0.12, "status": "complete"},
                    {"role": "spec-reviewer", "total_tokens": 1100, "cost": 0.03, "status": "complete"},
                    {"role": "code-reviewer", "total_tokens": 2800, "cost": 0.08, "status": "complete"},
                ]),
            },
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    assert "subagent-driven-development" in content
    assert "Task 1" in content
    assert "Fix bug" in content
    assert "implement" in content
    assert "spec-review" in content
    assert "quality" in content


def test_workflow_timeline_ungrouped_still_works():
    """Ungrouped subagent entries still render with ▶ format."""
    w = WorkflowWidget()
    entries = [
        {
            "kind": "subagent",
            "description": "Explore skills",
            "total_tokens": 8000,
            "cost": 0.20,
            "skills_invoked": [],
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    assert "\u25b6" in content  # ▶
    assert "Explore skills" in content
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_widget_workflow.py::test_workflow_timeline_with_task_groups -v`
Expected: FAIL (task_groups key not handled in update_timeline)

**Step 3: Write minimal implementation**

Update `update_timeline` in `src/superpowers_dashboard/widgets/workflow.py` to check for `task_groups` on skill entries:

```python
    def update_timeline(self, entries: list[dict]):
        if not entries:
            self.update("  No skills invoked yet.")
            return
        max_cost = max(e.get("cost", 0) for e in entries)
        parts = []
        skill_index = 0
        for e in entries:
            kind = e.get("kind", "skill")
            if kind == "overhead":
                text = self.format_overhead(
                    input_tokens=e.get("input_tokens", 0),
                    output_tokens=e.get("output_tokens", 0),
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    tool_summary=e.get("tool_summary", ""),
                )
            elif kind == "subagent":
                text = self.format_subagent_entry(
                    description=e.get("description", ""),
                    total_tokens=e.get("total_tokens", 0),
                    cost=e.get("cost", 0),
                    skills_invoked=e.get("skills_invoked", []),
                )
            else:
                skill_index += 1
                text = self.format_entry(
                    index=skill_index,
                    skill_name=e["skill_name"],
                    args=e.get("args", ""),
                    total_tokens=e.get("total_tokens", 0),
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    max_cost=max_cost,
                    is_active=e.get("is_active", False),
                )
                # Append task groups if present
                task_groups = e.get("task_groups")
                if task_groups:
                    sorted_groups = sorted(task_groups.values(), key=lambda g: g.task_number)
                    for i, group in enumerate(sorted_groups):
                        is_last = i == len(sorted_groups) - 1
                        text += "\n" + self.format_task_group(group, is_last=is_last)
            parts.append(text)
        separator = "\n   \u25bc\n"
        self.update(separator.join(parts))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_widget_workflow.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py tests/test_widget_workflow.py
git commit -m "feat: render task groups in workflow timeline"
```

---

### Task 6: Add Role Field to SubagentEvent

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py:37-44`
- Modify: `tests/test_watcher.py`

**Step 1: Write the failing test**

```python
# append to tests/test_watcher.py

def test_subagent_event_has_role_field():
    """SubagentEvent should have a role field defaulting to empty string."""
    event = SubagentEvent(
        timestamp="2026-02-07T10:00:00Z",
        description="Implement Task 1: Fix bug",
        subagent_type="general-purpose",
        model="inherit",
    )
    assert event.role == ""
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_watcher.py::test_subagent_event_has_role_field -v`
Expected: FAIL with "AttributeError"

**Step 3: Write minimal implementation**

In `src/superpowers_dashboard/watcher.py`, add `role: str = ""` to the `SubagentEvent` dataclass:

```python
@dataclass
class SubagentEvent:
    """A subagent dispatch event."""
    timestamp: str
    description: str
    subagent_type: str
    model: str
    tool_use_id: str = ""
    detail: "SubagentDetail | None" = None
    role: str = ""
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: add role field to SubagentEvent dataclass"
```

---

### Task 7: Wire Grouping Into App

**Files:**
- Modify: `src/superpowers_dashboard/app.py:239-304`

**Step 1: Write the failing test**

This task is integration wiring — the grouping module is tested independently. Instead, write a small test verifying the subagent entry includes role and status:

```python
# append to tests/test_grouping.py

def test_build_task_groups_subagent_status_detection():
    """Subagents with total_tokens > 0 get status 'complete', otherwise 'running'."""
    subagent_entries = [
        {"description": "Implement Task 1: Fix bug", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:00:00Z", "total_tokens": 4000, "cost": 0.12, "skills_invoked": []},
        {"description": "Review spec compliance Task 1", "subagent_type": "general-purpose",
         "timestamp": "2026-02-07T10:05:00Z", "total_tokens": 0, "cost": 0, "skills_invoked": []},
    ]
    groups, _ = build_task_groups(subagent_entries)
    subs = groups[1].subagents
    # Subagent with tokens has been parsed -> complete
    assert subs[0].get("status") == "complete"
    # Subagent without tokens -> running (dispatched but no result yet)
    assert subs[1].get("status") == "running"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_grouping.py::test_build_task_groups_subagent_status_detection -v`
Expected: FAIL (status not set yet in build_task_groups)

**Step 3: Update build_task_groups to set status**

In `src/superpowers_dashboard/grouping.py`, update `build_task_groups` to set a `status` field on each entry:

```python
        # In the loop, after setting role:
        entry_with_role = {**entry, "role": role}
        # Detect status: has token data = complete, otherwise = running
        if entry.get("total_tokens", 0) > 0:
            entry_with_role["status"] = "complete"
        else:
            entry_with_role["status"] = "running"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grouping.py -v`
Expected: All PASS

**Step 5: Update app.py to build groups and attach to skill entries**

In `src/superpowers_dashboard/app.py`, in `_refresh_ui`, after building the subagent entries and before sorting:

1. Add import at top of file:
```python
from superpowers_dashboard.grouping import build_task_groups
```

2. Replace the "Add subagent dispatches" block (lines 286-298) with:

```python
        # Build subagent entries with role/status for grouping
        subagent_entries_for_grouping = []
        for s in self.parser.subagents:
            if s.detail is not None:
                detail = s.detail
                sa_total = detail.input_tokens + detail.output_tokens + detail.cache_read_tokens + detail.cache_write_tokens
                subagent_entries_for_grouping.append({
                    "kind": "subagent",
                    "timestamp": s.timestamp,
                    "description": s.description,
                    "subagent_type": s.subagent_type,
                    "total_tokens": sa_total,
                    "cost": detail.cost,
                    "skills_invoked": detail.skills_invoked,
                })
            else:
                subagent_entries_for_grouping.append({
                    "kind": "subagent",
                    "timestamp": s.timestamp,
                    "description": s.description,
                    "subagent_type": s.subagent_type,
                    "total_tokens": 0,
                    "cost": 0,
                    "skills_invoked": [],
                })

        # Group subagents by task number
        task_groups, ungrouped = build_task_groups(subagent_entries_for_grouping)

        # Attach task groups to their parent skill entry
        # (the last skill entry is typically the parent, e.g. subagent-driven-development)
        if task_groups and entries:
            skill_entries_list = [e for e in entries if e.get("kind", "skill") == "skill"]
            if skill_entries_list:
                skill_entries_list[-1]["task_groups"] = task_groups

        # Add ungrouped subagents as flat entries
        for u in ungrouped:
            entries.append(u)
```

**Step 6: Run all tests to verify they pass**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/superpowers_dashboard/grouping.py src/superpowers_dashboard/app.py tests/test_grouping.py
git commit -m "feat: wire task grouping into app, attach groups to skill entries"
```

---

### Task 8: Final Integration and Cleanup

**Files:**
- All modified files

**Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 2: Verify dashboard imports cleanly**

Run: `uv run python -c "from superpowers_dashboard.app import SuperpowersDashboard; print('OK')"`
Expected: "OK"

**Step 3: Verify grouping works with real data**

```python
uv run python -c "
from superpowers_dashboard.grouping import classify_role, extract_task_number, build_task_groups
entries = [
    {'description': 'Implement Task 1: Fix overhead cost', 'subagent_type': 'general-purpose', 'total_tokens': 4000, 'cost': 0.12, 'skills_invoked': []},
    {'description': 'Review spec compliance Task 1', 'subagent_type': 'general-purpose', 'total_tokens': 1100, 'cost': 0.03, 'skills_invoked': []},
    {'description': 'Explore skills system', 'subagent_type': 'Explore', 'total_tokens': 8000, 'cost': 0.20, 'skills_invoked': []},
]
groups, ungrouped = build_task_groups(entries)
print(f'Groups: {len(groups)}, Ungrouped: {len(ungrouped)}')
for num, g in groups.items():
    print(f'  Task {g.task_number}: {g.label} (\${g.total_cost:.2f})')
    for s in g.subagents:
        print(f'    {s[\"role\"]} - {s[\"status\"]}')
for u in ungrouped:
    print(f'  Ungrouped: {u[\"description\"]} ({u[\"role\"]})')
"
```
Expected:
```
Groups: 1, Ungrouped: 1
  Task 1: Fix overhead cost ($0.15)
    implementer - complete
    spec-reviewer - complete
  Ungrouped: Explore skills system (explorer)
```

**Step 4: Reinstall the tool**

Run: `uv tool install --reinstall /Users/al/Documents/gitstuff/superpowers-tui`

**Step 5: Commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore: final integration cleanup for tree view"
```
