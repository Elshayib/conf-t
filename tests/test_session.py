"""Session-module seam tests for standing, Review queues, and stats (#17, #18)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from conf_t.models import Lesson, Task
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    ReviewEntry,
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


def test_first_try_pass_is_in_neither_due_review_nor_failed_queue(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    session.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)

    assert session.due_review() == []
    assert session.failed_queue() == []


def test_miss_is_due_now_and_in_failed_queue(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=False)

    due = session.due_review()
    failed = session.failed_queue()
    assert due == [ReviewEntry(lesson_id="l1", task_id="l1__a")]
    assert failed == [ReviewEntry(lesson_id="l1", task_id="l1__a")]


def test_skip_is_due_now_and_in_failed_queue(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=True)

    assert session.due_review() == [ReviewEntry(lesson_id="l1", task_id="l1__a")]
    assert session.failed_queue() == [ReviewEntry(lesson_id="l1", task_id="l1__a")]


def test_late_pass_stays_in_failed_queue_and_is_not_due(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)

    assert session.due_review() == []
    assert session.failed_queue() == [ReviewEntry(lesson_id="l1", task_id="l1__a")]


def test_late_pass_waits_1_then_3_then_7_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import conf_t.engine as engine

    clock = {"now": datetime(2026, 1, 1, tzinfo=timezone.utc)}

    def set_now(value: datetime) -> None:
        clock["now"] = value.replace(microsecond=0)

    monkeypatch.setattr(engine, "_utc_now", lambda: clock["now"])
    monkeypatch.setattr(engine, "_utc_now_iso", lambda: clock["now"].isoformat())

    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    entry = ReviewEntry(lesson_id="l1", task_id="l1__a")
    start = clock["now"]

    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=False)
    assert session.due_review() == [entry]

    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []
    assert session.failed_queue() == [entry]

    set_now(start + timedelta(days=1))
    assert session.due_review() == [entry]
    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []

    set_now(start + timedelta(days=1) + timedelta(days=3))
    assert session.due_review() == [entry]
    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []

    set_now(start + timedelta(days=1) + timedelta(days=3) + timedelta(days=7))
    assert session.due_review() == [entry]
    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []
    assert session.failed_queue() == [entry]

    almost = start + timedelta(days=1) + timedelta(days=3) + timedelta(days=7) + timedelta(days=6)
    set_now(almost)
    assert session.due_review() == []
    set_now(almost + timedelta(days=1))
    assert session.due_review() == [entry]


def test_due_review_lists_only_due_tasks_soonest_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import conf_t.engine as engine

    clock = {"now": datetime(2026, 6, 1, tzinfo=timezone.utc)}
    monkeypatch.setattr(engine, "_utc_now", lambda: clock["now"])
    monkeypatch.setattr(engine, "_utc_now_iso", lambda: clock["now"].isoformat())

    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__later"), _task("l1__soon")])
    later, soon = lesson.tasks

    session.record_attempt(lesson, later, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, later, correct=True, first_try=False, skipped=False)

    clock["now"] = clock["now"] + timedelta(hours=12)
    session.record_attempt(lesson, soon, correct=False, first_try=True, skipped=False)

    assert session.due_review() == [ReviewEntry(lesson_id="l1", task_id="l1__soon")]
    assert session.failed_queue() == [
        ReviewEntry(lesson_id="l1", task_id="l1__later"),
        ReviewEntry(lesson_id="l1", task_id="l1__soon"),
    ]

    clock["now"] = clock["now"] + timedelta(days=1)
    assert [entry.task_id for entry in session.due_review()] == ["l1__soon", "l1__later"]


def test_failed_queue_includes_tasks_that_are_not_due_yet(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__due"), _task("l1__waiting")])
    due_task, waiting = lesson.tasks

    session.record_attempt(lesson, due_task, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, waiting, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, waiting, correct=True, first_try=False, skipped=False)

    assert session.due_review() == [ReviewEntry(lesson_id="l1", task_id="l1__due")]
    assert session.failed_queue() == [
        ReviewEntry(lesson_id="l1", task_id="l1__due"),
        ReviewEntry(lesson_id="l1", task_id="l1__waiting"),
    ]


def test_stats_match_due_failed_and_lifetime_totals(tmp_path: Path) -> None:
    session = _session(tmp_path)
    linux = _lesson(
        lesson_id="linux_l",
        tasks=[_task("linux_l__a"), _task("linux_l__b")],
    )
    cisco = Lesson(
        id="cisco_l",
        title="Cisco Lesson",
        platform="Cisco",
        description="desc",
        tasks=[_task("cisco_l__a")],
    )

    session.record_attempt(linux, linux.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(linux, linux.tasks[1], correct=False, first_try=True, skipped=False)
    session.record_attempt(cisco, cisco.tasks[0], correct=False, first_try=True, skipped=True)

    stats = session.stats()
    assert stats.completed_lessons == 0
    assert stats.due_count == 2
    assert stats.failed_queue_size == 2
    assert stats.total_attempts == 3
    assert stats.correct_first_try == 1
    assert stats.skipped == 1
    assert stats.by_platform["Linux"].attempts == 2
    assert stats.by_platform["Linux"].correct_first_try == 1
    assert stats.by_platform["Linux"].skipped == 0
    assert stats.by_platform["Cisco"].attempts == 1
    assert stats.by_platform["Cisco"].correct_first_try == 0
    assert stats.by_platform["Cisco"].skipped == 1

    session.record_attempt(linux, linux.tasks[1], correct=True, first_try=True, skipped=False)
    assert session.stats().completed_lessons == 1
    assert session.stats().due_count == 1
    assert session.stats().failed_queue_size == 1


def test_full_reset_clears_standing_drills_stats_and_welcome(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    session.record_attempt(lesson, lesson.tasks[0], correct=False, first_try=True, skipped=False)
    session.dismiss_welcome()
    assert session.should_show_welcome() is False

    session.reset_all()

    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.due_review() == []
    assert session.failed_queue() == []
    stats = session.stats()
    assert stats.completed_lessons == 0
    assert stats.due_count == 0
    assert stats.failed_queue_size == 0
    assert stats.total_attempts == 0
    assert stats.correct_first_try == 0
    assert stats.skipped == 0
    assert stats.by_platform == {}
    assert session.should_show_welcome() is True


def test_welcome_shows_only_before_attempts_and_dismissal(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert session.should_show_welcome() is True

    session.dismiss_welcome()
    assert session.should_show_welcome() is False

    fresh = _session(tmp_path)
    # Same progress file: dismissal persists
    assert fresh.should_show_welcome() is False

    unused = _session(tmp_path / "other")
    assert unused.should_show_welcome() is True
    lesson = _lesson(tasks=[_task("l1__a")])
    unused.record_attempt(lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False)
    assert unused.should_show_welcome() is False


def test_older_progress_file_yields_same_passed_due_and_failed(tmp_path: Path) -> None:
    progress_file = tmp_path / "progress.json"
    legacy = {
        "progress_version": 2,
        "completed_lessons": ["done_l"],
        "attempted_lessons": ["done_l", "open_l"],
        "failed_tasks": [
            {"lesson_id": "open_l", "task_id": "open_l__miss"},
            {"lesson_id": "open_l", "task_id": "open_l__skip"},
        ],
        "total_attempts": 4,
        "correct_first_try": 2,
        "skipped_count": 1,
        "platform_stats": {
            "Linux": {"attempts": 4, "correct_first_try": 2, "skipped": 1}
        },
    }
    progress_file.write_text(json.dumps(legacy), encoding="utf-8")

    session = Session(progress_path=progress_file)
    open_lesson = _lesson(
        lesson_id="open_l",
        tasks=[_task("open_l__miss"), _task("open_l__skip"), _task("open_l__ok")],
    )

    assert session.failed_queue() == [
        ReviewEntry(lesson_id="open_l", task_id="open_l__miss"),
        ReviewEntry(lesson_id="open_l", task_id="open_l__skip"),
    ]
    assert {entry.task_id for entry in session.due_review()} == {
        "open_l__miss",
        "open_l__skip",
    }
    assert session.lesson_standing(open_lesson).passed == 0
    assert session.stats().due_count == 2
    assert session.stats().failed_queue_size == 2
    assert session.stats().total_attempts == 4
    assert session.stats().completed_lessons == 1
    assert "done_l" not in {entry.lesson_id for entry in session.failed_queue()}
