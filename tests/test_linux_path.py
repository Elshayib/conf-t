"""Final Linux curriculum through the real catalog and public Session (#33)."""

from dataclasses import replace
from pathlib import Path

from conf_t.acceptance import validate_input
from conf_t.engine import LessonLoader
from conf_t.models import Lesson
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    TURN_CORRECT,
    Session,
    TaskResult,
)


LINUX_LESSON_IDS = {
    "linux_basic",
    "linux_file_operations",
    "linux_text_processing",
    "linux_package_management",
    "linux_advanced",
    "linux_permissions_deep",
    "linux_users_groups",
    "linux_process_management",
    "linux_systemd",
    "linux_cron_scheduling",
    "linux_networking",
    "linux_shell_scripting",
    "linux_lvm_storage",
    "linux_firewall",
    "linux_troubleshooting_lab",
}


def linux_catalog() -> list[Lesson]:
    return [
        lesson for lesson in LessonLoader().load_all_lessons()
        if lesson.platform == "Linux"
    ]


def test_linux_path_reaches_every_lesson_with_completed_prerequisites(
    tmp_path: Path,
) -> None:
    lessons = linux_catalog()
    assert {lesson.id for lesson in lessons} == LINUX_LESSON_IDS
    assert sum(len(lesson.tasks) for lesson in lessons) == 146
    progress_path = tmp_path / "progress.json"
    session = Session(progress_path=progress_path)
    first = session.recommended_lesson(lessons)
    assert first is not None
    assert first.id == "linux_basic"
    assert first.prerequisites == []

    completed: set[str] = set()
    while len(completed) < len(lessons):
        lesson = session.recommended_lesson(lessons)
        assert lesson is not None, (
            f"Unreachable Lessons: {LINUX_LESSON_IDS - completed}"
        )
        assert lesson.id not in completed
        assert set(lesson.prerequisites) <= completed
        assert session.missing_prerequisite_titles(lesson, lessons) == []
        for task in lesson.tasks:
            # Command semantics are checked with manual-derived literals in
            # the topic tests. Recording a first-try pass walks the path
            # and does not invent a command.
            session.record_attempt(
                lesson, task, TaskResult.FIRST_TRY_PASS,
            )
        standing = session.lesson_standing(lesson)
        assert standing.status == LESSON_STATUS_COMPLETED
        completed.add(lesson.id)
        session = Session(progress_path=progress_path)

    assert completed == LINUX_LESSON_IDS
    assert session.recommended_lesson(lessons) is None


def test_repaired_lesson_preserves_passes_without_regrading_old_answers(
    tmp_path: Path,
) -> None:
    repaired = LessonLoader().get_lesson_by_id("linux_basic")
    assert repaired is not None
    # The old catalog accepted pagers for cat_syslog. Preserve a historical
    # pass even though the repaired Task specifically asks for GNU cat.
    legacy = replace(
        repaired,
        tasks=[
            replace(
                task,
                expected=r"^(cat\s+syslog|less\s+syslog|more\s+syslog)$",
                aliases=[],
            ) if task.id == "linux_basic__cat_syslog" else task
            for task in repaired.tasks
        ],
    )
    old_answers = {
        "linux_basic__pwd": "pwd",
        "linux_basic__ls_la": "ls -la",
        "linux_basic__mkdir": "mkdir backups",
        "linux_basic__cd_var_log": "cd /var/log",
        "linux_basic__cat_syslog": "less syslog",
        "linux_basic__rm_rf_temp": "rm -rf temp",
    }
    assert {task.id for task in legacy.tasks} == set(old_answers)
    progress_path = tmp_path / "progress.json"
    previous = Session(progress_path=progress_path)
    for task in legacy.tasks:
        result = previous.submit(legacy, task, old_answers[task.id])
        assert result.kind == TURN_CORRECT
        assert result.first_try
    assert previous.lesson_standing(legacy).status == LESSON_STATUS_COMPLETED

    current_cat = next(
        task for task in repaired.tasks if task.id == "linux_basic__cat_syslog"
    )
    assert not validate_input("less syslog", current_cat, "Linux")
    returning = Session(progress_path=progress_path)
    standing = returning.lesson_standing(repaired)
    assert standing.status == LESSON_STATUS_COMPLETED
    assert standing.passed == standing.total == 6
    assert returning.resume_tasks(repaired) == []
    assert returning.failed_queue() == []
