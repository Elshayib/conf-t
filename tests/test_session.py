"""Session-module seam tests for Learner standing (#17)."""

from pathlib import Path

from conf_t.models import Lesson, Task
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    Session,
)


def _task(task_id: str, expected: str = "^ok$") -> Task:
    return Task(
        id=task_id,
        prompt=f"Do {task_id}",
        prefix="$",
        expected=expected,
        aliases=[],
        hint="h",
        explanation="e",
    )


def _lesson(
    lesson_id: str = "l1",
    tasks: list[Task] | None = None,
) -> Lesson:
    return Lesson(
        id=lesson_id,
        title="Lesson One",
        platform="Linux",
        description="desc",
        tasks=tasks if tasks is not None else [_task(f"{lesson_id}__a"), _task(f"{lesson_id}__b")],
    )


def _session(tmp_path: Path) -> Session:
    return Session(progress_path=tmp_path / "progress.json")


def test_standing_not_started_when_untouched(tmp_path: Path) -> None:
    session = _session(tmp_path)
    standing = session.lesson_standing(_lesson())
    assert standing.status == LESSON_STATUS_NOT_STARTED
    assert standing.passed == 0
    assert standing.total == 2


def test_standing_completed_when_every_task_first_try_pass(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(lesson, lesson.tasks[1], correct=True, first_try=True, skipped=False)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_COMPLETED
    assert standing.passed == 2
    assert standing.total == 2


def test_standing_incomplete_when_any_task_not_first_try_pass(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(lesson, lesson.tasks[1], correct=False, first_try=True, skipped=False)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 1
    assert standing.total == 2


def test_standing_empty_lesson_is_not_completed(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[])
    session.mark_practice_opened(lesson)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 0
    assert standing.total == 0
    assert standing.status != LESSON_STATUS_COMPLETED


def test_standing_late_correct_does_not_complete(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    session.record_attempt(lesson, lesson.tasks[0], correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=False, skipped=False)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 0
    assert standing.total == 1


def test_last_first_try_pass_completes_from_practice_recording(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS

    session.record_attempt(lesson, lesson.tasks[1], correct=True, first_try=True, skipped=False)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED


def test_last_first_try_pass_completes_from_review_recording(tmp_path: Path) -> None:
    """Review recordings use the same session record path as Practice."""
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(lesson, lesson.tasks[1], correct=False, first_try=True, skipped=False)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS

    session.record_attempt(lesson, lesson.tasks[1], correct=True, first_try=True, skipped=False)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED


def test_list_and_menu_share_same_standing_counts(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)

    list_view = session.lesson_standing(lesson)
    menu_view = session.lesson_standing(lesson)
    assert list_view.status == menu_view.status == LESSON_STATUS_IN_PROGRESS
    assert list_view.passed == menu_view.passed == 1
    assert list_view.total == menu_view.total == 2


def test_opening_practice_marks_in_progress_before_answers(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.mark_practice_opened(lesson)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 0
    assert standing.total == 2
