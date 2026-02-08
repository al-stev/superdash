from superpowers_dashboard.widgets.activity import format_log_entry, format_compaction_entry, format_subagent_entry, format_subagent_detail_entry


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


def test_format_subagent_detail_entry():
    """Verify output contains description, tool counts, token amounts, cost, and status."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Research TUI",
        subagent_type="Explore",
        model="sonnet",
        tool_counts={"Read": 8, "Grep": 4, "Glob": 3},
        input_tokens=18500,
        output_tokens=4200,
        cost=0.42,
        skills_invoked=[],
        status="complete",
    )
    assert "Subagent: Research TUI" in text
    assert "[Explore/sonnet]" in text
    assert "Read(8)" in text
    assert "Grep(4)" in text
    assert "Glob(3)" in text
    assert "18.5k in" in text
    assert "4.2k out" in text
    assert "$0.42" in text
    assert "\u2713" in text  # checkmark for complete


def test_format_subagent_detail_with_skills():
    """Verify skills_invoked appears in output when non-empty."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Implement Feature",
        subagent_type="general-purpose",
        model="sonnet",
        tool_counts={"Read": 2},
        input_tokens=5000,
        output_tokens=1000,
        cost=0.10,
        skills_invoked=["test-driven-development"],
        status="complete",
    )
    assert "Skills: test-driven-development" in text


def test_format_subagent_detail_no_skills():
    """Verify Skills line is omitted when skills_invoked is empty."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Quick Task",
        subagent_type="Explore",
        model="sonnet",
        tool_counts={"Read": 1},
        input_tokens=500,
        output_tokens=200,
        cost=0.01,
        skills_invoked=[],
        status="running",
    )
    assert "Skills" not in text
    assert "\u25d0" in text  # half-circle for running


def test_format_subagent_detail_tokens_below_1k():
    """Token formatting: tokens below 1000 should show as raw numbers."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Tiny Task",
        subagent_type="Explore",
        model="sonnet",
        tool_counts={},
        input_tokens=500,
        output_tokens=200,
        cost=0.01,
        skills_invoked=[],
        status="complete",
    )
    assert "500 in" in text
    assert "200 out" in text


def test_format_subagent_detail_top_5_tools():
    """Only top 5 tools should be shown, sorted by count."""
    text = format_subagent_detail_entry(
        timestamp="2026-02-07T10:00:00.000Z",
        description="Big Task",
        subagent_type="general-purpose",
        model="sonnet",
        tool_counts={"Read": 10, "Grep": 8, "Glob": 6, "Edit": 5, "Write": 3, "Bash": 1},
        input_tokens=50000,
        output_tokens=10000,
        cost=1.50,
        skills_invoked=[],
        status="complete",
    )
    assert "Read(10)" in text
    assert "Grep(8)" in text
    assert "Glob(6)" in text
    assert "Edit(5)" in text
    assert "Write(3)" in text
    assert "Bash(1)" not in text  # 6th tool should be excluded
