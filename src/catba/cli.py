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
    p_start = subparsers.add_parser(
        "start",
        help="run the project with the native C runtime",
    )
    p_start.add_argument("--host", default="127.0.0.1")
    p_start.add_argument("--port", type=int, default=8000)
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
    if args.command == "start":
        return _start(args)
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
        app = App(app_dir, project_root=root)
    except RouteError as e:
        print(f"catba dev: {e}", file=sys.stderr)
        return 1

    # Prepare frontend and start SSR worker if page routes exist.
    ssr = _prepare_ssr(app, app_dir, root)

    print(f"catba dev: http://{args.host}:{args.port}", file=sys.stderr)
    server = DevServer(app, host=args.host, port=args.port, ssr=ssr, project_root=root)
    try:
        server.serve()
    finally:
        if ssr:
            ssr.stop()
    return 0


def _start(args):
    root = find_project_root()
    if root is None:
        print("catba start: no CatBa project found (need pyproject.toml and catba.py)",
              file=sys.stderr)
        return 1
    app_dir = os.path.join(root, "app")

    # Build the native runtime if not already built.
    native_dir = os.path.join(os.path.dirname(__file__), "..", "..", "native")
    native_dir = os.path.normpath(native_dir)
    build_script = os.path.join(native_dir, "build.sh")
    binary = os.path.join(native_dir, "build", "catba-native")

    if not os.path.isfile(binary) or \
       os.path.getmtime(build_script) > os.path.getmtime(binary):
        print("catba start: building native runtime...", file=sys.stderr)
        rc = subprocess.call(["bash", build_script, "server"])
        if rc != 0:
            print("catba start: native build failed", file=sys.stderr)
            return 1

    if not os.path.isfile(binary):
        print("catba start: native binary not found after build", file=sys.stderr)
        return 1

    return subprocess.call([binary, "--app-dir", app_dir,
                           "--host", args.host, "--port", str(args.port)])


def _prepare_ssr(app, app_dir, root):
    """Prepare frontend and start SSR worker. Returns SSRWorker or None."""
    from catba.pages import has_page_routes
    from catba.routing import discover_routes
    from catba.ssr import SSRWorker

    table = discover_routes(app_dir)
    if not has_page_routes(table):
        return None

    try:
        from catba.frontend import prepare_frontend, FrontendError
        prepared = prepare_frontend(app_dir, root)
        if not prepared:
            return None
    except FrontendError as e:
        print(f"catba: frontend build failed: {e}", file=sys.stderr)
        return None

    try:
        worker = SSRWorker(root)
        worker.start()
        app.ssr = worker
        return worker
    except Exception as e:
        print(f"catba: SSR worker failed to start: {e}", file=sys.stderr)
        return None


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
