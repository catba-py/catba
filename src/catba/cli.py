"""CatBa command-line interface.

The command surface is defined here: ``create``, ``dev``, ``build``,
``start`` and ``install``. None of these commands are implemented yet; each
reports that it is unavailable in the current pre-runtime phase. ``--help``
and ``--version`` are fully wired.

``catba install`` is intended to install the dependencies declared by the
project's ``pyproject.toml`` using standard Python packaging behaviour
(no custom resolver, no ``catba install <package>`` form).
"""

import argparse
import sys

from catba import __version__


def build_parser():
    """Construct the top-level argument parser and subcommand surface."""
    parser = argparse.ArgumentParser(
        prog="catba",
        description="CatBa: a Python web framework and runtime.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"catba {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        title="commands",
    )
    subparsers.add_parser(
        "create",
        help="scaffold a new CatBa project (not implemented yet)",
    )
    subparsers.add_parser(
        "dev",
        help="run the project in development mode (not implemented yet)",
    )
    subparsers.add_parser(
        "build",
        help="build the project for production (not implemented yet)",
    )
    subparsers.add_parser(
        "start",
        help="run the built project (not implemented yet)",
    )
    subparsers.add_parser(
        "install",
        help="install project dependencies from pyproject.toml (not implemented yet)",
    )
    return parser


def main(argv=None):
    """Entry point for the ``catba`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    # Pre-runtime phase: the command names exist, the behaviour does not.
    print(f"catba {args.command}: not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
