#!/usr/bin/env python3
import sys

from conf_t.cli import ConfTCLI, LearnerAlreadyTold
from conf_t.parser import build_parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        app = ConfTCLI()
        if not app.run_from_args(args):
            app.run()
    except LearnerAlreadyTold:
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        print("\nExiting Conf T...")
        sys.exit(0)


if __name__ == "__main__":
    main()