"""The only reader and writer of Lesson files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Sequence

from conf_t.models import Lesson
from conf_t.platform import Platform

DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


class CatalogRefusal(Exception):
    """A Lesson file cannot be accepted. The file is named on the exception."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = Path(path)
        super().__init__(f"{self.path.name}: {reason}")


def sort_lessons_by_curriculum(lessons: Sequence[Lesson]) -> list[Lesson]:
    return sorted(
        lessons,
        key=lambda lesson: (
            DIFFICULTY_ORDER.get(lesson.difficulty, 99),
            lesson.title.lower(),
        ),
    )


def parse_tags_csv(tags: Optional[str]) -> list[str]:
    if not tags:
        return []
    return [tag.strip().lower() for tag in tags.split(",") if tag.strip()]


def lesson_matches_tags(lesson: Lesson, tags: Sequence[str]) -> bool:
    if not tags:
        return True
    lesson_tags = {tag.lower() for tag in lesson.tags}
    return all(tag in lesson_tags for tag in tags)


def filter_lessons_by_tags(
    lessons: Sequence[Lesson], tags: Sequence[str]
) -> list[Lesson]:
    if not tags:
        return list(lessons)
    return [lesson for lesson in lessons if lesson_matches_tags(lesson, tags)]


def collect_all_tags(lessons: Sequence[Lesson]) -> list[str]:
    tags: set[str] = set()
    for lesson in lessons:
        tags.update(tag.lower() for tag in lesson.tags)
    return sorted(tags)


def platform_names(lessons: Sequence[Lesson]) -> list[str]:
    """One display spelling per Platform. A known Platform uses its canonical spelling."""
    chosen: dict[str, str] = {}
    for lesson in lessons:
        platform = Platform.of(lesson.platform)
        if platform.known:
            chosen[platform.spelling.casefold()] = platform.spelling
        else:
            key = lesson.platform.casefold()
            chosen.setdefault(key, lesson.platform)
    return sorted(chosen.values(), key=str.casefold)


def same_platform(lesson: Lesson, platform: str) -> bool:
    return lesson.platform.casefold() == platform.casefold()


class Catalog:
    """Loads, orders, and filters Lessons, and saves a Lesson file."""

    def __init__(self, lessons_dir: Optional[Path] = None) -> None:
        if lessons_dir is None:
            self.lessons_dir = Path(__file__).parent / "lessons"
        else:
            self.lessons_dir = Path(lessons_dir)

    def lessons(
        self,
        platform: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> list[Lesson]:
        """Lessons ordered by difficulty, then title.

        Platform match ignores case. Tags narrow the set the way a topic
        filter does today: every tag must be present, and case does not matter.
        A file that does not parse, a duplicated Task id, or an expected
        regex that does not compile refuses the whole set and names the file.
        """
        loaded = self._read_all()
        if platform:
            loaded = [lesson for lesson in loaded if same_platform(lesson, platform)]
        wanted = [tag.strip().lower() for tag in (tags or []) if tag and tag.strip()]
        return filter_lessons_by_tags(loaded, wanted)

    def platforms(self) -> list[str]:
        return platform_names(self.lessons())

    def load_all_lessons(self) -> list[Lesson]:
        return self.lessons()

    def get_lesson_by_id(self, lesson_id: str) -> Optional[Lesson]:
        for lesson in self.lessons():
            if lesson.id == lesson_id:
                return lesson
        return None

    def save_lesson(self, lesson: Lesson) -> bool:
        """Write the Lesson file when the next read would accept it.

        A Lesson the next read would refuse raises that same refusal and
        writes nothing. A disk failure returns False and is not a refusal.
        """
        if not self.lessons_dir.exists():
            try:
                self.lessons_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False

        destination = self.lessons_dir / f"{lesson.id}.json"
        try:
            text = json.dumps(lesson.to_dict(), indent=4)
        except (TypeError, ValueError) as exc:
            raise CatalogRefusal(
                destination, "file does not parse as a Lesson"
            ) from exc

        self._read_all(pending={destination: text})

        try:
            with open(destination, "w", encoding="utf-8") as handle:
                handle.write(text)
            return True
        except OSError:
            return False

    def _read_all(self, pending: Optional[dict[Path, str]] = None) -> list[Lesson]:
        pending = pending or {}
        if self.lessons_dir.exists() and self.lessons_dir.is_dir():
            files = list(self.lessons_dir.glob("*.json"))
        else:
            files = []

        pending_by_name = {
            path.name.casefold(): (path, text) for path, text in pending.items()
        }
        present = {path.name.casefold() for path in files}
        for name, (path, _text) in pending_by_name.items():
            if name not in present:
                files.append(path)
        files.sort(key=lambda path: path.name.casefold())

        lessons: list[Lesson] = []
        seen_task_ids: dict[str, Path] = {}
        for file_path in files:
            overlay = pending_by_name.get(file_path.name.casefold())
            if overlay is not None:
                file_path, text = overlay
                lesson = self._lesson_from_text(file_path, text)
            else:
                lesson = self._read_lesson(file_path)
            for task in lesson.tasks:
                previous = seen_task_ids.get(task.id)
                if previous is not None:
                    if previous == file_path:
                        reason = f"duplicate task id '{task.id}'"
                    else:
                        reason = (
                            f"duplicate task id '{task.id}' is also in {previous.name}"
                        )
                    raise CatalogRefusal(file_path, reason)
                self._require_expected(file_path, task.expected)
                seen_task_ids[task.id] = file_path
            lessons.append(lesson)
        return sort_lessons_by_curriculum(lessons)

    def _read_lesson(self, file_path: Path) -> Lesson:
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CatalogRefusal(file_path, "file does not parse as a Lesson") from exc
        return self._lesson_from_text(file_path, text)

    def _lesson_from_text(self, file_path: Path, text: str) -> Lesson:
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise CatalogRefusal(file_path, "file does not parse as a Lesson")
            return Lesson.from_dict(data)
        except CatalogRefusal:
            raise
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise CatalogRefusal(file_path, "file does not parse as a Lesson") from exc

    def _require_expected(self, file_path: Path, expected: object) -> None:
        if not isinstance(expected, str):
            raise CatalogRefusal(file_path, "expected regex does not compile")
        try:
            re.compile(expected)
        except re.error as exc:
            raise CatalogRefusal(
                file_path, "expected regex does not compile"
            ) from exc
