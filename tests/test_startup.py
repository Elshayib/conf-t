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


def _lesson(
    lesson_id: str,
    *,
    title: str,
    task_id: str,
    expected: str = "^true$",
    platform: str = "Linux",
    tags: list[str] | None = None,
) -> dict:
    body = {
        "id": lesson_id,
        "title": title,
        "platform": platform,
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
    if tags:
        body["tags"] = tags
    return body


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
    capsys: pytest.CaptureFixture[str],
    fault: str,
    command: str,
) -> None:
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    filename = _install_fault(lessons, fault)
    monkeypatch.setattr("conf_t.cli.Catalog", lambda lessons_dir=None: Catalog(lessons))
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(tmp_path / "progress.json"),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("menu opened")),
    )
    argv = {
        "menu": [],
        "list": ["--list"],
        "lesson": ["--lesson", "no_such_lesson"],
        "continue": ["--continue"],
        "review": ["--review"],
        "review-all": ["--review-all"],
    }[command]

    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 1
    text = output.getvalue()
    assert filename in text
    assert "Lesson not found" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err


def test_unknown_lesson_is_not_a_file_that_will_not_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "real.json", _lesson("real", title="Real", task_id="real__one"))
    opened = _block_prompts(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main(["--lesson", "missing"])

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Lesson not found:" in text
    assert "missing" in text
    assert "Use --list to see available lesson IDs." in text
    assert "does not parse" not in text
    assert opened == []
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err


def test_empty_lesson_id_is_a_refusal_and_does_not_open_the_menu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "real.json", _lesson("real", title="Real", task_id="real__one"))
    opened = _block_prompts(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main(["--lesson", ""])

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Lesson not found:" in text
    assert "Welcome to Conf T" not in text
    assert opened == []
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err


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

    assert exc.value.code == 1
    assert "bad.json" in output.getvalue()
    assert "Cannot open lessons." in output.getvalue()
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err


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


@pytest.mark.parametrize("argv", _PROGRESS_COMMANDS)
def test_unrewritable_old_progress_stops_without_the_leave_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    progress = tmp_path / "progress.json"
    payload = json.dumps(
        {
            "progress_version": 4,
            "total_attempts": 2,
            "task_progress": {
                "open_l__miss": {
                    "lesson_id": "open_l",
                    "status": "failed",
                    "passed_first_try": False,
                    "attempts": 1,
                }
            },
        }
    ).encode()
    progress.write_bytes(payload)
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=True)

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main(argv)
    finally:
        _thaw(progress)

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert "Cannot open progress." not in text
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


def test_quitting_exits_0_and_prints_the_leave_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _Answer("exit"),
    )

    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 0
    text = output.getvalue()
    assert "Thank you for training with Conf T" in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." in captured.out
    assert "Cannot open lessons." not in text
    assert "Lesson not found" not in text


def test_ctrl_c_on_the_menu_returns_to_the_menu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    choices = iter(["interrupt", "exit"])

    class _MenuQuestion:
        """The menu must ask without swallowing Ctrl+C."""

        def ask(self) -> str:
            raise AssertionError("menu swallowed Ctrl+C")

        def unsafe_ask(self) -> str:
            choice = next(choices)
            if choice == "interrupt":
                raise KeyboardInterrupt
            return choice

    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _MenuQuestion(),
    )

    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 0
    text = output.getvalue()
    assert "Session interrupted. Returning to main menu." in text
    assert "Thank you for training with Conf T" in text
    assert "Practice aborted." not in text
    assert "Exiting Conf T..." in capsys.readouterr().out


def test_ctrl_c_during_a_sitting_leaves_that_sitting_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    choices = iter(["practice", "Linux", "alpha", "exit"])

    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _Answer(next(choices)),
    )
    monkeypatch.setattr(
        "conf_t.cli.console.input",
        lambda prompt="": (_ for _ in ()).throw(KeyboardInterrupt),
    )

    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 0
    text = output.getvalue()
    assert "Practice aborted." in text
    assert "Session interrupted. Returning to main menu." not in text
    assert "Thank you for training with Conf T" in text
    assert "Exiting Conf T..." in capsys.readouterr().out


def test_catalog_refusal_while_saving_a_custom_lesson_stays_in_the_wizard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    choices = iter(["create", "Linux", "exit"])
    replies = iter([
        "Broken",
        "broken",
        "Desc",
        "Run it",
        "[unterminated",
        "",
        "$",
        "",
        "",
    ])
    paused: list[str] = []

    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _Answer(next(choices)),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.text",
        lambda *args, **kwargs: _Answer(next(replies)),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.confirm",
        lambda *args, **kwargs: _Answer(False),
    )

    def pause(*args: object, **kwargs: object) -> _Answer:
        paused.append("paused")
        return _Answer(None)

    monkeypatch.setattr("conf_t.cli.questionary.press_any_key_to_continue", pause)

    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 0
    text = output.getvalue()
    assert "broken.json" in text
    assert "expected regex does not compile" in text
    assert "Success" not in text
    assert paused == ["paused"]
    assert "Thank you for training with Conf T" in text
    assert not (lessons / "broken.json").exists()
    captured = capsys.readouterr()
    assert "Exiting Conf T..." in captured.out
    assert "Cannot open lessons." not in text


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

    def unsafe_ask(self) -> object:
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

def _use_isolated_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    monkeypatch.setattr("conf_t.cli.Catalog", lambda lessons_dir=None: Catalog(lessons))
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(tmp_path / "progress.json"),
    )
    return lessons


def _block_prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answer prompts without waiting, and record each menu prompt."""
    opened: list[str] = []

    class _Answer:
        def ask(self) -> None:
            return None

        def unsafe_ask(self) -> None:
            return None

    def select(*args: object, **kwargs: object) -> _Answer:
        opened.append(str(args[0]) if args else "")
        return _Answer()

    def ask_nothing(*args: object, **kwargs: object) -> _Answer:
        return _Answer()

    def no_input(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("conf_t.cli.questionary.select", select)
    monkeypatch.setattr("conf_t.cli.questionary.confirm", ask_nothing)
    monkeypatch.setattr("conf_t.cli.questionary.text", ask_nothing)
    monkeypatch.setattr("conf_t.cli.questionary.press_any_key_to_continue", ask_nothing)
    monkeypatch.setattr("conf_t.cli.console.input", no_input)
    return opened


_COMMAND_FLAGS_IN_RUN_ORDER = (
    "--list",
    "--stats",
    "--continue",
    "--review",
    "--review-all",
    "--lesson",
)


def test_help_lists_command_flags_in_the_order_the_first_set_flag_runs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The declaration order is the order that picks the command."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    text = capsys.readouterr().out
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        for flag in _COMMAND_FLAGS_IN_RUN_ORDER:
            if stripped.startswith(flag) and (
                len(stripped) == len(flag) or stripped[len(flag)].isspace()
            ):
                found.append(flag)
    assert found == list(_COMMAND_FLAGS_IN_RUN_ORDER)
    assert "Exiting Conf T..." not in text


def _commands_help_accepts(help_text: str) -> list[list[str]]:
    """Command flags printed by --help, in that order.

    An option line is indented two spaces. Platform, tags, and version are
    filters or a version exit, not commands. A metavar such as ID means the
    flag takes the Lesson id.
    """
    not_commands = {"--version", "--platform", "--tags"}
    invocations: list[list[str]] = []
    for line in help_text.splitlines():
        if not line.startswith("  --"):
            continue
        parts = line.split()
        option = parts[0]
        if option in not_commands:
            continue
        argv = [option]
        if len(parts) > 1 and parts[1].isupper():
            argv.append("alpha")
        invocations.append(argv)
    return invocations


def test_an_accepted_command_flag_does_not_open_the_menu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A flag the process accepts cannot fall through to the menu."""
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    opened = _block_prompts(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    invocations = _commands_help_accepts(capsys.readouterr().out)

    for argv in invocations:
        main(argv)

    assert [argv[0] for argv in invocations] == list(_COMMAND_FLAGS_IN_RUN_ORDER)
    assert all("Select an option:" not in prompt for prompt in opened)
    assert "Welcome to Conf T" not in output.getvalue()


def test_list_with_platform_and_tags_lists_the_filtered_lessons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(
        lessons,
        "vlan.json",
        _lesson(
            "vlan",
            title="Switching VLAN",
            task_id="vlan__one",
            platform="Cisco",
            tags=["vlan", "switching"],
        ),
    )
    _write(
        lessons,
        "ospf.json",
        _lesson(
            "ospf",
            title="Single Area OSPF",
            task_id="ospf__one",
            platform="Cisco",
            tags=["ospf"],
        ),
    )
    _write(
        lessons,
        "files.json",
        _lesson(
            "files",
            title="Linux Files",
            task_id="files__one",
            platform="Linux",
            tags=["vlan"],
        ),
    )
    opened = _block_prompts(monkeypatch)

    main(["--list", "--platform", "Cisco", "--tags", "vlan"])

    text = output.getvalue()
    assert "Switching VLAN" in text
    assert "Single Area OSPF" not in text
    assert "Linux Files" not in text
    assert "1 lesson(s) shown" in text
    assert opened == []


def test_unknown_flag_is_rejected_before_any_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    opened = _block_prompts(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main(["--not-a-command"])

    assert exc.value.code == 2
    assert opened == []
    text = output.getvalue()
    assert "Welcome to Conf T" not in text
    assert "Select an option:" not in text
    captured = capsys.readouterr()
    assert "unrecognized arguments" in captured.err
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err


@pytest.mark.parametrize(
    ("argv", "shown"),
    [
        (
            ["--stats", "--continue", "--review", "--review-all", "--lesson", "alpha", "--list"],
            "lesson(s) shown",
        ),
        (
            ["--continue", "--review", "--review-all", "--lesson", "alpha", "--stats"],
            "Total Attempts Registered",
        ),
        (
            ["--review", "--review-all", "--lesson", "alpha", "--continue"],
            "Continuing:",
        ),
        (
            ["--review-all", "--lesson", "alpha", "--review"],
            "No tasks due for review",
        ),
        (
            ["--lesson", "alpha", "--review-all"],
            "no failed commands to review",
        ),
        (
            ["--lesson", "alpha"],
            "tasks passed",
        ),
    ],
)
def test_first_set_command_flag_runs_and_the_others_are_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    argv: list[str],
    shown: str,
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    opened = _block_prompts(monkeypatch)

    main(argv)

    text = output.getvalue()
    markers = (
        "lesson(s) shown",
        "Total Attempts Registered",
        "Continuing:",
        "No tasks due for review",
        "no failed commands to review",
        "tasks passed",
    )
    for marker in markers:
        assert (marker in text) == (marker == shown), marker
    assert opened == []


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--platform", "Cisco"],
        ["--tags", "vlan"],
        ["--platform", "Cisco", "--tags", "vlan,ospf"],
    ],
)
def test_menu_opens_when_no_command_flag_is_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _write(lessons, "alpha.json", _lesson("alpha", title="Alpha", task_id="alpha__one"))
    opened = _block_prompts(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 0
    text = output.getvalue()
    assert opened == ["Select an option:"]
    assert "Welcome to Conf T" in text
    assert "Exiting Conf T..." in capsys.readouterr().out
    assert "lesson(s) shown" not in text
    assert "Total Attempts Registered" not in text
    assert "Continuing:" not in text
    assert "No tasks due for review" not in text
    assert "no failed commands to review" not in text
    assert "tasks passed" not in text


def test_stats_still_runs_when_lessons_cannot_be_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
) -> None:
    lessons = _use_isolated_files(monkeypatch, tmp_path)
    _install_fault(lessons, "parse")
    opened = _block_prompts(monkeypatch)

    main(["--continue", "--review", "--review-all", "--lesson", "alpha", "--stats"])

    text = output.getvalue()
    assert "Total Attempts Registered" in text
    assert "First-Try Correct Commands" in text
    assert "Skipped Commands" in text
    assert "Cannot open lessons" not in text
    assert "Continuing:" not in text
    assert "No tasks due for review" not in text
    assert "no failed commands to review" not in text
    assert "Lesson not found" not in text
    assert opened == []


def test_lesson_flag_does_not_start_when_the_lesson_cannot_be_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    progress = tmp_path / "progress.json"
    Session(progress_path=progress).dismiss_welcome()
    before = progress.read_bytes()
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=False)
    _write(
        tmp_path / "lessons",
        "kept.json",
        _lesson("kept", title="Kept", task_id="kept__one"),
    )
    monkeypatch.setattr(
        "conf_t.cli.console.input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("sitting started")),
    )

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main(["--lesson", "kept"])
    finally:
        _thaw(progress)

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(progress) in text
    assert "Type 'hint'" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    assert progress.read_bytes() == before


def _refuse_sitting_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "conf_t.cli.console.input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("sitting started")),
    )


def test_continue_flag_does_not_start_when_the_lesson_cannot_be_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    progress = tmp_path / "progress.json"
    Session(progress_path=progress).dismiss_welcome()
    before = progress.read_bytes()
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=False)
    _write(
        tmp_path / "lessons",
        "kept.json",
        _lesson("kept", title="Kept", task_id="kept__one"),
    )
    _refuse_sitting_input(monkeypatch)

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main(["--continue"])
    finally:
        _thaw(progress)

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(progress) in text
    assert "Type 'hint'" not in text
    assert "Continuing:" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    assert progress.read_bytes() == before


def _history_due_but_not_opened(tmp_path: Path) -> Path:
    """A due Task whose Lesson is not yet recorded as opened.

    A recorded line also records the Lesson as opened. Drop that mark so
    the next sitting has to save it.
    """
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    _write(lessons, "kept.json", _lesson("kept", title="Kept", task_id="kept__one"))
    progress = tmp_path / "progress.json"
    lesson = Catalog(lessons).lessons()[0]
    session = Session(progress_path=progress)
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.dismiss_welcome()
    stored = json.loads(progress.read_text(encoding="utf-8"))
    stored["attempted_lessons"] = []
    progress.write_text(json.dumps(stored), encoding="utf-8")
    return progress


@pytest.mark.parametrize("argv", [["--review"], ["--review-all"], ["--continue"]])
def test_review_flags_do_not_start_when_the_lesson_cannot_be_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    progress = _history_due_but_not_opened(tmp_path)
    before = progress.read_bytes()
    monkeypatch.setattr(
        "conf_t.cli.Catalog",
        lambda lessons_dir=None: Catalog(tmp_path / "lessons"),
    )
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(progress_path=progress),
    )
    _refuse_sitting_input(monkeypatch)

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main(argv)
    finally:
        _thaw(progress)

    assert exc.value.code == 1
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(progress) in text
    assert "Type 'hint'" not in text
    assert "Continuing:" not in text
    assert "Reviewing" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    assert progress.read_bytes() == before


def test_menu_stays_when_a_lesson_cannot_be_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    progress = tmp_path / "progress.json"
    Session(progress_path=progress).dismiss_welcome()
    before = progress.read_bytes()
    _point_cli_at(tmp_path, monkeypatch, progress, broken_lesson=False)
    _write(
        tmp_path / "lessons",
        "kept.json",
        _lesson("kept", title="Kept", task_id="kept__one"),
    )
    _script_menu(monkeypatch, ["practice", "Linux", "kept", "exit"])
    _refuse_sitting_input(monkeypatch)

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main([])
    finally:
        _thaw(progress)

    assert exc.value.code == 0
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(progress) in text
    assert "Thank you for training with Conf T" in text
    assert "Type 'hint'" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." in captured.out
    assert progress.read_bytes() == before


@pytest.mark.parametrize(
    "choice",
    ["continue", "due_review", "failed_drill"],
)
def test_menu_stays_when_continue_or_review_cannot_be_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    choice: str,
) -> None:
    progress = _history_due_but_not_opened(tmp_path)
    before = progress.read_bytes()
    monkeypatch.setattr(
        "conf_t.cli.Catalog",
        lambda lessons_dir=None: Catalog(tmp_path / "lessons"),
    )
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(progress_path=progress),
    )
    _script_menu(monkeypatch, [choice, "exit"])
    _refuse_sitting_input(monkeypatch)

    _freeze(progress)
    try:
        with pytest.raises(SystemExit) as exc:
            main([])
    finally:
        _thaw(progress)

    assert exc.value.code == 0
    text = output.getvalue()
    assert "Cannot save progress." in text
    assert str(progress) in text
    assert "Thank you for training with Conf T" in text
    assert "Type 'hint'" not in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." in captured.out
    assert progress.read_bytes() == before


@pytest.mark.parametrize("argv", [["--lesson", "kept"], ["--review"], ["--review-all"]])
def test_failed_line_stays_on_the_open_showing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: io.StringIO,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    _write(lessons, "kept.json", _lesson("kept", title="Kept", task_id="kept__one"))
    progress = tmp_path / "progress.json"
    lesson = Catalog(lessons).lessons()[0]
    session = Session(progress_path=progress)
    session.record_attempt(lesson, lesson.tasks[0], TaskResult.INCORRECT)
    session.dismiss_welcome()
    before = progress.read_bytes()
    monkeypatch.setattr(
        "conf_t.cli.Catalog",
        lambda lessons_dir=None: Catalog(lessons),
    )
    monkeypatch.setattr(
        "conf_t.cli.Session",
        lambda *args, **kwargs: Session(progress_path=progress),
    )
    lines = iter(["true", "exit"])
    prompts: list[str] = []

    def answer(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(lines)

    monkeypatch.setattr("conf_t.cli.console.input", answer)
    monkeypatch.setattr(
        "conf_t.cli.questionary.select",
        lambda *args, **kwargs: _Answer("resume"),
    )
    monkeypatch.setattr(
        "conf_t.cli.questionary.confirm",
        lambda *args, **kwargs: _Answer(True),
    )

    _freeze(progress)
    try:
        main(argv)
    finally:
        _thaw(progress)

    text = output.getvalue()
    assert prompts == ["$ ", "$ "]
    assert "That attempt was not stored." in text
    assert "Cannot save progress." not in text
    assert "✓ Correct!" in text
    captured = capsys.readouterr()
    assert "Exiting Conf T..." not in captured.out
    assert "Exiting Conf T..." not in captured.err
    assert progress.read_bytes() == before
