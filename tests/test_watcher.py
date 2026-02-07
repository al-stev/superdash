# tests/test_watcher.py
import json
from pathlib import Path
from superpowers_dashboard.watcher import SessionParser, SkillEvent, CompactionEvent


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


def test_parser_tracks_tool_counts():
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # Add a Read tool call
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/foo"}}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    assert parser.tool_counts["Skill"] == 1
    assert parser.tool_counts["Read"] == 1


def test_parser_detects_compaction():
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "compact_boundary",
        "compactMetadata": {"preTokens": 169162, "trigger": "auto"},
        "timestamp": "2026-02-07T08:14:37.918Z",
    }))
    assert len(parser.compactions) == 1
    assert parser.compactions[0].pre_tokens == 169162
    assert parser.compactions[0].kind == "compaction"


def test_parser_detects_microcompaction():
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "microcompact_boundary",
        "microcompactMetadata": {"preTokens": 50000, "trigger": "auto"},
        "timestamp": "2026-02-07T09:00:00.000Z",
    }))
    assert len(parser.compactions) == 1
    assert parser.compactions[0].pre_tokens == 50000
    assert parser.compactions[0].kind == "microcompaction"


def test_parser_tracks_both_compaction_types():
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "compact_boundary",
        "compactMetadata": {"preTokens": 169162, "trigger": "auto"},
        "timestamp": "2026-02-07T08:14:37.918Z",
    }))
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "microcompact_boundary",
        "microcompactMetadata": {"preTokens": 50000, "trigger": "auto"},
        "timestamp": "2026-02-07T09:00:00.000Z",
    }))
    assert len(parser.compactions) == 2
    assert parser.compactions[0].kind == "compaction"
    assert parser.compactions[1].kind == "microcompaction"


def test_parser_tracks_subagents():
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": "t1", "name": "Task", "input": {
                "description": "Implement config module",
                "subagent_type": "general-purpose",
                "model": "sonnet",
                "prompt": "Implement the config module..."
            }}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T06:00:00.000Z",
    }))
    assert len(parser.subagents) == 1
    assert parser.subagents[0].description == "Implement config module"
    assert parser.subagents[0].model == "sonnet"
    assert parser.subagents[0].subagent_type == "general-purpose"


def test_parser_accumulates_turn_duration():
    """turn_duration system entries should accumulate on the active skill's duration_ms."""
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # Simulate two turn_duration entries while brainstorming is active
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 30000,
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 45000,
        "timestamp": "2026-02-06T22:25:00.000Z",
    }))
    assert parser.skill_events[0].duration_ms == 75000


def test_parser_turn_duration_before_skill_goes_to_overhead():
    """turn_duration before any skill is active should go to overhead."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 10000,
        "timestamp": "2026-02-06T22:00:00.000Z",
    }))
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    assert parser.skill_events[0].duration_ms == 0
    assert parser.overhead_duration_ms == 10000
