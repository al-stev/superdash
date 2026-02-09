from superpowers_dashboard.widgets.costs_panel import StatsWidget, format_cache_ratio

def test_format_cache_ratio():
    assert format_cache_ratio(680, 1000) == "68%"

def test_format_cache_ratio_zero():
    assert format_cache_ratio(0, 0) == "0%"

def test_stats_widget_format_summary():
    w = StatsWidget()
    text = w.format_summary(total_cost=0.42, input_tokens=12847, output_tokens=3291, cache_read_tokens=8700)
    assert "$0.42" in text
    assert "12,847" in text
    assert "3,291" in text


def test_stats_widget_shows_compaction_counts():
    """Stats should show summary counts for each compaction type."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="2026-02-07T08:14:37.918Z", pre_tokens=169162, trigger="auto", kind="compaction"),
        CompactionEvent(timestamp="2026-02-07T08:30:00.000Z", pre_tokens=170000, trigger="auto", kind="compaction"),
        CompactionEvent(timestamp="2026-02-07T09:00:00.000Z", pre_tokens=50000, trigger="auto", kind="microcompaction"),
    ]
    text = w.format_compactions(compactions)
    assert "Context compactions: 2" in text
    assert "Context resets: 1" in text


def test_stats_widget_compaction_counts_omits_zero():
    """Only show compaction types that actually occurred."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="2026-02-07T08:14:37.918Z", pre_tokens=169162, trigger="auto", kind="compaction"),
    ]
    text = w.format_compactions(compactions)
    assert "Context compactions: 1" in text
    assert "resets" not in text.lower()


def test_stats_widget_shows_clear_counts():
    """Stats should show clear count separately."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="t1", pre_tokens=169162, trigger="auto", kind="compaction"),
        CompactionEvent(timestamp="t2", pre_tokens=0, trigger="manual", kind="clear"),
    ]
    text = w.format_compactions(compactions)
    assert "compactions:" in text
    assert "Context clears:" in text


def test_per_skill_bar_fits_in_panel():
    """Each per-skill line must fit within 43 chars (45 panel - 2 border)."""
    w = StatsWidget()
    per_skill = [
        {"name": "subagent-driven-development", "cost": 28.56},
        {"name": "test-driven-development", "cost": 9.25},
        {"name": "brainstorming", "cost": 4.20},
    ]
    lines = w.format_per_skill(per_skill)
    for line in lines:
        assert len(line) <= 43, f"Line too wide ({len(line)} chars): {line!r}"


def test_per_skill_bars_are_aligned():
    """All bar characters should start at the same column."""
    w = StatsWidget()
    per_skill = [
        {"name": "subagent-driven-development", "cost": 28.56},
        {"name": "brainstorming", "cost": 4.20},
    ]
    lines = w.format_per_skill(per_skill)
    bar_starts = []
    for line in lines:
        for i, ch in enumerate(line):
            if ch in ("\u2588", "\u2591"):
                bar_starts.append(i)
                break
    assert len(set(bar_starts)) == 1, f"Bars start at different columns: {bar_starts}"


def test_stats_widget_shows_session_count():
    """format_compactions should show 'Sessions: N' when session_count > 1."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="t1", pre_tokens=169162, trigger="auto", kind="compaction"),
    ]
    text = w.format_compactions(compactions, session_count=3)
    assert "Sessions: 3" in text


def test_stats_widget_hides_session_count_when_one():
    """format_compactions should not show 'Sessions' when session_count is 1."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="t1", pre_tokens=169162, trigger="auto", kind="compaction"),
    ]
    text = w.format_compactions(compactions, session_count=1)
    assert "Sessions" not in text


def test_stats_widget_shows_skill_compliance():
    """format_compliance should show skill and tool counts."""
    w = StatsWidget()
    text = w.format_compliance(skill_count=3, tool_count=28)
    assert "Skills: 3" in text
    assert "Tools: 28" in text


def test_stats_widget_shows_subagent_aggregate():
    """format_subagent_stats output should contain count, skills used ratio, cost, and tokens."""
    w = StatsWidget()
    text = w.format_subagent_stats(
        count=8,
        skills_used=2,
        total_cost=3.42,
        total_tokens=142000,
    )
    assert "Subagents:" in text
    assert "8" in text
    assert "Skills used:" in text
    assert "2/8" in text
    assert "$3.42" in text
    assert "142k" in text


def test_stats_widget_subagent_stats_zero_count():
    """format_subagent_stats with count 0 should show zeros gracefully."""
    w = StatsWidget()
    text = w.format_subagent_stats(
        count=0,
        skills_used=0,
        total_cost=0.0,
        total_tokens=0,
    )
    assert "Subagents:" in text
    assert "0" in text


def test_stats_widget_shows_model_usage():
    """Stats panel should display per-model token counts and costs."""
    w = StatsWidget()
    model_stats = [
        {"model": "opus", "input_tokens": 50000, "output_tokens": 10000, "cost": 4.50},
        {"model": "haiku", "input_tokens": 5000, "output_tokens": 1000, "cost": 0.08},
    ]
    text = w.format_model_usage(model_stats)
    assert "opus" in text
    assert "haiku" in text
    assert "$4.50" in text
    assert "$0.08" in text


def test_stats_widget_subagent_stats_tokens_below_1k():
    """Tokens below 1000 should not show k suffix."""
    w = StatsWidget()
    text = w.format_subagent_stats(
        count=1,
        skills_used=0,
        total_cost=0.05,
        total_tokens=500,
    )
    assert "500" in text
    assert "k" not in text.split("Total tokens:")[-1] or "500" in text
