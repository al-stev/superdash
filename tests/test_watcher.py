# tests/test_watcher.py
import json
from pathlib import Path
from superpowers_dashboard.watcher import (
    SessionParser, SkillEvent, CompactionEvent, OverheadSegment,
    SubagentDetail, SubagentEvent,
    extract_agent_id, parse_subagent_transcript, find_subagent_file,
)


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


def test_find_latest_project_sessions(tmp_path):
    """When no CWD match, find_latest_project_sessions returns most recent project."""
    from superpowers_dashboard.watcher import find_latest_project_sessions
    import time

    # Older project
    old_dir = tmp_path / "-Users-al-old"
    old_dir.mkdir()
    old_session = old_dir / "old.jsonl"
    old_session.write_text('{"type":"user"}\n')

    time.sleep(0.05)  # ensure different mtime

    # Newer project
    new_dir = tmp_path / "-Users-al-new"
    new_dir.mkdir()
    new_session = new_dir / "new.jsonl"
    new_session.write_text('{"type":"user"}\n')

    sessions = find_latest_project_sessions(base_dir=tmp_path)
    assert len(sessions) == 1
    assert sessions[0] == new_session


def test_find_latest_project_sessions_empty(tmp_path):
    """Return empty list when no projects exist."""
    from superpowers_dashboard.watcher import find_latest_project_sessions
    sessions = find_latest_project_sessions(base_dir=tmp_path)
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


def test_parser_has_session_count():
    """SessionParser starts with session_count = 1."""
    parser = SessionParser()
    assert parser.session_count == 1


def test_find_project_sessions_excludes_subagents(tmp_path):
    """Subagent JSONL files in a subagents/ subdirectory are NOT included."""
    from superpowers_dashboard.watcher import find_project_sessions

    project_dir = tmp_path / "-Users-al-myproject"
    project_dir.mkdir()

    # Regular session file
    session = project_dir / "session1.jsonl"
    session.write_text('{"type":"user"}\n')

    # Subagent session file inside a subagents/ subdirectory
    subagents_dir = project_dir / "subagents"
    subagents_dir.mkdir()
    subagent_session = subagents_dir / "subagent1.jsonl"
    subagent_session.write_text('{"type":"user"}\n')

    sessions = find_project_sessions(
        base_dir=tmp_path,
        project_cwd="/Users/al/myproject",
    )
    assert len(sessions) == 1
    assert sessions[0] == session


def test_parse_subagent_transcript(tmp_path):
    """Parse a subagent JSONL file and verify tokens, tool_counts, and duration."""
    transcript = tmp_path / "agent-abc123.jsonl"
    lines = []
    # Assistant message with two tool_use blocks and usage
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/foo"}},
                {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/foo", "old_string": "a", "new_string": "b"}},
            ],
            "usage": {"input_tokens": 1000, "output_tokens": 200, "cache_read_input_tokens": 500, "cache_creation_input_tokens": 50},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))
    # Second assistant message with one tool
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "tool_use", "id": "t3", "name": "Read", "input": {"file_path": "/bar"}},
            ],
            "usage": {"input_tokens": 800, "output_tokens": 150, "cache_read_input_tokens": 300, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:01:00.000Z",
    }))
    # Turn duration
    lines.append(json.dumps({
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 5000,
        "timestamp": "2026-02-07T10:01:30.000Z",
    }))
    lines.append(json.dumps({
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 3000,
        "timestamp": "2026-02-07T10:02:00.000Z",
    }))
    transcript.write_text("\n".join(lines) + "\n")

    detail = parse_subagent_transcript(transcript)
    assert detail.agent_id == "abc123"
    assert detail.input_tokens == 1800  # 1000 + 800
    assert detail.output_tokens == 350  # 200 + 150
    assert detail.cache_read_tokens == 800  # 500 + 300
    assert detail.cache_write_tokens == 50  # 50 + 0
    assert detail.tool_counts == {"Read": 2, "Edit": 1}
    assert detail.duration_ms == 8000  # 5000 + 3000
    assert detail.skills_invoked == []


def test_parse_subagent_with_skill(tmp_path):
    """Subagent that invokes a Skill should have it in skills_invoked."""
    transcript = tmp_path / "agent-def456.jsonl"
    lines = []
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "superpowers:commit", "args": "-m 'fix'"}},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "ls"}},
            ],
            "usage": {"input_tokens": 500, "output_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "tool_use", "id": "t3", "name": "Skill", "input": {"skill": "review-pr"}},
            ],
            "usage": {"input_tokens": 300, "output_tokens": 80, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:01:00.000Z",
    }))
    transcript.write_text("\n".join(lines) + "\n")

    detail = parse_subagent_transcript(transcript)
    assert detail.agent_id == "def456"
    assert detail.skills_invoked == ["commit", "review-pr"]
    assert detail.tool_counts == {"Skill": 2, "Bash": 1}


def test_extract_agent_id_from_tool_result():
    """Extract agentId from typical tool_result text."""
    text = "agentId: a82030d (for resuming to continue this agent's work if needed)\nSome other output..."
    assert extract_agent_id(text) == "a82030d"


def test_extract_agent_id_no_match():
    """Return None for text without agentId."""
    assert extract_agent_id("No agent ID here") is None
    assert extract_agent_id("") is None


def test_find_subagent_file(tmp_path):
    """Find a subagent file when directory structure exists."""
    session_dir = tmp_path / "session123"
    subagents_dir = session_dir / "subagents"
    subagents_dir.mkdir(parents=True)
    agent_file = subagents_dir / "agent-abc123.jsonl"
    agent_file.write_text('{"type":"assistant"}\n')

    result = find_subagent_file(tmp_path, "session123", "abc123")
    assert result == agent_file


def test_find_subagent_file_missing(tmp_path):
    """Return None when subagent file doesn't exist."""
    # No directory at all
    assert find_subagent_file(tmp_path, "session123", "abc123") is None

    # Directory exists but no file
    session_dir = tmp_path / "session456"
    subagents_dir = session_dir / "subagents"
    subagents_dir.mkdir(parents=True)
    assert find_subagent_file(tmp_path, "session456", "xyz789") is None


def test_parser_extracts_agent_id_from_tool_result():
    """Process a user entry with a tool_result containing agentId text (string content).

    The parser should populate agent_id_map with tool_use_id -> agent_id.
    """
    parser = SessionParser()
    # First, create a subagent dispatch so we have a tool_use_id
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": "toolu_task1", "name": "Task", "input": {
                "description": "Implement feature X",
                "subagent_type": "general-purpose",
                "model": "sonnet",
            }}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-07T10:00:00.000Z",
    }))
    # Now process the user entry containing the tool_result with agentId
    parser.process_line(json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_task1",
                "content": "agentId: a82030d (for resuming to continue this agent's work if needed)\nTask completed successfully.",
            }],
        },
        "timestamp": "2026-02-07T10:05:00.000Z",
    }))
    assert parser.agent_id_map == {"toolu_task1": "a82030d"}


def test_parser_handles_tool_result_list_content():
    """Process a tool_result where content is a list of dicts with text.

    The parser should still extract the agent_id from the joined text.
    """
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_task2",
                "content": [
                    {"type": "text", "text": "Task result: success."},
                    {"type": "text", "text": "agentId: b93141e (for resuming)"},
                ],
            }],
        },
        "timestamp": "2026-02-07T10:10:00.000Z",
    }))
    assert parser.agent_id_map == {"toolu_task2": "b93141e"}


def test_parser_detects_hook_events():
    """A progress entry with hook_progress type should be tracked in hook_events."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "progress",
        "data": {
            "type": "hook_progress",
            "hookEventName": "PreToolUse",
            "hookType": "pre_tool_use",
        },
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.hook_events) == 1
    assert parser.hook_events[0]["event"] == "PreToolUse"
    assert parser.hook_events[0]["hook_type"] == "pre_tool_use"
    assert parser.hook_events[0]["timestamp"] == "2026-02-07T12:00:00.000Z"


def test_parser_ignores_non_hook_progress():
    """A progress entry with a non-hook type should NOT create a hook event."""
    parser = SessionParser()
    parser.process_line(json.dumps({
        "type": "progress",
        "data": {
            "type": "tool_progress",
            "toolName": "Bash",
        },
        "timestamp": "2026-02-07T12:00:00.000Z",
    }))
    assert len(parser.hook_events) == 0


def test_subagent_event_has_role_field():
    """SubagentEvent should have a role field defaulting to empty string."""
    event = SubagentEvent(
        timestamp="2026-02-07T10:00:00Z",
        description="Implement Task 1: Fix bug",
        subagent_type="general-purpose",
        model="inherit",
    )
    assert event.role == ""
