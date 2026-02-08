# tests/test_app_cost.py
"""Tests verifying that total cost includes both skill-event costs and overhead costs."""
import json

from superpowers_dashboard.costs import calculate_cost
from superpowers_dashboard.config import DEFAULT_PRICING
from superpowers_dashboard.watcher import SessionParser


def _make_skill_invocation(skill_name: str, args: str = "", timestamp: str = "2026-02-06T22:16:50.558Z", tool_use_id: str = "toolu_abc") -> list[str]:
    """Generate the 3-line JSONL sequence for a skill invocation."""
    lines = []
    lines.append(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "tool_use", "id": tool_use_id, "name": "Skill", "input": {"skill": f"superpowers:{skill_name}", "args": args}}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0},
        },
        "timestamp": timestamp,
    }))
    lines.append(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": f"Launching skill: superpowers:{skill_name}"}]},
        "toolUseResult": {"success": True, "commandName": f"superpowers:{skill_name}"},
        "timestamp": timestamp,
    }))
    lines.append(json.dumps({
        "type": "user",
        "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": f"# {skill_name}\n\nSkill content..."}]},
        "timestamp": timestamp,
        "sourceToolUseID": tool_use_id,
    }))
    return lines


def _make_assistant_message(input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0, timestamp: str = "2026-02-06T22:20:00.000Z") -> str:
    """Generate an assistant message JSONL line with given token counts."""
    return json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "response"}],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_write,
            },
        },
        "timestamp": timestamp,
    })


def test_overhead_tokens_contribute_to_cost():
    """Overhead tokens (no active skill) must produce a non-zero cost."""
    parser = SessionParser()
    # Feed an assistant message BEFORE any skill is invoked -> goes to overhead
    parser.process_line(_make_assistant_message(
        input_tokens=10_000, output_tokens=5_000, cache_read=2_000,
        timestamp="2026-02-06T22:00:00.000Z",
    ))

    assert parser.overhead_tokens["input"] == 10_000
    assert parser.overhead_tokens["output"] == 5_000
    assert parser.overhead_tokens["cache_read"] == 2_000

    overhead_cost = calculate_cost(
        "claude-opus-4-6",
        parser.overhead_tokens["input"],
        parser.overhead_tokens["output"],
        parser.overhead_tokens["cache_read"],
        parser.overhead_tokens.get("cache_write", 0),
        DEFAULT_PRICING,
    )
    # 10k input @ $5/M = $0.05, 5k output @ $25/M = $0.125, 2k cache_read @ $0.5/M = $0.001
    assert overhead_cost > 0
    assert abs(overhead_cost - 0.176) < 0.001


def test_total_cost_includes_skill_and_overhead():
    """Total cost must equal skill-event costs PLUS overhead costs."""
    parser = SessionParser()

    # 1) Overhead: assistant message before any skill
    parser.process_line(_make_assistant_message(
        input_tokens=20_000, output_tokens=10_000,
        timestamp="2026-02-06T22:00:00.000Z",
    ))

    # 2) Skill invocation
    for line in _make_skill_invocation("brainstorming", tool_use_id="t1", timestamp="2026-02-06T22:05:00.000Z"):
        parser.process_line(line)

    # 3) More tokens while skill is active
    parser.process_line(_make_assistant_message(
        input_tokens=5_000, output_tokens=2_000,
        timestamp="2026-02-06T22:10:00.000Z",
    ))

    pricing = DEFAULT_PRICING

    # Calculate skill-event costs (same way app.py does it)
    skill_costs = 0.0
    for event in parser.skill_events:
        model = next(iter(event.models), "claude-opus-4-6")
        skill_costs += calculate_cost(
            model, event.input_tokens, event.output_tokens,
            event.cache_read_tokens, event.cache_write_tokens, pricing,
        )

    # Calculate overhead cost
    overhead_cost = calculate_cost(
        "claude-opus-4-6",
        parser.overhead_tokens["input"],
        parser.overhead_tokens["output"],
        parser.overhead_tokens["cache_read"],
        parser.overhead_tokens.get("cache_write", 0),
        pricing,
    )

    total_cost = skill_costs + overhead_cost

    assert skill_costs > 0, "Skill events should have cost"
    assert overhead_cost > 0, "Overhead tokens should have cost"
    assert total_cost > skill_costs, "Total must exceed skill-only costs"
    assert abs(total_cost - (skill_costs + overhead_cost)) < 1e-9
