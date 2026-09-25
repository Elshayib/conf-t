"""Learner session: standing and progress answers behind one seam."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from conf_t.engine import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    ProgressManager,
    format_display_answer,
    validate_input,
)
from conf_t.models import Lesson, SessionStats, Task

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
    "LessonStanding",
    "LearnerStats",
    "PlatformTotals",
    "ReviewEntry",
    "Session",
    "TurnResult",
    "practice_summary",
]


@dataclass(frozen=True)
class LessonStanding:
    status: str
    passed: int
    total: int


@dataclass(frozen=True)
class ReviewEntry:
    lesson_id: str
    task_id: str


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


class Session:
    """Owns Lesson standing and related progress answers for Practice and Review."""

    def __init__(self, progress_path: Optional[Path] = None) -> None:
        self._progress = ProgressManager(filepath=progress_path)
        self._lost_first_try: set[str] = set()

    @property
    def progress(self) -> ProgressManager:
        """Temporary bridge for callers not yet moved onto session queries."""
        return self._progress

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
            self.record_attempt(
                lesson,
                task,
                correct=False,
                first_try=first_try,
                skipped=True,
            )
            self._lost_first_try.discard(task.id)
            return TurnResult(
                kind=TURN_SKIPPED,
                explanation=task.explanation,
                readable_command=format_display_answer(task, lesson.platform),
                first_try=first_try,
            )

        is_correct = validate_input(cleaned, task, lesson.platform)
        if is_correct:
            self.record_attempt(
                lesson,
                task,
                correct=True,
                first_try=first_try,
                skipped=False,
            )
            self._lost_first_try.discard(task.id)
            return TurnResult(
                kind=TURN_CORRECT,
                explanation=task.explanation,
                first_try=first_try,
            )

        self.record_attempt(
            lesson,
            task,
            correct=False,
            first_try=first_try,
            skipped=False,
        )
        self._lost_first_try.add(task.id)
        return TurnResult(kind=TURN_INCORRECT, first_try=first_try)

    def record_attempt(
        self,
        lesson: Lesson,
        task: Task,
        *,
        correct: bool,
        first_try: bool,
        skipped: bool,
    ) -> None:
        self._progress.record_attempt(
            lesson_id=lesson.id,
            platform=lesson.platform,
            task_id=task.id,
            is_correct=correct,
            is_first_try=first_try,
            is_skipped=skipped,
        )
        self._sync_completion(lesson)

    def due_review(self) -> list[ReviewEntry]:
        return [
            ReviewEntry(lesson_id=entry["lesson_id"], task_id=entry["task_id"])
            for entry in self._progress.get_due_review_entries()
        ]

    def failed_queue(self) -> list[ReviewEntry]:
        return [
            ReviewEntry(lesson_id=entry["lesson_id"], task_id=entry["task_id"])
            for entry in self._progress.get_failed_task_entries()
        ]

    def stats(self) -> LearnerStats:
        data = self._progress.data
        by_platform = {
            platform: PlatformTotals(
                attempts=int(totals.get("attempts", 0)),
                correct_first_try=int(totals.get("correct_first_try", 0)),
                skipped=int(totals.get("skipped", 0)),
            )
            for platform, totals in data.get("platform_stats", {}).items()
        }
        return LearnerStats(
            completed_lessons=len(data.get("completed_lessons", [])),
            due_count=len(self.due_review()),
            failed_queue_size=len(self.failed_queue()),
            total_attempts=int(data.get("total_attempts", 0)),
            correct_first_try=int(data.get("correct_first_try", 0)),
            skipped=int(data.get("skipped_count", 0)),
            by_platform=by_platform,
        )

    def reset_all(self) -> None:
        self._progress.reset_progress()

    def should_show_welcome(self) -> bool:
        data = self._progress.data
        if data.get("onboarding_complete"):
            return False
        return int(data.get("total_attempts", 0)) == 0

    def dismiss_welcome(self) -> None:
        self._progress.data["onboarding_complete"] = True
        self._progress.save()

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

    def _has_progress(self, lesson: Lesson, task_ids: list[str]) -> bool:
        if lesson.id in self._progress.data.get("attempted_lessons", []):
            return True
        task_progress = self._progress.data.get("task_progress", {})
        return any(task_id in task_progress for task_id in task_ids)

    def _sync_completion(self, lesson: Lesson) -> None:
        standing = self.lesson_standing(lesson)
        if standing.status == LESSON_STATUS_COMPLETED:
            self._progress.mark_lesson_completed(lesson.id)
        elif lesson.id in self._progress.data.get("completed_lessons", []):
            self._progress.data["completed_lessons"].remove(lesson.id)
            self._progress.save()
