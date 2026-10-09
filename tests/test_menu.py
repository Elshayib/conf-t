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
    lesson = Lesson(
        id="l",
        title="Lesson",
        platform="Linux",
        description="Desc",
        tasks=[task],
    )
    session = Session(tmp_path / "progress.json")
    session.record_attempt(lesson, task, TaskResult.INCORRECT)
    choices = _app(tmp_path, session)._main_menu_choices()

    assert choices[0].title == "★ Daily Review (1 due)"
    assert choices[0].value == "due_review"
    assert choices[1].value == "continue"


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
