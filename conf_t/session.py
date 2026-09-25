"""Learner session: standing and progress answers behind one seam."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from conf_t.engine import (
    LESSON_STATUS_COMPLETED,
    LESSON_STATUS_IN_PROGRESS,
    LESSON_STATUS_NOT_STARTED,
    ProgressManager,
)
from conf_t.models import Lesson, Task

__all__ = [
    "LESSON_STATUS_COMPLETED",
    "LESSON_STATUS_IN_PROGRESS",
    "LESSON_STATUS_NOT_STARTED",
    "LessonStanding",
    "LearnerStats",
    "PlatformTotals",
    "ReviewEntry",
    "Session",
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


class Session:
    """Owns Lesson standing and related progress answers for Practice and Review."""

    def __init__(self, progress_path: Optional[Path] = None) -> None:
        self._progress = ProgressManager(filepath=progress_path)

    @property
    def progress(self) -> ProgressManager:
        """Temporary bridge for callers not yet moved onto session queries."""
        return self._progress

    def mark_practice_opened(self, lesson: Lesson) -> None:
        self._progress.mark_lesson_attempted(lesson.id)

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
