"""Skill list widget showing all skills with status indicators."""
from textual.widgets import Static
from textual.reactive import reactive

STATE_ICONS = {
    "active": "\u25c6",   # ◆
    "used": "\u25cf",      # ●
    "available": "\u25cb", # ○
}

class SkillListWidget(Static):
    """Displays all skills with active/used/available status."""
    skills_data: reactive[dict] = reactive(dict)

    def format_skill(self, name: str, state: str) -> str:
        icon = STATE_ICONS.get(state, "\u25cb")
        return f"  {icon} {name}"

    def update_skills(self, all_skills: list[str], active: str | None, used: set[str]):
        lines = []
        for name in all_skills:
            if name == active:
                state = "active"
            elif name in used:
                state = "used"
            else:
                state = "available"
            lines.append(self.format_skill(name, state))
        self.skills_data = {"lines": lines, "active": active, "used": used}
        self.update("\n".join(lines))
