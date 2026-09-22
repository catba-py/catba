"""Static asset serving for client bundles.

Serves generated client JavaScript from .catba/generated/client/ so the
browser can load the hydration bundle. Both the Python transport and the
native C runtime use this path convention.

The asset path prefix is /__catba/ so it does not collide with user routes.
"""

import os

ASSET_PREFIX = "/__catba/"


def get_client_dir(project_root):
    """Return the client bundle directory path, or None if not built."""
    client_dir = os.path.join(project_root, ".catba", "generated", "client")
    if os.path.isdir(client_dir):
        return client_dir
    return None


def get_client_bundle_url(project_root):
    """Return the URL path to the main client JS file, or None.

    The URL is relative to the server root and uses the /__catba/ prefix.
    """
    client_dir = get_client_dir(project_root)
    if not client_dir:
        return None
    for name in os.listdir(client_dir):
        if name.endswith(".js"):
            return ASSET_PREFIX + name
    return None


def is_asset_path(path):
    """Return True if path starts with the asset prefix."""
    return path.startswith(ASSET_PREFIX)


def serve_asset(path, project_root):
    """Serve a static asset. Returns (status, headers, body) or None.

    Returns None if the path is not an asset or the file is not found.
    """
    if not is_asset_path(path):
        return None
    rel = path[len(ASSET_PREFIX):]
    client_dir = get_client_dir(project_root)
    if not client_dir:
        return None
    # Prevent path traversal: only allow simple filenames.
    if "/" in rel or "\\" in rel or ".." in rel:
        return 403, {"Content-Type": "text/plain"}, b"Forbidden"
    file_path = os.path.join(client_dir, rel)
    if not os.path.isfile(file_path):
        return 404, {"Content-Type": "text/plain"}, b"Not Found"
    with open(file_path, "rb") as f:
        body = f.read()
    content_type = "application/javascript" if rel.endswith(".js") else "application/octet-stream"
    return 200, {
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        "Cache-Control": "no-cache",
    }, body
