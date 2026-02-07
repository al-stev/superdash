from pathlib import Path
from superpowers_dashboard.registry import SkillRegistry


def test_load_skills_from_directory(fixtures_dir):
    registry = SkillRegistry(fixtures_dir / "skills")
    skills = registry.skills
    assert len(skills) == 2
    assert "brainstorming" in skills
    assert "writing-plans" in skills


def test_skill_has_name_and_description(fixtures_dir):
    registry = SkillRegistry(fixtures_dir / "skills")
    skill = registry.skills["brainstorming"]
    assert skill["name"] == "brainstorming"
    assert "intent" in skill["description"].lower() or "design" in skill["description"].lower()


def test_empty_directory(tmp_path):
    registry = SkillRegistry(tmp_path)
    assert registry.skills == {}


def test_nonexistent_directory(tmp_path):
    registry = SkillRegistry(tmp_path / "nope")
    assert registry.skills == {}
