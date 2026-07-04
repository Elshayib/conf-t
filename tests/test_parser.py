from __future__ import annotations

import pytest

from conf_t.parser import build_parser, has_cli_action


@pytest.fixture
def parser():
    return build_parser()


def test_default_no_action(parser):
    args = parser.parse_args([])
    assert has_cli_action(args) is False


def test_list_is_action(parser):
    args = parser.parse_args(["--list"])
    assert has_cli_action(args) is True
    assert args.list is True
    assert args.platform is None


def test_list_with_platform(parser):
    args = parser.parse_args(["--list", "--platform", "Cisco"])
    assert args.list is True
    assert args.platform == "Cisco"


def test_list_with_tags(parser):
    args = parser.parse_args(["--list", "--platform", "Cisco", "--tags", "vlan,ospf"])
    assert args.list is True
    assert args.tags == "vlan,ospf"


def test_lesson_is_action(parser):
    args = parser.parse_args(["--lesson", "cisco_basic"])
    assert has_cli_action(args) is True
    assert args.lesson == "cisco_basic"


def test_review_flags(parser):
    args = parser.parse_args(["--review"])
    assert has_cli_action(args) is True
    assert args.review is True

    args = parser.parse_args(["--review-all"])
    assert has_cli_action(args) is True
    assert args.review_all is True


def test_continue_is_action(parser):
    args = parser.parse_args(["--continue"])
    assert has_cli_action(args) is True
    assert args.continue_session is True


def test_stats_is_action(parser):
    args = parser.parse_args(["--stats"])
    assert has_cli_action(args) is True
    assert args.stats is True


def test_version_flag(parser):
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0


def test_run_lesson_by_id_unknown_exits(monkeypatch):
    from conf_t.cli import ConfTCLI

    app = ConfTCLI()
    monkeypatch.setattr(
        "conf_t.cli.sys.exit",
        lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )
    with pytest.raises(SystemExit) as exc:
        app.run_lesson_by_id("nonexistent_lesson_id_xyz")
    assert exc.value.code == 1