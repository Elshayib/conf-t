"""Main menu values and Review sitting wording (#38)."""

import io
from pathlib import Path

import pytest
from rich.console import Console

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


def test_review_sentence_follows_the_showing(tmp_path: Path) -> None:
    session = Session(tmp_path / "progress.json")
    lesson = Lesson(
        id="l",
        title="Lesson",
        platform="Linux",
        description="Desc",
        tasks=[
            Task(id="l__clean", prompt="Run it", prefix="$", expected="^ok$"),
            Task(id="l__late", prompt="Run it", prefix="$", expected="^ok$"),
        ],
    )
    clean, late_task = lesson.tasks

    session.begin_task(clean)
    session.submit(lesson, clean, "nope")
    session.begin_task(clean)
    passed = session.submit(lesson, clean, "ok")
    assert review_correct_message(passed) == "✓ Correct! This Task left the drill."

    session.begin_task(late_task)
    session.submit(lesson, late_task, "nope")
    rescheduled = session.submit(lesson, late_task, "ok")
    assert review_correct_message(rescheduled) == (
        "✓ Correct, but not first-try — rescheduled for later review"
    )


def test_practice_menu_offers_an_unknown_difficulty_in_catalog_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lessons_dir = tmp_path / "lessons"

    def save(lesson_id: str, title: str, platform: str, difficulty: str) -> None:
        lesson = Lesson(
            id=lesson_id,
            title=title,
            platform=platform,
            description="Desc",
            difficulty=difficulty,
            tasks=[
                Task(
                    id=f"{lesson_id}__one",
                    prompt="Run it",
                    prefix="$",
                    expected="^true$",
                )
            ],
        )
        assert Catalog(lessons_dir).save_lesson(lesson) is True

    save("zebra", "Zebra", "Linux", "beginner")
    save("apple", "Apple", "Linux", "expert")
    save("mango", "Mango", "Linux", "expert")
    save("hidden", "Hidden", "Cisco", "beginner")

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
    ConfTCLI(
        catalog=Catalog(lessons_dir),
        session=Session(tmp_path / "progress.json"),
    ).practice_lessons_menu()

    def at(fragment: str) -> int:
        return next(index for index, title in enumerate(seen) if fragment in title)

    assert at("── Beginner ──") < at("○ Zebra")
    assert at("○ Zebra") < at("── Expert ──")
    assert at("── Expert ──") < at("○ Apple") < at("○ Mango")
    assert all("Hidden" not in title for title in seen)


def test_continue_opens_the_due_review_it_already_chose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = Task(id="l__a", prompt="Run it", prefix="$", expected="^true$")
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
    app = ConfTCLI(catalog=Catalog(lessons_dir), session=session)

    buffer = io.StringIO()
    monkeypatch.setattr(
        "conf_t.cli.console",
        Console(file=buffer, force_terminal=False, no_color=True, highlight=False),
    )
    captured: dict[str, object] = {}

    def run_review(tasks, **kwargs):
        captured["tasks"] = tasks

    due_calls = {"n": 0}
    original_due = session.due_review

    def counting(lessons):
        due_calls["n"] += 1
        return original_due(lessons)

    session.due_review = counting
    chosen: dict[str, object] = {}
    original_continue = session.continue_target

    def wrapping(lessons, **kwargs):
        chosen["value"] = original_continue(lessons, **kwargs)
        return chosen["value"]

    session.continue_target = wrapping
    monkeypatch.setattr(app, "_run_review_session", run_review)

    app.run_continue(interactive=False)

    assert due_calls["n"] == 1
    assert captured["tasks"] is chosen["value"]
    assert len(captured["tasks"]) == 1
    assert captured["tasks"][0][1].id == "l__a"
    text = buffer.getvalue()
    assert "Daily Review" in text
    assert "1 task(s) due" in text
