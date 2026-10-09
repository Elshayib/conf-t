"""Whether a submitted line answers a Task, and which command skip shows."""

from __future__ import annotations

import re

from conf_t.models import Task
from conf_t.platform import Platform


def validate_input(user_input: str, task: Task, platform: str) -> bool:
    """True when the line matches the Task's expected regex or an alias.

    `expected` is a Python regex. Aliases are exact alternatives under the
    Platform's case rule.
    """
    cleaned_input = user_input.strip()
    ignores_case = Platform.of(platform).ignores_case
    flags = re.IGNORECASE if ignores_case else 0

    try:
        pattern = re.compile(task.expected, flags)
        if pattern.match(cleaned_input):
            return True
    except re.error:
        # A pattern that does not compile never matches. Aliases still can.
        pass

    for alias in task.aliases:
        alias_clean = alias.strip()
        if ignores_case:
            if cleaned_input.lower() == alias_clean.lower():
                return True
        elif cleaned_input == alias_clean:
            return True

    return False


def format_display_answer(task: Task) -> str:
    """Command skip shows: the first alias, or the pattern without anchors.

    The shown command is the same on every Platform.
    """
    if task.aliases:
        return task.aliases[0]

    display = task.expected
    if display.startswith("^"):
        display = display[1:]
    if display.endswith("$"):
        display = display[:-1]
    display = display.replace(r"\s+", " ")
    display = display.replace(r"\s", " ")
    display = display.replace("\\", "")
    return display
