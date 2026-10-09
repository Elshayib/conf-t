"""Learner session: standing and progress answers behind one seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from conf_t.acceptance import format_display_answer, validate_input
from conf_t.catalog import sort_lessons_by_curriculum
from conf_t.platform import Platform
from conf_t.engine import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    PlatformLifetime,
    ProgressManager,
)
from conf_t.models import Lesson, SessionStats, Task, TaskResult

TURN_IGNORE = "ignore"
TURN_LEAVE = "leave"
TURN_HINT = "hint"
TURN_SKIPPED = "skipped"
TURN_CORRECT = "correct"
TURN_INCORRECT = "incorrect"

__all__ = [
    "LESSON_STATUS_COMPLETED",
    "LESSON_STATUS_IN_PROGRESS",
    "LESSON_STATUS_NOT_STARTED",
    "TURN_CORRECT",
    "TURN_HINT",
    "TURN_IGNORE",
    "TURN_INCORRECT",
    "TURN_LEAVE",
    "TURN_SKIPPED",
    "ContinueTarget",
    "LessonStanding",
    "LearnerStats",
    "PlatformTotals",
    "Session",
    "TaskResult",
    "TurnResult",
    "practice_summary",
]


@dataclass(frozen=True)
class LessonStanding:
    status: str
    passed: int
    total: int


@dataclass(frozen=True)
class ContinueTarget:
    action: str
    lesson_id: str | None = None


@dataclass(frozen=True)
class PlatformTotals:
    attempts: int
    correct_first_try: int
    skipped: int


@dataclass(frozen=True)
class LearnerStats:
    completed_lessons: int
    due_count: int
    failed_queue_size: int
    total_attempts: int
    correct_first_try: int
    skipped: int
    by_platform: dict[str, PlatformTotals]


@dataclass(frozen=True)
class TurnResult:
    kind: str
    hint: str | None = None
    explanation: str | None = None
    readable_command: str | None = None
    first_try: bool = False


def practice_summary(
    results: Sequence[TurnResult],
    *,
    total_tasks: int,
) -> SessionStats:
    """Build a Practice sitting summary from the turn results of this sitting."""
    correct_first_try = sum(
        1 for result in results if result.kind == TURN_CORRECT and result.first_try
    )
    skipped = sum(1 for result in results if result.kind == TURN_SKIPPED)
    total_attempts = sum(
        1
        for result in results
        if result.kind in {TURN_CORRECT, TURN_INCORRECT, TURN_SKIPPED}
    )
    return SessionStats(
        total_questions=total_tasks,
        correct_first_try=correct_first_try,
        total_attempts=total_attempts,
        skipped_count=skipped,
    )


def _fold_platform_totals(
    stored: dict[str, PlatformLifetime],
) -> dict[str, PlatformTotals]:
    """Known Platforms share one canonical stats key. Unknown spellings stay apart."""
    folded: dict[str, PlatformTotals] = {}
    for name, totals in stored.items():
        key = Platform.of(name).spelling
        current = folded.get(key)
        if current is None:
            folded[key] = PlatformTotals(
                attempts=totals.attempts,
                correct_first_try=totals.correct_first_try,
                skipped=totals.skipped,
            )
            continue
        folded[key] = PlatformTotals(
            attempts=current.attempts + totals.attempts,
            correct_first_try=current.correct_first_try + totals.correct_first_try,
            skipped=current.skipped + totals.skipped,
        )
    return folded


class Session:
    """Owns Lesson standing and related progress answers for Practice and Review."""

    def __init__(
        self,
        progress_path: Optional[Path] = None,
        *,
        clock: datetime | None = None,
    ) -> None:
        """Open progress.

        `clock`, when given, is the fixed time for every review check in this
        session. When omitted, each check uses the current time. A Learner
        does not set the clock.
        """
        self._progress = ProgressManager(filepath=progress_path, clock=clock)
        self._lost_first_try: set[str] = set()

    def mark_practice_opened(self, lesson: Lesson) -> None:
        self._progress.mark_lesson_attempted(lesson.id)

    def begin_task(self, task: Task) -> None:
        """Start a fresh confrontation with the Task for this sitting."""
        self._lost_first_try.discard(task.id)

    def submit(self, lesson: Lesson, task: Task, line: str) -> TurnResult:
        cleaned = line.strip()
        if not cleaned:
            return TurnResult(kind=TURN_IGNORE)

        lowered = cleaned.lower()
        if lowered == "hint":
            hint_text = task.hint.strip() if task.hint else ""
            return TurnResult(kind=TURN_HINT, hint=hint_text or None)

        is_exit_word = lowered in {"exit", "quit"}
        if is_exit_word and not validate_input(cleaned, task, lesson.platform):
            return TurnResult(kind=TURN_LEAVE)

        first_try = task.id not in self._lost_first_try

        if lowered == "skip":
            self.record_attempt(lesson, task, TaskResult.SKIP)
            self._lost_first_try.discard(task.id)
            return TurnResult(
                kind=TURN_SKIPPED,
                explanation=task.explanation,
                readable_command=format_display_answer(task),
                first_try=first_try,
            )

        is_correct = validate_input(cleaned, task, lesson.platform)
        if is_correct:
            result = (
                TaskResult.FIRST_TRY_PASS
                if first_try
                else TaskResult.CORRECT_NOT_FIRST_TRY
            )
            self.record_attempt(lesson, task, result)
            self._lost_first_try.discard(task.id)
            return TurnResult(
                kind=TURN_CORRECT,
                explanation=task.explanation,
                first_try=first_try,
            )

        self.record_attempt(lesson, task, TaskResult.INCORRECT)
        self._lost_first_try.add(task.id)
        return TurnResult(kind=TURN_INCORRECT, first_try=first_try)

    def record_attempt(
        self,
        lesson: Lesson,
        task: Task,
        result: TaskResult,
    ) -> None:
        """Store one result. Does not change the showing in progress."""
        if not isinstance(result, TaskResult):
            result = TaskResult(result)
        self._progress.record_attempt(
            lesson_id=lesson.id,
            platform=Platform.of(lesson.platform).spelling,
            task_id=task.id,
            result=result,
        )
        self._sync_completion(lesson)

    def continue_target(self, lessons: Sequence[Lesson]) -> ContinueTarget | None:
        """Choose where continue / the menu continue entry should send the Learner."""
        if not lessons:
            return None
        if self.due_review(lessons):
            return ContinueTarget(action="daily_review")

        by_id = {lesson.id: lesson for lesson in lessons}
        for lesson_id in reversed(self._progress.attempted_lesson_ids()):
            lesson = by_id.get(lesson_id)
            if lesson is None:
                continue
            if self._can_resume(lesson):
                return ContinueTarget(action="lesson", lesson_id=lesson.id)

        recommended = self.recommended_lesson(lessons)
        if recommended is not None:
            return ContinueTarget(action="lesson", lesson_id=recommended.id)

        first = sort_lessons_by_curriculum(list(lessons))[0]
        return ContinueTarget(action="lesson", lesson_id=first.id)

    def _can_resume(self, lesson: Lesson) -> bool:
        standing = self.lesson_standing(lesson)
        return (
            standing.status != LESSON_STATUS_COMPLETED
            and standing.total > 0
            and standing.passed < standing.total
        )

    def recommended_lesson(
        self,
        lessons: Sequence[Lesson],
        *,
        catalog: Sequence[Lesson] | None = None,
    ) -> Lesson | None:
        """Next Lesson among `lessons` whose prerequisites are completed in `catalog`."""
        standing_source = list(catalog) if catalog is not None else list(lessons)
        completed_ids = {
            lesson.id
            for lesson in standing_source
            if self.lesson_standing(lesson).status == LESSON_STATUS_COMPLETED
        }
        for lesson in sort_lessons_by_curriculum(list(lessons)):
            if lesson.id in completed_ids:
                continue
            if all(prereq in completed_ids for prereq in lesson.prerequisites):
                return lesson
        return None

    def due_review(self, lessons: Sequence[Lesson]) -> list[tuple[Lesson, Task]]:
        """Due Tasks that still exist, soonest next review time first."""
        return self._resolve(self._progress.get_due_review_entries(), lessons)

    def failed_queue(self, lessons: Sequence[Lesson]) -> list[tuple[Lesson, Task]]:
        """Drill Tasks that still exist, in drill-place order."""
        return self._resolve(self._progress.get_failed_task_entries(), lessons)

    def _resolve(
        self,
        entries: list[dict[str, str]],
        lessons: Sequence[Lesson],
    ) -> list[tuple[Lesson, Task]]:
        by_id: dict[str, Lesson] = {}
        for lesson in lessons:
            by_id.setdefault(lesson.id, lesson)
        resolved: list[tuple[Lesson, Task]] = []
        for entry in entries:
            lesson = by_id.get(entry["lesson_id"])
            if lesson is None:
                continue
            task = next(
                (item for item in lesson.tasks if item.id == entry["task_id"]),
                None,
            )
            if task is None:
                continue
            resolved.append((lesson, task))
        return resolved

    def stats(self) -> LearnerStats:
        stored = self._progress.lifetime_stats()
        by_platform = _fold_platform_totals(stored.by_platform)
        return LearnerStats(
            completed_lessons=stored.completed_lessons,
            due_count=len(self._progress.get_due_review_entries()),
            failed_queue_size=len(self._progress.get_failed_task_entries()),
            total_attempts=stored.total_attempts,
            correct_first_try=stored.correct_first_try,
            skipped=stored.skipped,
            by_platform=by_platform,
        )

    def reset_all(self) -> None:
        self._progress.reset_progress()

    def should_show_welcome(self) -> bool:
        return self._progress.should_show_welcome()

    def dismiss_welcome(self) -> None:
        self._progress.dismiss_welcome()

    def lesson_standing(self, lesson: Lesson) -> LessonStanding:
        task_ids = [task.id for task in lesson.tasks]
        summary = self._progress.get_lesson_task_summary(lesson.id, task_ids)
        passed = summary["passed"]
        total = summary["total"]

        if total > 0 and passed == total:
            status = LESSON_STATUS_COMPLETED
        elif self._has_progress(lesson, task_ids):
            status = LESSON_STATUS_IN_PROGRESS
        else:
            status = LESSON_STATUS_NOT_STARTED

        return LessonStanding(status=status, passed=passed, total=total)

    def resume_tasks(self, lesson: Lesson) -> list[Task]:
        """Tasks that are not first-try passes, in Lesson order."""
        return [
            task for task in lesson.tasks if not self._progress.is_task_passed(task.id)
        ]

    def start_over(self, lesson: Lesson) -> None:
        """Clear this Lesson's Task records, failed-queue entries, and completion."""
        task_ids = [task.id for task in lesson.tasks]
        self._progress.reset_lesson_progress(lesson.id, task_ids)

    def missing_prerequisite_titles(
        self, lesson: Lesson, lessons: Sequence[Lesson]
    ) -> list[str]:
        """Titles of prerequisites that are not yet completed."""
        by_id = {item.id: item for item in lessons}
        completed_ids = {
            item.id
            for item in lessons
            if self.lesson_standing(item).status == LESSON_STATUS_COMPLETED
        }
        titles: list[str] = []
        for prereq_id in lesson.prerequisites:
            if prereq_id in completed_ids:
                continue
            prereq = by_id.get(prereq_id)
            titles.append(prereq.title if prereq is not None else prereq_id)
        return titles

    def _has_progress(self, lesson: Lesson, task_ids: list[str]) -> bool:
        return self._progress.has_lesson_activity(lesson.id, task_ids)

    def _sync_completion(self, lesson: Lesson) -> None:
        standing = self.lesson_standing(lesson)
        self._progress.set_lesson_completed(
            lesson.id,
            standing.status == LESSON_STATUS_COMPLETED,
        )
