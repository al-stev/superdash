from superpowers_dashboard.widgets.activity import format_log_entry, format_compaction_entry, format_subagent_entry


def test_format_log_entry():
    text = format_log_entry(
        timestamp="2026-02-06T22:16:50.558Z",
        skill_name="brainstorming",
        args="Terminal UI for superpowers",
    )
    assert "22:16" in text
    assert "brainstorming" in text


def test_format_log_entry_truncates_args():
    text = format_log_entry(
        timestamp="2026-02-06T22:16:50.558Z",
        skill_name="brainstorming",
        args="A" * 100,
    )
    assert "..." in text


def test_format_compaction_entry():
    text = format_compaction_entry(
        timestamp="2026-02-07T08:14:37.918Z",
        kind="compaction",
        pre_tokens=169162,
    )
    assert "COMPACTION" in text
    assert "169,162" in text


def test_format_microcompaction_entry():
    text = format_compaction_entry(
        timestamp="2026-02-07T09:00:00.000Z",
        kind="microcompaction",
        pre_tokens=50000,
    )
    assert "MICRO" in text
    assert "50,000" in text


def test_format_subagent_entry():
    text = format_subagent_entry(
        timestamp="2026-02-07T06:00:00.000Z",
        description="Implement Task 2",
        subagent_type="general-purpose",
        model="sonnet",
    )
    assert "Subagent" in text
    assert "Implement Task 2" in text
    assert "[sonnet]" in text
    assert "general-purpose" in text


def test_format_subagent_entry_inherit_model():
    text = format_subagent_entry(
        timestamp="2026-02-07T06:00:00.000Z",
        description="Research",
        subagent_type="Explore",
        model="inherit",
    )
    assert "[inherit]" not in text
    assert "Research" in text
