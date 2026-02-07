"""Skill registry — reads SKILL.md frontmatter from superpowers plugin directory."""
import yaml
from pathlib import Path


class SkillRegistry:
    """Loads skill metadata from SKILL.md files."""

    def __init__(self, skills_dir: Path):
        self.skills: dict[str, dict] = {}
        self._load(skills_dir)

    def _load(self, skills_dir: Path):
        if not skills_dir.exists():
            return
        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            meta = self._parse_frontmatter(skill_file)
            if meta and "name" in meta:
                self.skills[meta["name"]] = meta

    def _parse_frontmatter(self, path: Path) -> dict | None:
        text = path.read_text()
        if not text.startswith("---"):
            return None
        end = text.index("---", 3)
        frontmatter = text[3:end].strip()
        return yaml.safe_load(frontmatter)
