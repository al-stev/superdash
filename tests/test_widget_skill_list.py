from superpowers_dashboard.widgets.skill_list import SkillListWidget

def test_skill_list_format_available():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "available")
    assert "brainstorming" in line
    assert "\u25cb" in line  # ○

def test_skill_list_format_active():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "active")
    assert "\u25c6" in line  # ◆

def test_skill_list_format_used():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "used")
    assert "\u25cf" in line  # ●
