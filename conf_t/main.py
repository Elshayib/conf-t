#!/usr/bin/env python3
import sys

from conf_t.cli import ConfTCLI
from conf_t.parser import build_parser, has_cli_action


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        app = ConfTCLI()
        if has_cli_action(args):
            app.run_from_args(args)
        else:
            app.run()
    except (KeyboardInterrupt, SystemExit):
        print("\nExiting Conf T...")
        sys.exit(0)


if __name__ == "__main__":
    main()