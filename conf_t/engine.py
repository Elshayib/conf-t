import copy
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, NamedTuple, Optional
from pathlib import Path

from conf_t.models import TaskProgress, TaskResult

LESSON_STATUS_COMPLETED = "completed"
LESSON_STATUS_IN_PROGRESS = "in_progress"
LESSON_STATUS_NOT_STARTED = "not_started"

TASK_STATUS_PASSED = "passed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_SKIPPED = "skipped"

PROGRESS_VERSION = 5

REVIEW_INTERVALS_DAYS = [0, 1, 3, 7]


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_task_progress_passed(entry: Optional[Dict[str, Any]]) -> bool:
    if not entry:
        return False
    return (
        entry.get("status") == TASK_STATUS_PASSED
        and entry.get("passed_first_try", False)
    )


def _record_is_first_try_pass(record: Optional[TaskProgress]) -> bool:
    if record is None:
        return False
    return (
        record.status == TASK_STATUS_PASSED and record.passed_first_try
    )


class PlatformLifetime(NamedTuple):
    attempts: int
    correct_first_try: int
    skipped: int


class LifetimeStats(NamedTuple):
    completed_lessons: int
    total_attempts: int
    correct_first_try: int
    skipped: int
    by_platform: Dict[str, PlatformLifetime]


class ProgressManager:
    """One Task history on disk: file, migration, and review times."""
    def __init__(
        self,
        filepath: Optional[Path] = None,
        *,
        clock: Optional[datetime] = None,
    ) -> None:
        if filepath is None:
            self.filepath = Path.home() / ".conf_t_progress.json"
        else:
            self.filepath = Path(filepath)
        self._clock = clock
        self._data, migrated = self._load_data()
        if migrated:
            self.save()

    def _now(self) -> datetime:
        if self._clock is not None:
            current = self._clock
        else:
            current = datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.replace(microsecond=0)

    def _now_iso(self) -> str:
        return self._now().isoformat()

    def _load_data(self) -> tuple[Dict[str, Any], bool]:
        if not self.filepath.exists():
            return self._default_structure(), False
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                original_version = data.get("progress_version", 1)
                had_drill_list = "failed_tasks" in data
                defaults = self._default_structure()
                for key, value in defaults.items():
                    if key not in data and key not in ("progress_version", "task_progress"):
                        data[key] = value
                data = self._migrate_if_needed(data, original_version)
                for key, value in defaults.items():
                    if key not in data:
                        data[key] = value
                migrated = (
                    original_version < PROGRESS_VERSION or had_drill_list
                )
                return data, migrated
        except (json.JSONDecodeError, OSError):
            return self._default_structure(), False

    def _default_structure(self) -> Dict[str, Any]:
        return {
            "progress_version": PROGRESS_VERSION,
            "completed_lessons": [],
            "attempted_lessons": [],
            "task_progress": {},
            "total_attempts": 0,
            "correct_first_try": 0,
            "skipped_count": 0,
            "platform_stats": {},
            "onboarding_complete": False,
        }

    def _migrate_if_needed(
        self, data: Dict[str, Any], original_version: int
    ) -> Dict[str, Any]:
        had_drill_list = "failed_tasks" in data
        if original_version >= PROGRESS_VERSION and not had_drill_list:
            return data

        now = self._now_iso()
        task_progress: Dict[str, Any] = dict(data.get("task_progress") or {})
        # Files from before review scheduling had no next-review time.
        if original_version < 4:
            for entry in task_progress.values():
                if (
                    not isinstance(entry, dict)
                    or is_task_progress_passed(entry)
                ):
                    continue
                entry["review_level"] = 0
                entry["next_review_at"] = now

        # A first-try pass outranks a leftover drill entry. A drill entry with
        # no Task record becomes a Task with no first-try pass that is due now.
        # Drill order follows the old list, then any other Task with no pass.
        drill_order: List[str] = []
        seen: set[str] = set()
        for drill in data.get("failed_tasks") or []:
            if not isinstance(drill, dict):
                continue
            task_id = drill.get("task_id")
            lesson_id = drill.get("lesson_id")
            if not task_id or not lesson_id or task_id in seen:
                continue
            existing = task_progress.get(task_id)
            if isinstance(existing, dict) and is_task_progress_passed(
                existing
            ):
                continue
            if existing is None:
                task_progress[task_id] = TaskProgress(
                    lesson_id=lesson_id,
                    status=TASK_STATUS_FAILED,
                    passed_first_try=False,
                    attempts=1,
                    last_attempt=None,
                    review_level=0,
                    next_review_at=now,
                ).to_dict()
            drill_order.append(task_id)
            seen.add(task_id)

        for task_id, entry in task_progress.items():
            if (
                not isinstance(entry, dict)
                or task_id in seen
                or is_task_progress_passed(entry)
            ):
                continue
            drill_order.append(task_id)

        for index, task_id in enumerate(drill_order, start=1):
            record = TaskProgress.from_dict(task_progress[task_id])
            record.drill_place = index
            task_progress[task_id] = record.to_dict()

        data["task_progress"] = task_progress
        data.pop("failed_tasks", None)
        data["progress_version"] = PROGRESS_VERSION
        return data

    def save(self) -> bool:
        """Write the whole history in one replace. A failure leaves the file as it was."""
        temporary = self.filepath.with_name(self.filepath.name + ".tmp")
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=4)
            os.replace(temporary, self.filepath)
            return True
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def commit(self, apply: Callable[[], None]) -> bool:
        """Apply one history change and save it. A failed save restores memory."""
        previous = copy.deepcopy(self._data)
        try:
            apply()
            saved = self.save()
        except Exception:
            self._data = previous
            raise
        if saved:
            return True
        self._data = previous
        return False

    def mark_lesson_attempted(self, lesson_id: str) -> None:
        if self._remember_lesson_attempted(lesson_id):
            self.save()

    def _remember_lesson_attempted(self, lesson_id: str) -> bool:
        attempted = self._data["attempted_lessons"]
        if lesson_id in attempted:
            return False
        attempted.append(lesson_id)
        return True

    def _read_record(self, task_id: str) -> Optional[TaskProgress]:
        raw = self._data.get("task_progress", {}).get(task_id)
        if not isinstance(raw, dict):
            return None
        if not raw.get("lesson_id") or "status" not in raw:
            return None
        return TaskProgress.from_dict(raw)

    def _write_record(self, task_id: str, record: TaskProgress) -> None:
        self._data["task_progress"][task_id] = record.to_dict()

    def _record_for_result(
        self,
        lesson_id: str,
        result: TaskResult,
        prior: Optional[TaskProgress],
    ) -> TaskProgress:
        if result is TaskResult.SKIP:
            status = TASK_STATUS_SKIPPED
            passed_first_try = False
        elif result is TaskResult.FIRST_TRY_PASS:
            status = TASK_STATUS_PASSED
            passed_first_try = True
        else:
            status = TASK_STATUS_FAILED
            passed_first_try = False

        record = TaskProgress(
            lesson_id=lesson_id,
            status=status,
            passed_first_try=passed_first_try,
            attempts=(prior.attempts if prior else 0) + 1,
            last_attempt=self._now_iso(),
            review_level=prior.review_level if prior else 0,
            next_review_at=prior.next_review_at if prior else None,
        )
        if result is TaskResult.FIRST_TRY_PASS:
            record.review_level = 0
            record.next_review_at = None
            return record

        level = record.review_level
        if result is TaskResult.CORRECT_NOT_FIRST_TRY:
            level = min(level + 1, len(REVIEW_INTERVALS_DAYS) - 1)
        else:
            level = 0
        days = REVIEW_INTERVALS_DAYS[level]
        if days == 0:
            due_at = self._now()
        else:
            due_at = self._now() + timedelta(days=days)
        record.review_level = level
        record.next_review_at = due_at.isoformat()
        return record

    def _drill_place_for(
        self, result: TaskResult, prior: Optional[TaskProgress]
    ) -> Optional[int]:
        if result is TaskResult.FIRST_TRY_PASS:
            return None
        if (
            prior is not None
            and not _record_is_first_try_pass(prior)
            and prior.drill_place is not None
        ):
            return prior.drill_place
        return self._next_drill_place()

    def is_task_due(self, task_id: str) -> bool:
        record = self._read_record(task_id)
        if record is None or _record_is_first_try_pass(record):
            return False
        if not record.next_review_at:
            return record.status in (TASK_STATUS_FAILED, TASK_STATUS_SKIPPED)
        return _parse_iso_datetime(record.next_review_at) <= self._now()

    def get_due_review_entries(self) -> List[Dict[str, str]]:
        due_entries: List[Dict[str, str]] = []
        for task_id in self._data.get("task_progress", {}):
            record = self._read_record(task_id)
            if record is None or not record.lesson_id:
                continue
            if not self.is_task_due(task_id):
                continue
            due_entries.append(
                {"lesson_id": record.lesson_id, "task_id": task_id}
            )
        due_entries.sort(key=lambda item: self._due_sort_key(item["task_id"]))
        return due_entries

    def _due_sort_key(self, task_id: str) -> str:
        record = self._read_record(task_id)
        if record is None or not record.next_review_at:
            return ""
        return record.next_review_at

    def is_task_passed(self, task_id: str) -> bool:
        return _record_is_first_try_pass(self._read_record(task_id))

    def get_lesson_task_summary(
        self, lesson_id: str, task_ids: List[str]
    ) -> Dict[str, int]:
        passed = sum(1 for task_id in task_ids if self.is_task_passed(task_id))
        total = len(task_ids)
        return {
            "passed": passed,
            "total": total,
            "incomplete": total - passed,
        }

    def reset_lesson_progress(self, lesson_id: str, task_ids: List[str]) -> None:
        task_id_set = set(task_ids)
        self._data["task_progress"] = {
            task_id: entry
            for task_id, entry in self._data.get("task_progress", {}).items()
            if task_id not in task_id_set
        }
        done = self._data.get("completed_lessons", [])
        if lesson_id in done:
            done.remove(lesson_id)
        self.save()

    def record_attempt(
        self,
        lesson_id: str,
        platform: str,
        task_id: str,
        result: TaskResult,
    ) -> None:
        """Remember one attempt in memory. The caller saves the whole change."""
        prior = self._read_record(task_id)
        self._remember_lesson_attempted(lesson_id)
        record = self._record_for_result(lesson_id, result, prior)
        record.drill_place = self._drill_place_for(result, prior)
        self._write_record(task_id, record)
        self._data["total_attempts"] += 1

        if platform not in self._data["platform_stats"]:
            self._data["platform_stats"][platform] = {
                "attempts": 0,
                "correct_first_try": 0,
                "skipped": 0
            }

        p_stats = self._data["platform_stats"][platform]
        p_stats["attempts"] += 1

        if result is TaskResult.SKIP:
            self._data["skipped_count"] += 1
            p_stats["skipped"] += 1
        elif result is TaskResult.FIRST_TRY_PASS:
            self._data["correct_first_try"] += 1
            p_stats["correct_first_try"] += 1

    def set_lesson_completed(
        self,
        lesson_id: str,
        completed: bool,
        *,
        save: bool = True,
    ) -> None:
        done = self._data.setdefault("completed_lessons", [])
        changed = False
        if completed and lesson_id not in done:
            done.append(lesson_id)
            changed = True
        elif not completed and lesson_id in done:
            done.remove(lesson_id)
            changed = True
        if changed and save:
            self.save()

    def _next_drill_place(self) -> int:
        highest = 0
        for task_id in self._data.get("task_progress", {}):
            record = self._read_record(task_id)
            place = (
                0
                if record is None or record.drill_place is None
                else record.drill_place
            )
            if place > highest:
                highest = place
        return highest + 1

    def _drill_sort_key(self, task_id: str) -> tuple[int, int]:
        record = self._read_record(task_id)
        place = None if record is None else record.drill_place
        if place is None:
            return (1, 0)
        return (0, place)

    def get_failed_task_entries(self) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        for task_id in self._data.get("task_progress", {}):
            record = self._read_record(task_id)
            if record is None or _record_is_first_try_pass(record):
                continue
            if not record.lesson_id:
                continue
            entries.append(
                {"lesson_id": record.lesson_id, "task_id": task_id}
            )
        entries.sort(key=lambda item: self._drill_sort_key(item["task_id"]))
        return entries

    def attempted_lesson_ids(self) -> List[str]:
        return list(self._data.get("attempted_lessons", []))

    def has_lesson_activity(self, lesson_id: str, task_ids: List[str]) -> bool:
        if lesson_id in self._data.get("attempted_lessons", []):
            return True
        progress = self._data.get("task_progress", {})
        return any(task_id in progress for task_id in task_ids)

    def should_show_welcome(self) -> bool:
        if self._data.get("onboarding_complete"):
            return False
        return int(self._data.get("total_attempts", 0)) == 0

    def dismiss_welcome(self) -> None:
        self._data["onboarding_complete"] = True
        self.save()

    def lifetime_stats(self) -> LifetimeStats:
        by_platform: Dict[str, PlatformLifetime] = {}
        for platform, totals in self._data.get("platform_stats", {}).items():
            if not isinstance(totals, dict):
                continue
            by_platform[str(platform)] = PlatformLifetime(
                attempts=int(totals.get("attempts", 0)),
                correct_first_try=int(totals.get("correct_first_try", 0)),
                skipped=int(totals.get("skipped", 0)),
            )
        return LifetimeStats(
            completed_lessons=len(self._data.get("completed_lessons", [])),
            total_attempts=int(self._data.get("total_attempts", 0)),
            correct_first_try=int(self._data.get("correct_first_try", 0)),
            skipped=int(self._data.get("skipped_count", 0)),
            by_platform=by_platform,
        )

    def reset_progress(self):
        self._data = self._default_structure()
        self.save()
