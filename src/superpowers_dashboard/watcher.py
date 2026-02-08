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
    duration_ms: int = 0

    @property
    def start_time(self) -> datetime:
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class CompactionEvent:
    """A context compaction or microcompaction event."""
    timestamp: str
    pre_tokens: int
    trigger: str
    kind: str = "compaction"  # "compaction" or "microcompaction"


@dataclass
class SubagentEvent:
    """A subagent dispatch event."""
    timestamp: str
    description: str
    subagent_type: str
    model: str


@dataclass
class OverheadSegment:
    """A segment of work done without any skill active."""
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int = 0
    tool_count: int = 0


class SessionParser:
    """Parses JSONL lines and tracks skill state."""

    def __init__(self):
        self.skill_events: list[SkillEvent] = []
        self.active_skill: str | None = None
        self.used_skills: set[str] = set()
        self.overhead_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        self.overhead_duration_ms: int = 0
        self._pending_skill: dict | None = None
        self.tool_counts: dict[str, int] = {}
        self.compactions: list[CompactionEvent] = []
        self.subagents: list[SubagentEvent] = []
        self.last_context_tokens: int = 0
        self.overhead_segments: list[OverheadSegment] = []
        self._current_overhead: OverheadSegment | None = None
        self.session_count: int = 1

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
        elif entry_type == "system":
            self._process_system(entry)

    def _process_assistant(self, entry: dict):
        message = entry.get("message", {})
        content = message.get("content", [])
        usage = message.get("usage", {})
        model = message.get("model", "")

        # Track context window size from every assistant turn
        total_input = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        if total_input > 0:
            self.last_context_tokens = total_input

        for item in content:
            if item.get("type") != "tool_use":
                continue
            tool_name = item.get("name", "")

            # Track all tool usage
            if tool_name:
                self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1

            # Skill invocations
            if tool_name == "Skill":
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
                return

            # Subagent dispatches
            if tool_name == "Task":
                task_input = item.get("input", {})
                self.subagents.append(SubagentEvent(
                    timestamp=entry.get("timestamp", ""),
                    description=task_input.get("description", ""),
                    subagent_type=task_input.get("subagent_type", ""),
                    model=task_input.get("model", "inherit"),
                ))

        # Count overhead tools when no skill is active
        if not (self.skill_events and self.active_skill):
            tool_count = sum(1 for item in content if item.get("type") == "tool_use")
            if tool_count > 0:
                timestamp = entry.get("timestamp", "")
                if self._current_overhead is None:
                    self._current_overhead = OverheadSegment(timestamp=timestamp)
                self._current_overhead.tool_count += tool_count

        self._accumulate_tokens(usage, model, entry.get("timestamp", ""))

    def _process_user(self, entry: dict):
        if entry.get("isMeta") and self._pending_skill:
            # Finalize any current overhead segment before starting the skill
            if self._current_overhead is not None:
                self.overhead_segments.append(self._current_overhead)
                self._current_overhead = None

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

    def _process_system(self, entry: dict):
        subtype = entry.get("subtype", "")
        if subtype == "compact_boundary":
            meta = entry.get("compactMetadata", {})
            self.compactions.append(CompactionEvent(
                timestamp=entry.get("timestamp", ""),
                pre_tokens=meta.get("preTokens", 0),
                trigger=meta.get("trigger", "unknown"),
                kind="compaction",
            ))
        elif subtype == "microcompact_boundary":
            meta = entry.get("microcompactMetadata", {})
            self.compactions.append(CompactionEvent(
                timestamp=entry.get("timestamp", ""),
                pre_tokens=meta.get("preTokens", 0),
                trigger=meta.get("trigger", "unknown"),
                kind="microcompaction",
            ))
        elif subtype == "local_command":
            content = entry.get("content", "")
            if "<command-name>/clear</command-name>" in content:
                self.compactions.append(CompactionEvent(
                    timestamp=entry.get("timestamp", ""),
                    pre_tokens=0,
                    trigger="manual",
                    kind="clear",
                ))
        elif subtype == "turn_duration":
            duration = entry.get("durationMs", 0)
            if self.skill_events and self.active_skill:
                self.skill_events[-1].duration_ms += duration
            else:
                self.overhead_duration_ms += duration
                if self._current_overhead is None:
                    self._current_overhead = OverheadSegment(timestamp=entry.get("timestamp", ""))
                self._current_overhead.duration_ms += duration

    def _accumulate_tokens(self, usage: dict, model: str, timestamp: str = ""):
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

            # Also track on the current overhead segment
            if self._current_overhead is None:
                self._current_overhead = OverheadSegment(timestamp=timestamp)
            self._current_overhead.input_tokens += input_tok
            self._current_overhead.output_tokens += output_tok
            self._current_overhead.cache_read_tokens += cache_read
            self._current_overhead.cache_write_tokens += cache_write


def _cwd_to_project_dir_name(cwd: str) -> str:
    """Convert a working directory path to Claude's project directory name."""
    return cwd.replace("/", "-")


def find_project_sessions(base_dir: Path | None = None, project_cwd: str | None = None) -> list[Path]:
    """Find all session JSONL files for the given project directory.

    Matches CWD to Claude's project directory naming convention.
    Returns sessions sorted oldest-first.
    """
    if base_dir is None:
        base_dir = Path.home() / ".claude" / "projects"
    if not base_dir.exists():
        return []
    if project_cwd is None:
        project_cwd = str(Path.cwd())

    dir_name = _cwd_to_project_dir_name(project_cwd)
    project_dir = base_dir / dir_name
    if not project_dir.exists():
        return []

    sessions = list(project_dir.glob("*.jsonl"))
    sessions = [s for s in sessions if "subagents" not in s.parts]
    sessions.sort(key=lambda p: p.stat().st_mtime)
    return sessions
