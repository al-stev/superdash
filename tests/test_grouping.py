# tests/test_grouping.py
from superpowers_dashboard.grouping import classify_role, extract_task_number, build_task_groups, TaskGroup


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


def test_extract_task_number():
    assert extract_task_number("Implement Task 3: Workflow gaps") == 3


def test_extract_task_number_spec_review():
    assert extract_task_number("Review spec compliance Task 7") == 7


def test_extract_task_number_none():
    assert extract_task_number("Final code review of all changes") is None


def test_extract_task_number_no_match():
    assert extract_task_number("Explore superpowers skills") is None


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
    assert subs[0].get("status") == "complete"
    assert subs[1].get("status") == "running"
