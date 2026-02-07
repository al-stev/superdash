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
