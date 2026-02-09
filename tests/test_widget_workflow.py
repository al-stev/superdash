from superpowers_dashboard.widgets.workflow import WorkflowWidget, format_tokens, format_duration_minutes
from superpowers_dashboard.grouping import TaskGroup

def test_format_tokens_small():
    assert format_tokens(500) == "500"

def test_format_tokens_thousands():
    assert format_tokens(12847) == "12.8k"

def test_format_tokens_millions():
    assert format_tokens(1_200_000) == "1.2M"

def test_format_duration_minutes():
    assert format_duration_minutes(1740) == "29m"

def test_format_duration_seconds():
    assert format_duration_minutes(45) == "<1m"

def test_format_duration_hours():
    assert format_duration_minutes(7200) == "2h 0m"

def test_workflow_format_entry():
    w = WorkflowWidget()
    text = w.format_entry(index=1, skill_name="brainstorming", args="Terminal UI for superpowers", total_tokens=12847, cost=0.31, duration_seconds=1740, max_cost=1.02, is_active=False, timestamp="2026-02-06T22:16:50.558Z")
    assert "brainstorming" in text
    assert "12.8k" in text
    assert "$0.31" in text
    assert "29m" in text
    assert "22:16" in text


def test_workflow_format_compaction():
    """format_compaction renders compaction events with token count."""
    w = WorkflowWidget()
    text = w.format_compaction(
        timestamp="2026-02-07T08:14:37.918Z",
        kind="compaction",
        pre_tokens=169162,
    )
    assert "COMPACTION" in text
    assert "169,162" in text
    assert "08:14" in text


def test_workflow_format_microcompaction():
    """format_compaction renders microcompaction with MICRO label."""
    w = WorkflowWidget()
    text = w.format_compaction(
        timestamp="2026-02-07T09:00:00.000Z",
        kind="microcompaction",
        pre_tokens=50000,
    )
    assert "MICRO" in text
    assert "50,000" in text


def test_workflow_format_overhead():
    """format_overhead produces text with token count, cost, duration, and 'no skill' label."""
    w = WorkflowWidget()
    text = w.format_overhead(
        input_tokens=15000,
        output_tokens=3500,
        cost=4.20,
        duration_seconds=125,
        tool_summary="Edit(3) Read(5)",
        timestamp="2026-02-07T10:30:00.000Z",
    )
    assert "no skill" in text
    assert "18.5k" in text  # 15000 + 3500 = 18500 -> 18.5k
    assert "$4.20" in text
    assert "2m" in text
    assert "Edit(3) Read(5)" in text
    assert "10:30" in text


def test_workflow_format_overhead_empty_tools():
    """format_overhead works when there are no tools."""
    w = WorkflowWidget()
    text = w.format_overhead(
        input_tokens=500,
        output_tokens=100,
        cost=0.05,
        duration_seconds=30,
        tool_summary="",
        timestamp="2026-02-07T11:00:00.000Z",
    )
    assert "no skill" in text
    assert "$0.05" in text
    assert "<1m" in text


def test_workflow_timeline_with_overhead():
    """update_timeline handles a mixed list of skill and overhead entries."""
    w = WorkflowWidget()
    entries = [
        {
            "kind": "skill",
            "timestamp": "2026-02-07T10:00:00.000Z",
            "skill_name": "brainstorming",
            "args": "test idea",
            "total_tokens": 5000,
            "cost": 0.50,
            "duration_seconds": 120,
            "is_active": False,
        },
        {
            "kind": "overhead",
            "timestamp": "2026-02-07T10:05:00.000Z",
            "input_tokens": 3000,
            "output_tokens": 1000,
            "cost": 0.30,
            "duration_seconds": 60,
            "tool_summary": "Read(2)",
        },
        {
            "kind": "skill",
            "timestamp": "2026-02-07T10:10:00.000Z",
            "skill_name": "implementing",
            "args": "build feature",
            "total_tokens": 10000,
            "cost": 1.20,
            "duration_seconds": 300,
            "is_active": True,
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    # Skill entries should use circled numbers
    assert "\u2460" in content  # ① for first skill
    assert "brainstorming" in content
    assert "\u2461" in content  # ② for second skill
    assert "implementing" in content
    # Overhead entry should show 'no skill'
    assert "no skill" in content
    assert "Read(2)" in content


def test_workflow_timeline_with_compaction():
    """update_timeline renders compaction events in the timeline."""
    w = WorkflowWidget()
    entries = [
        {
            "kind": "skill",
            "timestamp": "2026-02-07T10:00:00.000Z",
            "skill_name": "brainstorming",
            "args": "",
            "total_tokens": 5000,
            "cost": 0.50,
            "duration_seconds": 120,
            "is_active": False,
        },
        {
            "kind": "compaction",
            "timestamp": "2026-02-07T10:30:00.000Z",
            "compaction_kind": "compaction",
            "pre_tokens": 169162,
        },
        {
            "kind": "skill",
            "timestamp": "2026-02-07T10:31:00.000Z",
            "skill_name": "implementing",
            "args": "",
            "total_tokens": 10000,
            "cost": 1.20,
            "duration_seconds": 300,
            "is_active": True,
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    assert "COMPACTION" in content
    assert "169,162" in content
    assert "brainstorming" in content
    assert "implementing" in content


def test_workflow_timeline_backwards_compat():
    """Entries without a 'kind' field default to skill rendering."""
    w = WorkflowWidget()
    entries = [
        {
            "skill_name": "brainstorming",
            "args": "",
            "total_tokens": 1000,
            "cost": 0.10,
            "duration_seconds": 60,
            "is_active": False,
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    assert "brainstorming" in content
    assert "\u2460" in content


def test_workflow_format_subagent():
    """format_subagent_entry produces text with description, token count, cost, and 'no skills' label."""
    w = WorkflowWidget()
    text = w.format_subagent_entry(
        description="Research TUI",
        total_tokens=18500,
        cost=0.42,
        skills_invoked=[],
    )
    assert "\u25b6" in text  # ▶ prefix
    assert "Research TUI" in text
    assert "18.5k" in text
    assert "$0.42" in text
    assert "(no skills)" in text


def test_workflow_format_subagent_with_skills():
    """format_subagent_entry shows skills when provided."""
    w = WorkflowWidget()
    text = w.format_subagent_entry(
        description="Implement feature",
        total_tokens=24000,
        cost=1.20,
        skills_invoked=["test-driven-development"],
    )
    assert "\u25b6" in text  # ▶ prefix
    assert "Implement feature" in text
    assert "24.0k" in text
    assert "$1.20" in text
    assert "test-driven-development" in text
    assert "(no skills)" not in text


def test_workflow_timeline_with_subagent():
    """update_timeline handles a mixed list of skill and subagent entries."""
    w = WorkflowWidget()
    entries = [
        {
            "kind": "skill",
            "skill_name": "brainstorming",
            "args": "test idea",
            "total_tokens": 5000,
            "cost": 0.50,
            "duration_seconds": 120,
            "is_active": False,
        },
        {
            "kind": "subagent",
            "description": "Research TUI",
            "total_tokens": 18500,
            "cost": 0.42,
            "skills_invoked": [],
        },
        {
            "kind": "skill",
            "skill_name": "implementing",
            "args": "build feature",
            "total_tokens": 10000,
            "cost": 1.20,
            "duration_seconds": 300,
            "is_active": True,
        },
    ]
    w.update_timeline(entries)
    content = w._Static__content
    # Skill entries should use circled numbers
    assert "\u2460" in content  # ① for first skill
    assert "brainstorming" in content
    assert "\u2461" in content  # ② for second skill
    assert "implementing" in content
    # Subagent entry should show ▶ prefix and description
    assert "\u25b6" in content
    assert "Research TUI" in content
    assert "(no skills)" in content


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
    assert "\u2713" in text  # checkmark


def test_workflow_format_task_group_in_progress():
    """format_task_group shows pending subagents with circle icon."""
    w = WorkflowWidget()
    group = TaskGroup(task_number=3, label="Workflow gaps", subagents=[
        {"role": "implementer", "total_tokens": 3100, "cost": 0.09, "status": "running"},
    ])
    text = w.format_task_group(group, is_last=True)
    assert "Task 3" in text
    assert "\u25cf" in text  # filled circle running
    assert "\u25cb" in text  # open circle pending (spec and quality not dispatched)


def test_workflow_format_subagent_row_complete():
    """format_subagent_row renders a complete subagent with tokens and cost."""
    w = WorkflowWidget()
    text = w.format_subagent_row(
        role="implementer", total_tokens=4200, cost=0.12, status="complete", connector="\u251c"
    )
    assert "implement" in text
    assert "4.2k" in text
    assert "$0.12" in text
    assert "\u2713" in text  # checkmark


def test_workflow_format_subagent_row_pending():
    """format_subagent_row renders a pending subagent without tokens."""
    w = WorkflowWidget()
    text = w.format_subagent_row(
        role="spec-reviewer", total_tokens=0, cost=0, status="pending", connector="\u251c"
    )
    assert "spec-review" in text
    assert "\u25cb" in text  # open circle
    assert "tok" not in text  # no tokens shown for pending


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


def test_workflow_format_clear():
    """format_compaction renders clear events with CLEAR label."""
    w = WorkflowWidget()
    text = w.format_compaction(
        timestamp="2026-02-07T09:30:00.000Z",
        kind="clear",
        pre_tokens=0,
    )
    assert "CLEAR" in text
    assert "COMPACTION" not in text
    assert "09:30" in text


def test_workflow_timeline_ungrouped_still_works():
    """Ungrouped subagent entries still render with the existing format."""
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
