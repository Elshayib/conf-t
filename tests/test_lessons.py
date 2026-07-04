import json
import re
from pathlib import Path

import pytest

from conf_t.models import Lesson

LESSONS_DIR = Path(__file__).parent.parent / "conf_t" / "lessons"
TASK_ID_PATTERN = re.compile(r"^[a-z0-9_]+__[a-z0-9_]+$")


def _load_all_lessons() -> list[Lesson]:
    lessons = []
    for file_path in sorted(LESSONS_DIR.glob("*.json")):
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        lessons.append(Lesson.from_dict(data))
    return lessons


@pytest.fixture(scope="module")
def all_lessons() -> list[Lesson]:
    return _load_all_lessons()


@pytest.fixture(scope="module")
def lesson_ids(all_lessons: list[Lesson]) -> set[str]:
    return {lesson.id for lesson in all_lessons}


def test_lessons_directory_not_empty(all_lessons: list[Lesson]):
    assert len(all_lessons) > 0


def test_every_lesson_parses(all_lessons: list[Lesson]):
    for lesson in all_lessons:
        assert lesson.id
        assert lesson.title
        assert lesson.platform
        assert lesson.description
        assert len(lesson.tasks) > 0


def test_task_ids_globally_unique(all_lessons: list[Lesson]):
    seen: dict[str, str] = {}
    for lesson in all_lessons:
        for task in lesson.tasks:
            assert task.id not in seen, (
                f"Duplicate task id '{task.id}' in lessons "
                f"'{seen[task.id]}' and '{lesson.id}'"
            )
            seen[task.id] = lesson.id


def test_task_ids_follow_hybrid_convention(all_lessons: list[Lesson]):
    for lesson in all_lessons:
        prefix = f"{lesson.id}__"
        for task in lesson.tasks:
            assert task.id.startswith(prefix), (
                f"Task '{task.id}' in lesson '{lesson.id}' must start with '{prefix}'"
            )
            assert TASK_ID_PATTERN.match(task.id), (
                f"Task id '{task.id}' must match pattern lesson_id__action_slug"
            )


def test_expected_regex_compiles(all_lessons: list[Lesson]):
    for lesson in all_lessons:
        for task in lesson.tasks:
            try:
                re.compile(task.expected)
            except re.error as exc:
                pytest.fail(
                    f"Invalid regex in lesson '{lesson.id}' task '{task.id}': {exc}"
                )


def test_no_duplicate_expected_within_lesson(all_lessons: list[Lesson]):
    for lesson in all_lessons:
        seen: set[str] = set()
        for task in lesson.tasks:
            assert task.expected not in seen, (
                f"Duplicate expected regex '{task.expected}' in lesson '{lesson.id}'"
            )
            seen.add(task.expected)


def test_prerequisites_reference_existing_lessons(
    all_lessons: list[Lesson], lesson_ids: set[str]
):
    for lesson in all_lessons:
        for prereq in lesson.prerequisites:
            assert prereq in lesson_ids, (
                f"Lesson '{lesson.id}' references unknown prerequisite '{prereq}'"
            )


def test_difficulty_values_valid(all_lessons: list[Lesson]):
    valid = {"beginner", "intermediate", "advanced"}
    for lesson in all_lessons:
        assert lesson.difficulty in valid, (
            f"Lesson '{lesson.id}' has invalid difficulty '{lesson.difficulty}'"
        )