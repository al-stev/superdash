"""Skill list widget showing all skills with status indicators."""
from rich.text import Text
from textual.widgets import Static
from textual.reactive import reactive


class SkillListWidget(Static):
    """Displays all skills with active/used/available status."""
    skills_data: reactive[dict] = reactive(dict)

    def format_skill(self, name: str, state: str) -> str:
        """Format a single skill line as plain text (for testing)."""
        if state == "active":
            return f"  >> {name}"
        elif state == "used":
            return f"  *  {name}"
        else:
            return f"     {name}"

    def update_skills(self, all_skills: list[str], active: str | None, used: set[str]):
        text = Text()
        for i, name in enumerate(all_skills):
            if name == active:
                state = "active"
            elif name in used:
                state = "used"
            else:
                state = "available"
            if i > 0:
                text.append("\n")
            if state == "active":
                text.append(f"  >> {name}", style="bold reverse")
            elif state == "used":
                text.append(f"  *  {name}", style="bold")
            else:
                text.append(f"     {name}", style="dim")
        self.skills_data = {"lines": [], "active": active, "used": used}
        self.update(text)
