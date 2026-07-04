import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from conf_t.models import Lesson, Task, SessionStats, TaskProgress

DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}
LESSON_STATUS_COMPLETED = "completed"
LESSON_STATUS_IN_PROGRESS = "in_progress"
LESSON_STATUS_NOT_STARTED = "not_started"

TASK_STATUS_PASSED = "passed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_SKIPPED = "skipped"

PROGRESS_VERSION = 4

REVIEW_INTERVALS_DAYS = [0, 1, 3, 7]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


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


def get_missing_prerequisites(
    lesson: Lesson, completed_lessons: List[str]
) -> List[str]:
    completed = set(completed_lessons)
    return [prereq for prereq in lesson.prerequisites if prereq not in completed]


def are_prerequisites_met(lesson: Lesson, completed_lessons: List[str]) -> bool:
    return not get_missing_prerequisites(lesson, completed_lessons)


def get_lesson_status(
    lesson_id: str,
    completed_lessons: List[str],
    attempted_lessons: List[str],
    failed_lesson_ids: List[str],
) -> str:
    if lesson_id in completed_lessons:
        return LESSON_STATUS_COMPLETED
    if lesson_id in attempted_lessons or lesson_id in failed_lesson_ids:
        return LESSON_STATUS_IN_PROGRESS
    return LESSON_STATUS_NOT_STARTED


def get_recommended_lesson(
    lessons: List[Lesson], completed_lessons: List[str]
) -> Optional[Lesson]:
    for lesson in sort_lessons_by_curriculum(lessons):
        if lesson.id in completed_lessons:
            continue
        if are_prerequisites_met(lesson, completed_lessons):
            return lesson
    return None


def get_continue_target(
    lessons: List[Lesson],
    completed_lessons: List[str],
    attempted_lessons: List[str],
    due_review_count: int,
    lesson_has_resume_state_fn,
    is_lesson_fully_passed_fn,
) -> Optional[Dict[str, str]]:
    """
    Pick the best continue action for --continue / quick start.
    Returns {"action": "daily_review"} or {"action": "lesson", "lesson_id": "..."}.
    """
    if due_review_count > 0:
        return {"action": "daily_review"}

    for lesson_id in reversed(attempted_lessons):
        lesson = next((item for item in lessons if item.id == lesson_id), None)
        if not lesson:
            continue
        if is_lesson_fully_passed_fn(lesson):
            continue
        if lesson_has_resume_state_fn(lesson):
            return {"action": "lesson", "lesson_id": lesson.id}

    recommended = get_recommended_lesson(lessons, completed_lessons)
    if recommended:
        return {"action": "lesson", "lesson_id": recommended.id}

    if lessons:
        first = sort_lessons_by_curriculum(lessons)[0]
        return {"action": "lesson", "lesson_id": first.id}

    return None


def get_failed_lesson_ids(failed_tasks: List[Dict[str, str]]) -> List[str]:
    return sorted({entry["lesson_id"] for entry in failed_tasks if "lesson_id" in entry})


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
        lessons = []
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


class ProgressManager:
    """Manages reading and writing user progress stats to a JSON file."""
    def __init__(self, filepath: Optional[Path] = None):
        if filepath is None:
            self.filepath = Path.home() / ".conf_t_progress.json"
        else:
            self.filepath = Path(filepath)
        self.data, migrated = self._load_data()
        if migrated:
            self.save()

    def _load_data(self) -> tuple[Dict[str, Any], bool]:
        if not self.filepath.exists():
            return self._default_structure(), False
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                original_version = data.get("progress_version", 1)
                defaults = self._default_structure()
                for key, value in defaults.items():
                    if key not in data and key not in ("progress_version", "task_progress"):
                        data[key] = value
                data = self._migrate_if_needed(data, original_version)
                for key, value in defaults.items():
                    if key not in data:
                        data[key] = value
                migrated = original_version < PROGRESS_VERSION
                return data, migrated
        except (json.JSONDecodeError, OSError):
            return self._default_structure(), False

    def _default_structure(self) -> Dict[str, Any]:
        return {
            "progress_version": PROGRESS_VERSION,
            "completed_lessons": [],
            "attempted_lessons": [],
            "task_progress": {},
            "failed_tasks": [],
            "total_attempts": 0,
            "correct_first_try": 0,
            "skipped_count": 0,
            "platform_stats": {},
            "onboarding_complete": False,
        }

    def _migrate_if_needed(
        self, data: Dict[str, Any], original_version: int
    ) -> Dict[str, Any]:
        if original_version >= PROGRESS_VERSION:
            return data

        if original_version < 3:
            task_progress: Dict[str, Any] = dict(data.get("task_progress", {}))
            for entry in data.get("failed_tasks", []):
                task_id = entry.get("task_id")
                lesson_id = entry.get("lesson_id")
                if not task_id or not lesson_id or task_id in task_progress:
                    continue
                task_progress[task_id] = TaskProgress(
                    lesson_id=lesson_id,
                    status=TASK_STATUS_FAILED,
                    passed_first_try=False,
                    attempts=1,
                    last_attempt=None,
                ).to_dict()
            data["task_progress"] = task_progress

        if original_version < 4:
            now = _utc_now_iso()
            for entry in data.get("task_progress", {}).values():
                if is_task_progress_passed(entry):
                    continue
                entry["review_level"] = 0
                entry["next_review_at"] = now

        data["progress_version"] = PROGRESS_VERSION
        return data

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except OSError:
            pass  # Fail silently if directory or permissions block writes

    def mark_lesson_attempted(self, lesson_id: str):
        if lesson_id not in self.data["attempted_lessons"]:
            self.data["attempted_lessons"].append(lesson_id)
            self.save()

    def _update_task_progress(
        self,
        lesson_id: str,
        task_id: str,
        is_correct: bool,
        is_first_try: bool,
        is_skipped: bool,
    ) -> None:
        existing = self.data["task_progress"].get(task_id, {})
        attempts = existing.get("attempts", 0) + 1
        now = _utc_now_iso()

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
        self.data["task_progress"][task_id] = TaskProgress(
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
        entry = self.data["task_progress"][task_id]
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
        due_at = _utc_now() if days == 0 else _utc_now() + timedelta(days=days)
        entry["review_level"] = level
        entry["next_review_at"] = due_at.isoformat()

    def is_task_due(self, task_id: str) -> bool:
        if self.is_task_passed(task_id):
            return False
        entry = self.get_task_progress_entry(task_id)
        if not entry:
            return task_id in {
                item.get("task_id") for item in self.data.get("failed_tasks", [])
            }
        next_review_at = entry.get("next_review_at")
        if not next_review_at:
            return entry.get("status") in (TASK_STATUS_FAILED, TASK_STATUS_SKIPPED)
        return _parse_iso_datetime(next_review_at) <= _utc_now()

    def get_due_review_entries(self) -> List[Dict[str, str]]:
        due_entries: List[Dict[str, str]] = []
        seen: set[str] = set()

        for task_id in self.data.get("task_progress", {}):
            if not self.is_task_due(task_id):
                continue
            entry = self.get_task_progress_entry(task_id)
            if not entry or not entry.get("lesson_id"):
                continue
            due_entries.append(
                {"lesson_id": entry["lesson_id"], "task_id": task_id}
            )
            seen.add(task_id)

        for entry in self.data.get("failed_tasks", []):
            task_id = entry.get("task_id")
            lesson_id = entry.get("lesson_id")
            if not task_id or not lesson_id or task_id in seen:
                continue
            if self.is_task_due(task_id):
                due_entries.append({"lesson_id": lesson_id, "task_id": task_id})
                seen.add(task_id)

        due_entries.sort(
            key=lambda item: (
                self.get_task_progress_entry(item["task_id"]) or {}
            ).get("next_review_at") or ""
        )
        return due_entries

    def get_due_review_count(self) -> int:
        return len(self.get_due_review_entries())

    def get_task_progress_entry(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.data.get("task_progress", {}).get(task_id)

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

    def lesson_has_resume_state(self, lesson: Lesson) -> bool:
        task_ids = [task.id for task in lesson.tasks]
        summary = self.get_lesson_task_summary(lesson.id, task_ids)
        if summary["total"] == 0:
            return False
        if summary["passed"] == summary["total"]:
            return False
        if lesson.id in self.data.get("attempted_lessons", []):
            return True
        return any(task_id in self.data.get("task_progress", {}) for task_id in task_ids)

    def get_incomplete_tasks(self, tasks: List[Task]) -> List[Task]:
        return [task for task in tasks if not self.is_task_passed(task.id)]

    def is_lesson_fully_passed(self, lesson: Lesson) -> bool:
        task_ids = [task.id for task in lesson.tasks]
        summary = self.get_lesson_task_summary(lesson.id, task_ids)
        return summary["total"] > 0 and summary["passed"] == summary["total"]

    def reset_lesson_progress(self, lesson_id: str, task_ids: List[str]) -> None:
        task_id_set = set(task_ids)
        self.data["task_progress"] = {
            task_id: entry
            for task_id, entry in self.data.get("task_progress", {}).items()
            if task_id not in task_id_set
        }
        self.data["failed_tasks"] = [
            entry
            for entry in self.data.get("failed_tasks", [])
            if entry.get("task_id") not in task_id_set
        ]
        if lesson_id in self.data.get("completed_lessons", []):
            self.data["completed_lessons"].remove(lesson_id)
        self.save()

    def record_attempt(self, lesson_id: str, platform: str, task_id: str, is_correct: bool, is_first_try: bool, is_skipped: bool):
        self.mark_lesson_attempted(lesson_id)
        self._update_task_progress(
            lesson_id, task_id, is_correct, is_first_try, is_skipped
        )
        self._apply_review_schedule(task_id, is_correct, is_first_try, is_skipped)
        self.data["total_attempts"] += 1
        
        # Initialize platform stats
        if platform not in self.data["platform_stats"]:
            self.data["platform_stats"][platform] = {
                "attempts": 0,
                "correct_first_try": 0,
                "skipped": 0
            }
            
        p_stats = self.data["platform_stats"][platform]
        p_stats["attempts"] += 1

        if is_skipped:
            self.data["skipped_count"] += 1
            p_stats["skipped"] += 1
            self.add_failed_task(lesson_id, task_id)
        elif is_correct and is_first_try:
            self.data["correct_first_try"] += 1
            p_stats["correct_first_try"] += 1
            self.remove_failed_task(task_id)
        elif not is_correct:
            self.add_failed_task(lesson_id, task_id)
            
        self.save()

    def add_failed_task(self, lesson_id: str, task_id: str):
        # Format stored as a dictionary to easily identify the lesson
        entry = {"lesson_id": lesson_id, "task_id": task_id}
        if entry not in self.data["failed_tasks"]:
            self.data["failed_tasks"].append(entry)

    def remove_failed_task(self, task_id: str):
        self.data["failed_tasks"] = [
            item for item in self.data["failed_tasks"] if item["task_id"] != task_id
        ]

    def mark_lesson_completed(self, lesson_id: str):
        if lesson_id not in self.data["completed_lessons"]:
            self.data["completed_lessons"].append(lesson_id)
            self.save()

    def get_failed_task_entries(self) -> List[Dict[str, str]]:
        return self.data.get("failed_tasks", [])

    def reset_progress(self):
        self.data = self._default_structure()
        self.save()
