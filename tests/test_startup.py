"""CLI entry: a catalog refusal names the file and exits (#39)."""

from __future__ import annotations

import io
import json
import os
import stat
from contextlib import nullcontext
from pathlib import Path

import pytest
from rich.console import Console

from conf_t.catalog import Catalog
from conf_t.cli import ConfTCLI
from conf_t.main import main
from conf_t.parser import build_parser
from conf_t.models import TaskResult
from conf_t.session import Session
from tests.test_session import _DeniedRead


def _write(directory: Path, filename: str, body: dict) -> None:
    (directory / filename).write_text(json.dumps(body), encoding="utf-8")


def _lesson(lesson_id: str, *, title: str, task_id: str, expected: str = "^true$") -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "platform": "Linux",
        "description": "Desc",
        "tasks": [
            {
                "id": task_id,
                "prompt": "Run it",
                "prefix": "$",
                "expected": expected,
            }
        ],
    }


def _install_fault(directory: Path, fault: str) -> str:
    if fault == "parse":
        (directory / "broken.json").write_text("{", encoding="utf-8")
        _write(directory, "good.json", _lesson("good", title="Good", task_id="good__one"))
        return "broken.json"
    if fault == "duplicate":
        shared = "shared__one"
        _write(directory, "a.json", _lesson("alpha", title="Alpha", task_id=shared))
        _write(directory, "b.json", _lesson("beta", title="Beta", task_id=shared))
        return "b.json"
    if fault == "regex":
        _write(
            directory,
            "bad.json",
            _lesson("bad", title="Bad", task_id="bad__one", expected="[unterminated"),
        )
        return "bad.json"
    raise AssertionError(fault)


def _raise_exit(code: int = 0) -> None:
    raise SystemExit(code)


def _app(tmp_path: Path) -> ConfTCLI:
    return ConfTCLI(
        catalog=Catalog(tmp_path),
        session=Session(tmp_path / "progress.json"),
    )


@pytest.fixture
def output(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(
        "conf_t.cli.console",
        Console(file=buffer, force_terminal=False, no_color=True, highlight=False),
    )
    return buffer


@pytest.mark.parametrize("fault", ["parse", "duplicate", "regex"])
@pytest.mark.parametrize("command", ["menu", "list", "lesson", "continue", "review", "review-all"])
def test_reading_lessons_stops_and_names_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    fault: str,
    command: str,
) -> None:
    filename = _install_fault(tmp_path, fault)
    monkeypatch.setattr("conf_t.cli.sys.exit", _raise_exit)
    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("menu opened")),
    )
    app = _app(tmp_path)

    with pytest.raises(SystemExit) as exc:
        if command == "menu":
            app.run()
        else:
            argv = {
                "list": ["--list"],
                "lesson": ["--lesson", "no_such_lesson"],
                "continue": ["--continue"],
                "review": ["--review"],
                "review-all": ["--review-all"],
            }[command]
            app.run_from_args(build_parser().parse_args(argv))

    assert exc.value.code == 1
    text = output.getvalue()
    assert filename in text
    assert "Lesson not found" not in text


def test_unknown_lesson_is_not_a_file_that_will_not_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    _write(tmp_path, "real.json", _lesson("real", title="Real", task_id="real__one"))
    monkeypatch.setattr("conf_t.cli.sys.exit", _raise_exit)
    app = _app(tmp_path)

    with pytest.raises(SystemExit) as exc:
        app.run_from_args(build_parser().parse_args(["--lesson", "missing"]))

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Lesson not found" in text
    assert "missing" in text
    assert "does not parse" not in text


def test_stats_open_when_a_lesson_file_is_bad(
    tmp_path: Path,
    output: io.StringIO,
) -> None:
    _install_fault(tmp_path, "parse")
    app = _app(tmp_path)
    app.run_from_args(build_parser().parse_args(["--stats"]))
    text = output.getvalue()
    assert "Total Attempts Registered" in text
    assert "First-Try Correct Commands" in text
    assert "Skipped Commands" in text
    assert "Completed Lessons" not in text
    assert "Due for Review" not in text
    assert "Failed Commands Queue Size" not in text


def test_stats_command_omits_counts_until_lessons_are_supplied(
    tmp_path: Path,
    output: io.StringIO,
) -> None:
    _write(tmp_path, "good.json", _lesson("good", title="Good", task_id="good__one"))
    app = _app(tmp_path)
    lesson = app.catalog.lessons()[0]
    app.session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)

    app.run_from_args(build_parser().parse_args(["--stats"]))
    text = output.getvalue()
    assert "Total Attempts Registered" in text
    assert "Due for Review" not in text
    assert "Completed Lessons" not in text
    assert "Failed Commands Queue Size" not in text

    output.seek(0)
    output.truncate(0)
    app.view_stats(interactive=False, lessons=[lesson])
    shown = output.getvalue()
    assert "Due for Review" in shown
    assert "Completed Lessons" in shown
    assert "Failed Commands Queue Size" in shown
    assert "Total Attempts Registered" in shown


def test_version_runs_when_a_lesson_file_is_bad(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fault(tmp_path, "parse")
    monkeypatch.setattr("conf_t.cli.Catalog", lambda lessons_dir=None: Catalog(tmp_path))

    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert "conf-t" in capsys.readouterr().out


def test_list_stops_and_names_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output: io.StringIO,
) -> None:
    _install_fault(tmp_path, "regex")
    monkeypatch.setattr("conf_t.cli.Catalog", lambda lessons_dir=None: Catalog(tmp_path))
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(tmp_path / "progress.json"),
    )

    with pytest.raises(SystemExit) as exc:
        main(["--list"])

    assert exc.value.code == 0
    assert "bad.json" in output.getvalue()
    assert "Exiting Conf T..." in capsys.readouterr().out


def test_shape_problems_do_not_stop_the_lesson_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    _write(
        tmp_path,
        "shape.json",
        {
            "id": "shape",
            "title": "Shape Problems",
            "platform": "Linux",
            "description": "Desc",
            "difficulty": "expert",
            "prerequisites": ["missing_lesson"],
            "tasks": [
                {
                    "id": "Not-A-Slug",
                    "prompt": "Run it",
                    "prefix": "$",
                    "expected": "^echo$",
                },
                {
                    "id": "Also Bad",
                    "prompt": "Run it again",
                    "prefix": "$",
                    "expected": "^echo$",
                },
            ],
        },
    )
    monkeypatch.setattr(
        "conf_t.cli.sys.exit",
        lambda code=0: (_ for _ in ()).throw(AssertionError(f"exited {code}")),
    )
    app = _app(tmp_path)
    app.run_from_args(build_parser().parse_args(["--list"]))
    assert "Shape Problems" in output.getvalue()


_PROGRESS_COMMANDS = (
    [],
    ["--list"],
    ["--stats"],
    ["--continue"],
    ["--review"],
    ["--review-all"],
    ["--lesson", "cisco_basic"],
)


def _point_cli_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    progress: Path,
    *,
    broken_lesson: bool,
) -> None:
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    if broken_lesson:
        (lessons / "broken.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(
        "conf_t.cli.Catalog",
        lambda lessons_dir=None: Catalog(lessons),
    )
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(progress_path=progress),
    )


@pytest.mark.parametrize("fault", ["truncated", "unopenable"])
@pytest.mark.parametrize("argv", _PROGRESS_COMMANDS)
def test_unreadable_progress_stops_without_the_leave_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    fault: str,
    argv: list[str],
) -> None:
    progress = tmp_path / "progress.json"
    payload = (
        b'{"progress_version": 5, "task_progress":'
        if fault == "truncated"
        else b'{"progress_version": 5, "kept": true}'
    )
    progress.write_bytes(payload)
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=True)
    denied = _DeniedRead(progress) if fault == "unopenable" else nullcontext()

    with denied:
        with pytest.raises(SystemExit) as exc:
            main(argv)

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Cannot open progress." in text
    assert str(progress) in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    assert "Cannot open lessons." not in text
    assert "Lesson not found" not in text
    assert progress.read_bytes() == payload


def test_version_exits_without_opening_progress_or_lessons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    progress = tmp_path / "progress.json"
    payload = b'{"progress_version": 5, "task_progress":'
    progress.write_bytes(payload)
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=True)

    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "conf-t" in captured.out
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    text = output.getvalue()
    assert "Cannot open progress." not in text
    assert "Cannot open lessons." not in text
    assert progress.read_bytes() == payload


def test_interrupt_at_the_process_entry_prints_the_leave_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    progress = tmp_path / "progress.json"
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=False)

    def _interrupt(self: ConfTCLI, args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("conf_t.cli.ConfTCLI.run_from_args", _interrupt)

    with pytest.raises(SystemExit) as exc:
        main(["--stats"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Exiting Conf T..." in captured.out
    assert "Cannot open progress." not in output.getvalue()


def _freeze(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


def _thaw(path: Path) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)


class _Answer:
    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def _script_menu(
    monkeypatch: pytest.MonkeyPatch,
    choices: list[str],
    *,
    confirmed: bool = True,
) -> None:
    pending = iter(choices)
    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _Answer(next(pending)),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.confirm",
        lambda *args, **kwargs: _Answer(confirmed),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.press_any_key_to_continue",
        lambda *args, **kwargs: _Answer(None),
    )
    monkeypatch.setattr(
        "conf_t.cli.sys.exit",
        lambda code=0: (_ for _ in ()).throw(AssertionError(f"exited {code}")),
    )


def _cli(tmp_path: Path) -> ConfTCLI:
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    return ConfTCLI(
        catalog=Catalog(lessons_dir),
        session=Session(tmp_path / "progress.json"),
    )


def test_failed_reset_stays_on_the_menu_and_does_not_claim_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    app = _cli(tmp_path)
    _write(
        tmp_path / "lessons",
        "kept.json",
        _lesson("kept", title="Kept", task_id="kept__one"),
    )
    lesson = app.catalog.lessons()[0]
    app.session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    app.session.dismiss_welcome()
    path = tmp_path / "progress.json"
    before = path.read_bytes()
    _script_menu(monkeypatch, ["reset", "exit"])

    _freeze(path)
    try:
        app.run()
    finally:
        _thaw(path)

    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(path) in text
    assert "reset successfully" not in text
    assert "Thank you for training with Conf T" in text
    assert path.read_bytes() == before


def test_failed_welcome_dismissal_lets_this_launch_continue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    app = _cli(tmp_path)
    _write(
        tmp_path / "lessons",
        "kept.json",
        _lesson("kept", title="Kept", task_id="kept__one"),
    )
    app.session.dismiss_welcome()
    app.session.reset_all()
    path = tmp_path / "progress.json"
    before = path.read_bytes()
    assert app.session.should_show_welcome() is True
    _script_menu(monkeypatch, ["exit"])

    _freeze(path)
    try:
        app.run()
    finally:
        _thaw(path)

    text = output.getvalue()
    assert "Welcome!" in text
    assert "Cannot save progress." in text
    assert str(path) in text
    assert "Thank you for training with Conf T" in text
    assert path.read_bytes() == before
    assert Session(progress_path=path).should_show_welcome() is True


def _kept_lesson(*task_ids: str) -> dict:
    body = _lesson("kept", title="Kept", task_id=task_ids[0])
    body["tasks"] = [
        {
            "id": task_id,
            "prompt": "Run it",
            "prefix": "$",
            "expected": "^true$",
        }
        for task_id in task_ids
    ]
    return body


def test_failed_stats_rewrite_shows_first_try_counts_and_does_not_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    app = _cli(tmp_path)
    lessons_dir = tmp_path / "lessons"
    _write(lessons_dir, "kept.json", _kept_lesson("kept__a", "kept__b"))
    lesson = app.catalog.lessons()[0]
    app.session.record_attempt(lesson, lesson.tasks[0], TaskResult.FIRST_TRY_PASS)
    app.session.record_attempt(lesson, lesson.tasks[1], TaskResult.FIRST_TRY_PASS)
    app.session.dismiss_welcome()
    path = tmp_path / "progress.json"
    before = path.read_bytes()
    _write(lessons_dir, "kept.json", _kept_lesson("kept__a", "kept__b", "kept__c"))
    _script_menu(monkeypatch, ["stats", "exit"])

    _freeze(path)
    try:
        app.run()
    finally:
        _thaw(path)

    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(path) in text
    assert "Thank you for training with Conf T" in text
    completed = next(line for line in text.splitlines() if "Completed Lessons" in line)
    attempts = next(line for line in text.splitlines() if "Total Attempts Registered" in line)
    first_try = next(line for line in text.splitlines() if "First-Try Correct Commands" in line)
    assert "0" in completed
    assert "1" not in completed
    assert "2" in attempts
    assert "2" in first_try
    assert "Due for Review" in text
    assert "Failed Commands Queue Size" in text
    assert path.read_bytes() == before
