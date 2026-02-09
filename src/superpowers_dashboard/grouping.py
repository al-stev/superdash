"""Subagent role classification and task grouping."""
import re
from dataclasses import dataclass, field


def extract_task_number(description: str) -> int | None:
    """Extract task number from a description like 'Implement Task 3: ...'."""
    m = re.search(r"[Tt]ask\s+(\d+)", description)
    return int(m.group(1)) if m else None


@dataclass
class TaskGroup:
    """A group of subagents working on the same task."""
    task_number: int
    label: str
    subagents: list[dict] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(s.get("cost", 0) for s in self.subagents)


def build_task_groups(
    subagent_entries: list[dict],
) -> tuple[dict[int, TaskGroup], list[dict]]:
    """Group subagent entries by task number.

    Returns:
        (groups, ungrouped) where groups is {task_number: TaskGroup}
        and ungrouped is a list of entries without a task number.
    """
    groups: dict[int, TaskGroup] = {}
    ungrouped: list[dict] = []

    for entry in subagent_entries:
        desc = entry.get("description", "")
        stype = entry.get("subagent_type", "")
        role = classify_role(desc, stype)
        entry_with_role = {**entry, "role": role}

        # Detect status: has token data = complete, otherwise = running
        if entry.get("total_tokens", 0) > 0:
            entry_with_role["status"] = "complete"
        else:
            entry_with_role["status"] = "running"

        task_num = extract_task_number(desc)
        if task_num is None:
            ungrouped.append(entry_with_role)
            continue

        if task_num not in groups:
            label_match = re.search(r"[Tt]ask\s+\d+:\s*(.*)", desc)
            label = label_match.group(1).strip() if label_match else desc
            groups[task_num] = TaskGroup(task_number=task_num, label=label)

        groups[task_num].subagents.append(entry_with_role)

    return groups, ungrouped


def classify_role(description: str, subagent_type: str) -> str:
    """Classify a subagent's role from its description and type."""
    desc_lower = description.lower()
    if desc_lower.startswith("implement task"):
        return "implementer"
    if "spec compliance" in desc_lower:
        return "spec-reviewer"
    if "code-reviewer" in subagent_type or "code review" in desc_lower:
        return "code-reviewer"
    if subagent_type == "Explore":
        return "explorer"
    return "other"
