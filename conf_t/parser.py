from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from conf_t import __version__


@dataclass(frozen=True)
class CommandFlag:
    """One command the process accepts.

    ``COMMAND_FLAGS`` is the only declaration. Its order is the order the
    first set flag runs.
    """

    option: str
    dest: str
    help: str
    run: Callable[[Any, argparse.Namespace], None]
    metavar: str | None = None

    def install(self, parser: argparse.ArgumentParser) -> None:
        if self.metavar is None:
            parser.add_argument(
                self.option,
                action="store_true",
                dest=self.dest,
                help=self.help,
            )
            return
        parser.add_argument(
            self.option,
            dest=self.dest,
            metavar=self.metavar,
            help=self.help,
        )

    def is_set(self, args: argparse.Namespace) -> bool:
        value = getattr(args, self.dest)
        if self.metavar is None:
            return value is True
        return value is not None


def _run_list(app: Any, args: argparse.Namespace) -> None:
    app.list_lessons(args.platform, args.tags)


def _run_stats(app: Any, _args: argparse.Namespace) -> None:
    app.view_stats(interactive=False)


def _run_continue(app: Any, _args: argparse.Namespace) -> None:
    app.run_continue(interactive=False)


def _run_due_review(app: Any, _args: argparse.Namespace) -> None:
    app.daily_review_menu(interactive=False)


def _run_failed_drill(app: Any, _args: argparse.Namespace) -> None:
    app.review_failed_menu(interactive=False)


def _run_lesson(app: Any, args: argparse.Namespace) -> None:
    app.run_lesson_by_id(args.lesson)


# List, then stats, then continue, then Due Review, then the failed-command
# drill, then a Lesson. Platform, tags, and version are not commands.
COMMAND_FLAGS: tuple[CommandFlag, ...] = (
    CommandFlag(
        "--list",
        "list",
        "List available lessons and exit",
        _run_list,
    ),
    CommandFlag(
        "--stats",
        "stats",
        "Show progress statistics and exit",
        _run_stats,
    ),
    CommandFlag(
        "--continue",
        "continue_session",
        "Continue where you left off (due review, last lesson, or recommended next)",
        _run_continue,
    ),
    CommandFlag(
        "--review",
        "review",
        "Run daily review for tasks due on the spaced-repetition schedule",
        _run_due_review,
    ),
    CommandFlag(
        "--review-all",
        "review_all",
        "Review every failed command in the queue",
        _run_failed_drill,
    ),
    CommandFlag(
        "--lesson",
        "lesson",
        "Start a lesson by ID (resume flow applies if in progress)",
        _run_lesson,
        metavar="ID",
    ),
)


def first_set_command(args: argparse.Namespace) -> CommandFlag | None:
    """The first command flag that is set. None means the menu should open."""
    for flag in COMMAND_FLAGS:
        if flag.is_set(args):
            return flag
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conf-t",
        description="Interactive CLI trainer for command-line skills.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"conf-t {__version__}",
    )
    parser.add_argument(
        "--platform",
        help="Filter lessons by platform (use with --list)",
    )
    parser.add_argument(
        "--tags",
        help="Comma-separated tags to filter lessons (use with --list)",
    )
    for flag in COMMAND_FLAGS:
        flag.install(parser)
    parser.epilog = (
        "Examples:\n"
        "  conf-t --continue              Jump back into practice\n"
        "  conf-t --list --platform Cisco List Cisco lessons\n"
        "  conf-t --lesson cisco_basic    Start a lesson by ID\n"
        "  pipx install conf-t            Easiest install (recommended)"
    )
    return parser
