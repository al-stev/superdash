from superpowers_dashboard.widgets.hooks_panel import HooksWidget, parse_hooks_config


def test_parse_hooks_config_from_dict():
    """Parse a dict with UserPromptSubmit and PreToolUse hooks."""
    hooks_dict = {
        "UserPromptSubmit": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/hooks/skill-check.sh",
                    }
                ],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Edit|Write|Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/hooks/warn-no-skill.sh",
                    }
                ],
            }
        ],
    }
    result = parse_hooks_config(hooks_dict, source="user config")
    assert len(result) == 2

    # Check UserPromptSubmit entry
    ups = [h for h in result if h["event"] == "UserPromptSubmit"]
    assert len(ups) == 1
    assert ups[0]["source"] == "user config"
    assert ups[0]["matcher"] == ""
    assert ups[0]["command"] == "skill-check.sh"

    # Check PreToolUse entry
    ptu = [h for h in result if h["event"] == "PreToolUse"]
    assert len(ptu) == 1
    assert ptu[0]["matcher"] == "Edit|Write|Bash"
    assert ptu[0]["command"] == "warn-no-skill.sh"
    assert ptu[0]["source"] == "user config"


def test_parse_hooks_config_empty():
    """Empty dict returns empty list."""
    result = parse_hooks_config({}, source="test")
    assert result == []


def test_hooks_widget_format():
    """Widget formats hooks for display, check event names and source appear."""
    w = HooksWidget()
    hooks = [
        {"event": "SessionStart", "matcher": "startup|resume", "command": "session-start.sh", "source": "superpowers"},
        {"event": "UserPromptSubmit", "matcher": "", "command": "skill-check.sh", "source": "user config"},
    ]
    text = w.format_hooks(hooks)
    assert "SessionStart" in text
    assert "superpowers" in text
    assert "session-start.sh" in text
    assert "UserPromptSubmit" in text
    assert "user config" in text
    assert "skill-check.sh" in text


def test_hooks_widget_no_hooks():
    """Empty hooks shows 'no hooks' message."""
    w = HooksWidget()
    text = w.format_hooks([])
    assert "No hooks configured" in text
