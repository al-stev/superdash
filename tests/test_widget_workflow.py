from superpowers_dashboard.widgets.workflow import WorkflowWidget, format_tokens, format_duration_minutes

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
    text = w.format_entry(index=1, skill_name="brainstorming", args="Terminal UI for superpowers", total_tokens=12847, cost=0.31, duration_seconds=1740, max_cost=1.02, is_active=False)
    assert "brainstorming" in text
    assert "12.8k" in text
    assert "$0.31" in text
    assert "29m" in text


def test_workflow_format_overhead():
    """format_overhead produces text with token count, cost, duration, and 'no skill' label."""
    w = WorkflowWidget()
    text = w.format_overhead(
        input_tokens=15000,
        output_tokens=3500,
        cost=4.20,
        duration_seconds=125,
        tool_summary="Edit(3) Read(5)",
    )
    assert "no skill" in text
    assert "18.5k" in text  # 15000 + 3500 = 18500 -> 18.5k
    assert "$4.20" in text
    assert "2m" in text
    assert "Edit(3) Read(5)" in text


def test_workflow_format_overhead_empty_tools():
    """format_overhead works when there are no tools."""
    w = WorkflowWidget()
    text = w.format_overhead(
        input_tokens=500,
        output_tokens=100,
        cost=0.05,
        duration_seconds=30,
        tool_summary="",
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
            "skill_name": "brainstorming",
            "args": "test idea",
            "total_tokens": 5000,
            "cost": 0.50,
            "duration_seconds": 120,
            "is_active": False,
        },
        {
            "kind": "overhead",
            "input_tokens": 3000,
            "output_tokens": 1000,
            "cost": 0.30,
            "duration_seconds": 60,
            "tool_summary": "Read(2)",
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
    # Overhead entry should show 'no skill'
    assert "no skill" in content
    assert "Read(2)" in content


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
