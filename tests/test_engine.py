import pytest
import tempfile
import json
import re
from pathlib import Path
from conf_t.models import Lesson, Task, SessionStats
from conf_t.engine import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    LessonLoader,
    ProgressManager,
    are_prerequisites_met,
    format_display_answer,
    get_lesson_status,
    get_missing_prerequisites,
    get_recommended_lesson,
    sort_lessons_by_curriculum,
    validate_input,
)

# 1. Tests for validate_input
def test_validate_input_cisco_case_insensitive():
    task = Task(
        id="test_task",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"]
    )
    # Cisco platform is case-insensitive
    assert validate_input("configure terminal", task, "Cisco") is True
    assert validate_input("CONFIGURE TERMINAL", task, "Cisco") is True
    assert validate_input("conf t", task, "Cisco") is True
    assert validate_input("CONF T", task, "Cisco") is True
    assert validate_input("wrong command", task, "Cisco") is False

def test_validate_input_linux_case_sensitive():
    task = Task(
        id="test_task",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=[]
    )
    # Linux platform is case-sensitive
    assert validate_input("pwd", task, "Linux") is True
    assert validate_input("PWD", task, "Linux") is False
    assert validate_input(" pwd ", task, "Linux") is True  # strip is applied

def test_validate_input_powershell_case_insensitive():
    task = Task(
        id="test_task",
        prompt="Get services",
        prefix="PS C:\\>",
        expected="^Get-Service$",
        aliases=["gsv"]
    )
    assert validate_input("get-service", task, "PowerShell") is True
    assert validate_input("GSV", task, "PowerShell") is True

def test_validate_input_fallback_exact_match():
    # If expected contains invalid regex, it should fallback to exact match (or try/except)
    task = Task(
        id="test_task",
        prompt="Command with bad regex",
        prefix="$",
        expected="[invalid-regex",
        aliases=[]
    )
    # fallback to exact match isn't explicitly tested if it catches re.error and passes,
    # but let's see how fallback works.
    # validate_input:
    # try:
    #     pattern = re.compile(task.expected, flags)
    #     if pattern.match(cleaned_input): return True
    # except re.error: pass
    # Since compile fails, it goes to aliases. Wait, it only falls back to aliases!
    # Let's check:
    # 2. Test against aliases list
    # so if regex is invalid, it falls back to matching aliases list.
    task_with_alias = Task(
        id="test_task",
        prompt="Command with bad regex",
        prefix="$",
        expected="[invalid-regex",
        aliases=["exact_cmd"]
    )
    assert validate_input("exact_cmd", task_with_alias, "Linux") is True

# 2. Tests for LessonLoader
def test_lesson_loader_empty_or_nonexistent_dir(tmp_path):
    loader = LessonLoader(lessons_dir=tmp_path / "nonexistent")
    assert loader.load_all_lessons() == []

def test_lesson_loader_save_and_load(tmp_path):
    loader = LessonLoader(lessons_dir=tmp_path)
    task = Task(id="t1", prompt="Prompt 1", prefix=">", expected="^cmd1$", aliases=[], hint="h1", explanation="e1")
    lesson = Lesson(id="test_lesson", title="Test Lesson", platform="Linux", description="Desc", tasks=[task])
    
    # Save lesson
    assert loader.save_lesson(lesson) is True
    
    # Load all
    lessons = loader.load_all_lessons()
    assert len(lessons) == 1
    assert lessons[0].id == "test_lesson"
    assert lessons[0].title == "Test Lesson"
    assert len(lessons[0].tasks) == 1
    assert lessons[0].tasks[0].prompt == "Prompt 1"
    
    # Get by ID
    retrieved = loader.get_lesson_by_id("test_lesson")
    assert retrieved is not None
    assert retrieved.id == "test_lesson"
    
    # Non-existent ID
    assert loader.get_lesson_by_id("nonexistent") is None

# 3. Tests for ProgressManager
def test_progress_manager_defaults(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    assert manager.data["completed_lessons"] == []
    assert manager.data["attempted_lessons"] == []
    assert manager.data["failed_tasks"] == []
    assert manager.data["total_attempts"] == 0
    assert manager.data["correct_first_try"] == 0

def test_progress_manager_record_attempt(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    
    # Record a correct first try
    manager.record_attempt(
        lesson_id="l1",
        platform="Linux",
        task_id="t1",
        is_correct=True,
        is_first_try=True,
        is_skipped=False
    )
    
    assert manager.data["total_attempts"] == 1
    assert manager.data["correct_first_try"] == 1
    assert manager.data["platform_stats"]["Linux"]["attempts"] == 1
    assert manager.data["platform_stats"]["Linux"]["correct_first_try"] == 1
    assert manager.data["failed_tasks"] == []
    
    # Record an incorrect attempt (not first try, not correct)
    manager.record_attempt(
        lesson_id="l1",
        platform="Linux",
        task_id="t2",
        is_correct=False,
        is_first_try=False,
        is_skipped=False
    )
    assert manager.data["total_attempts"] == 2
    assert manager.data["correct_first_try"] == 1
    assert {"lesson_id": "l1", "task_id": "t2"} in manager.data["failed_tasks"]

    # Record a correct attempt that resolves the failed task
    manager.record_attempt(
        lesson_id="l1",
        platform="Linux",
        task_id="t2",
        is_correct=True,
        is_first_try=False,
        is_skipped=False
    )
    assert manager.data["total_attempts"] == 3
    assert manager.data["correct_first_try"] == 1  # not first try, so remains 1
    assert {"lesson_id": "l1", "task_id": "t2"} not in manager.data["failed_tasks"]

def test_progress_manager_skipped_attempt(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    
    # Record a skip
    manager.record_attempt(
        lesson_id="l1",
        platform="Linux",
        task_id="t3",
        is_correct=False,
        is_first_try=True,
        is_skipped=True
    )
    assert manager.data["skipped_count"] == 1
    assert {"lesson_id": "l1", "task_id": "t3"} in manager.data["failed_tasks"]

def test_progress_manager_reset(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "t1", True, True, False)
    manager.mark_lesson_completed("l1")
    
    manager.reset_progress()
    assert manager.data["total_attempts"] == 0
    assert manager.data["completed_lessons"] == []

def test_format_display_answer_prefers_alias():
    task = Task(
        id="t1",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"],
    )
    assert format_display_answer(task, "Cisco") == "conf t"

def test_format_display_answer_strips_regex():
    task = Task(
        id="t1",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=[],
    )
    assert format_display_answer(task, "Linux") == "pwd"

def test_sort_lessons_by_curriculum_orders_by_difficulty():
    lessons = [
        Lesson(id="advanced", title="Advanced", platform="Linux", description="", difficulty="advanced", tasks=[]),
        Lesson(id="beginner", title="Basics", platform="Linux", description="", difficulty="beginner", tasks=[]),
        Lesson(id="intermediate", title="Middle", platform="Linux", description="", difficulty="intermediate", tasks=[]),
    ]
    ordered = sort_lessons_by_curriculum(lessons)
    assert [lesson.id for lesson in ordered] == ["beginner", "intermediate", "advanced"]

def test_prerequisite_helpers():
    lesson = Lesson(
        id="vlan",
        title="VLANs",
        platform="Cisco",
        description="",
        prerequisites=["cisco_basic", "cisco_interface_basics"],
        tasks=[],
    )
    assert get_missing_prerequisites(lesson, ["cisco_basic"]) == ["cisco_interface_basics"]
    assert are_prerequisites_met(lesson, ["cisco_basic", "cisco_interface_basics"]) is True

def test_get_lesson_status():
    assert get_lesson_status("l1", ["l1"], [], []) == LESSON_STATUS_COMPLETED
    assert get_lesson_status("l2", [], ["l2"], []) == LESSON_STATUS_IN_PROGRESS
    assert get_lesson_status("l3", [], [], ["l3"]) == LESSON_STATUS_IN_PROGRESS
    assert get_lesson_status("l4", [], [], []) == LESSON_STATUS_NOT_STARTED

def test_get_recommended_lesson():
    lessons = [
        Lesson(id="basic", title="Basic", platform="Cisco", description="", difficulty="beginner", tasks=[]),
        Lesson(
            id="vlan",
            title="VLAN",
            platform="Cisco",
            description="",
            difficulty="intermediate",
            prerequisites=["basic"],
            tasks=[],
        ),
        Lesson(
            id="ospf",
            title="OSPF",
            platform="Cisco",
            description="",
            difficulty="intermediate",
            prerequisites=["vlan"],
            tasks=[],
        ),
    ]
    assert get_recommended_lesson(lessons, []).id == "basic"
    assert get_recommended_lesson(lessons, ["basic"]).id == "vlan"
    assert get_recommended_lesson(lessons, ["basic", "vlan"]).id == "ospf"
    assert get_recommended_lesson(lessons, ["basic", "vlan", "ospf"]) is None

def test_mark_lesson_attempted(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.mark_lesson_attempted("lesson_a")
    assert "lesson_a" in manager.data["attempted_lessons"]
    manager.mark_lesson_attempted("lesson_a")
    assert manager.data["attempted_lessons"].count("lesson_a") == 1
