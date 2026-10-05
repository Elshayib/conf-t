"""Session-module seam tests for standing, Review queues, stats, submit, continue, resume."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from conf_t.models import Lesson, Task
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    ContinueTarget,
    ReviewEntry,
    Session,
    TURN_CORRECT,
    TURN_HINT,
    TURN_IGNORE,
    TURN_INCORRECT,
    TURN_LEAVE,
    TURN_SKIPPED,
    TurnResult,
    practice_summary,
)


def _task(
    task_id: str,
    expected: str = "^ok$",
    *,
    aliases: list[str] | None = None,
    hint: str = "h",
    explanation: str = "e",
) -> Task:
    return Task(
        id=task_id,
        prompt=f"Do {task_id}",
        prefix="$",
        expected=expected,
        aliases=aliases if aliases is not None else [],
        hint=hint,
        explanation=explanation,
    )


def _lesson(
    lesson_id: str = "l1",
    tasks: list[Task] | None = None,
    *,
    title: str | None = None,
    difficulty: str = "beginner",
    prerequisites: list[str] | None = None,
    platform: str = "Linux",
) -> Lesson:
    return Lesson(
        id=lesson_id,
        title=title if title is not None else "Lesson One",
        platform=platform,
        description="desc",
        tasks=tasks if tasks is not None else [_task(f"{lesson_id}__a"), _task(f"{lesson_id}__b")],
        difficulty=difficulty,
        prerequisites=prerequisites if prerequisites is not None else [],
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


def _session_at(path: Path, when: datetime) -> Session:
    return Session(progress_path=path, clock=when)


def test_late_pass_waits_1_then_3_then_7_days(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    entry = ReviewEntry(lesson_id="l1", task_id="l1__a")

    session = _session_at(path, start)
    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=False)
    assert session.due_review() == [entry]

    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []
    assert session.failed_queue() == [entry]

    day_1 = _session_at(path, start + timedelta(days=1))
    assert day_1.due_review() == [entry]
    day_1.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert day_1.due_review() == []

    day_4 = _session_at(path, start + timedelta(days=1 + 3))
    assert day_4.due_review() == [entry]
    day_4.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert day_4.due_review() == []

    day_11 = _session_at(path, start + timedelta(days=1 + 3 + 7))
    assert day_11.due_review() == [entry]
    day_11.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert day_11.due_review() == []
    assert day_11.failed_queue() == [entry]

    almost = start + timedelta(days=1 + 3 + 7 + 6)
    assert _session_at(path, almost).due_review() == []
    assert _session_at(path, almost + timedelta(days=1)).due_review() == [entry]


def test_due_review_lists_only_due_tasks_soonest_first(tmp_path: Path) -> None:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__later"), _task("l1__soon")])
    later, soon = lesson.tasks

    first = _session_at(path, start)
    first.record_attempt(lesson, later, correct=False, first_try=True, skipped=False)
    first.record_attempt(lesson, later, correct=True, first_try=False, skipped=False)

    midway = _session_at(path, start + timedelta(hours=12))
    midway.record_attempt(lesson, soon, correct=False, first_try=True, skipped=False)

    assert midway.due_review() == [ReviewEntry(lesson_id="l1", task_id="l1__soon")]
    assert midway.failed_queue() == [
        ReviewEntry(lesson_id="l1", task_id="l1__later"),
        ReviewEntry(lesson_id="l1", task_id="l1__soon"),
    ]

    later_on = _session_at(path, start + timedelta(hours=12) + timedelta(days=1))
    assert [entry.task_id for entry in later_on.due_review()] == ["l1__soon", "l1__later"]


def test_another_miss_or_skip_is_due_immediately(tmp_path: Path) -> None:
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    entry = ReviewEntry(lesson_id="l1", task_id="l1__a")

    session = _session_at(path, start)
    session.record_attempt(lesson, task, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert session.due_review() == []

    same_day = _session_at(path, start + timedelta(hours=1))
    assert same_day.due_review() == []
    same_day.record_attempt(lesson, task, correct=False, first_try=False, skipped=False)
    assert same_day.due_review() == [entry]
    assert same_day.failed_queue() == [entry]

    same_day.record_attempt(lesson, task, correct=True, first_try=False, skipped=False)
    assert same_day.due_review() == []

    still_waiting = _session_at(path, start + timedelta(hours=2))
    assert still_waiting.due_review() == []
    still_waiting.record_attempt(lesson, task, correct=False, first_try=False, skipped=True)
    assert still_waiting.due_review() == [entry]
    assert still_waiting.failed_queue() == [entry]


def test_reentering_drill_after_first_try_pass_goes_to_the_end(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    passed, other = lesson.tasks

    session.record_attempt(lesson, passed, correct=True, first_try=True, skipped=False)
    session.record_attempt(lesson, other, correct=False, first_try=True, skipped=False)
    session.record_attempt(lesson, passed, correct=False, first_try=False, skipped=False)

    assert session.failed_queue() == [
        ReviewEntry(lesson_id="l1", task_id="l1__b"),
        ReviewEntry(lesson_id="l1", task_id="l1__a"),
    ]

    reopened = Session(progress_path=tmp_path / "progress.json")
    assert reopened.failed_queue() == [
        ReviewEntry(lesson_id="l1", task_id="l1__b"),
        ReviewEntry(lesson_id="l1", task_id="l1__a"),
    ]


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


def test_old_file_first_try_pass_outranks_leftover_drill_entry(tmp_path: Path) -> None:
    """A pass wins over a drill entry; a drill entry with no record is due now."""
    progress_file = tmp_path / "progress.json"
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    waiting_until = datetime(2026, 6, 8, tzinfo=timezone.utc)
    legacy = {
        "progress_version": 4,
        "completed_lessons": ["done_l"],
        "attempted_lessons": ["done_l", "open_l"],
        "task_progress": {
            "open_l__pass": {
                "lesson_id": "open_l",
                "status": "passed",
                "passed_first_try": True,
                "attempts": 1,
                "review_level": 0,
            },
            "open_l__waiting": {
                "lesson_id": "open_l",
                "status": "failed",
                "passed_first_try": False,
                "attempts": 2,
                "review_level": 1,
                "next_review_at": waiting_until.isoformat(),
            },
        },
        "failed_tasks": [
            {"lesson_id": "open_l", "task_id": "open_l__pass"},
            {"lesson_id": "open_l", "task_id": "open_l__only"},
            {"lesson_id": "open_l", "task_id": "open_l__waiting"},
        ],
        "total_attempts": 8,
        "correct_first_try": 3,
        "skipped_count": 2,
        "platform_stats": {
            "Linux": {"attempts": 5, "correct_first_try": 2, "skipped": 1},
            "Cisco": {"attempts": 3, "correct_first_try": 1, "skipped": 1},
        },
    }
    progress_file.write_text(json.dumps(legacy), encoding="utf-8")

    session = Session(progress_path=progress_file, clock=when)
    lesson = _lesson(
        lesson_id="open_l",
        tasks=[
            _task("open_l__pass"),
            _task("open_l__only"),
            _task("open_l__waiting"),
        ],
    )
    passed = ReviewEntry(lesson_id="open_l", task_id="open_l__pass")
    only = ReviewEntry(lesson_id="open_l", task_id="open_l__only")
    waiting = ReviewEntry(lesson_id="open_l", task_id="open_l__waiting")

    assert passed not in session.due_review()
    assert passed not in session.failed_queue()
    assert only in session.due_review()
    assert only in session.failed_queue()
    assert waiting not in session.due_review()
    assert waiting in session.failed_queue()
    assert session.lesson_standing(lesson).passed == 1

    stats = session.stats()
    assert stats.completed_lessons == 1
    assert stats.total_attempts == 8
    assert stats.correct_first_try == 3
    assert stats.skipped == 2
    assert stats.by_platform["Linux"].attempts == 5
    assert stats.by_platform["Linux"].correct_first_try == 2
    assert stats.by_platform["Linux"].skipped == 1
    assert stats.by_platform["Cisco"].attempts == 3
    assert stats.by_platform["Cisco"].correct_first_try == 1
    assert stats.by_platform["Cisco"].skipped == 1

    reopened = Session(progress_path=progress_file, clock=when)
    assert passed not in reopened.due_review()
    assert passed not in reopened.failed_queue()
    assert only in reopened.due_review()
    assert waiting not in reopened.due_review()
    assert reopened.stats().total_attempts == 8
    assert reopened.stats().correct_first_try == 3


# --- submit turn ---


def test_blank_line_is_ignored_and_does_not_record(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "   ")

    assert result == TurnResult(kind=TURN_IGNORE)
    assert session.stats().total_attempts == 0
    assert session.failed_queue() == []


def test_hint_shows_text_without_recording_or_ending_first_try(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a", hint="try ok")])
    task = lesson.tasks[0]

    hinted = session.submit(lesson, task, "hint")
    assert hinted == TurnResult(kind=TURN_HINT, hint="try ok")
    assert session.stats().total_attempts == 0

    passed = session.submit(lesson, task, "ok")
    assert passed.kind == TURN_CORRECT
    assert passed.first_try is True
    assert passed.explanation == "e"


def test_hint_with_none_available_still_does_not_record(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a", hint="")])
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "HINT")
    assert result == TurnResult(kind=TURN_HINT, hint=None)
    assert session.stats().total_attempts == 0


def test_skip_records_reveals_readable_command_and_explanation(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[
            _task(
                "l1__a",
                expected=r"^show\s+ip\s+interface\s+brief$",
                aliases=["sh ip int br"],
                explanation="brief interfaces",
            )
        ]
    )
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "skip")

    assert result.kind == TURN_SKIPPED
    assert result.readable_command == "sh ip int br"
    assert result.explanation == "brief interfaces"
    assert session.failed_queue() == [ReviewEntry(lesson_id="l1", task_id="l1__a")]
    assert session.stats().skipped == 1
    assert session.stats().total_attempts == 1


def test_miss_stays_on_task_and_later_correct_is_not_first_try(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]

    missed = session.submit(lesson, task, "nope")
    assert missed.kind == TURN_INCORRECT
    assert session.failed_queue() == [ReviewEntry(lesson_id="l1", task_id="l1__a")]

    blank = session.submit(lesson, task, "")
    assert blank.kind == TURN_IGNORE

    hinted = session.submit(lesson, task, "hint")
    assert hinted.kind == TURN_HINT

    late = session.submit(lesson, task, "ok")
    assert late.kind == TURN_CORRECT
    assert late.first_try is False
    assert late.explanation == "e"
    assert session.lesson_standing(lesson).passed == 0


def test_first_graded_correct_passes_and_shows_explanation(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a", explanation="because ok")])
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "ok")

    assert result == TurnResult(
        kind=TURN_CORRECT,
        explanation="because ok",
        first_try=True,
    )
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue() == []


def test_exit_leave_request_records_nothing_when_not_the_answer(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.submit(lesson, task, "nope")

    leave = session.submit(lesson, task, "exit")
    assert leave == TurnResult(kind=TURN_LEAVE)
    assert session.stats().total_attempts == 1

    # Leave is only a request; cancelling keeps the same confrontation.
    late = session.submit(lesson, task, "ok")
    assert late.kind == TURN_CORRECT
    assert late.first_try is False


def test_begin_task_restores_first_try_for_a_new_sitting(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.submit(lesson, task, "nope")
    session.submit(lesson, task, "exit")

    session.begin_task(task)
    result = session.submit(lesson, task, "ok")
    assert result.kind == TURN_CORRECT
    assert result.first_try is True


def test_quit_that_task_accepts_is_graded_not_leave(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a", expected="^quit$")])
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "quit")
    assert result.kind == TURN_CORRECT
    assert result.first_try is True
    assert session.lesson_standing(lesson).passed == 1


def test_exit_that_task_accepts_is_graded_not_leave(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a", expected="^exit$")])
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "exit")
    assert result.kind == TURN_CORRECT
    assert result.first_try is True
    assert session.failed_queue() == []


def test_case_rules_and_aliases_follow_platform(tmp_path: Path) -> None:
    session = _session(tmp_path)
    cisco = Lesson(
        id="cisco_l",
        title="Cisco",
        platform="Cisco",
        description="d",
        tasks=[
            _task("cisco_l__a", expected="^configure terminal$"),
            _task("cisco_l__b", expected="^unused$", aliases=["CONF T"]),
        ],
    )
    powershell = Lesson(
        id="ps_l",
        title="PS",
        platform="PowerShell",
        description="d",
        tasks=[_task("ps_l__a", expected="^Get-Service$", aliases=["GSV"])],
    )
    linux = Lesson(
        id="linux_l",
        title="Linux",
        platform="Linux",
        description="d",
        tasks=[_task("linux_l__a", expected="^pwd$")],
    )
    git = Lesson(
        id="git_l",
        title="Git",
        platform="Git",
        description="d",
        tasks=[_task("git_l__a", expected="^git status$")],
    )

    assert session.submit(cisco, cisco.tasks[0], "CONFIGURE TERMINAL").kind == TURN_CORRECT
    assert session.submit(cisco, cisco.tasks[1], "conf t").kind == TURN_CORRECT
    assert session.submit(powershell, powershell.tasks[0], "get-service").kind == TURN_CORRECT
    session.begin_task(powershell.tasks[0])
    assert session.submit(powershell, powershell.tasks[0], "gsv").kind == TURN_CORRECT

    assert session.submit(linux, linux.tasks[0], "PWD").kind == TURN_INCORRECT
    assert session.submit(linux, linux.tasks[0], "pwd").kind == TURN_CORRECT
    assert session.submit(git, git.tasks[0], "GIT STATUS").kind == TURN_INCORRECT
    assert session.submit(git, git.tasks[0], "git status").kind == TURN_CORRECT


def test_broken_pattern_falls_through_to_aliases(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[
            _task(
                "l1__a",
                expected="[unterminated",
                aliases=["safe alias"],
            )
        ]
    )
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "safe alias")
    assert result.kind == TURN_CORRECT
    assert result.first_try is True


def test_practice_summary_comes_from_sitting_turn_results(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[
            _task("l1__a"),
            _task("l1__b"),
            _task("l1__c"),
        ]
    )
    results = [
        session.submit(lesson, lesson.tasks[0], "ok"),
        session.submit(lesson, lesson.tasks[1], "nope"),
        session.submit(lesson, lesson.tasks[1], "ok"),
        session.submit(lesson, lesson.tasks[2], "skip"),
    ]

    summary = practice_summary(results, total_tasks=3)
    assert summary.total_questions == 3
    assert summary.correct_first_try == 1
    assert summary.skipped_count == 1
    assert summary.total_attempts == 4


def test_opening_practice_via_submit_path_still_marks_in_progress(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.mark_practice_opened(lesson)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS
    leave = session.submit(lesson, lesson.tasks[0], "quit")
    assert leave.kind == TURN_LEAVE
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS


# --- Review sitting on the same submit (#20) ---


def test_review_path_does_not_mark_in_progress_until_a_line_is_recorded(
    tmp_path: Path,
) -> None:
    """Review opens without mark_practice_opened; only a recorded line starts the Lesson."""
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]

    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED

    session.begin_task(task)
    assert session.submit(lesson, task, "   ").kind == TURN_IGNORE
    assert session.submit(lesson, task, "hint").kind == TURN_HINT
    assert session.submit(lesson, task, "exit").kind == TURN_LEAVE
    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.stats().total_attempts == 0

    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS


def test_review_first_try_pass_leaves_due_and_failed_queues(tmp_path: Path) -> None:
    """A clean Review pass (new sitting) clears the Task from both drills."""
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    entry = ReviewEntry(lesson_id="l1", task_id="l1__a")

    session.submit(lesson, task, "nope")
    assert session.due_review() == [entry]
    assert session.failed_queue() == [entry]

    session.begin_task(task)
    result = session.submit(lesson, task, "ok")

    assert result.kind == TURN_CORRECT
    assert result.first_try is True
    assert result.explanation == "e"
    assert session.due_review() == []
    assert session.failed_queue() == []


def test_review_late_pass_stays_in_failed_queue_and_is_not_due(tmp_path: Path) -> None:
    """A late Review pass reschedules; the Task stays in the failed queue."""
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    entry = ReviewEntry(lesson_id="l1", task_id="l1__a")

    session.begin_task(task)
    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT
    late = session.submit(lesson, task, "ok")

    assert late.kind == TURN_CORRECT
    assert late.first_try is False
    assert late.explanation == "e"
    assert session.due_review() == []
    assert session.failed_queue() == [entry]


def test_review_attempts_count_in_platform_lifetime_stats(tmp_path: Path) -> None:
    """Review recordings attribute attempts to the Task's Lesson Platform."""
    session = _session(tmp_path)
    cisco = Lesson(
        id="cisco_l",
        title="Cisco",
        platform="Cisco",
        description="d",
        tasks=[_task("cisco_l__a")],
    )
    task = cisco.tasks[0]

    session.begin_task(task)
    session.submit(cisco, task, "nope")
    session.submit(cisco, task, "skip")

    stats = session.stats()
    assert stats.total_attempts == 2
    assert stats.skipped == 1
    assert stats.by_platform["Cisco"].attempts == 2
    assert stats.by_platform["Cisco"].skipped == 1
    assert stats.by_platform["Cisco"].correct_first_try == 0


# --- continue choice (#21) ---


def test_continue_nowhere_when_no_lessons(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert session.continue_target([]) is None


def test_continue_sends_due_review_before_any_lesson(tmp_path: Path) -> None:
    session = _session(tmp_path)
    open_lesson = _lesson("open")
    session.mark_practice_opened(open_lesson)
    session.record_attempt(
        open_lesson, open_lesson.tasks[0], correct=False, first_try=True, skipped=False
    )

    target = session.continue_target([open_lesson])
    assert target == ContinueTarget(action="daily_review")
    assert session.due_review()  # due exists; continue must prefer it


def test_continue_resumes_last_unfinished_resumable_lesson(tmp_path: Path) -> None:
    session = _session(tmp_path)
    older = _lesson("older")
    newer = _lesson("newer")
    session.mark_practice_opened(older)
    session.mark_practice_opened(newer)

    target = session.continue_target([older, newer])
    assert target == ContinueTarget(action="lesson", lesson_id="newer")


def test_continue_skips_completed_lesson_when_resuming(tmp_path: Path) -> None:
    session = _session(tmp_path)
    done = _lesson("done")
    open_lesson = _lesson("open")
    session.record_attempt(done, done.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(done, done.tasks[1], correct=True, first_try=True, skipped=False)
    session.mark_practice_opened(open_lesson)
    assert session.lesson_standing(done).status == LESSON_STATUS_COMPLETED

    target = session.continue_target([done, open_lesson])
    assert target == ContinueTarget(action="lesson", lesson_id="open")


def test_continue_opens_recommended_when_nothing_unfinished(tmp_path: Path) -> None:
    session = _session(tmp_path)
    basic = _lesson("basic", title="Basic", difficulty="beginner")
    advanced = _lesson(
        "advanced",
        title="Advanced",
        difficulty="advanced",
        prerequisites=["basic"],
    )
    session.record_attempt(basic, basic.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(basic, basic.tasks[1], correct=True, first_try=True, skipped=False)

    target = session.continue_target([advanced, basic])
    assert target == ContinueTarget(action="lesson", lesson_id="advanced")


def test_recommended_within_platform_uses_full_catalog_for_prereqs(
    tmp_path: Path,
) -> None:
    """Practice menu walks one Platform but prereqs may live on another."""
    session = _session(tmp_path)
    linux_basic = _lesson(
        "linux_basic",
        title="Linux Basic",
        difficulty="beginner",
        platform="Linux",
    )
    cisco_next = _lesson(
        "cisco_next",
        title="Cisco Next",
        difficulty="beginner",
        platform="Cisco",
        prerequisites=["linux_basic"],
    )
    session.record_attempt(
        linux_basic, linux_basic.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        linux_basic, linux_basic.tasks[1], correct=True, first_try=True, skipped=False
    )

    # Candidates are Cisco-only; completed standing comes from the full catalog.
    assert session.recommended_lesson([cisco_next]) is None
    recommended = session.recommended_lesson(
        [cisco_next], catalog=[linux_basic, cisco_next]
    )
    assert recommended is not None
    assert recommended.id == "cisco_next"


def test_continue_recommended_skips_completed_and_unmet_prereqs(tmp_path: Path) -> None:
    session = _session(tmp_path)
    alpha = _lesson("alpha", title="Alpha", difficulty="beginner")
    bravo = _lesson(
        "bravo",
        title="Bravo",
        difficulty="intermediate",
        prerequisites=["alpha"],
    )
    charlie = _lesson("charlie", title="Charlie", difficulty="beginner")
    session.record_attempt(alpha, alpha.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(alpha, alpha.tasks[1], correct=True, first_try=True, skipped=False)

    # alpha completed → skip; bravo prereqs met but intermediate; charlie beginner unfinished
    target = session.continue_target([bravo, charlie, alpha])
    assert target == ContinueTarget(action="lesson", lesson_id="charlie")


def test_continue_recommended_follows_path_order_by_title(tmp_path: Path) -> None:
    session = _session(tmp_path)
    zebra = _lesson("zebra", title="Zebra", difficulty="beginner")
    apple = _lesson("apple", title="Apple", difficulty="beginner")

    target = session.continue_target([zebra, apple])
    assert target == ContinueTarget(action="lesson", lesson_id="apple")


def test_continue_opens_first_lesson_when_nothing_recommended(tmp_path: Path) -> None:
    session = _session(tmp_path)
    locked = _lesson(
        "locked",
        title="Locked",
        difficulty="beginner",
        prerequisites=["missing"],
    )
    later = _lesson(
        "later",
        title="Later",
        difficulty="advanced",
        prerequisites=["missing"],
    )

    target = session.continue_target([later, locked])
    assert target == ContinueTarget(action="lesson", lesson_id="locked")


def test_continue_does_not_recommend_a_completed_lesson(tmp_path: Path) -> None:
    session = _session(tmp_path)
    done = _lesson("done", title="Done", difficulty="beginner")
    next_lesson = _lesson("next", title="Next", difficulty="intermediate")
    session.record_attempt(done, done.tasks[0], correct=True, first_try=True, skipped=False)
    session.record_attempt(done, done.tasks[1], correct=True, first_try=True, skipped=False)

    target = session.continue_target([done, next_lesson])
    assert target == ContinueTarget(action="lesson", lesson_id="next")


def test_continue_skips_empty_opened_lesson_when_resuming(tmp_path: Path) -> None:
    """Opened empty Lessons are unfinished standing but have nothing to resume."""
    session = _session(tmp_path)
    empty = _lesson("empty", tasks=[])
    real = _lesson("real", title="Real")
    session.mark_practice_opened(real)
    session.mark_practice_opened(empty)

    target = session.continue_target([empty, real])
    assert target == ContinueTarget(action="lesson", lesson_id="real")


# --- resume, start over, prerequisites (#22) ---


def test_resume_offers_only_non_first_try_pass_tasks_in_lesson_order(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c"), _task("l1__d")]
    )
    session.record_attempt(
        lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        lesson, lesson.tasks[1], correct=False, first_try=True, skipped=False
    )
    session.record_attempt(
        lesson, lesson.tasks[1], correct=True, first_try=False, skipped=False
    )
    # tasks[2] and tasks[3] untouched — neither is a first-try pass

    resume = session.resume_tasks(lesson)

    assert [task.id for task in resume] == ["l1__b", "l1__c", "l1__d"]


def test_start_over_clears_lesson_records_failed_queue_and_completion(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(
        lesson, lesson.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        lesson, lesson.tasks[1], correct=False, first_try=True, skipped=False
    )
    assert session.failed_queue() == [ReviewEntry(lesson_id="l1", task_id="l1__b")]
    session.record_attempt(
        lesson, lesson.tasks[1], correct=True, first_try=True, skipped=False
    )
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED

    session.start_over(lesson)

    standing = session.lesson_standing(lesson)
    assert standing.status != LESSON_STATUS_COMPLETED
    assert standing.passed == 0
    assert session.resume_tasks(lesson) == list(lesson.tasks)
    assert session.failed_queue() == []
    assert session.due_review() == []
    assert session.stats().completed_lessons == 0


def test_start_over_leaves_other_lessons_drills_and_completion(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    target = _lesson("target", tasks=[_task("target__a"), _task("target__b")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a"), _task("keeper__b")])
    drill = _lesson("drill", tasks=[_task("drill__a")])

    session.record_attempt(
        target, target.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        target, target.tasks[1], correct=False, first_try=True, skipped=False
    )
    session.record_attempt(
        keeper, keeper.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        keeper, keeper.tasks[1], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        drill, drill.tasks[0], correct=False, first_try=True, skipped=False
    )
    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert ReviewEntry(lesson_id="drill", task_id="drill__a") in session.failed_queue()

    session.start_over(target)

    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(keeper).passed == 2
    assert session.failed_queue() == [
        ReviewEntry(lesson_id="drill", task_id="drill__a")
    ]
    assert session.due_review() == [
        ReviewEntry(lesson_id="drill", task_id="drill__a")
    ]
    assert session.stats().completed_lessons == 1
    assert session.lesson_standing(target).passed == 0
    assert (
        ReviewEntry(lesson_id="target", task_id="target__b")
        not in session.failed_queue()
    )


def test_missing_prerequisites_named_by_lesson_title(tmp_path: Path) -> None:
    session = _session(tmp_path)
    basics = _lesson("basics", title="Networking Basics")
    vlan = _lesson("vlan", title="VLAN Fundamentals", prerequisites=["basics"])
    routing = _lesson(
        "routing",
        title="Static Routing",
        prerequisites=["basics", "vlan"],
    )
    catalog = [basics, vlan, routing]

    assert session.missing_prerequisite_titles(routing, catalog) == [
        "Networking Basics",
        "VLAN Fundamentals",
    ]

    session.record_attempt(
        basics, basics.tasks[0], correct=True, first_try=True, skipped=False
    )
    session.record_attempt(
        basics, basics.tasks[1], correct=True, first_try=True, skipped=False
    )
    assert session.missing_prerequisite_titles(routing, catalog) == [
        "VLAN Fundamentals",
    ]
    assert session.missing_prerequisite_titles(vlan, catalog) == []


def test_learner_can_start_when_prerequisites_are_missing(tmp_path: Path) -> None:
    """Missing prerequisites are a warning only; Practice may still begin."""
    session = _session(tmp_path)
    basics = _lesson("basics", title="Networking Basics")
    advanced = _lesson(
        "advanced",
        title="Advanced",
        prerequisites=["basics"],
    )
    catalog = [basics, advanced]

    assert session.missing_prerequisite_titles(advanced, catalog) == [
        "Networking Basics",
    ]

    session.mark_practice_opened(advanced)
    result = session.submit(advanced, advanced.tasks[0], "ok")

    assert result.kind == TURN_CORRECT
    assert result.first_try is True
    assert session.lesson_standing(advanced).status == LESSON_STATUS_IN_PROGRESS
    assert session.lesson_standing(advanced).passed == 1

