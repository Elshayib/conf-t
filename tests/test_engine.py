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
    PROGRESS_VERSION,
    REVIEW_INTERVALS_DAYS,
    TASK_STATUS_FAILED,
    TASK_STATUS_PASSED,
    TASK_STATUS_SKIPPED,
    LessonLoader,
    ProgressManager,
    _parse_iso_datetime,
    _utc_now,
    are_prerequisites_met,
    collect_all_tags,
    filter_lessons_by_tags,
    format_display_answer,
    lesson_matches_tags,
    parse_tags_csv,
    get_lesson_status,
    get_missing_prerequisites,
    get_recommended_lesson,
    is_task_progress_passed,
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
    assert manager.data["progress_version"] == PROGRESS_VERSION
    assert manager.data["completed_lessons"] == []
    assert manager.data["attempted_lessons"] == []
    assert manager.data["task_progress"] == {}
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
    assert manager.is_task_passed("t1") is True
    assert manager.data["task_progress"]["t1"]["status"] == TASK_STATUS_PASSED
    assert manager.data["task_progress"]["t1"]["passed_first_try"] is True
    
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

    # Correct on retry does not pass under first-try-only rules
    manager.record_attempt(
        lesson_id="l1",
        platform="Linux",
        task_id="t2",
        is_correct=True,
        is_first_try=False,
        is_skipped=False
    )
    assert manager.data["total_attempts"] == 3
    assert manager.data["correct_first_try"] == 1
    assert {"lesson_id": "l1", "task_id": "t2"} in manager.data["failed_tasks"]
    assert manager.is_task_passed("t2") is False
    assert manager.data["task_progress"]["t2"]["status"] == TASK_STATUS_FAILED

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
    assert manager.data["task_progress"]["t3"]["status"] == TASK_STATUS_SKIPPED
    assert manager.is_task_passed("t3") is False

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

def test_lesson_has_resume_state(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    lesson = Lesson(
        id="l1",
        title="Lesson",
        platform="Linux",
        description="",
        tasks=[
            Task(id="l1__a", prompt="A", prefix="$", expected="^a$"),
            Task(id="l1__b", prompt="B", prefix="$", expected="^b$"),
        ],
    )
    assert manager.lesson_has_resume_state(lesson) is False
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    assert manager.lesson_has_resume_state(lesson) is True
    manager.record_attempt("l1", "Linux", "l1__b", True, True, False)
    assert manager.lesson_has_resume_state(lesson) is False


def test_get_incomplete_tasks(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    tasks = [
        Task(id="l1__a", prompt="A", prefix="$", expected="^a$"),
        Task(id="l1__b", prompt="B", prefix="$", expected="^b$"),
    ]
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    incomplete = manager.get_incomplete_tasks(tasks)
    assert [task.id for task in incomplete] == ["l1__b"]


def test_reset_lesson_progress(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    manager.record_attempt("l1", "Linux", "l1__b", False, True, False)
    manager.mark_lesson_completed("l1")

    manager.reset_lesson_progress("l1", ["l1__a", "l1__b"])
    assert manager.get_task_progress_entry("l1__a") is None
    assert manager.get_task_progress_entry("l1__b") is None
    assert manager.data["failed_tasks"] == []
    assert "l1" not in manager.data["completed_lessons"]


def test_is_lesson_fully_passed(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    lesson = Lesson(
        id="l1",
        title="Lesson",
        platform="Linux",
        description="",
        tasks=[
            Task(id="l1__a", prompt="A", prefix="$", expected="^a$"),
            Task(id="l1__b", prompt="B", prefix="$", expected="^b$"),
        ],
    )
    assert manager.is_lesson_fully_passed(lesson) is False
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    assert manager.is_lesson_fully_passed(lesson) is False
    manager.record_attempt("l1", "Linux", "l1__b", True, True, False)
    assert manager.is_lesson_fully_passed(lesson) is True


def test_get_lesson_task_summary(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    manager.record_attempt("l1", "Linux", "l1__b", False, True, False)

    summary = manager.get_lesson_task_summary("l1", ["l1__a", "l1__b", "l1__c"])
    assert summary == {"passed": 1, "total": 3, "incomplete": 2}


def test_progress_migration_from_v0_2(tmp_path):
    progress_file = tmp_path / "progress.json"
    legacy = {
        "completed_lessons": ["cisco_basic"],
        "attempted_lessons": ["cisco_basic"],
        "failed_tasks": [
            {"lesson_id": "cisco_basic", "task_id": "cisco_basic__enable"},
            {"lesson_id": "cisco_vlan", "task_id": "cisco_vlan__create"},
        ],
        "total_attempts": 5,
        "correct_first_try": 2,
        "skipped_count": 1,
        "platform_stats": {"Cisco": {"attempts": 5, "correct_first_try": 2, "skipped": 1}},
    }
    progress_file.write_text(json.dumps(legacy), encoding="utf-8")

    manager = ProgressManager(filepath=progress_file)
    assert manager.data["progress_version"] == PROGRESS_VERSION
    assert manager.data["completed_lessons"] == ["cisco_basic"]
    assert manager.data["total_attempts"] == 5
    assert "cisco_basic__enable" in manager.data["task_progress"]
    assert manager.data["task_progress"]["cisco_basic__enable"]["status"] == TASK_STATUS_FAILED
    assert "cisco_vlan__create" in manager.data["task_progress"]
    reloaded = json.loads(progress_file.read_text(encoding="utf-8"))
    assert reloaded["progress_version"] == PROGRESS_VERSION
    assert "task_progress" in reloaded


def test_is_task_progress_passed_helper():
    assert is_task_progress_passed({"status": TASK_STATUS_PASSED, "passed_first_try": True})
    assert not is_task_progress_passed({"status": TASK_STATUS_PASSED, "passed_first_try": False})
    assert not is_task_progress_passed({"status": TASK_STATUS_FAILED, "passed_first_try": False})
    assert not is_task_progress_passed(None)


def test_fail_schedules_immediate_review(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "l1__a", False, True, False)
    entry = manager.get_task_progress_entry("l1__a")
    assert entry["review_level"] == 0
    assert entry["next_review_at"] is not None
    assert manager.is_task_due("l1__a") is True
    assert manager.get_due_review_count() == 1


def test_first_try_pass_clears_review_schedule(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "l1__a", False, True, False)
    manager.record_attempt("l1", "Linux", "l1__a", True, True, False)
    entry = manager.get_task_progress_entry("l1__a")
    assert entry["status"] == TASK_STATUS_PASSED
    assert "next_review_at" not in entry
    assert manager.get_due_review_count() == 0


def test_late_pass_bumps_review_interval(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.record_attempt("l1", "Linux", "l1__a", False, True, False)
    manager.record_attempt("l1", "Linux", "l1__a", True, False, False)
    entry = manager.get_task_progress_entry("l1__a")
    assert entry["review_level"] == 1
    due_at = _parse_iso_datetime(entry["next_review_at"])
    assert due_at > _utc_now()
    assert manager.is_task_due("l1__a") is False
    assert manager.get_due_review_count() == 0


def test_due_review_sorted_by_urgency(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.data["task_progress"] = {
        "t1": {
            "lesson_id": "l1",
            "status": TASK_STATUS_FAILED,
            "passed_first_try": False,
            "attempts": 1,
            "review_level": 0,
            "next_review_at": "2020-01-01T00:00:00+00:00",
        },
        "t2": {
            "lesson_id": "l1",
            "status": TASK_STATUS_FAILED,
            "passed_first_try": False,
            "attempts": 1,
            "review_level": 0,
            "next_review_at": "2021-01-01T00:00:00+00:00",
        },
    }
    manager.data["failed_tasks"] = [
        {"lesson_id": "l1", "task_id": "t1"},
        {"lesson_id": "l1", "task_id": "t2"},
    ]
    due = manager.get_due_review_entries()
    assert [entry["task_id"] for entry in due] == ["t1", "t2"]


def test_migration_v3_to_v4_schedules_non_passed(tmp_path):
    progress_file = tmp_path / "progress.json"
    legacy = {
        "progress_version": 3,
        "completed_lessons": [],
        "attempted_lessons": ["l1"],
        "task_progress": {
            "l1__a": {
                "lesson_id": "l1",
                "status": TASK_STATUS_FAILED,
                "passed_first_try": False,
                "attempts": 2,
                "last_attempt": "2026-01-01T00:00:00+00:00",
            }
        },
        "failed_tasks": [{"lesson_id": "l1", "task_id": "l1__a"}],
        "total_attempts": 2,
        "correct_first_try": 0,
        "skipped_count": 0,
        "platform_stats": {},
    }
    progress_file.write_text(json.dumps(legacy), encoding="utf-8")
    manager = ProgressManager(filepath=progress_file)
    assert manager.data["progress_version"] == PROGRESS_VERSION
    assert manager.data["task_progress"]["l1__a"]["next_review_at"] is not None
    assert manager.is_task_due("l1__a") is True


def test_review_interval_constants():
    assert REVIEW_INTERVALS_DAYS == [0, 1, 3, 7]


def test_parse_tags_csv():
    assert parse_tags_csv(None) == []
    assert parse_tags_csv("") == []
    assert parse_tags_csv("vlan, ospf, CCNA") == ["vlan", "ospf", "ccna"]


def test_filter_lessons_by_tags():
    lessons = [
        Lesson(
            id="vlan",
            title="VLAN",
            platform="Cisco",
            description="",
            tags=["vlan", "switching"],
            tasks=[],
        ),
        Lesson(
            id="ospf",
            title="OSPF",
            platform="Cisco",
            description="",
            tags=["ospf", "routing"],
            tasks=[],
        ),
    ]
    assert [lesson.id for lesson in filter_lessons_by_tags(lessons, ["vlan"])] == ["vlan"]
    assert [lesson.id for lesson in filter_lessons_by_tags(lessons, ["routing"])] == ["ospf"]
    assert len(filter_lessons_by_tags(lessons, ["vlan", "routing"])) == 0
    assert lesson_matches_tags(lessons[0], ["vlan", "switching"]) is True


def test_collect_all_tags():
    lessons = [
        Lesson(id="a", title="A", platform="Cisco", description="", tags=["vlan", "ccna"], tasks=[]),
        Lesson(id="b", title="B", platform="Cisco", description="", tags=["ospf", "ccna"], tasks=[]),
    ]
    assert collect_all_tags(lessons) == ["ccna", "ospf", "vlan"]


def test_mark_lesson_attempted(tmp_path):
    progress_file = tmp_path / "progress.json"
    manager = ProgressManager(filepath=progress_file)
    manager.mark_lesson_attempted("lesson_a")
    assert "lesson_a" in manager.data["attempted_lessons"]
    manager.mark_lesson_attempted("lesson_a")
    assert manager.data["attempted_lessons"].count("lesson_a") == 1
