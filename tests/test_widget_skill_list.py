from superpowers_dashboard.widgets.skill_list import SkillListWidget

def test_skill_list_format_available():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "available")
    assert "brainstorming" in line
    assert ">>" not in line
    assert "*" not in line

def test_skill_list_format_active():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "active")
    assert ">>" in line
    assert "brainstorming" in line

def test_skill_list_format_used():
    w = SkillListWidget()
    line = w.format_skill("brainstorming", "used")
    assert "*" in line
    assert "brainstorming" in line
