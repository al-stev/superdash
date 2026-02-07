from superpowers_dashboard.widgets.activity import format_log_entry

def test_format_log_entry():
    text = format_log_entry(timestamp="2026-02-06T22:16:50.558Z", skill_name="brainstorming", args="Terminal UI for superpowers")
    assert "22:16" in text
    assert "brainstorming" in text

def test_format_log_entry_truncates_args():
    text = format_log_entry(timestamp="2026-02-06T22:16:50.558Z", skill_name="brainstorming", args="A" * 100)
    assert "..." in text
