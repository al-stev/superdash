# tests/test_watcher.py
import json
from pathlib import Path
from superpowers_dashboard.watcher import SessionParser, SkillEvent


def _make_skill_invocation(skill_name: str, args: str = "", timestamp: str = "2026-02-06T22:16:50.558Z", tool_use_id: str = "toolu_abc") -> list[str]:
    """Generate the 3-line JSONL sequence for a skill invocation."""
    lines = []
    # Step 1: assistant tool_use
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": tool_use_id, "name": "Skill", "input": {"skill": f"superpowers:{skill_name}", "args": args}}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0},
        },
        "timestamp": timestamp,
    }))
    # Step 2: tool_result
    lines.append(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": f"Launching skill: superpowers:{skill_name}"}]},
        "toolUseResult": {"success": True, "commandName": f"superpowers:{skill_name}"},
        "timestamp": timestamp,
    }))
    # Step 3: isMeta
    lines.append(json.dumps({
        "type": "user",
        "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": f"# {skill_name}\n\nSkill content..."}]},
        "timestamp": timestamp,
        "sourceToolUseID": tool_use_id,
    }))
    return lines


def test_parser_detects_skill_invocation():
    parser = SessionParser()
    lines = _make_skill_invocation("brainstorming", args="test idea")
    for line in lines:
        parser.process_line(line)
    assert len(parser.skill_events) == 1
    event = parser.skill_events[0]
    assert event.skill_name == "brainstorming"
    assert event.args == "test idea"


def test_parser_tracks_active_skill():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", timestamp="2026-02-06T22:00:00.000Z"):
        parser.process_line(line)
    assert parser.active_skill == "brainstorming"


def test_parser_transitions_active_to_used():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", timestamp="2026-02-06T22:00:00.000Z", tool_use_id="t1"):
        parser.process_line(line)
    for line in _make_skill_invocation("writing-plans", timestamp="2026-02-06T22:30:00.000Z", tool_use_id="t2"):
        parser.process_line(line)
    assert parser.active_skill == "writing-plans"
    assert "brainstorming" in parser.used_skills


def test_parser_accumulates_tokens():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # Add an assistant message with tokens (attributed to brainstorming)
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 500, "output_tokens": 200, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    event = parser.skill_events[0]
    # 100 from invocation + 500 from response
    assert event.input_tokens == 600
    assert event.output_tokens == 250


def test_parser_handles_non_skill_lines():
    parser = SessionParser()
    parser.process_line(json.dumps({"type": "progress", "data": {"type": "hook_progress"}, "timestamp": "2026-02-06T22:00:00.000Z"}))
    assert len(parser.skill_events) == 0
    assert parser.active_skill is None
