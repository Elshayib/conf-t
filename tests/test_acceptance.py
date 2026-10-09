"""Command acceptance: a line answers a Task, and skip shows one command (#37)."""

from conf_t.acceptance import format_display_answer, validate_input
from conf_t.models import Task


def test_cisco_answers_ignore_case() -> None:
    task = Task(
        id="test_task",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"],
    )
    assert validate_input("configure terminal", task, "Cisco") is True
    assert validate_input("CONFIGURE TERMINAL", task, "cisco") is True
    assert validate_input("conf t", task, "cIsCo") is True
    assert validate_input("CONF T", task, "Cisco") is True
    assert validate_input("wrong command", task, "Cisco") is False


def test_powershell_answers_ignore_case() -> None:
    task = Task(
        id="test_task",
        prompt="Get services",
        prefix="PS C:\\>",
        expected="^Get-Service$",
        aliases=["gsv"],
    )
    assert validate_input("get-service", task, "PowerShell") is True
    assert validate_input("GSV", task, "powershell") is True


def test_linux_git_and_docker_answers_keep_case() -> None:
    linux = Task(
        id="linux_task",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=[],
    )
    assert validate_input("pwd", linux, "Linux") is True
    assert validate_input("PWD", linux, "Linux") is False
    assert validate_input(" pwd ", linux, "Linux") is True

    git = Task(
        id="git_task",
        prompt="Show status",
        prefix="$",
        expected=r"^git\s+status$",
        aliases=["git status"],
    )
    assert validate_input("git status", git, "Git") is True
    assert validate_input("Git Status", git, "Git") is False

    docker = Task(
        id="docker_task",
        prompt="List containers",
        prefix="$",
        expected=r"^docker\s+ps$",
        aliases=[],
    )
    assert validate_input("docker ps", docker, "Docker") is True
    assert validate_input("Docker PS", docker, "docker") is False

    custom = Task(
        id="custom_task",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=["Pwd"],
    )
    assert validate_input("pwd", custom, "Juniper") is True
    assert validate_input("PWD", custom, "Juniper") is False
    assert validate_input("Pwd", custom, "Juniper") is True
    assert validate_input("pwd", custom, "juniper") is True


def test_invalid_regex_does_not_match_and_aliases_still_can() -> None:
    task = Task(
        id="test_task",
        prompt="Command with bad regex",
        prefix="$",
        expected="[invalid-regex",
        aliases=["exact_cmd"],
    )
    assert validate_input("exact_cmd", task, "Linux") is True
    assert validate_input("[invalid-regex", task, "Linux") is False


def test_skip_shows_the_first_alias() -> None:
    task = Task(
        id="t1",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"],
    )
    assert format_display_answer(task) == "conf t"


def test_skip_without_an_alias_strips_anchors_and_whitespace_markers() -> None:
    task = Task(
        id="t1",
        prompt="Show status",
        prefix="$",
        expected=r"^git\s+status$",
        aliases=[],
    )
    assert format_display_answer(task) == "git status"
