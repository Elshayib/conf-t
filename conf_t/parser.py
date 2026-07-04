from __future__ import annotations

import argparse

from conf_t import __version__


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
        "--list",
        action="store_true",
        help="List available lessons and exit",
    )
    parser.add_argument(
        "--platform",
        help="Filter lessons by platform (use with --list)",
    )
    parser.add_argument(
        "--tags",
        help="Comma-separated tags to filter lessons (use with --list)",
    )
    parser.add_argument(
        "--lesson",
        metavar="ID",
        help="Start a lesson by ID (resume flow applies if in progress)",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Run daily review for tasks due on the spaced-repetition schedule",
    )
    parser.add_argument(
        "--review-all",
        action="store_true",
        dest="review_all",
        help="Review every failed command in the queue",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show progress statistics and exit",
    )
    return parser


def has_cli_action(args: argparse.Namespace) -> bool:
    return bool(
        args.list
        or args.lesson
        or args.review
        or args.review_all
        or args.stats
    )