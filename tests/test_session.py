"""Session-module seam tests for standing, Review queues, stats, submit, continue, resume, continuation."""

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conf_t.models import Lesson, Task
from conf_t.session import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    ANSWER_PICK,
    ANSWER_RESUME,
    ANSWER_START_OVER,
    PracticeAgain,
    PracticeChoice,
    PracticeTasks,
    PracticeUnsaved,
    ProgressRefusal,
    Session,
    TaskResult,
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
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_COMPLETED
    assert standing.passed == 2
    assert standing.total == 2


def test_standing_incomplete_when_any_task_not_first_try_pass(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)

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
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.CORRECT_NOT_FIRST_TRY)

    standing = session.lesson_standing(lesson)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 0
    assert standing.total == 1


def test_last_first_try_pass_completes_from_practice_recording(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS

    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED


def test_last_first_try_pass_completes_from_review_recording(tmp_path: Path) -> None:
    """Review recordings use the same session record path as Practice."""
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS

    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED


def test_list_and_menu_share_same_standing_counts(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)

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
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)

    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == []


def test_miss_is_due_now_and_in_failed_queue(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, TaskResult.INCORRECT)

    due = session.due_review([lesson])
    failed = session.failed_queue([lesson])
    assert due == [(lesson, task)]
    assert failed == [(lesson, task)]


def test_skip_is_due_now_and_in_failed_queue(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, TaskResult.SKIP)

    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]


def test_late_pass_stays_in_failed_queue_and_is_not_due(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    session.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)

    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == [(lesson, task)]


def _session_at(path: Path, when: datetime) -> Session:
    return Session(progress_path=path, clock=when)


def test_late_pass_waits_1_then_3_then_7_days(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    pair = (lesson, task)

    session = _session_at(path, start)
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    assert session.due_review([lesson]) == [pair]

    session.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == [pair]

    day_1 = _session_at(path, start + timedelta(days=1))
    assert day_1.due_review([lesson]) == [pair]
    day_1.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert day_1.due_review([lesson]) == []

    day_4 = _session_at(path, start + timedelta(days=1 + 3))
    assert day_4.due_review([lesson]) == [pair]
    day_4.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert day_4.due_review([lesson]) == []

    day_11 = _session_at(path, start + timedelta(days=1 + 3 + 7))
    assert day_11.due_review([lesson]) == [pair]
    day_11.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert day_11.due_review([lesson]) == []
    assert day_11.failed_queue([lesson]) == [pair]

    almost = start + timedelta(days=1 + 3 + 7 + 6)
    assert _session_at(path, almost).due_review([lesson]) == []
    assert _session_at(path, almost + timedelta(days=1)).due_review([lesson]) == [pair]


def test_due_review_lists_only_due_tasks_soonest_first(tmp_path: Path) -> None:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__later"), _task("l1__soon")])
    later, soon = lesson.tasks

    first = _session_at(path, start)
    first.record_attempt(lesson, later, TaskResult.INCORRECT)
    first.record_attempt(lesson, later, TaskResult.CORRECT_NOT_FIRST_TRY)

    midway = _session_at(path, start + timedelta(hours=12))
    midway.record_attempt(lesson, soon, TaskResult.INCORRECT)

    assert midway.due_review([lesson]) == [(lesson, soon)]
    assert midway.failed_queue([lesson]) == [(lesson, later), (lesson, soon)]

    later_on = _session_at(path, start + timedelta(hours=12) + timedelta(days=1))
    assert [task.id for _, task in later_on.due_review([lesson])] == [
        "l1__soon",
        "l1__later",
    ]


def test_due_review_omits_a_gone_task_and_keeps_next_review_time_order(
    tmp_path: Path,
) -> None:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    full = _lesson(tasks=[_task("l1__early"), _task("l1__middle"), _task("l1__late")])
    early, middle, late = full.tasks

    first = _session_at(path, start)
    first.record_attempt(full, early, TaskResult.INCORRECT)
    first.record_attempt(full, early, TaskResult.CORRECT_NOT_FIRST_TRY)

    second = _session_at(path, start + timedelta(days=1))
    second.record_attempt(full, middle, TaskResult.INCORRECT)
    second.record_attempt(full, middle, TaskResult.CORRECT_NOT_FIRST_TRY)

    third = _session_at(path, start + timedelta(days=1, hours=1))
    third.record_attempt(full, late, TaskResult.INCORRECT)

    kept = _lesson(tasks=[early, late])
    sitting = _session_at(path, start + timedelta(days=2))
    assert sitting.due_review([full]) == [
        (full, early),
        (full, late),
        (full, middle),
    ]
    assert sitting.due_review([kept]) == [(kept, early), (kept, late)]
    assert sitting.stats([kept]).due_count == len(sitting.due_review([kept]))
    assert sitting.stats([full]).due_count == len(sitting.due_review([full]))
    assert sitting.stats().due_count is None
    assert sitting.continue_target([kept]) == sitting.due_review([kept])


def test_failed_queue_omits_a_gone_task_and_keeps_drill_place(tmp_path: Path) -> None:
    session = _session(tmp_path)
    full = _lesson(tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c")])
    first, second, third = full.tasks
    session.record_attempt(full, first, TaskResult.INCORRECT)
    session.record_attempt(full, second, TaskResult.INCORRECT)
    session.record_attempt(full, third, TaskResult.INCORRECT)
    session.record_attempt(full, second, TaskResult.CORRECT_NOT_FIRST_TRY)

    kept = _lesson(tasks=[first, third])
    assert session.failed_queue([full]) == [
        (full, first),
        (full, second),
        (full, third),
    ]
    assert session.failed_queue([kept]) == [(kept, first), (kept, third)]
    assert [task.id for _, task in session.due_review([kept])] == ["l1__a", "l1__c"]
    assert session.stats([kept]).failed_queue_size == len(session.failed_queue([kept]))
    assert session.stats([full]).failed_queue_size == len(session.failed_queue([full]))
    assert session.stats().failed_queue_size is None


def test_continue_opens_the_grown_lesson_when_no_resolvable_task_is_due(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    original = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(original, original.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(original, original.tasks[1], TaskResult.FIRST_TRY_PASS)
    assert session.stats([original]).completed_lessons == 1

    ghost = _lesson("ghost", tasks=[_task("ghost__a")])
    session.record_attempt(ghost, ghost.tasks[0], TaskResult.INCORRECT)

    grown = _lesson(tasks=[*original.tasks, _task("l1__c")])
    standing = session.lesson_standing(grown)
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert standing.passed == 2
    assert standing.total == 3
    assert session.stats([grown]).completed_lessons == 0
    assert [task.id for task in session.resume_tasks(grown)] == ["l1__c"]
    assert session.due_review([grown]) == []
    assert session.failed_queue([grown]) == []
    assert session.continue_target([grown]) is grown
    assert session.stats([grown]).due_count == 0
    assert session.stats([grown]).failed_queue_size == 0
    assert session.stats([grown, ghost]).due_count == len(
        session.due_review([grown, ghost])
    )
    assert session.stats([grown, ghost]).failed_queue_size == len(
        session.failed_queue([grown, ghost])
    )


def test_another_miss_or_skip_is_due_immediately(tmp_path: Path) -> None:
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    path = tmp_path / "progress.json"
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    pair = (lesson, task)

    session = _session_at(path, start)
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    session.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert session.due_review([lesson]) == []

    same_day = _session_at(path, start + timedelta(hours=1))
    assert same_day.due_review([lesson]) == []
    same_day.record_attempt(lesson, task, TaskResult.INCORRECT)
    assert same_day.due_review([lesson]) == [pair]
    assert same_day.failed_queue([lesson]) == [pair]

    same_day.record_attempt(lesson, task, TaskResult.CORRECT_NOT_FIRST_TRY)
    assert same_day.due_review([lesson]) == []

    still_waiting = _session_at(path, start + timedelta(hours=2))
    assert still_waiting.due_review([lesson]) == []
    still_waiting.record_attempt(lesson, task, TaskResult.SKIP)
    assert still_waiting.due_review([lesson]) == [pair]
    assert still_waiting.failed_queue([lesson]) == [pair]


def test_reentering_drill_after_first_try_pass_goes_to_the_end(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    passed, other = lesson.tasks

    session.record_attempt(lesson, passed, TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, other, TaskResult.INCORRECT)
    session.record_attempt(lesson, passed, TaskResult.INCORRECT)

    assert session.failed_queue([lesson]) == [(lesson, other), (lesson, passed)]

    reopened = Session(progress_path=tmp_path / "progress.json")
    assert reopened.failed_queue([lesson]) == [(lesson, other), (lesson, passed)]


def test_failed_queue_includes_tasks_that_are_not_due_yet(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__due"), _task("l1__waiting")])
    due_task, waiting = lesson.tasks

    session.record_attempt(lesson, due_task, TaskResult.INCORRECT)
    session.record_attempt(lesson, waiting, TaskResult.INCORRECT)
    session.record_attempt(lesson, waiting, TaskResult.CORRECT_NOT_FIRST_TRY)

    assert session.due_review([lesson]) == [(lesson, due_task)]
    assert session.failed_queue([lesson]) == [
        (lesson, due_task),
        (lesson, waiting),
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

    session.record_attempt(linux, linux.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(linux, linux.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(cisco, cisco.tasks[0], TaskResult.SKIP)
    known = [linux, cisco]

    stats = session.stats(known)
    assert stats.completed_lessons == 0
    assert stats.due_count == len(session.due_review(known))
    assert stats.failed_queue_size == len(session.failed_queue(known))
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

    unresolved = session.stats()
    assert unresolved.completed_lessons is None
    assert unresolved.due_count is None
    assert unresolved.failed_queue_size is None
    assert unresolved.total_attempts == 3
    assert unresolved.correct_first_try == 1
    assert unresolved.skipped == 1

    session.record_attempt(linux, linux.tasks[1], TaskResult.FIRST_TRY_PASS)
    assert session.stats(known).completed_lessons == 1
    assert session.stats(known).due_count == len(session.due_review(known))
    assert session.stats(known).failed_queue_size == len(session.failed_queue(known))


def test_linux_and_Linux_are_one_stats_row(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lower = _lesson(lesson_id="low", platform="linux", tasks=[_task("low__a")])
    upper = _lesson(lesson_id="up", platform="Linux", tasks=[_task("up__a")])
    cisco = _lesson(
        lesson_id="cisco_l", platform="CISCO", tasks=[_task("cisco_l__a")]
    )
    powershell = _lesson(
        lesson_id="ps_l", platform="powershell", tasks=[_task("ps_l__a")]
    )
    git = _lesson(lesson_id="git_l", platform="git", tasks=[_task("git_l__a")])
    docker = _lesson(
        lesson_id="docker_l", platform="DOCKER", tasks=[_task("docker_l__a")]
    )
    juniper = _lesson(
        lesson_id="juniper_l", platform="Juniper", tasks=[_task("juniper_l__a")]
    )
    juniper_lower = _lesson(
        lesson_id="juniper_low", platform="juniper", tasks=[_task("juniper_low__a")]
    )

    session.record_attempt(lower, lower.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(upper, upper.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(cisco, cisco.tasks[0], TaskResult.SKIP)
    session.record_attempt(powershell, powershell.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(git, git.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(docker, docker.tasks[0], TaskResult.SKIP)
    session.record_attempt(juniper, juniper.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(juniper_lower, juniper_lower.tasks[0], TaskResult.INCORRECT)

    stats = session.stats()
    assert set(stats.by_platform) == {
        "Linux",
        "Cisco",
        "PowerShell",
        "Git",
        "Docker",
        "Juniper",
        "juniper",
    }
    assert stats.by_platform["Linux"].attempts == 2
    assert stats.by_platform["Linux"].correct_first_try == 1
    assert stats.by_platform["Linux"].skipped == 0
    assert stats.by_platform["Cisco"].attempts == 1
    assert stats.by_platform["Cisco"].skipped == 1
    assert stats.by_platform["PowerShell"].attempts == 1
    assert stats.by_platform["Git"].correct_first_try == 1
    assert stats.by_platform["Docker"].skipped == 1
    assert stats.by_platform["Juniper"].attempts == 1
    assert stats.by_platform["juniper"].attempts == 1

    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "progress_version": 5,
                "platform_stats": {
                    "linux": {"attempts": 4, "correct_first_try": 1, "skipped": 2},
                    "Linux": {"attempts": 1, "correct_first_try": 0, "skipped": 0},
                    "myos": {"attempts": 1, "correct_first_try": 0, "skipped": 0},
                    "MyOS": {"attempts": 2, "correct_first_try": 0, "skipped": 0},
                },
            }
        ),
        encoding="utf-8",
    )
    opened = Session(progress_path=legacy).stats()
    assert opened.by_platform["Linux"].attempts == 5
    assert opened.by_platform["Linux"].correct_first_try == 1
    assert opened.by_platform["Linux"].skipped == 2
    assert "linux" not in opened.by_platform
    assert opened.by_platform["myos"].attempts == 1
    assert opened.by_platform["MyOS"].attempts == 2


def test_full_reset_clears_standing_drills_stats_and_welcome(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.dismiss_welcome()
    assert session.should_show_welcome() is False

    session.reset_all()

    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == []
    stats = session.stats()
    assert stats.completed_lessons is None
    assert stats.due_count is None
    assert stats.failed_queue_size is None
    assert stats.total_attempts == 0
    assert stats.correct_first_try == 0
    assert stats.skipped == 0
    assert stats.by_platform == {}
    resolved = session.stats([lesson])
    assert resolved.completed_lessons == 0
    assert resolved.due_count == 0
    assert resolved.failed_queue_size == 0
    assert session.should_show_welcome() is True


def test_welcome_shows_only_before_attempts_and_dismissal(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert session.should_show_welcome() is True

    session.dismiss_welcome()
    assert session.should_show_welcome() is False

    fresh = _session(tmp_path)
    # Same progress file: dismissal persists
    assert fresh.should_show_welcome() is False

    other = tmp_path / "other"
    other.mkdir()
    unused = _session(other)
    assert unused.should_show_welcome() is True
    lesson = _lesson(tasks=[_task("l1__a")])
    unused.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
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

    miss, skipped, _ok = open_lesson.tasks
    done = _lesson(lesson_id="done_l", tasks=[_task("done_l__unused")])
    known = [open_lesson, done]
    assert session.failed_queue(known) == [
        (open_lesson, miss),
        (open_lesson, skipped),
    ]
    assert {task.id for _, task in session.due_review(known)} == {
        "open_l__miss",
        "open_l__skip",
    }
    assert session.lesson_standing(open_lesson).passed == 0
    assert session.lesson_standing(done).status != LESSON_STATUS_COMPLETED
    stats = session.stats(known)
    assert stats.due_count == len(session.due_review(known))
    assert stats.failed_queue_size == len(session.failed_queue(known))
    assert stats.due_count == 2
    assert stats.failed_queue_size == 2
    assert stats.completed_lessons == 0
    assert stats.total_attempts == 4
    assert session.stats().due_count is None
    assert session.stats().completed_lessons is None
    assert "done_l" not in {lesson.id for lesson, _task in session.failed_queue(known)}


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
    passed_task, only_task, waiting_task = lesson.tasks
    passed = (lesson, passed_task)
    only = (lesson, only_task)
    waiting = (lesson, waiting_task)

    assert passed not in session.due_review([lesson])
    assert passed not in session.failed_queue([lesson])
    assert only in session.due_review([lesson])
    assert only in session.failed_queue([lesson])
    assert waiting not in session.due_review([lesson])
    assert waiting in session.failed_queue([lesson])
    assert session.lesson_standing(lesson).passed == 1

    stats = session.stats()
    assert stats.completed_lessons is None
    assert stats.due_count is None
    assert stats.failed_queue_size is None
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
    assert passed not in reopened.due_review([lesson])
    assert passed not in reopened.failed_queue([lesson])
    assert only in reopened.due_review([lesson])
    assert waiting not in reopened.due_review([lesson])
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
    assert session.failed_queue([lesson]) == []


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
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]
    assert session.stats().skipped == 1
    assert session.stats().total_attempts == 1


def test_skip_without_alias_shows_the_pattern_without_anchors(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[_task("l1__a", expected=r"^git\s+status$", aliases=[])]
    )
    task = lesson.tasks[0]

    result = session.submit(lesson, task, "skip")

    assert result.kind == TURN_SKIPPED
    assert result.readable_command == "git status"
    assert result.explanation == "e"
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.stats().total_attempts == 1


def test_miss_stays_on_task_and_later_correct_is_not_first_try(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]

    missed = session.submit(lesson, task, "nope")
    assert missed.kind == TURN_INCORRECT
    assert session.failed_queue([lesson]) == [(lesson, task)]

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
        left_the_drill=True,
        rescheduled=False,
    )
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue([lesson]) == []


def test_exit_leave_request_records_nothing_when_not_the_answer(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.submit(lesson, task, "nope")

    leave = session.submit(lesson, task, "exit")
    assert leave == TurnResult(kind=TURN_LEAVE)
    quit_request = session.submit(lesson, task, "quit")
    assert quit_request == TurnResult(kind=TURN_LEAVE)
    assert session.stats().total_attempts == 1

    # Leave is only a request; cancelling keeps the same confrontation.
    late = session.submit(lesson, task, "ok")
    assert late.kind == TURN_CORRECT
    assert late.first_try is False


def test_task_already_in_the_drill_keeps_its_place(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    first, second = lesson.tasks
    session.record_attempt(lesson, first, TaskResult.INCORRECT)
    session.record_attempt(lesson, second, TaskResult.INCORRECT)

    session.record_attempt(lesson, first, TaskResult.INCORRECT)
    session.record_attempt(lesson, first, TaskResult.SKIP)

    assert session.failed_queue([lesson]) == [(lesson, first), (lesson, second)]


def test_refused_first_try_place_keeps_the_miss_and_the_drill(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.begin_task(task)
    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT
    assert session.stats().total_attempts == 1
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]

    placed = session.record_attempt(lesson, task, TaskResult.FIRST_TRY_PASS)

    assert placed is False
    assert session.stats().total_attempts == 1
    assert session.lesson_standing(lesson).passed == 0
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]

    late = session.submit(lesson, task, "ok")

    assert late.kind == TURN_CORRECT
    assert late.first_try is False
    assert late.explanation == "e"
    assert session.lesson_standing(lesson).passed == 0
    assert session.failed_queue([lesson]) == [(lesson, task)]


def test_refused_miss_place_leaves_the_showing_first_try_eligible(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.begin_task(task)

    placed = session.record_attempt(lesson, task, TaskResult.INCORRECT)

    assert placed is False
    assert session.stats().total_attempts == 0
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == []

    passed = session.submit(lesson, task, "ok")

    assert passed.kind == TURN_CORRECT
    assert passed.first_try is True
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == []
    assert session.lesson_standing(lesson).passed == 1


def test_place_for_another_task_is_allowed_while_a_showing_is_open(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    shown, other = lesson.tasks
    session.begin_task(shown)

    placed = session.record_attempt(lesson, other, TaskResult.SKIP)

    assert placed is True
    assert session.due_review([lesson]) == [(lesson, other)]
    assert session.failed_queue([lesson]) == [(lesson, other)]
    assert session.stats().total_attempts == 1
    assert session.stats().skipped == 1

    passed = session.submit(lesson, shown, "ok")
    assert passed.first_try is True
    assert session.failed_queue([lesson]) == [(lesson, other)]


def test_place_is_allowed_again_after_the_showing_ends(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    finished, waiting = lesson.tasks
    session.record_attempt(lesson, waiting, TaskResult.INCORRECT)
    session.begin_task(finished)
    assert session.submit(lesson, finished, "ok").first_try is True

    placed = session.record_attempt(lesson, finished, TaskResult.INCORRECT)

    assert placed is True
    assert session.failed_queue([lesson]) == [
        (lesson, waiting),
        (lesson, finished),
    ]
    assert session.due_review([lesson]) == [
        (lesson, waiting),
        (lesson, finished),
    ]


def test_exit_word_keeps_the_showing_open(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.begin_task(task)
    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT

    assert session.submit(lesson, task, "quit").kind == TURN_LEAVE
    placed = session.record_attempt(lesson, task, TaskResult.FIRST_TRY_PASS)

    assert placed is False
    assert session.stats().total_attempts == 1
    assert session.lesson_standing(lesson).passed == 0
    assert session.failed_queue([lesson]) == [(lesson, task)]

    late = session.submit(lesson, task, "ok")
    assert late.first_try is False
    assert session.failed_queue([lesson]) == [(lesson, task)]


def test_leave_ends_the_showing_so_a_later_place_is_stored(tmp_path: Path) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.begin_task(task)
    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT

    session.end_showing(task)
    placed = session.record_attempt(lesson, task, TaskResult.SKIP)

    assert placed is True
    assert session.stats().total_attempts == 2
    assert session.stats().skipped == 1
    assert session.lesson_standing(lesson).passed == 0
    assert session.failed_queue([lesson]) == [(lesson, task)]
    assert session.due_review([lesson]) == [(lesson, task)]


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
    assert session.failed_queue([lesson]) == []


def test_case_rules_and_aliases_follow_platform(tmp_path: Path) -> None:
    session = _session(tmp_path)
    cisco = Lesson(
        id="cisco_l",
        title="Cisco",
        platform="cIsCo",
        description="d",
        tasks=[
            _task("cisco_l__a", expected="^configure terminal$"),
            _task("cisco_l__b", expected="^unused$", aliases=["CONF T"]),
        ],
    )
    powershell = Lesson(
        id="ps_l",
        title="PS",
        platform="powershell",
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
    pair = (lesson, task)

    session.submit(lesson, task, "nope")
    assert session.due_review([lesson]) == [pair]
    assert session.failed_queue([lesson]) == [pair]

    session.begin_task(task)
    result = session.submit(lesson, task, "ok")

    assert result.kind == TURN_CORRECT
    assert result.first_try is True
    assert result.left_the_drill is True
    assert result.rescheduled is False
    assert result.explanation == "e"
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == []


def test_review_late_pass_stays_in_failed_queue_and_is_not_due(tmp_path: Path) -> None:
    """A late Review pass reschedules; the Task stays in the failed queue."""
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]

    session.begin_task(task)
    assert session.submit(lesson, task, "nope").kind == TURN_INCORRECT
    late = session.submit(lesson, task, "ok")

    assert late.kind == TURN_CORRECT
    assert late.first_try is False
    assert late.left_the_drill is False
    assert late.rescheduled is True
    assert late.explanation == "e"
    assert session.due_review([lesson]) == []
    assert session.failed_queue([lesson]) == [(lesson, task)]


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
        open_lesson, open_lesson.tasks[0], TaskResult.INCORRECT
    )

    target = session.continue_target([open_lesson])
    assert target == [(open_lesson, open_lesson.tasks[0])]
    assert target == session.due_review([open_lesson])


def test_continue_resumes_last_unfinished_resumable_lesson(tmp_path: Path) -> None:
    session = _session(tmp_path)
    older = _lesson("older")
    newer = _lesson("newer")
    session.mark_practice_opened(older)
    session.mark_practice_opened(newer)

    target = session.continue_target([older, newer])
    assert target is newer


def test_continue_skips_completed_lesson_when_resuming(tmp_path: Path) -> None:
    session = _session(tmp_path)
    done = _lesson("done")
    open_lesson = _lesson("open")
    session.record_attempt(done, done.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(done, done.tasks[1], TaskResult.FIRST_TRY_PASS)
    session.mark_practice_opened(open_lesson)
    assert session.lesson_standing(done).status == LESSON_STATUS_COMPLETED

    target = session.continue_target([done, open_lesson])
    assert target is open_lesson


def test_continue_opens_recommended_when_nothing_unfinished(tmp_path: Path) -> None:
    session = _session(tmp_path)
    basic = _lesson("basic", title="Basic", difficulty="beginner")
    advanced = _lesson(
        "advanced",
        title="Advanced",
        difficulty="advanced",
        prerequisites=["basic"],
    )
    session.record_attempt(basic, basic.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(basic, basic.tasks[1], TaskResult.FIRST_TRY_PASS)

    target = session.continue_target([advanced, basic])
    assert target is advanced


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
        linux_basic, linux_basic.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        linux_basic, linux_basic.tasks[1], TaskResult.FIRST_TRY_PASS
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
    session.record_attempt(alpha, alpha.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(alpha, alpha.tasks[1], TaskResult.FIRST_TRY_PASS)

    # alpha completed → skip; bravo prereqs met but intermediate; charlie beginner unfinished
    target = session.continue_target([bravo, charlie, alpha])
    assert target is charlie


def test_continue_recommended_follows_path_order_by_title(tmp_path: Path) -> None:
    session = _session(tmp_path)
    zebra = _lesson("zebra", title="Zebra", difficulty="beginner")
    apple = _lesson("apple", title="Apple", difficulty="beginner")

    target = session.continue_target([zebra, apple])
    assert target is apple


def test_continue_recommendation_uses_the_full_catalog_for_prerequisites(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    linux_basic = _lesson("linux_basic", title="Linux Basic", platform="Linux")
    blocked = _lesson(
        "blocked",
        title="Alpha",
        platform="Cisco",
        prerequisites=["missing"],
    )
    ready = _lesson(
        "ready",
        title="Zulu",
        platform="Cisco",
        prerequisites=["linux_basic"],
    )
    session.record_attempt(linux_basic, linux_basic.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(linux_basic, linux_basic.tasks[1], TaskResult.FIRST_TRY_PASS)

    assert session.continue_target([blocked, ready]) is blocked
    assert (
        session.continue_target(
            [blocked, ready],
            catalog=[linux_basic, blocked, ready],
        )
        is ready
    )


def test_continue_follows_catalog_order_past_an_unknown_difficulty(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    expert = _lesson("expert", title="Apple", difficulty="expert")
    beginner = _lesson("beginner", title="Zebra", difficulty="beginner")
    assert session.recommended_lesson([expert, beginner]) is beginner
    assert session.continue_target([expert, beginner]) is beginner

    locked_expert = _lesson(
        "locked_expert",
        title="Apple",
        difficulty="expert",
        prerequisites=["missing"],
    )
    locked_beginner = _lesson(
        "locked_beginner",
        title="Zebra",
        difficulty="beginner",
        prerequisites=["missing"],
    )
    assert session.continue_target([locked_expert, locked_beginner]) is locked_beginner


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
    assert target is locked


def test_continue_does_not_recommend_a_completed_lesson(tmp_path: Path) -> None:
    session = _session(tmp_path)
    done = _lesson("done", title="Done", difficulty="beginner")
    next_lesson = _lesson("next", title="Next", difficulty="intermediate")
    session.record_attempt(done, done.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(done, done.tasks[1], TaskResult.FIRST_TRY_PASS)

    target = session.continue_target([done, next_lesson])
    assert target is next_lesson


def test_continue_skips_empty_opened_lesson_when_resuming(tmp_path: Path) -> None:
    """Opened empty Lessons are unfinished standing but have nothing to resume."""
    session = _session(tmp_path)
    empty = _lesson("empty", tasks=[])
    real = _lesson("real", title="Real")
    session.mark_practice_opened(real)
    session.mark_practice_opened(empty)

    target = session.continue_target([empty, real])
    assert target is real


# --- resume, start over, prerequisites (#22) ---


def test_resume_offers_only_non_first_try_pass_tasks_in_lesson_order(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c"), _task("l1__d")]
    )
    session.record_attempt(
        lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        lesson, lesson.tasks[1], TaskResult.INCORRECT
    )
    session.record_attempt(
        lesson, lesson.tasks[1], TaskResult.CORRECT_NOT_FIRST_TRY
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
        lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        lesson, lesson.tasks[1], TaskResult.INCORRECT
    )
    assert session.failed_queue([lesson]) == [(lesson, lesson.tasks[1])]
    session.record_attempt(
        lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS
    )
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED

    session.start_over(lesson)

    standing = session.lesson_standing(lesson)
    assert standing.status != LESSON_STATUS_COMPLETED
    assert standing.passed == 0
    assert session.resume_tasks(lesson) == list(lesson.tasks)
    assert session.failed_queue([lesson]) == []
    assert session.due_review([lesson]) == []
    assert session.stats([lesson]).completed_lessons == 0


def test_start_over_leaves_other_lessons_drills_and_completion(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    target = _lesson("target", tasks=[_task("target__a"), _task("target__b")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a"), _task("keeper__b")])
    drill = _lesson("drill", tasks=[_task("drill__a")])

    session.record_attempt(
        target, target.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        target, target.tasks[1], TaskResult.INCORRECT
    )
    session.record_attempt(
        keeper, keeper.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        keeper, keeper.tasks[1], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        drill, drill.tasks[0], TaskResult.INCORRECT
    )
    known = [target, keeper, drill]
    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert (drill, drill.tasks[0]) in session.failed_queue(known)

    session.start_over(target)

    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(keeper).passed == 2
    assert session.failed_queue(known) == [(drill, drill.tasks[0])]
    assert session.due_review(known) == [(drill, drill.tasks[0])]
    assert session.stats(known).completed_lessons == 1
    assert session.lesson_standing(target).passed == 0
    assert (target, target.tasks[1]) not in session.failed_queue(known)


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
        basics, basics.tasks[0], TaskResult.FIRST_TRY_PASS
    )
    session.record_attempt(
        basics, basics.tasks[1], TaskResult.FIRST_TRY_PASS
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


def _freeze(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


def _thaw(path: Path) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)


class _DeniedRead:
    """Hold a real file so the process cannot open it, then give it back."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: int | None = None

    def __enter__(self) -> "_DeniedRead":
        if os.name == "nt":
            self._handle = _lock_against_open(self.path)
        else:
            os.chmod(self.path, 0)
        return self

    def __exit__(self, *args: object) -> None:
        if self._handle is None:
            os.chmod(self.path, stat.S_IWRITE | stat.S_IREAD)
            return
        import ctypes

        ctypes.windll.kernel32.CloseHandle(self._handle)
        self._handle = None


def _lock_against_open(path: Path) -> int:
    import ctypes
    from ctypes import wintypes

    generic_read = 0x80000000
    open_existing = 3
    file_attribute_normal = 0x80
    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        generic_read,
        0,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise OSError(f"could not lock {path}")
    return int(handle)


def test_failed_lesson_opened_keeps_the_previous_history(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Opening a Lesson writes nothing when that save cannot land."""
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    prior = _lesson("prior")
    session.record_attempt(prior, prior.tasks[0], TaskResult.INCORRECT)
    session.dismiss_welcome()
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    lesson = _lesson("fresh")

    _freeze(path)
    try:
        saved = session.mark_practice_opened(lesson)
    finally:
        _thaw(path)

    captured = capsys.readouterr()
    assert saved is False
    assert path.read_bytes() == before
    assert not (tmp_path / "progress.json.tmp").exists()
    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.stats().total_attempts == attempts
    assert captured.out == ""
    assert captured.err == ""

    reopened = Session(progress_path=path)
    assert reopened.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert reopened.stats().total_attempts == attempts
    assert reopened.lesson_standing(prior).status == LESSON_STATUS_IN_PROGRESS

    again = session.mark_practice_opened(lesson)
    assert again is True
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["attempted_lessons"] == ["prior", "fresh"]
    assert stored["total_attempts"] == attempts


def test_opening_an_already_opened_lesson_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson()
    assert session.mark_practice_opened(lesson) is True
    before = path.read_bytes()

    _freeze(path)
    try:
        saved = session.mark_practice_opened(lesson)
    finally:
        _thaw(path)

    assert saved is True
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS


def test_failed_save_of_a_correct_line_keeps_the_previous_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    prior = _lesson("prior")
    session.record_attempt(prior, prior.tasks[0], TaskResult.INCORRECT)
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    lesson = _lesson(
        "fresh",
        tasks=[_task("fresh__a", explanation="secret why")],
    )
    task = lesson.tasks[0]
    session.begin_task(task)

    _freeze(path)
    try:
        result = session.submit(lesson, task, "ok")
    finally:
        _thaw(path)

    assert result.kind == TURN_CORRECT
    assert result.stored is False
    assert result.explanation is None
    assert result.readable_command is None
    assert result.left_the_drill is False
    assert result.rescheduled is False
    assert result.first_try is True
    assert path.read_bytes() == before
    assert session.stats().total_attempts == attempts
    assert session.stats().correct_first_try == 0
    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.record_attempt(lesson, task, TaskResult.SKIP) is False

    again = session.submit(lesson, task, "ok")

    assert again.stored is True
    assert again.kind == TURN_CORRECT
    assert again.first_try is True
    assert again.explanation == "secret why"
    assert again.left_the_drill is True
    assert again.rescheduled is False
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue([lesson]) == []
    assert session.stats().total_attempts == attempts + 1
    assert session.stats().correct_first_try == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["attempted_lessons"] == ["prior", "fresh"]
    assert stored["task_progress"]["fresh__a"]["passed_first_try"] is True
    assert stored["total_attempts"] == attempts + 1
    assert stored["correct_first_try"] == 1
    assert stored["completed_lessons"] == ["fresh"]
    assert not (tmp_path / "progress.json.tmp").exists()


def test_unstored_miss_spends_first_try_on_this_showing(tmp_path: Path) -> None:
    """Practice and Review share submit. An unsaved miss still spends first-try."""
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    other = _lesson("other")
    session.record_attempt(other, other.tasks[0], TaskResult.SKIP)
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    lesson = _lesson("l1", tasks=[_task("l1__a", explanation="because")])
    task = lesson.tasks[0]
    session.begin_task(task)

    _freeze(path)
    try:
        missed = session.submit(lesson, task, "nope")
        assert session.submit(lesson, task, "nope").stored is False
    finally:
        _thaw(path)

    assert missed.kind == TURN_INCORRECT
    assert missed.stored is False
    assert missed.first_try is True
    assert missed.explanation is None
    assert path.read_bytes() == before
    assert session.stats().total_attempts == attempts
    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert session.failed_queue([lesson]) == []

    late = session.submit(lesson, task, "ok")

    assert late.stored is True
    assert late.kind == TURN_CORRECT
    assert late.first_try is False
    assert late.left_the_drill is False
    assert late.rescheduled is True
    assert late.explanation == "because"
    assert session.lesson_standing(lesson).passed == 0
    assert session.failed_queue([lesson]) == [(lesson, task)]
    assert session.due_review([lesson]) == []
    assert session.stats().total_attempts == attempts + 1
    assert session.stats().correct_first_try == 0


def test_unstored_skip_hides_the_command_and_stays_open(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    other = _lesson("other")
    session.record_attempt(other, other.tasks[0], TaskResult.INCORRECT)
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    lesson = _lesson(
        "l1",
        tasks=[
            _task(
                "l1__a",
                expected=r"^show\s+ip\s+interface\s+brief$",
                aliases=["sh ip int br"],
                explanation="brief interfaces",
            )
        ],
    )
    task = lesson.tasks[0]
    session.begin_task(task)

    _freeze(path)
    try:
        skipped = session.submit(lesson, task, "skip")
    finally:
        _thaw(path)

    assert skipped.kind == TURN_SKIPPED
    assert skipped.stored is False
    assert skipped.explanation is None
    assert skipped.readable_command is None
    assert path.read_bytes() == before
    assert session.stats().total_attempts == attempts
    assert session.stats().skipped == 0
    assert session.record_attempt(lesson, task, TaskResult.FIRST_TRY_PASS) is False

    again = session.submit(lesson, task, "skip")

    assert again.stored is True
    assert again.kind == TURN_SKIPPED
    assert again.readable_command == "sh ip int br"
    assert again.explanation == "brief interfaces"
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]
    assert session.stats().skipped == 1
    assert session.stats().total_attempts == attempts + 1


def test_leave_after_an_unstored_miss_keeps_the_older_pass(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson("l1", tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.begin_task(task)
    assert session.submit(lesson, task, "ok").first_try is True
    before = path.read_bytes()
    attempts = session.stats().total_attempts

    session.begin_task(task)
    _freeze(path)
    try:
        missed = session.submit(lesson, task, "nope")
    finally:
        _thaw(path)

    assert missed.stored is False
    assert missed.kind == TURN_INCORRECT
    session.end_showing(task)
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue([lesson]) == []

    reopened = Session(progress_path=path)
    assert reopened.stats().total_attempts == attempts
    assert reopened.lesson_standing(lesson).passed == 1
    assert reopened.failed_queue([lesson]) == []
    assert reopened.due_review([lesson]) == []
    reopened.begin_task(task)
    again = reopened.submit(lesson, task, "ok")
    assert again.stored is True
    assert again.first_try is True
    assert again.left_the_drill is True
    assert reopened.lesson_standing(lesson).passed == 1


def test_failed_reset_keeps_the_previous_history(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a")])
    task = lesson.tasks[0]
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    session.dismiss_welcome()
    before = path.read_bytes()
    attempts = session.stats().total_attempts

    _freeze(path)
    try:
        saved = session.reset_all()
    finally:
        _thaw(path)

    assert saved is False
    assert path.read_bytes() == before
    assert session.stats().total_attempts == attempts
    assert session.stats().correct_first_try == 0
    assert session.should_show_welcome() is False
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS
    assert session.due_review([lesson]) == [(lesson, task)]
    assert session.failed_queue([lesson]) == [(lesson, task)]

    reopened = Session(progress_path=path)
    assert reopened.stats().total_attempts == attempts
    assert reopened.should_show_welcome() is False
    assert reopened.due_review([lesson]) == [(lesson, task)]
    assert reopened.failed_queue([lesson]) == [(lesson, task)]


def test_failed_welcome_dismissal_keeps_the_welcome(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    session.dismiss_welcome()
    session.reset_all()
    before = path.read_bytes()
    assert session.should_show_welcome() is True

    _freeze(path)
    try:
        saved = session.dismiss_welcome()
    finally:
        _thaw(path)

    assert saved is False
    assert path.read_bytes() == before
    assert session.should_show_welcome() is True
    assert session.stats().total_attempts == 0

    reopened = Session(progress_path=path)
    assert reopened.should_show_welcome() is True


def test_failed_completion_rewrite_keeps_the_previous_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    original = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(original, original.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(original, original.tasks[1], TaskResult.FIRST_TRY_PASS)
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    grown = _lesson(tasks=[*original.tasks, _task("l1__c")])

    _freeze(path)
    try:
        stats = session.stats([grown])
    finally:
        _thaw(path)

    assert stats.progress_saved is False
    assert stats.completed_lessons == 0
    assert stats.due_count == 0
    assert stats.failed_queue_size == 0
    assert stats.total_attempts == attempts
    assert stats.correct_first_try == 2
    assert path.read_bytes() == before
    assert session.lesson_standing(grown).passed == 2
    assert session.lesson_standing(grown).total == 3

    again = session.stats([grown])
    assert again.progress_saved is True
    assert again.completed_lessons == 0
    assert again.total_attempts == attempts
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert rewritten["completed_lessons"] == []
    assert rewritten["total_attempts"] == attempts
    assert rewritten["correct_first_try"] == 2


def test_failed_place_keeps_the_previous_history(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson()
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    before = path.read_bytes()
    attempts = session.stats().total_attempts

    _freeze(path)
    try:
        placed = session.record_attempt(lesson, lesson.tasks[1], TaskResult.SKIP)
    finally:
        _thaw(path)

    assert placed is False
    assert path.read_bytes() == before
    assert not (tmp_path / "progress.json.tmp").exists()
    assert session.stats().total_attempts == attempts
    assert session.stats().skipped == 0
    assert session.failed_queue([lesson]) == [(lesson, lesson.tasks[0])]


def test_hint_blank_and_outside_place_still_write_nothing(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a", hint="try ok"), _task("l1__b")])
    shown, other = lesson.tasks
    session.record_attempt(lesson, other, TaskResult.INCORRECT)
    before = path.read_bytes()
    session.begin_task(shown)

    _freeze(path)
    try:
        assert session.submit(lesson, shown, "   ").kind == TURN_IGNORE
        hinted = session.submit(lesson, shown, "hint")
    finally:
        _thaw(path)

    placed = session.record_attempt(lesson, shown, TaskResult.SKIP)
    assert hinted == TurnResult(kind=TURN_HINT, hint="try ok")
    assert placed is False
    assert path.read_bytes() == before
    assert session.stats().total_attempts == 1

    passed = session.submit(lesson, shown, "ok")
    assert passed.stored is True
    assert passed.first_try is True
    assert passed.left_the_drill is True


def test_missing_progress_file_stays_a_new_learner_until_stored(
    tmp_path: Path,
) -> None:
    """A missing file is a new Learner. The first stored result creates it."""
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a")])

    assert not path.exists()
    assert session.stats().total_attempts == 0
    assert session.stats().correct_first_try == 0
    assert session.stats().skipped == 0
    assert session.lesson_standing(lesson).status == LESSON_STATUS_NOT_STARTED
    assert not path.exists()

    stored = session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)

    assert stored is True
    assert path.is_file()
    reopened = Session(progress_path=path)
    assert reopened.stats().total_attempts == 1
    assert reopened.stats().correct_first_try == 0
    assert reopened.failed_queue([lesson]) == [(lesson, lesson.tasks[0])]
    assert reopened.lesson_standing(lesson).passed == 0


def test_truncated_progress_file_is_left_untouched(tmp_path: Path) -> None:
    """A present file that cannot be read is not opened as an empty history."""
    path = tmp_path / "progress.json"
    payload = b'{"progress_version": 5, "task_progress":'
    path.write_bytes(payload)

    with pytest.raises(ProgressRefusal) as exc:
        Session(progress_path=path)

    refusal = exc.value
    assert refusal.action == "opening"
    assert refusal.path == path
    assert path.read_bytes() == payload
    assert not (tmp_path / "progress.json.tmp").exists()


def test_unopenable_progress_file_is_left_untouched(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file the process cannot open is the same refusal as truncated contents."""
    path = tmp_path / "progress.json"
    payload = b'{"progress_version": 5, "kept": true}'
    path.write_bytes(payload)

    with _DeniedRead(path):
        with pytest.raises(ProgressRefusal) as exc:
            Session(progress_path=path)

    captured = capsys.readouterr()
    assert exc.value.action == "opening"
    assert exc.value.path == path
    assert "Cannot open progress." not in captured.out
    assert "Cannot open progress." not in captured.err
    assert path.read_bytes() == payload
    assert not (tmp_path / "progress.json.tmp").exists()


def test_undecodable_progress_file_is_left_untouched(tmp_path: Path) -> None:
    """Bytes that are not text are the same refusal as a truncated file."""
    path = tmp_path / "progress.json"
    payload = b"\xff\xfe{"
    path.write_bytes(payload)

    with pytest.raises(ProgressRefusal) as exc:
        Session(progress_path=path)

    assert exc.value.action == "opening"
    assert exc.value.path == path
    assert path.read_bytes() == payload
    assert not (tmp_path / "progress.json.tmp").exists()


@pytest.mark.parametrize(
    "legacy",
    [
        {
            "progress_version": 4,
            "total_attempts": 2,
            "task_progress": {
                "open_l__miss": {
                    "lesson_id": "open_l",
                    "status": "failed",
                    "passed_first_try": False,
                    "attempts": 1,
                }
            },
        },
        {
            "progress_version": 5,
            "total_attempts": 1,
            "failed_tasks": [
                {"lesson_id": "open_l", "task_id": "open_l__only"},
            ],
        },
    ],
)
def test_old_progress_file_that_cannot_be_rewritten_is_left_untouched(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    legacy: dict,
) -> None:
    """An old file whose rewrite cannot be saved is a saving refusal."""
    path = tmp_path / "progress.json"
    payload = json.dumps(legacy).encode()
    path.write_bytes(payload)

    _freeze(path)
    try:
        with pytest.raises(ProgressRefusal) as exc:
            Session(progress_path=path)
    finally:
        _thaw(path)

    captured = capsys.readouterr()
    assert exc.value.action == "saving"
    assert exc.value.path == path
    assert "Cannot save progress." not in captured.out
    assert "Cannot save progress." not in captured.err
    assert "Cannot open progress." not in captured.out
    assert "Cannot open progress." not in captured.err
    assert path.read_bytes() == payload
    assert not (tmp_path / "progress.json.tmp").exists()


def test_current_progress_file_is_not_rewritten_at_open(tmp_path: Path) -> None:
    """A current file that does not migrate stays as it was, even if unwritable."""
    path = tmp_path / "progress.json"
    payload = b'{"progress_version": 5, "total_attempts": 3}'
    path.write_bytes(payload)

    _freeze(path)
    try:
        session = Session(progress_path=path)
        assert session.stats().total_attempts == 3
    finally:
        _thaw(path)

    assert path.read_bytes() == payload
    assert not (tmp_path / "progress.json.tmp").exists()


# --- Practice continuation (#58) ---


def test_not_started_lesson_runs_every_task_without_a_question(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c")])

    report = session.practice_continuation(lesson)

    assert isinstance(report, PracticeTasks)
    assert [task.id for task in report.tasks] == ["l1__a", "l1__b", "l1__c"]
    assert not path.exists()


def test_empty_lesson_runs_no_tasks_and_asks_nothing(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson("empty", tasks=[])
    session.mark_practice_opened(lesson)
    before = path.read_bytes()

    report = session.practice_continuation(lesson)

    assert isinstance(report, PracticeTasks)
    assert report.tasks == ()
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).status == LESSON_STATUS_IN_PROGRESS


def test_finished_lesson_asks_to_practice_again_and_decline_writes_nothing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    before = path.read_bytes()

    report = session.practice_continuation(lesson)

    assert isinstance(report, PracticeAgain)
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(lesson).passed == 2


def test_agreeing_to_practice_again_clears_that_lesson_and_runs_every_task(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    assert isinstance(session.practice_continuation(lesson), PracticeAgain)
    attempts = session.stats().total_attempts
    firsts = session.stats().correct_first_try

    tasks = session.commit_practice_continuation(lesson, ANSWER_START_OVER)

    assert [task.id for task in tasks] == ["l1__a", "l1__b"]
    standing = session.lesson_standing(lesson)
    assert standing.passed == 0
    assert standing.status == LESSON_STATUS_IN_PROGRESS
    assert session.stats().total_attempts == attempts
    assert session.stats().correct_first_try == firsts
    assert session.failed_queue([lesson]) == []
    assert session.due_review([lesson]) == []
    assert session.stats([lesson]).completed_lessons == 0


def test_resume_runs_only_tasks_with_no_first_try_pass_in_lesson_order(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    lesson = _lesson(
        tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c"), _task("l1__d")]
    )
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(
        lesson, lesson.tasks[1], TaskResult.CORRECT_NOT_FIRST_TRY
    )
    session.record_attempt(lesson, lesson.tasks[2], TaskResult.INCORRECT)

    report = session.practice_continuation(lesson)

    assert isinstance(report, PracticeChoice)
    assert [(pick.task.id, pick.first_try_pass) for pick in report.picks] == [
        ("l1__a", True),
        ("l1__b", False),
        ("l1__c", False),
        ("l1__d", False),
    ]

    resumed = session.commit_practice_continuation(lesson, ANSWER_RESUME)

    assert [task.id for task in resumed] == ["l1__b", "l1__c", "l1__d"]


def test_start_over_clears_only_that_lesson_and_runs_every_task(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    target = _lesson("target", tasks=[_task("target__a"), _task("target__b")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a"), _task("keeper__b")])
    drill = _lesson("drill", tasks=[_task("drill__a")])
    session.record_attempt(target, target.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(target, target.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(keeper, keeper.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(keeper, keeper.tasks[1], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(drill, drill.tasks[0], TaskResult.INCORRECT)
    known = [target, keeper, drill]
    assert isinstance(session.practice_continuation(target), PracticeChoice)
    attempts = session.stats().total_attempts
    firsts = session.stats().correct_first_try

    tasks = session.commit_practice_continuation(target, ANSWER_START_OVER)

    assert [task.id for task in tasks] == ["target__a", "target__b"]
    assert session.lesson_standing(target).status == LESSON_STATUS_IN_PROGRESS
    assert session.lesson_standing(target).passed == 0
    assert session.stats().total_attempts == attempts
    assert session.stats().correct_first_try == firsts
    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(keeper).passed == 2
    assert session.failed_queue(known) == [(drill, drill.tasks[0])]
    assert session.due_review(known) == [(drill, drill.tasks[0])]
    assert session.stats(known).completed_lessons == 1
    assert (target, target.tasks[1]) not in session.failed_queue(known)


def test_failed_start_over_keeps_passes_drill_and_due_review(
    tmp_path: Path,
) -> None:
    """A clear that does not land leaves that Lesson, and the sitting is not cleared."""
    path = tmp_path / "progress.json"
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session = _session_at(path, when)
    target = _lesson("target", tasks=[_task("target__pass"), _task("target__due")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a"), _task("keeper__b")])
    drill = _lesson("drill", tasks=[_task("drill__a")])
    session.record_attempt(target, target.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(target, target.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(keeper, keeper.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(keeper, keeper.tasks[1], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(drill, drill.tasks[0], TaskResult.INCORRECT)
    known = [target, keeper, drill]
    before = path.read_bytes()
    totals = session.stats(known)
    assert isinstance(session.practice_continuation(target), PracticeChoice)
    assert session.due_review(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]
    assert session.failed_queue(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]

    _freeze(path)
    try:
        committed = session.commit_practice_continuation(target, ANSWER_START_OVER)
    finally:
        _thaw(path)

    assert isinstance(committed, PracticeUnsaved)
    assert not isinstance(committed, list)
    assert path.read_bytes() == before
    assert not (tmp_path / "progress.json.tmp").exists()
    assert session.lesson_standing(target).status == LESSON_STATUS_IN_PROGRESS
    assert session.lesson_standing(target).passed == 1
    assert session.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(keeper).passed == 2
    assert session.due_review(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]
    assert session.failed_queue(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]
    again = session.stats(known)
    assert again.completed_lessons == totals.completed_lessons == 1
    assert again.due_count == totals.due_count == 2
    assert again.failed_queue_size == totals.failed_queue_size == 2
    assert again.total_attempts == totals.total_attempts == 5
    assert again.correct_first_try == totals.correct_first_try == 3
    assert again.skipped == totals.skipped == 0

    reopened = Session(progress_path=path, clock=when)
    assert reopened.lesson_standing(target).passed == 1
    assert reopened.lesson_standing(target).status == LESSON_STATUS_IN_PROGRESS
    assert reopened.lesson_standing(keeper).status == LESSON_STATUS_COMPLETED
    assert reopened.due_review(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]
    assert reopened.failed_queue(known) == [
        (target, target.tasks[1]),
        (drill, drill.tasks[0]),
    ]
    assert reopened.stats(known).completed_lessons == 1
    assert reopened.stats(known).total_attempts == 5
    assert isinstance(reopened.practice_continuation(target), PracticeChoice)


def test_failed_practice_again_keeps_the_finished_lesson(tmp_path: Path) -> None:
    """Agreeing to practice a finished Lesson again leaves it finished when the save fails."""
    path = tmp_path / "progress.json"
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session = _session_at(path, when)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    other = _lesson("other", tasks=[_task("other__due")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(other, other.tasks[0], TaskResult.INCORRECT)
    known = [lesson, other]
    before = path.read_bytes()
    attempts = session.stats().total_attempts
    firsts = session.stats().correct_first_try
    assert isinstance(session.practice_continuation(lesson), PracticeAgain)

    _freeze(path)
    try:
        committed = session.commit_practice_continuation(lesson, ANSWER_START_OVER)
    finally:
        _thaw(path)

    assert isinstance(committed, PracticeUnsaved)
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED
    assert session.lesson_standing(lesson).passed == 2
    assert isinstance(session.practice_continuation(lesson), PracticeAgain)
    assert session.due_review(known) == [(other, other.tasks[0])]
    assert session.failed_queue(known) == [(other, other.tasks[0])]
    assert session.stats(known).completed_lessons == 1
    assert session.stats().total_attempts == attempts
    assert session.stats().correct_first_try == firsts

    reopened = Session(progress_path=path, clock=when)
    assert reopened.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED
    assert reopened.lesson_standing(lesson).passed == 2
    assert reopened.due_review(known) == [(other, other.tasks[0])]
    assert reopened.failed_queue(known) == [(other, other.tasks[0])]
    assert reopened.stats(known).completed_lessons == 1
    assert reopened.stats().total_attempts == attempts
    assert reopened.stats().correct_first_try == firsts


def test_later_stored_result_keeps_records_a_failed_clear_did_not_remove(
    tmp_path: Path,
) -> None:
    """The next successful write must not persist a clear that never landed."""
    path = tmp_path / "progress.json"
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session = _session_at(path, when)
    target = _lesson("target", tasks=[_task("target__pass"), _task("target__due")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a"), _task("keeper__b")])
    session.record_attempt(target, target.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(target, target.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(keeper, keeper.tasks[0], TaskResult.FIRST_TRY_PASS)
    known = [target, keeper]
    attempts = session.stats().total_attempts

    _freeze(path)
    try:
        committed = session.commit_practice_continuation(target, ANSWER_START_OVER)
    finally:
        _thaw(path)

    assert isinstance(committed, PracticeUnsaved)
    assert session.lesson_standing(target).passed == 1
    assert session.record_attempt(keeper, keeper.tasks[1], TaskResult.INCORRECT) is True

    reopened = Session(progress_path=path, clock=when)
    assert reopened.lesson_standing(target).status == LESSON_STATUS_IN_PROGRESS
    assert reopened.lesson_standing(target).passed == 1
    assert (target, target.tasks[1]) in reopened.due_review(known)
    assert (target, target.tasks[1]) in reopened.failed_queue(known)
    assert (target, target.tasks[0]) not in reopened.failed_queue(known)
    assert reopened.lesson_standing(keeper).passed == 1
    assert (keeper, keeper.tasks[1]) in reopened.due_review(known)
    assert (keeper, keeper.tasks[1]) in reopened.failed_queue(known)
    assert reopened.stats().total_attempts == attempts + 1
    assert reopened.stats(known).completed_lessons == 0
    assert reopened.stats().correct_first_try == 2


def test_failed_clear_is_not_a_cancellation_or_an_empty_lesson(
    tmp_path: Path,
) -> None:
    """Cancel never commits. An empty Lesson is a sitting with no Tasks. A failed clear is neither."""
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)
    before = path.read_bytes()
    assert isinstance(session.practice_continuation(lesson), PracticeChoice)
    assert path.read_bytes() == before

    _freeze(path)
    try:
        committed = session.commit_practice_continuation(lesson, ANSWER_START_OVER)
    finally:
        _thaw(path)

    assert isinstance(committed, PracticeUnsaved)
    assert committed != []
    assert isinstance(session.practice_continuation(lesson), PracticeChoice)
    assert path.read_bytes() == before

    empty = _lesson("empty", tasks=[])
    empty_report = session.practice_continuation(empty)
    assert isinstance(empty_report, PracticeTasks)
    assert empty_report.tasks == ()
    assert not isinstance(empty_report, PracticeUnsaved)
    assert not isinstance(committed, PracticeTasks)


def test_pick_of_a_passed_task_includes_that_task(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(
        tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c")]
    )
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    before = path.read_bytes()
    assert isinstance(session.practice_continuation(lesson), PracticeChoice)

    picked = session.commit_practice_continuation(
        lesson, ANSWER_PICK, "l1__b"
    )

    assert [task.id for task in picked] == ["l1__b", "l1__c"]
    assert session.lesson_standing(lesson).passed == 1
    assert path.read_bytes() == before


def test_pick_skips_later_first_try_passes(tmp_path: Path) -> None:
    """The sitting is the chosen Task, then later Tasks with no first-try pass."""
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(
        tasks=[_task("l1__a"), _task("l1__b"), _task("l1__c"), _task("l1__d")]
    )
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.record_attempt(lesson, lesson.tasks[2], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[3], TaskResult.INCORRECT)
    before = path.read_bytes()

    picked = session.commit_practice_continuation(lesson, ANSWER_PICK, "l1__b")

    assert [task.id for task in picked] == ["l1__b", "l1__d"]
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).passed == 1


def test_miss_on_a_task_chosen_again_removes_its_first_try_pass(
    tmp_path: Path,
) -> None:
    """A miss on a Task the Learner picked to see again puts it back in Review."""
    when = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session = _session_at(tmp_path / "progress.json", when)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    chosen = lesson.tasks[0]
    other = lesson.tasks[1]
    session.record_attempt(lesson, chosen, TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, other, TaskResult.INCORRECT)

    report = session.practice_continuation(lesson)
    assert isinstance(report, PracticeChoice)
    assert [(pick.task.id, pick.first_try_pass) for pick in report.picks] == [
        ("l1__a", True),
        ("l1__b", False),
    ]
    picked = session.commit_practice_continuation(lesson, ANSWER_PICK, "l1__a")
    assert [task.id for task in picked] == ["l1__a", "l1__b"]

    session.begin_task(chosen)
    missed = session.submit(lesson, chosen, "nope")

    assert missed.kind == TURN_INCORRECT
    assert session.lesson_standing(lesson).passed == 0
    assert session.due_review([lesson]) == [(lesson, chosen), (lesson, other)]
    assert session.failed_queue([lesson]) == [(lesson, other), (lesson, chosen)]


def test_unknown_task_id_returns_no_tasks_and_writes_nothing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    keeper = _lesson("keeper", tasks=[_task("keeper__a")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)
    session.record_attempt(keeper, keeper.tasks[0], TaskResult.INCORRECT)
    before = path.read_bytes()

    picked = session.commit_practice_continuation(lesson, ANSWER_PICK, "keeper__a")

    assert picked == []
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue([lesson, keeper]) == [
        (lesson, lesson.tasks[1]),
        (keeper, keeper.tasks[0]),
    ]


def test_cancel_leaves_the_continuation_uncommitted(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    session = Session(progress_path=path)
    lesson = _lesson(tasks=[_task("l1__a"), _task("l1__b")])
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    session.record_attempt(lesson, lesson.tasks[1], TaskResult.INCORRECT)
    before = path.read_bytes()

    report = session.practice_continuation(lesson)

    assert isinstance(report, PracticeChoice)
    assert path.read_bytes() == before
    assert session.lesson_standing(lesson).passed == 1
    assert session.failed_queue([lesson]) == [(lesson, lesson.tasks[1])]

