"""CatBa command-line interface.

The command surface: ``create``, ``dev``, ``build``, ``start``, ``install``.
``dev`` and ``install`` are implemented; ``build`` and ``start`` are not
implemented yet (they require SSR and the production server). ``--help`` and
``--version`` are fully wired.
"""

import argparse
import os
import shutil
import subprocess
import sys

from catba import __version__
from catba.project import find_project_root
from catba.routing import RouteError


def build_parser():
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

    p_create = subparsers.add_parser(
        "create",
        help="scaffold a new CatBa project",
    )
    p_create.add_argument("name", help="project directory name")

    p_dev = subparsers.add_parser(
        "dev",
        help="run the project in development mode",
    )
    p_dev.add_argument("--host", default="127.0.0.1")
    p_dev.add_argument("--port", type=int, default=8000)

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
        help="install project dependencies from pyproject.toml",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "dev":
        return _dev(args)
    if args.command == "install":
        return _install()
    if args.command == "create":
        return _create(args)
    print(f"catba {args.command}: not implemented yet", file=sys.stderr)
    return 1


def _dev(args):
    root = find_project_root()
    if root is None:
        print("catba dev: no CatBa project found (need pyproject.toml and catba.py)",
              file=sys.stderr)
        return 1
    app_dir = os.path.join(root, "app")
    from catba.runtime import App
    from catba.transport import DevServer
    try:
        app = App(app_dir)
    except RouteError as e:
        print(f"catba dev: {e}", file=sys.stderr)
        return 1
    print(f"catba dev: http://{args.host}:{args.port}", file=sys.stderr)
    DevServer(app, host=args.host, port=args.port).serve()
    return 0


def _install():
    root = find_project_root()
    if root is None:
        print("catba install: no CatBa project found", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, "-m", "pip", "install", "-e", root])


def _create(args):
    template = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "app")
    template = os.path.normpath(template)
    dest = os.path.join(os.getcwd(), args.name)
    if os.path.exists(dest):
        print(f"catba create: {args.name} already exists", file=sys.stderr)
        return 1
    shutil.copytree(template, dest)
    print(f"catba create: created {args.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
