# tests/test_watcher.py
import json
from pathlib import Path
from superpowers_dashboard.watcher import SessionParser, SkillEvent, CompactionEvent, OverheadSegment


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


def test_parser_tracks_last_context_tokens():
    """last_context_tokens should reflect the most recent turn's total input."""
    parser = SessionParser()
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)
    # The skill invocation assistant message has input_tokens=100, cache_read=200
    assert parser.last_context_tokens == 300

    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 5000, "output_tokens": 200, "cache_read_input_tokens": 45000, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))
    assert parser.last_context_tokens == 50000


def test_parser_detects_clear_command():
    """A /clear local_command should be tracked as a clear event."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "local_command",
        "content": '<command-name>/clear</command-name>\n            <command-message>clear</command-message>\n            <command-args></command-args>',
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.compactions) == 1
    assert parser.compactions[0].kind == "clear"
    assert parser.compactions[0].timestamp == "2026-02-07T12:00:00.000Z"


def test_parser_ignores_non_clear_local_commands():
    """Other local commands like /model should not be tracked as clears."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "system",
        "subtype": "local_command",
        "content": '<command-name>/model</command-name>\n            <command-message>model</command-message>\n            <command-args></command-args>',
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.compactions) == 0


def test_find_project_sessions_by_cwd(tmp_path):
    """Sessions should be found by matching CWD to Claude's directory naming."""
    from superpowers_dashboard.watcher import find_project_sessions
    project_dir = tmp_path / "-Users-al-myproject"
    project_dir.mkdir()
    session1 = project_dir / "session1.jsonl"
    session2 = project_dir / "session2.jsonl"
    session1.write_text('{"type":"user"}\n')
    session2.write_text('{"type":"user"}\n')

    other_dir = tmp_path / "-Users-al-other"
    other_dir.mkdir()
    (other_dir / "other.jsonl").write_text('{"type":"user"}\n')

    sessions = find_project_sessions(
        base_dir=tmp_path,
        project_cwd="/Users/al/myproject",
    )
    assert len(sessions) == 2
    assert all(s.parent == project_dir for s in sessions)


def test_find_project_sessions_no_match(tmp_path):
    """Return empty list when no sessions match the CWD."""
    from superpowers_dashboard.watcher import find_project_sessions
    project_dir = tmp_path / "-Users-al-other"
    project_dir.mkdir()
    (project_dir / "s.jsonl").write_text('{"type":"user"}\n')

    sessions = find_project_sessions(
        base_dir=tmp_path,
        project_cwd="/Users/al/myproject",
    )
    assert sessions == []


def test_parser_tracks_overhead_segments():
    """Overhead before first skill creates a segment with correct tokens and tool count."""
    parser = SessionParser()

    # Two assistant messages before any skill (overhead work)
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "tool_use", "id": "t0a", "name": "Read", "input": {"file_path": "/foo"}},
                {"type": "tool_use", "id": "t0b", "name": "Grep", "input": {"pattern": "bar"}},
            ],
            "usage": {"input_tokens": 300, "output_tokens": 100, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10},
        },
        "timestamp": "2026-02-06T22:00:00.000Z",
    }))
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "tool_use", "id": "t0c", "name": "Bash", "input": {"command": "ls"}},
            ],
            "usage": {"input_tokens": 200, "output_tokens": 80, "cache_read_input_tokens": 30, "cache_creation_input_tokens": 5},
        },
        "timestamp": "2026-02-06T22:01:00.000Z",
    }))

    # Now invoke a skill — this should finalize the overhead segment
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)

    assert len(parser.overhead_segments) == 1
    seg = parser.overhead_segments[0]
    assert isinstance(seg, OverheadSegment)
    assert seg.input_tokens == 500  # 300 + 200
    assert seg.output_tokens == 180  # 100 + 80
    assert seg.cache_read_tokens == 80  # 50 + 30
    assert seg.cache_write_tokens == 15  # 10 + 5
    assert seg.tool_count == 3  # Read, Grep, Bash
    assert seg.timestamp == "2026-02-06T22:00:00.000Z"

    # Existing overhead_tokens should still work
    assert parser.overhead_tokens["input"] == 500
    assert parser.overhead_tokens["output"] == 180


def test_parser_overhead_segment_between_skills():
    """Overhead gap between two skills creates a segment."""
    parser = SessionParser()

    # First skill
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1", timestamp="2026-02-06T22:00:00.000Z"):
        parser.process_line(line)

    # Clear active skill by having overhead work appear
    # (In real usage, once a new skill starts the old one moves to used_skills,
    #  but overhead happens when active_skill is set — we need to simulate
    #  a gap where no skill is active. We do this by setting active_skill = None.)
    parser.active_skill = None

    # Overhead assistant message in the gap
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "tool_use", "id": "t2a", "name": "Edit", "input": {"file_path": "/x", "old_string": "a", "new_string": "b"}},
            ],
            "usage": {"input_tokens": 400, "output_tokens": 150, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-06T22:15:00.000Z",
    }))

    # Second skill — should finalize the between-skills overhead segment
    for line in _make_skill_invocation("writing-plans", tool_use_id="t3", timestamp="2026-02-06T22:30:00.000Z"):
        parser.process_line(line)

    assert len(parser.overhead_segments) == 1
    seg = parser.overhead_segments[0]
    assert seg.input_tokens == 400
    assert seg.output_tokens == 150
    assert seg.tool_count == 1
    assert seg.timestamp == "2026-02-06T22:15:00.000Z"


def test_parser_no_overhead_segment_when_skill_active():
    """No overhead segment should be created while a skill is active."""
    parser = SessionParser()

    # Start a skill
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1"):
        parser.process_line(line)

    # Assistant messages while skill is active — should NOT create overhead segments
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [
                {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/bar"}},
            ],
            "usage": {"input_tokens": 500, "output_tokens": 200, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-06T22:20:00.000Z",
    }))

    assert len(parser.overhead_segments) == 0
    assert parser._current_overhead is None
