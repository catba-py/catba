"""Inertia protocol: request detection, page object, and response helpers.

The Inertia protocol lets CatBa return JSON page objects instead of HTML
when the client sends X-Inertia: true. The server still owns routing, data
fetching, and page selection. The client only consumes page objects.

This module is the single place where Inertia protocol semantics live.
The C runtime does not implement Inertia; it receives ordinary HTTP
results from the Python layer.
"""

import json


def is_inertia_request(ctx):
    """Return True if the request has X-Inertia: true.

    The header name check is case-insensitive (ctx.headers already handles
    this). The value 'true' is accepted case-insensitively.
    """
    value = ctx.headers.get("X-Inertia", "")
    return value.strip().lower() == "true"


def get_inertia_version(ctx):
    """Return the X-Inertia-Version header value, or None if absent."""
    value = ctx.headers.get("X-Inertia-Version", "")
    return value if value else None


def get_partial_component(ctx):
    """Return the X-Inertia-Partial-Component header value, or None."""
    value = ctx.headers.get("X-Inertia-Partial-Component", "")
    return value if value else None


def get_partial_data(ctx):
    """Return the X-Inertia-Partial-Data header as a list of keys, or None."""
    value = ctx.headers.get("X-Inertia-Partial-Data", "")
    if not value:
        return None
    return [k.strip() for k in value.split(",") if k.strip()]


def get_partial_except(ctx):
    """Return the X-Inertia-Partial-Except header as a list of keys, or None."""
    value = ctx.headers.get("X-Inertia-Partial-Except", "")
    if not value:
        return None
    return [k.strip() for k in value.split(",") if k.strip()]


def build_page_object(component, props, url, version):
    """Build the Inertia page object as a dict.

    The component is the stable page identifier from the route table.
    The url includes the query string. The version is the deterministic
    asset version.
    """
    return {
        "component": component,
        "props": props,
        "url": url,
        "version": version,
    }


def filter_partial_props(props, partial_data, partial_except):
    """Filter props for a partial reload response.

    If partial_data is given, include only those keys.
    If partial_except is given, exclude those keys.
    Both may be applied: first include, then exclude.
    """
    result = dict(props)
    if partial_data is not None:
        result = {k: v for k, v in result.items() if k in partial_data}
    if partial_except is not None:
        result = {k: v for k, v in result.items() if k not in partial_except}
    return result


def inertia_json_response(page_object):
    """Build an HTTP response tuple for an Inertia page object.

    Returns (status, headers, body) with the required Inertia headers.
    """
    body = json.dumps(page_object, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
        "X-Inertia": "true",
        "Vary": "X-Inertia",
    }
    return 200, headers, body


def inertia_version_conflict(url, version):
    """Build a 409 Conflict response for a version mismatch.

    Returns (status, headers, body) with X-Inertia-Location and the
    current version.
    """
    headers = {
        "X-Inertia-Location": url,
        "X-Inertia-Version": version,
        "Vary": "X-Inertia",
    }
    return 409, headers, b""


def inertia_location(url):
    """Build a 409 Conflict response for an external Inertia redirect.

    Returns (status, headers, body) instructing the client to perform a
    hard window.location redirect.
    """
    headers = {
        "X-Inertia-Location": url,
        "Content-Length": "0",
        "Vary": "X-Inertia",
    }
    return 409, headers, b""


def is_external_url(url, request=None):
    """Return True if url points to an external origin.

    A URL starting with http://, https://, or // is external unless its host
    matches the request Host header. Relative paths (/foo) are never external.
    """
    if not url:
        return False
    if url.startswith("//"):
        return True
    if url.startswith("http://") or url.startswith("https://"):
        if request is not None:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = request.headers.get("Host", "").lower()
            if host and parsed.netloc.lower() == host:
                return False
        return True
    return False


def add_vary_inertia(headers):
    """Add 'X-Inertia' to the Vary header without overwriting existing values."""
    existing = headers.get("Vary", "")
    if existing:
        parts = [p.strip() for p in existing.split(",")]
        if "X-Inertia" not in parts:
            parts.append("X-Inertia")
        headers["Vary"] = ", ".join(parts)
    else:
        headers["Vary"] = "X-Inertia"
    return headers


def get_asset_version(project_root):
    """Derive a deterministic asset version from the frontend build.

    Hashes the Vite client build output to produce a stable version string.
    Returns a fixed dev version if no build exists yet.

    The version does not use timestamps, random values, or machine-specific
    paths. It is stable across requests for the same build.
    """
    import hashlib
    import os

    client_dir = os.path.join(project_root, ".catba", "generated", "client")
    if not os.path.isdir(client_dir):
        return "dev"

    h = hashlib.sha256()
    found = False
    for name in sorted(os.listdir(client_dir)):
        path = os.path.join(client_dir, name)
        if os.path.isfile(path):
            found = True
            h.update(name.encode("utf-8"))
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)

    if not found:
        return "dev"

    return h.hexdigest()[:16]
