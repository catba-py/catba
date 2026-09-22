"""Frontend build: detect Node, install dependencies, build SSR/client bundles.

CatBa uses Vite for TSX transformation and React processing. This module
orchestrates the build by calling Node and Vite via subprocess. It does
not duplicate Vite's module resolution or write a custom TSX transpiler.

Build outputs go to .catba/generated/:
  ssr/   - the SSR bundle (loadable by Node)
  client/ - the client hydration bundle (loadable by browser)
"""

import os
import shutil
import subprocess


class FrontendError(Exception):
    """A frontend build or setup error."""


def find_node():
    """Find the Node.js executable. Returns the path or None."""
    return shutil.which("node")


def find_npx():
    """Find the npx executable. Returns the path or None."""
    return shutil.which("npx")


def find_npm():
    """Find the npm executable. Returns the path or None."""
    return shutil.which("npm")


def check_node():
    """Raise FrontendError if Node.js is not available."""
    if not find_node():
        raise FrontendError(
            "Node.js is required for SSR but was not found. "
            "Install Node.js or use API-only routes."
        )


def ensure_dependencies(project_root):
    """Run npm install if node_modules does not exist.

    Returns 0 on success. Raises FrontendError on failure.
    """
    node_modules = os.path.join(project_root, "node_modules")
    if os.path.isdir(node_modules):
        return 0

    npm = find_npm()
    if not npm:
        raise FrontendError(
            "npm is required to install frontend dependencies but was not found."
        )

    package_json = os.path.join(project_root, "package.json")
    if not os.path.isfile(package_json):
        raise FrontendError(
            "package.json not found. Frontend dependencies are required for SSR."
        )

    print("catba: installing frontend dependencies...", file=os.sys.stderr)
    rc = subprocess.call([npm, "install"], cwd=project_root)
    if rc != 0:
        raise FrontendError("npm install failed.")
    return 0


def build_ssr(project_root):
    """Build the SSR bundle via Vite.

    The SSR entry is .catba/generated/ssr-entry.js. Output goes to
    .catba/generated/ssr/. Returns the output directory path.

    Raises FrontendError on failure.
    """
    check_node()
    ensure_dependencies(project_root)

    ssr_entry = os.path.join(".catba", "generated", "ssr-entry.js")
    out_dir = os.path.join(".catba", "generated", "ssr")

    npx = find_npx()
    if not npx:
        raise FrontendError("npx is required to run Vite but was not found.")

    print("catba: building SSR bundle...", file=os.sys.stderr)
    rc = subprocess.call(
        [npx, "vite", "build", "--ssr", ssr_entry, "--outDir", out_dir],
        cwd=project_root,
    )
    if rc != 0:
        raise FrontendError("Vite SSR build failed.")

    result = os.path.join(project_root, out_dir)
    if not os.path.isdir(result):
        raise FrontendError("Vite SSR build produced no output.")
    return result


def build_client(project_root):
    """Build the client hydration bundle via Vite.

    The client entry is .catba/generated/client-entry.js. Output goes to
    .catba/generated/client/. Returns the output directory path.

    Raises FrontendError on failure.
    """
    check_node()
    ensure_dependencies(project_root)

    client_entry = os.path.join(".catba", "generated", "client-entry.js")
    out_dir = os.path.join(".catba", "generated", "client")

    npx = find_npx()
    if not npx:
        raise FrontendError("npx is required to run Vite but was not found.")

    print("catba: building client bundle...", file=os.sys.stderr)
    rc = subprocess.call(
        [npx, "vite", "build", "--outDir", out_dir, "--assetsDir", "."],
        cwd=project_root,
    )
    if rc != 0:
        raise FrontendError("Vite client build failed.")

    result = os.path.join(project_root, out_dir)
    if not os.path.isdir(result):
        raise FrontendError("Vite client build produced no output.")
    return result


def find_ssr_bundle(project_root):
    """Find the SSR bundle file. Returns the path or None."""
    ssr_dir = os.path.join(project_root, ".catba", "generated", "ssr")
    if not os.path.isdir(ssr_dir):
        return None
    for name in ("ssr-entry.js", "client-entry.js"):
        path = os.path.join(ssr_dir, name)
        if os.path.isfile(path):
            return path
    for name in os.listdir(ssr_dir):
        if name.endswith(".js"):
            return os.path.join(ssr_dir, name)
    return None


def find_client_bundle(project_root):
    """Find the main client JS file. Returns the path or None."""
    client_dir = os.path.join(project_root, ".catba", "generated", "client")
    if not os.path.isdir(client_dir):
        return None
    for name in os.listdir(client_dir):
        if name.endswith(".js"):
            return os.path.join(client_dir, name)
    return None


def prepare_frontend(app_dir, project_root):
    """Prepare the frontend for SSR: generate entries, build bundles.

    Returns True if frontend was prepared (pages exist), False if not needed
    (API-only project, no page routes). Raises FrontendError on failure.

    Steps:
      1. Discover routes from app_dir
      2. Discover page modules from the route table
      3. If no pages, return False (no frontend needed)
      4. Generate manifest.json, ssr-entry.js, client-entry.js
      5. Build the SSR bundle via Vite
      6. Build the client bundle via Vite
    """
    from catba.routing import discover_routes
    from catba.pages import discover_pages, has_page_routes
    from catba.manifest import (
        generate_manifest,
        generate_ssr_entry,
        generate_client_entry,
    )

    table = discover_routes(app_dir)
    if not has_page_routes(table):
        return False

    pages = discover_pages(table, project_root)
    gen_dir = os.path.join(project_root, ".catba", "generated")
    os.makedirs(gen_dir, exist_ok=True)

    generate_manifest(pages, gen_dir)
    generate_ssr_entry(pages, gen_dir)
    generate_client_entry(pages, gen_dir)

    build_ssr(project_root)
    build_client(project_root)

    return True
