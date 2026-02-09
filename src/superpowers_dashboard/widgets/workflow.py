"""Workflow timeline widget showing skill invocation history."""
from datetime import datetime
from textual.widgets import Static


def _parse_time(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return "??:??:??"


def format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)

def format_duration_minutes(seconds: float) -> str:
    if seconds < 60:
        return "<1m"
    minutes = int(seconds // 60)
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    return f"{minutes}m"

def _cost_bar(cost: float, max_cost: float, width: int = 14) -> str:
    if max_cost <= 0:
        return "\u2591" * width
    filled = int((cost / max_cost) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)

class WorkflowWidget(Static):
    """Displays vertical timeline of skill invocations."""

    def format_entry(self, index: int, skill_name: str, args: str, total_tokens: int, cost: float, duration_seconds: float, max_cost: float, is_active: bool, timestamp: str = "") -> str:
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        bar = _cost_bar(cost, max_cost)
        active_marker = " \u25cf" if is_active else ""
        args_display = f'"{args[:30]}..."' if len(args) > 30 else f'"{args}"' if args else ""
        num = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469"
        idx_char = num[index - 1] if 1 <= index <= 10 else f"({index})"
        time_str = _parse_time(timestamp) if timestamp else ""
        time_prefix = f"{time_str}  " if time_str else ""
        result = f"{time_prefix}{idx_char} {skill_name:<24} {tok_str:>6} tok  ${cost:.2f}\n"
        if args_display:
            result += f"   \u2503  {args_display}\n"
        result += f"   \u2503  {bar}  {dur_str}{active_marker}"
        return result

    def format_subagent_entry(self, description: str, total_tokens: int, cost: float, skills_invoked: list[str]) -> str:
        """Render a subagent dispatch entry in the workflow timeline."""
        tok_str = format_tokens(total_tokens)
        skills_line = ", ".join(skills_invoked) if skills_invoked else "(no skills)"
        result = f"\u25b6 {description:<24} {tok_str:>6} tok  ${cost:.2f}\n"
        result += f"  \u2514 {skills_line}"
        return result

    def format_overhead(self, input_tokens: int, output_tokens: int, cost: float, duration_seconds: float, tool_summary: str, timestamp: str = "") -> str:
        """Render an overhead segment (work done without any skill active)."""
        total_tokens = input_tokens + output_tokens
        tok_str = format_tokens(total_tokens)
        dur_str = format_duration_minutes(duration_seconds)
        time_str = _parse_time(timestamp) if timestamp else ""
        time_prefix = f"{time_str}  " if time_str else ""
        result = f"{time_prefix}   \u2500\u2500 no skill \u2500\u2500        {tok_str:>6} tok  ${cost:.2f}\n"
        if tool_summary:
            result += f"   \u2503  {tool_summary}\n"
        result += f"   \u2503  {dur_str}"
        return result

    def format_compaction(self, timestamp: str, kind: str, pre_tokens: int) -> str:
        """Render a compaction event in the timeline."""
        time_str = _parse_time(timestamp) if timestamp else ""
        time_prefix = f"{time_str}  " if time_str else ""
        label = "MICROCOMPACTION" if kind == "microcompaction" else "COMPACTION"
        return f"{time_prefix}   \u2500\u2500 {label} \u2500\u2500  {pre_tokens:,} tok"

    _ROLE_LABELS = {
        "implementer": "implement",
        "spec-reviewer": "spec-review",
        "code-reviewer": "quality",
        "explorer": "explore",
        "other": "agent",
    }

    _EXPECTED_ROLES = ["implementer", "spec-reviewer", "code-reviewer"]

    def format_subagent_row(self, role: str, total_tokens: int, cost: float, status: str, connector: str) -> str:
        """Render a single subagent row within a task group."""
        label = self._ROLE_LABELS.get(role, role)
        if status == "complete":
            icon = "\u2713"  # checkmark
            tok_str = format_tokens(total_tokens)
            return f"   \u2503    {connector} {label:<12} {tok_str:>6} tok  ${cost:.2f}  {icon}"
        elif status == "running":
            icon = "\u25cf"  # filled circle
            tok_str = format_tokens(total_tokens) if total_tokens > 0 else ""
            cost_str = f"${cost:.2f}" if cost > 0 else ""
            return f"   \u2503    {connector} {label:<12} {tok_str:>6}      {cost_str}  {icon}"
        else:  # pending
            icon = "\u25cb"  # open circle
            return f"   \u2503    {connector} {label:<12}                    {icon}"

    def format_task_group(self, group, is_last: bool = False) -> str:
        """Render a task group with its subagent rows."""
        branch = "\u2517\u2501" if is_last else "\u2523\u2501"  # box drawing
        total_cost = group.total_cost
        lines = [f"   {branch} Task {group.task_number}: {group.label:<20} ${total_cost:.2f}"]

        existing_roles = [s["role"] for s in group.subagents]
        all_rows = list(group.subagents)

        for expected_role in self._EXPECTED_ROLES:
            if expected_role not in existing_roles:
                all_rows.append({"role": expected_role, "total_tokens": 0, "cost": 0, "status": "pending"})

        for i, sa in enumerate(all_rows):
            is_last_row = i == len(all_rows) - 1
            connector = "\u2514" if is_last_row else "\u251c"  # corner or tee
            status = sa.get("status", "complete")
            lines.append(self.format_subagent_row(
                role=sa["role"],
                total_tokens=sa.get("total_tokens", 0),
                cost=sa.get("cost", 0),
                status=status,
                connector=connector,
            ))

        return "\n".join(lines)

    def update_timeline(self, entries: list[dict]):
        if not entries:
            self.update("  No skills invoked yet.")
            return
        max_cost = max(e.get("cost", 0) for e in entries)
        parts = []
        skill_index = 0
        for e in entries:
            kind = e.get("kind", "skill")
            timestamp = e.get("timestamp", "")
            if kind == "overhead":
                text = self.format_overhead(
                    input_tokens=e.get("input_tokens", 0),
                    output_tokens=e.get("output_tokens", 0),
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    tool_summary=e.get("tool_summary", ""),
                    timestamp=timestamp,
                )
            elif kind == "subagent":
                text = self.format_subagent_entry(
                    description=e.get("description", ""),
                    total_tokens=e.get("total_tokens", 0),
                    cost=e.get("cost", 0),
                    skills_invoked=e.get("skills_invoked", []),
                )
            elif kind == "compaction":
                text = self.format_compaction(
                    timestamp=timestamp,
                    kind=e.get("compaction_kind", "compaction"),
                    pre_tokens=e.get("pre_tokens", 0),
                )
            else:
                skill_index += 1
                text = self.format_entry(
                    index=skill_index,
                    skill_name=e["skill_name"],
                    args=e.get("args", ""),
                    total_tokens=e.get("total_tokens", 0),
                    cost=e.get("cost", 0),
                    duration_seconds=e.get("duration_seconds", 0),
                    max_cost=max_cost,
                    is_active=e.get("is_active", False),
                    timestamp=timestamp,
                )
                # Append task groups if present
                task_groups = e.get("task_groups")
                if task_groups:
                    sorted_groups = sorted(task_groups.values(), key=lambda g: g.task_number)
                    for i, group in enumerate(sorted_groups):
                        is_last = i == len(sorted_groups) - 1
                        text += "\n" + self.format_task_group(group, is_last=is_last)
            parts.append(text)
        separator = "\n   \u25bc\n"
        self.update(separator.join(parts))
