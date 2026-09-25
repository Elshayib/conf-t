"""Git path assignable-lesson checks (issue #5).

Seam: load a lesson, then validate answers the way Practice does via
validate_input. Assert pass/fail commands for new and repaired tasks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conf_t.engine import validate_input
from conf_t.models import Lesson, Task

LESSONS_DIR = Path(__file__).parent.parent / "conf_t" / "lessons"

GIT_LESSON_IDS = [
    "git_basic",
    "git_staging",
    "git_branching",
    "git_merging",
    "git_remote",
    "git_stash",
    "git_tags",
    "git_rebasing",
    "git_recovery",
    "git_troubleshooting_lab",
]


def _load_lesson(lesson_id: str) -> Lesson:
    path = LESSONS_DIR / f"{lesson_id}.json"
    with open(path, encoding="utf-8") as f:
        return Lesson.from_dict(json.load(f))


def _task_by_id(lesson: Lesson, task_id: str) -> Task:
    for task in lesson.tasks:
        if task.id == task_id:
            return task
    raise AssertionError(f"Task '{task_id}' not found in lesson '{lesson.id}'")


def _assert_accepts(task: Task, command: str) -> None:
    assert validate_input(command, task, "Git") is True, (
        f"Expected accept for {task.id!r}: {command!r}"
    )


def _assert_rejects(task: Task, command: str) -> None:
    assert validate_input(command, task, "Git") is False, (
        f"Expected reject for {task.id!r}: {command!r}"
    )


@pytest.fixture(scope="module")
def git_basic() -> Lesson:
    return _load_lesson("git_basic")


def test_beginner_lesson_starts_with_init(git_basic: Lesson):
    assert git_basic.tasks[0].id == "git_basic__init"


def test_beginner_local_user_name_task_after_init(git_basic: Lesson):
    assert git_basic.tasks[1].id == "git_basic__config_user_name"
    task = git_basic.tasks[1]

    _assert_accepts(task, 'git config user.name "Ada Lovelace"')
    _assert_accepts(task, "git config user.name 'Ada Lovelace'")
    _assert_accepts(task, 'git config --local user.name "Ada Lovelace"')
    _assert_accepts(task, "git config --local user.name 'Ada Lovelace'")
    _assert_rejects(task, 'git config --global user.name "Ada Lovelace"')
    _assert_rejects(task, 'GIT CONFIG USER.NAME "Ada Lovelace"')


def test_beginner_local_user_email_task_after_name(git_basic: Lesson):
    assert git_basic.tasks[2].id == "git_basic__config_user_email"
    task = git_basic.tasks[2]

    _assert_accepts(task, 'git config user.email "ada@example.com"')
    _assert_accepts(task, "git config user.email 'ada@example.com'")
    _assert_accepts(task, 'git config --local user.email "ada@example.com"')
    _assert_accepts(task, "git config --local user.email 'ada@example.com'")
    _assert_rejects(task, 'git config --global user.email "ada@example.com"')
    _assert_rejects(task, 'GIT CONFIG USER.EMAIL "ada@example.com"')


def test_beginner_existing_tasks_keep_relative_order(git_basic: Lesson):
    ids = [t.id for t in git_basic.tasks]
    relative = [
        "git_basic__init",
        "git_basic__clone",
        "git_basic__status",
        "git_basic__add_all",
        "git_basic__commit",
        "git_basic__checkout_branch",
    ]
    positions = [ids.index(tid) for tid in relative]
    assert positions == sorted(positions)


def test_beginner_ignore_file_before_stage_all(git_basic: Lesson):
    ids = [t.id for t in git_basic.tasks]
    ignore_idx = ids.index("git_basic__gitignore_log")
    add_idx = ids.index("git_basic__add_all")
    assert ignore_idx == add_idx - 1

    task = _task_by_id(git_basic, "git_basic__gitignore_log")
    _assert_accepts(task, 'echo "*.log" >> .gitignore')
    _assert_accepts(task, "echo '*.log' >> .gitignore")
    _assert_rejects(task, 'echo "*.log" > .gitignore')
    _assert_rejects(task, "echo *.log >> .gitignore")
    _assert_rejects(task, "git check-ignore *.log")


def test_beginner_existing_tasks_accept_real_git(git_basic: Lesson):
    cases = [
        ("git_basic__init", "git init", "git init --bare"),
        ("git_basic__clone", "git clone https://github.com/user/repo.git", "git pull"),
        ("git_basic__status", "git status", "git status --short"),
        ("git_basic__add_all", "git add .", "git add app.py"),
        ("git_basic__commit", 'git commit -m "initial commit"', "git commit"),
        ("git_basic__checkout_branch", "git checkout -b feature", "git branch feature"),
    ]
    for task_id, good, bad in cases:
        task = _task_by_id(git_basic, task_id)
        _assert_accepts(task, good)
        _assert_rejects(task, bad)


def test_merging_show_merge_accepts_real_git_command():
    """git show --merge is not a Git option; accept a real command instead."""
    lesson = _load_lesson("git_merging")
    task = _task_by_id(lesson, "git_merging__show_merge")

    _assert_accepts(task, "git log -1 --merges")
    _assert_accepts(task, "git log --merges -1")
    _assert_rejects(task, "git show --merge")


def test_staging_commit_message_drops_misleading_verbose_flag():
    """-v with -m does not show a diffstat; drill the real message form."""
    lesson = _load_lesson("git_staging")
    task = _task_by_id(lesson, "git_staging__commit_verbose")

    _assert_accepts(task, 'git commit -m "fix login bug"')
    _assert_accepts(task, "git commit -m 'fix login bug'")
    _assert_rejects(task, 'git commit -v -m "fix login bug"')


@pytest.mark.parametrize("lesson_id", GIT_LESSON_IDS)
def test_git_lesson_tasks_have_explanation_and_accept_alias(lesson_id: str):
    """Every Git lesson task teaches why and accepts a real listed spelling."""
    lesson = _load_lesson(lesson_id)
    assert lesson.platform == "Git"
    for task in lesson.tasks:
        assert task.explanation.strip(), f"{task.id} missing explanation"
        assert len(task.prompt.strip()) > 0
        if task.aliases:
            _assert_accepts(task, task.aliases[0])
