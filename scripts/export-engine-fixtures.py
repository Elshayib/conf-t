#!/usr/bin/env python3
"""Export engine test fixtures from Python for TypeScript parity tests."""

from __future__ import annotations

import json
from pathlib import Path

from conf_t.engine import format_display_answer, validate_input
from conf_t.models import Task

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "web" / "src" / "lib" / "engine" / "fixtures" / "engine-fixtures.json"

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
]


def build_fixture(case: dict) -> dict:
    task = case["task"]
    platform = case["platform"]
    fn = case["fn"]

    fixture: dict = {
        "fn": fn,
        "task": task.to_dict(),
        "platform": platform,
    }

    if fn == "validate_input":
        fixture["input"] = case["input"]
        fixture["python_result"] = validate_input(case["input"], task, platform)
    elif fn == "format_display_answer":
        fixture["python_result"] = format_display_answer(task, platform)
    else:
        raise ValueError(f"Unknown function: {fn}")

    return fixture


def main() -> None:
    fixtures = [build_fixture(case) for case in CASES]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(fixtures)} fixtures to {OUTPUT}")


if __name__ == "__main__":
    main()