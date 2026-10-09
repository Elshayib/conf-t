"""CLI entry: a catalog refusal names the file and exits (#39)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from conf_t.catalog import Catalog
from conf_t.cli import ConfTCLI
from conf_t.main import main
from conf_t.parser import build_parser
from conf_t.models import TaskResult
from conf_t.session import Session


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
