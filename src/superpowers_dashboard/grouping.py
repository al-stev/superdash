"""Subagent role classification and task grouping."""
import re
from dataclasses import dataclass, field


def extract_task_number(description: str) -> int | None:
    """Extract task number from a description like 'Implement Task 3: ...'."""
    m = re.search(r"[Tt]ask\s+(\d+)", description)
    return int(m.group(1)) if m else None


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
