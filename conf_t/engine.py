import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, NamedTuple, Optional
from pathlib import Path

from conf_t.models import Lesson, Task, SessionStats, TaskProgress

DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}
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


def validate_input(user_input: str, task: Task, platform: str) -> bool:
    """
    Validates the user's input command against the task's expected regex and aliases.
    Applies case-sensitivity based on the platform:
    - Cisco, PowerShell: case-insensitive
    - Linux, Git, Docker: case-sensitive
    """
    cleaned_input = user_input.strip()
    
    # Determine regex flags
    is_case_insensitive = platform.lower() in ["cisco", "powershell"]
    flags = re.IGNORECASE if is_case_insensitive else 0

    # 1. Test against expected regex pattern
    try:
        pattern = re.compile(task.expected, flags)
        if pattern.match(cleaned_input):
            return True
    except re.error:
        # Fallback to exact match if regex compilation fails
        pass

    # 2. Test against aliases list
    for alias in task.aliases:
        alias_clean = alias.strip()
        if is_case_insensitive:
            if cleaned_input.lower() == alias_clean.lower():
                return True
        else:
            if cleaned_input == alias_clean:
                return True

    return False


def format_display_answer(task: Task, platform: str) -> str:
    """Return a human-readable correct answer for hints and skip reveals."""
    if task.aliases:
        return task.aliases[0]

    display = task.expected
    if display.startswith("^"):
        display = display[1:]
    if display.endswith("$"):
        display = display[:-1]
    display = display.replace(r"\s+", " ")
    display = display.replace(r"\s", " ")
    display = display.replace("\\", "")
    return display


def sort_lessons_by_curriculum(lessons: List[Lesson]) -> List[Lesson]:
    return sorted(
        lessons,
        key=lambda lesson: (
            DIFFICULTY_ORDER.get(lesson.difficulty, 99),
            lesson.title.lower(),
        ),
    )


def parse_tags_csv(tags: Optional[str]) -> List[str]:
    if not tags:
        return []
    return [tag.strip().lower() for tag in tags.split(",") if tag.strip()]


def lesson_matches_tags(lesson: Lesson, tags: List[str]) -> bool:
    if not tags:
        return True
    lesson_tags = {tag.lower() for tag in lesson.tags}
    return all(tag in lesson_tags for tag in tags)


def filter_lessons_by_tags(lessons: List[Lesson], tags: List[str]) -> List[Lesson]:
    if not tags:
        return lessons
    return [lesson for lesson in lessons if lesson_matches_tags(lesson, tags)]


def collect_all_tags(lessons: List[Lesson]) -> List[str]:
    tags: set[str] = set()
    for lesson in lessons:
        tags.update(tag.lower() for tag in lesson.tags)
    return sorted(tags)


def is_task_progress_passed(entry: Optional[Dict[str, Any]]) -> bool:
    if not entry:
        return False
    return (
        entry.get("status") == TASK_STATUS_PASSED
        and entry.get("passed_first_try", False)
    )


class LessonLoader:
    """Loads and caches lessons from JSON files in the lessons directory."""
    def __init__(self, lessons_dir: Optional[Path] = None):
        if lessons_dir is None:
            # Default to the lessons subdirectory inside the package
            self.lessons_dir = Path(__file__).parent / "lessons"
        else:
            self.lessons_dir = Path(lessons_dir)

    def load_all_lessons(self) -> List[Lesson]:
        lessons: List[Lesson] = []
        if not self.lessons_dir.exists() or not self.lessons_dir.is_dir():
            return lessons

        for file_path in self.lessons_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    lessons.append(Lesson.from_dict(data))
            except (json.JSONDecodeError, KeyError, OSError):
                # Fail silently or ignore malformed lesson files to avoid crash
                continue
        return lessons

    def get_lesson_by_id(self, lesson_id: str) -> Optional[Lesson]:
        lessons = self.load_all_lessons()
        for lesson in lessons:
            if lesson.id == lesson_id:
                return lesson
        return None

    def save_lesson(self, lesson: Lesson) -> bool:
        """Saves a Lesson object as a JSON file in the lessons directory."""
        if not self.lessons_dir.exists():
            try:
                self.lessons_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False
        
        file_path = self.lessons_dir / f"{lesson.id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(lesson.to_dict(), f, indent=4)
            return True
        except OSError:
            return False


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
            task_progress[task_id]["drill_seq"] = index

        data["task_progress"] = task_progress
        data.pop("failed_tasks", None)
        data["progress_version"] = PROGRESS_VERSION
        return data

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except OSError:
            pass  # Fail silently if directory or permissions block writes

    def mark_lesson_attempted(self, lesson_id: str):
        if lesson_id not in self._data["attempted_lessons"]:
            self._data["attempted_lessons"].append(lesson_id)
            self.save()

    def _update_task_progress(
        self,
        lesson_id: str,
        task_id: str,
        is_correct: bool,
        is_first_try: bool,
        is_skipped: bool,
    ) -> None:
        existing = self._data["task_progress"].get(task_id, {})
        attempts = existing.get("attempts", 0) + 1
        now = self._now_iso()

        if is_skipped:
            status = TASK_STATUS_SKIPPED
            passed_first_try = False
        elif is_correct and is_first_try:
            status = TASK_STATUS_PASSED
            passed_first_try = True
        else:
            status = TASK_STATUS_FAILED
            passed_first_try = False

        review_level = existing.get("review_level", 0)
        next_review_at = existing.get("next_review_at")
        self._data["task_progress"][task_id] = TaskProgress(
            lesson_id=lesson_id,
            status=status,
            passed_first_try=passed_first_try,
            attempts=attempts,
            last_attempt=now,
            review_level=review_level,
            next_review_at=next_review_at,
        ).to_dict()

    def _apply_review_schedule(
        self,
        task_id: str,
        is_correct: bool,
        is_first_try: bool,
        is_skipped: bool,
    ) -> None:
        entry = self._data["task_progress"][task_id]
        if is_correct and is_first_try:
            entry["review_level"] = 0
            entry.pop("next_review_at", None)
            return

        level = entry.get("review_level", 0)
        if is_correct and not is_first_try:
            level = min(level + 1, len(REVIEW_INTERVALS_DAYS) - 1)
        else:
            level = 0

        days = REVIEW_INTERVALS_DAYS[level]
        if days == 0:
            due_at = self._now()
        else:
            due_at = self._now() + timedelta(days=days)
        entry["review_level"] = level
        entry["next_review_at"] = due_at.isoformat()

    def is_task_due(self, task_id: str) -> bool:
        if self.is_task_passed(task_id):
            return False
        entry = self.get_task_progress_entry(task_id)
        if not entry:
            return False
        next_review_at = entry.get("next_review_at")
        if not next_review_at:
            return entry.get("status") in (TASK_STATUS_FAILED, TASK_STATUS_SKIPPED)
        return _parse_iso_datetime(next_review_at) <= self._now()

    def get_due_review_entries(self) -> List[Dict[str, str]]:
        due_entries: List[Dict[str, str]] = []
        for task_id, entry in self._data.get("task_progress", {}).items():
            if not isinstance(entry, dict) or not entry.get("lesson_id"):
                continue
            if not self.is_task_due(task_id):
                continue
            due_entries.append(
                {"lesson_id": entry["lesson_id"], "task_id": task_id}
            )
        due_entries.sort(
            key=lambda item: (
                self.get_task_progress_entry(item["task_id"]) or {}
            ).get("next_review_at") or ""
        )
        return due_entries

    def get_task_progress_entry(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get("task_progress", {}).get(task_id)

    def is_task_passed(self, task_id: str) -> bool:
        return is_task_progress_passed(self.get_task_progress_entry(task_id))

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
        is_correct: bool,
        is_first_try: bool,
        is_skipped: bool,
    ) -> None:
        prior = self.get_task_progress_entry(task_id) or {}
        kept_seq = None
        if not is_task_progress_passed(prior):
            kept_seq = prior.get("drill_seq")
        self.mark_lesson_attempted(lesson_id)
        self._update_task_progress(
            lesson_id, task_id, is_correct, is_first_try, is_skipped
        )
        self._apply_review_schedule(
            task_id, is_correct, is_first_try, is_skipped
        )
        entry = self._data["task_progress"][task_id]
        if is_correct and is_first_try:
            entry.pop("drill_seq", None)
        elif isinstance(kept_seq, int) and not isinstance(kept_seq, bool):
            # Still in the drill: keep the place it already had.
            entry["drill_seq"] = kept_seq
        else:
            # Entering the drill, including after a first-try pass, goes last.
            entry["drill_seq"] = self._next_drill_seq()
        self._data["total_attempts"] += 1
        
        # Initialize platform stats
        if platform not in self._data["platform_stats"]:
            self._data["platform_stats"][platform] = {
                "attempts": 0,
                "correct_first_try": 0,
                "skipped": 0
            }
            
        p_stats = self._data["platform_stats"][platform]
        p_stats["attempts"] += 1

        if is_skipped:
            self._data["skipped_count"] += 1
            p_stats["skipped"] += 1
        elif is_correct and is_first_try:
            self._data["correct_first_try"] += 1
            p_stats["correct_first_try"] += 1

        self.save()

    def set_lesson_completed(self, lesson_id: str, completed: bool) -> None:
        done = self._data.setdefault("completed_lessons", [])
        if completed and lesson_id not in done:
            done.append(lesson_id)
            self.save()
        elif not completed and lesson_id in done:
            done.remove(lesson_id)
            self.save()

    def _next_drill_seq(self) -> int:
        highest = 0
        for entry in self._data.get("task_progress", {}).values():
            if not isinstance(entry, dict):
                continue
            seq = entry.get("drill_seq")
            if (
                isinstance(seq, int)
                and not isinstance(seq, bool)
                and seq > highest
            ):
                highest = seq
        return highest + 1

    def _drill_sort_key(self, task_id: str) -> tuple[int, int]:
        entry = self.get_task_progress_entry(task_id) or {}
        seq = entry.get("drill_seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq)
        return (1, 0)

    def get_failed_task_entries(self) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        for task_id, entry in self._data.get("task_progress", {}).items():
            if not isinstance(entry, dict) or is_task_progress_passed(entry):
                continue
            lesson_id = entry.get("lesson_id")
            if not lesson_id:
                continue
            entries.append({"lesson_id": lesson_id, "task_id": task_id})
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
