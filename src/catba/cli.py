"""CatBa command-line interface.

Minimal core: ``--help`` and ``--version`` are the only wired behaviours.
The project command surface (create/dev/build/start/install) is added in a
later commit.
"""

import argparse
import sys

from catba import __version__


def build_parser():
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="catba",
        description="CatBa: a Python web framework and runtime.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"catba {__version__}",
    )
    return parser


def main(argv=None):
    """Entry point for the ``catba`` console script."""
    parser = build_parser()
    parser.parse_args(argv)
    # No subcommands yet: show the available surface and succeed.
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
