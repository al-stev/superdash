"""Subagent role classification and task grouping."""
import re
from dataclasses import dataclass, field


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
