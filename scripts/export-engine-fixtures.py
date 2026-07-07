#!/usr/bin/env python3
"""Export engine test fixtures from Python for TypeScript parity tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from conf_t.engine import (
    ProgressManager,
    format_display_answer,
    get_continue_target,
    get_recommended_lesson,
    is_task_progress_passed,
    validate_input,
)
from conf_t.models import Lesson, Task

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "web" / "src" / "lib" / "engine" / "fixtures" / "engine-fixtures.json"


def fresh_progress_manager() -> ProgressManager:
    """In-memory progress state without persisting to the repo."""
    missing = Path(tempfile.gettempdir()) / "conf_t_fixture_nonexistent_progress.json"
    return ProgressManager(filepath=missing)

CISCO_TASK = Task(
    id="test_task",
    prompt="Enter config mode",
    prefix="Router#",
    expected=r"^configure\s+terminal$",
    aliases=["conf t", "config t"],
)

LINUX_PWD_TASK = Task(
    id="test_task",
    prompt="Print directory",
    prefix="$",
    expected=r"^pwd$",
    aliases=[],
)

POWERSHELL_TASK = Task(
    id="test_task",
    prompt="Get services",
    prefix=r"PS C:\>",
    expected=r"^Get-Service$",
    aliases=["gsv"],
)

INVALID_REGEX_ALIAS_TASK = Task(
    id="test_task",
    prompt="Command with bad regex",
    prefix="$",
    expected="[invalid-regex",
    aliases=["exact_cmd"],
)

FORMAT_ALIAS_TASK = Task(
    id="t1",
    prompt="Enter config mode",
    prefix="Router#",
    expected=r"^configure\s+terminal$",
    aliases=["conf t", "config t"],
)

FORMAT_REGEX_TASK = Task(
    id="t1",
    prompt="Print directory",
    prefix="$",
    expected=r"^pwd$",
    aliases=[],
)

CURRICULUM_LESSONS = [
    Lesson(
        id="basic",
        title="Basic",
        platform="Cisco",
        description="",
        difficulty="beginner",
        tasks=[],
    ),
    Lesson(
        id="vlan",
        title="VLAN",
        platform="Cisco",
        description="",
        difficulty="intermediate",
        prerequisites=["basic"],
        tasks=[],
    ),
    Lesson(
        id="ospf",
        title="OSPF",
        platform="Cisco",
        description="",
        difficulty="intermediate",
        prerequisites=["vlan"],
        tasks=[],
    ),
]

RESUME_LESSON = Lesson(
    id="l1",
    title="Lesson 1",
    platform="Linux",
    description="",
    tasks=[Task(id="l1__a", prompt="A", prefix="$", expected="^a$")],
)

CASES: list[dict] = [
    # validate_input — Cisco (case-insensitive)
    {"fn": "validate_input", "input": "configure terminal", "task": CISCO_TASK, "platform": "Cisco"},
    {"fn": "validate_input", "input": "CONFIGURE TERMINAL", "task": CISCO_TASK, "platform": "Cisco"},
    {"fn": "validate_input", "input": "conf t", "task": CISCO_TASK, "platform": "Cisco"},
    {"fn": "validate_input", "input": "CONF T", "task": CISCO_TASK, "platform": "Cisco"},
    {"fn": "validate_input", "input": "wrong command", "task": CISCO_TASK, "platform": "Cisco"},
    # validate_input — Linux (case-sensitive)
    {"fn": "validate_input", "input": "pwd", "task": LINUX_PWD_TASK, "platform": "Linux"},
    {"fn": "validate_input", "input": "PWD", "task": LINUX_PWD_TASK, "platform": "Linux"},
    {"fn": "validate_input", "input": " pwd ", "task": LINUX_PWD_TASK, "platform": "Linux"},
    # validate_input — PowerShell (case-insensitive)
    {"fn": "validate_input", "input": "get-service", "task": POWERSHELL_TASK, "platform": "PowerShell"},
    {"fn": "validate_input", "input": "GSV", "task": POWERSHELL_TASK, "platform": "PowerShell"},
    # validate_input — invalid regex falls back to aliases
    {
        "fn": "validate_input",
        "input": "exact_cmd",
        "task": INVALID_REGEX_ALIAS_TASK,
        "platform": "Linux",
    },
    # format_display_answer
    {"fn": "format_display_answer", "task": FORMAT_ALIAS_TASK, "platform": "Cisco"},
    {"fn": "format_display_answer", "task": FORMAT_REGEX_TASK, "platform": "Linux"},
    # is_task_progress_passed
    {
        "fn": "is_task_progress_passed",
        "entry": {"status": "passed", "passed_first_try": True},
    },
    {
        "fn": "is_task_progress_passed",
        "entry": {"status": "passed", "passed_first_try": False},
    },
    {
        "fn": "is_task_progress_passed",
        "entry": {"status": "failed", "passed_first_try": False},
    },
    {"fn": "is_task_progress_passed", "entry": None},
    # get_recommended_lesson
    {
        "fn": "get_recommended_lesson",
        "lessons": CURRICULUM_LESSONS,
        "completed_lessons": [],
    },
    {
        "fn": "get_recommended_lesson",
        "lessons": CURRICULUM_LESSONS,
        "completed_lessons": ["basic"],
    },
    {
        "fn": "get_recommended_lesson",
        "lessons": CURRICULUM_LESSONS,
        "completed_lessons": ["basic", "vlan"],
    },
    {
        "fn": "get_recommended_lesson",
        "lessons": CURRICULUM_LESSONS,
        "completed_lessons": ["basic", "vlan", "ospf"],
    },
    # get_continue_target
    {
        "fn": "get_continue_target",
        "lessons": [CURRICULUM_LESSONS[0]],
        "completed_lessons": [],
        "attempted_lessons": [],
        "due_review_count": 3,
        "use_progress_manager": False,
    },
    {
        "fn": "get_continue_target",
        "lessons": CURRICULUM_LESSONS,
        "completed_lessons": ["basic"],
        "attempted_lessons": [],
        "due_review_count": 0,
        "use_progress_manager": False,
    },
    {
        "fn": "get_continue_target",
        "lessons": [RESUME_LESSON],
        "completed_lessons": [],
        "attempted_lessons": None,
        "due_review_count": 0,
        "use_progress_manager": True,
        "progress_setup": {
            "record_attempt": {
                "lesson_id": "l1",
                "platform": "Linux",
                "task_id": "l1__a",
                "is_correct": False,
                "is_first_try": True,
                "is_skipped": False,
            }
        },
    },
    # get_due_review_count
    {
        "fn": "get_due_review_count",
        "progress_setup": {
            "record_attempt": {
                "lesson_id": "l1",
                "platform": "Linux",
                "task_id": "l1__a",
                "is_correct": False,
                "is_first_try": True,
                "is_skipped": False,
            }
        },
    },
]


def lesson_to_fixture_dict(lesson: Lesson) -> dict:
    data = lesson.to_dict()
    data.setdefault("difficulty", "beginner")
    data.setdefault("tags", [])
    data.setdefault("prerequisites", [])
    data.setdefault("estimated_minutes", 0)
    for task in data.get("tasks", []):
        task.setdefault("aliases", [])
        task.setdefault("hint", "")
        task.setdefault("explanation", "")
    return data


def build_fixture(case: dict) -> dict:
    fn = case["fn"]

    if fn == "validate_input":
        task = case["task"]
        platform = case["platform"]
        return {
            "fn": fn,
            "task": task.to_dict(),
            "platform": platform,
            "input": case["input"],
            "python_result": validate_input(case["input"], task, platform),
        }

    if fn == "format_display_answer":
        task = case["task"]
        platform = case["platform"]
        return {
            "fn": fn,
            "task": task.to_dict(),
            "platform": platform,
            "python_result": format_display_answer(task, platform),
        }

    if fn == "is_task_progress_passed":
        entry = case.get("entry")
        return {
            "fn": fn,
            "entry": entry,
            "python_result": is_task_progress_passed(entry),
        }

    if fn == "get_recommended_lesson":
        lessons = case["lessons"]
        completed = case["completed_lessons"]
        result = get_recommended_lesson(lessons, completed)
        return {
            "fn": fn,
            "lessons": [lesson_to_fixture_dict(lesson) for lesson in lessons],
            "completed_lessons": completed,
            "python_result": result.id if result else None,
        }

    if fn == "get_continue_target":
        lessons = case["lessons"]
        completed = case["completed_lessons"]
        due_review_count = case["due_review_count"]

        if case.get("use_progress_manager"):
            manager = fresh_progress_manager()
            setup = case.get("progress_setup", {})
            attempt = setup.get("record_attempt")
            if attempt:
                manager.record_attempt(**attempt)
            attempted = manager.data["attempted_lessons"]
            target = get_continue_target(
                lessons=lessons,
                completed_lessons=completed,
                attempted_lessons=attempted,
                due_review_count=due_review_count,
                lesson_has_resume_state_fn=manager.lesson_has_resume_state,
                is_lesson_fully_passed_fn=manager.is_lesson_fully_passed,
            )
        else:
            attempted = case.get("attempted_lessons", [])
            target = get_continue_target(
                lessons=lessons,
                completed_lessons=completed,
                attempted_lessons=attempted,
                due_review_count=due_review_count,
                lesson_has_resume_state_fn=lambda _lesson: False,
                is_lesson_fully_passed_fn=lambda _lesson: False,
            )

        return {
            "fn": fn,
            "lessons": [lesson_to_fixture_dict(lesson) for lesson in lessons],
            "completed_lessons": completed,
            "attempted_lessons": attempted,
            "due_review_count": due_review_count,
            "use_progress_manager": case.get("use_progress_manager", False),
            "progress_setup": case.get("progress_setup"),
            "python_result": target,
        }

    if fn == "get_due_review_count":
        manager = fresh_progress_manager()
        setup = case.get("progress_setup", {})
        attempt = setup.get("record_attempt")
        if attempt:
            manager.record_attempt(**attempt)
        return {
            "fn": fn,
            "progress_setup": setup,
            "python_result": manager.get_due_review_count(),
        }

    raise ValueError(f"Unknown function: {fn}")


def main() -> None:
    fixtures = [build_fixture(case) for case in CASES]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(fixtures)} fixtures to {OUTPUT}")


if __name__ == "__main__":
    main()