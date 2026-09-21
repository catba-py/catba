"""CatBa command-line entry point."""

import sys


def main(argv=None):
    """Entry point for the ``catba`` console script.

    At this stage the command does nothing but confirm that the installed
    package and its entry point resolve correctly. The real command surface
    is wired up in later commits.
    """
    print("catba")
    return 0


if __name__ == "__main__":
    sys.exit(main())
