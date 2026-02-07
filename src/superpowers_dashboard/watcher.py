"""JSONL session watcher and parser for skill invocation detection."""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SkillEvent:
    """A single skill invocation with accumulated metrics."""
    skill_name: str
    args: str
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    models: set = field(default_factory=set)

    @property
    def start_time(self) -> datetime:
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


class SessionParser:
    """Parses JSONL lines and tracks skill state."""

    def __init__(self):
        self.skill_events: list[SkillEvent] = []
        self.active_skill: str | None = None
        self.used_skills: set[str] = set()
        self.overhead_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        self._pending_skill: dict | None = None

    def process_line(self, line: str):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return

        entry_type = entry.get("type")

        if entry_type == "assistant":
            self._process_assistant(entry)
        elif entry_type == "user":
            self._process_user(entry)

    def _process_assistant(self, entry: dict):
        message = entry.get("message", {})
        content = message.get("content", [])
        usage = message.get("usage", {})
        model = message.get("model", "")

        for item in content:
            if item.get("type") == "tool_use" and item.get("name") == "Skill":
                skill_input = item.get("input", {})
                skill_full = skill_input.get("skill", "")
                skill_name = skill_full.split(":")[-1] if ":" in skill_full else skill_full
                self._pending_skill = {
                    "skill_name": skill_name,
                    "args": skill_input.get("args", ""),
                    "timestamp": entry.get("timestamp", ""),
                    "tool_use_id": item.get("id", ""),
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                    "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
                    "model": model,
                }
                # Tokens from the invocation message will be attributed
                # to the SkillEvent when it is created, so skip accumulation.
                return

        self._accumulate_tokens(usage, model)

    def _process_user(self, entry: dict):
        if entry.get("isMeta") and self._pending_skill:
            if self.active_skill:
                self.used_skills.add(self.active_skill)
            skill = self._pending_skill
            event = SkillEvent(
                skill_name=skill["skill_name"],
                args=skill["args"],
                timestamp=skill["timestamp"],
                input_tokens=skill.get("input_tokens", 0),
                output_tokens=skill.get("output_tokens", 0),
                cache_read_tokens=skill.get("cache_read_tokens", 0),
                cache_write_tokens=skill.get("cache_write_tokens", 0),
            )
            model = skill.get("model", "")
            if model:
                event.models.add(model)
            self.skill_events.append(event)
            self.active_skill = skill["skill_name"]
            self._pending_skill = None

    def _accumulate_tokens(self, usage: dict, model: str):
        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)

        if self.skill_events and self.active_skill:
            event = self.skill_events[-1]
            event.input_tokens += input_tok
            event.output_tokens += output_tok
            event.cache_read_tokens += cache_read
            event.cache_write_tokens += cache_write
            if model:
                event.models.add(model)
        else:
            self.overhead_tokens["input"] += input_tok
            self.overhead_tokens["output"] += output_tok
            self.overhead_tokens["cache_read"] += cache_read
            self.overhead_tokens["cache_write"] += cache_write


def find_latest_session(base_dir: Path | None = None) -> Path | None:
    """Find the most recently modified session JSONL file."""
    if base_dir is None:
        base_dir = Path.home() / ".claude" / "projects"
    if not base_dir.exists():
        return None
    sessions = list(base_dir.glob("*/*.jsonl"))
    sessions = [s for s in sessions if "subagents" not in s.parts]
    if not sessions:
        return None
    return max(sessions, key=lambda p: p.stat().st_mtime)
