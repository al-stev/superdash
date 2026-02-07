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


def test_stats_widget_shows_compaction_details():
    """Compactions should show individual events with token counts and type."""
    from superpowers_dashboard.watcher import CompactionEvent
    w = StatsWidget()
    compactions = [
        CompactionEvent(timestamp="2026-02-07T08:14:37.918Z", pre_tokens=169162, trigger="auto", kind="compaction"),
        CompactionEvent(timestamp="2026-02-07T09:00:00.000Z", pre_tokens=50000, trigger="auto", kind="microcompaction"),
    ]
    text = w.format_compactions(compactions)
    assert "Compactions" in text
    assert "169,162" in text
    assert "50,000" in text
    assert "compact" in text.lower()
    assert "micro" in text.lower()
