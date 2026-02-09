# tests/test_grouping.py
from superpowers_dashboard.grouping import classify_role


def test_classify_implementer():
    assert classify_role("Implement Task 1: Fix cost bug", "general-purpose") == "implementer"


def test_classify_implementer_case_insensitive():
    assert classify_role("implement task 3: overhead", "general-purpose") == "implementer"


def test_classify_spec_reviewer():
    assert classify_role("Review spec compliance Task 1", "general-purpose") == "spec-reviewer"


def test_classify_code_reviewer_by_type():
    assert classify_role("Final code review", "superpowers:code-reviewer") == "code-reviewer"


def test_classify_code_reviewer_by_description():
    assert classify_role("Final code review of all changes", "general-purpose") == "code-reviewer"


def test_classify_explorer():
    assert classify_role("Explore superpowers skills", "Explore") == "explorer"


def test_classify_other():
    assert classify_role("Calculate budget", "Bash") == "other"
