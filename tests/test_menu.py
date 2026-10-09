"""Main menu values and Review sitting wording (#38)."""

from pathlib import Path

import pytest

from conf_t.catalog import Catalog
from conf_t.cli import (
    ConfTCLI,
    interrupt_message,
    review_correct_message,
)
from conf_t.models import Lesson, Task
from conf_t.session import Session, TaskResult


def _app(tmp_path: Path, session: Session | None = None) -> ConfTCLI:
    return ConfTCLI(
        catalog=Catalog(tmp_path),
        session=session or Session(tmp_path / "progress.json"),
    )


def test_menu_keeps_its_wording_and_stable_values(tmp_path: Path) -> None:
    choices = _app(tmp_path)._main_menu_choices()
    assert [(choice.title, choice.value) for choice in choices] == [
        ("↩ Continue where I left off", "continue"),
        ("1. Practice a Lesson", "practice"),
        ("2. Review All Failed Commands", "failed_drill"),
        ("3. View Progress & Stats", "stats"),
        ("4. Reset All Progress", "reset"),
        ("5. Create a Custom Lesson", "create"),
        ("6. Exit", "exit"),
    ]


def test_due_review_keeps_its_wording_and_value(tmp_path: Path) -> None:
    task = Task(id="l__a", prompt="Run it", prefix="$", expected="^true$")
    gone = Task(id="l__gone", prompt="Missing", prefix="$", expected="^true$")
    lesson = Lesson(
        id="l",
        title="Lesson",
        platform="Linux",
        description="Desc",
        tasks=[task],
    )
    lessons_dir = tmp_path / "lessons"
    assert Catalog(lessons_dir).save_lesson(lesson) is True
    session = Session(tmp_path / "progress.json")
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    session.record_attempt(
        Lesson(
            id="l",
            title="Lesson",
            platform="Linux",
            description="Desc",
            tasks=[task, gone],
        ),
        gone,
        TaskResult.INCORRECT,
    )
    choices = ConfTCLI(catalog=Catalog(lessons_dir), session=session)._main_menu_choices()

    assert choices[0].title == "★ Daily Review (1 due)"
    assert choices[0].value == "due_review"
    assert choices[1].value == "continue"


def test_practice_menu_failed_count_skips_a_task_that_left_the_lesson(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept = Task(id="l__kept", prompt="Keep", prefix="$", expected="^true$")
    gone = Task(id="l__gone", prompt="Gone", prefix="$", expected="^true$")
    lesson = Lesson(
        id="l",
        title="Lesson",
        platform="Linux",
        description="Desc",
        tasks=[kept],
    )
    lessons_dir = tmp_path / "lessons"
    assert Catalog(lessons_dir).save_lesson(lesson) is True
    session = Session(tmp_path / "progress.json")
    session.record_attempt(lesson, kept, TaskResult.INCORRECT)
    session.record_attempt(
        Lesson(
            id="l",
            title="Lesson",
            platform="Linux",
            description="Desc",
            tasks=[kept, gone],
        ),
        gone,
        TaskResult.INCORRECT,
    )
    seen: list[str] = []

    class _Answer:
        def __init__(self, value: str) -> None:
            self._value = value

        def ask(self) -> str:
            return self._value

    def select(message: str, *, choices, **kwargs):
        if message == "Choose a platform:":
            return _Answer("Linux")
        seen.extend(choice.title for choice in choices)
        return _Answer("__back__")

    monkeypatch.setattr("conf_t.cli.questionary.select", select)
    ConfTCLI(catalog=Catalog(lessons_dir), session=session).practice_lessons_menu()

    assert "◐ Lesson (0/1 · 0%) · 1 failed" in seen
    assert all("2 failed" not in title for title in seen)


def test_menu_dispatch_follows_the_value_not_the_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    called: list[str] = []
    monkeypatch.setattr(app, "practice_lessons_menu", lambda: called.append("practice"))
    monkeypatch.setattr(app, "view_stats", lambda: called.append("stats"))

    assert app._dispatch_menu("practice") is True
    assert app._dispatch_menu("1. Practice a Lesson") is False
    assert app._dispatch_menu("stats") is True
    assert called == ["practice", "stats"]


def test_interrupting_review_says_the_learner_left_review() -> None:
    assert interrupt_message(review=True) == "You left Review."
    assert interrupt_message(review=False) == "Practice aborted."


def test_review_says_when_a_task_leaves_the_drill_or_is_rescheduled() -> None:
    assert review_correct_message(first_try=True) == "✓ Correct! This Task left the drill."
    assert review_correct_message(first_try=False) == (
        "✓ Correct, but not first-try — rescheduled for later review"
    )
