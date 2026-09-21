"""Filesystem route discovery and matching.

The ``app/`` directory is the route root. Each directory containing a
``route.py`` is a route; its URL is the directory path relative to ``app/``.
A directory named ``[name]`` is a dynamic segment capturing one path
segment into ``ctx.params["name]``.

Discovery is deterministic: static routes beat dynamic routes, and two
dynamic segments competing at the same position is a discovery error.
"""

import os
import re
from dataclasses import dataclass, field

DYNAMIC = re.compile(r"^\[(.+)\]$")

# Methods discovered as handlers in a route module.
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


class RouteError(Exception):
    """A discovery or structure error in the route tree."""


@dataclass
class Route:
    """One discovered route.

    ``pattern`` is a list of segments. A plain string is a literal segment
    that must match exactly. A string starting with ":" is a parameter
    name whose value is captured from that position. ``params`` is the
    ordered list of parameter names (without the leading colon).
    """

    url: str
    fs_path: str
    module_name: str
    pattern: list = field(default_factory=list)
    params: list = field(default_factory=list)
    has_page: bool = False


def _pattern_for(rel):
    """Build the pattern, params, and URL for a directory relative to app/."""
    parts = [p for p in rel.replace(os.sep, "/").split("/") if p]
    pattern = []
    params = []
    for part in parts:
        m = DYNAMIC.match(part)
        if m:
            name = m.group(1)
            if name in params:
                raise RouteError(f"duplicate parameter '{name}' in route {rel or '/'}")
            pattern.append(":" + name)
            params.append(name)
        else:
            pattern.append(part)
    url = "/" + "/".join(parts) if parts else "/"
    return pattern, params, url


@dataclass
class RouteTable:
    """All discovered routes, ready to match request paths."""

    routes: list = field(default_factory=list)

    def add(self, route):
        self.routes.append(route)

    def match(self, path):
        """Resolve a request path to ``(Route, params_dict)``.

        Returns ``(None, {})`` when no route matches. A static segment beats
        a dynamic segment at the same position; ties are broken by the number
        of static segments (more specific wins).
        """
        segments = [s for s in path.split("/") if s]
        best = None
        best_params = {}
        best_score = -1
        for route in self.routes:
            if len(route.pattern) != len(segments):
                continue
            params = {}
            ok = True
            static_count = 0
            for i, seg in enumerate(route.pattern):
                if seg.startswith(":"):
                    params[seg[1:]] = segments[i]
                elif seg != segments[i]:
                    ok = False
                    break
                else:
                    static_count += 1
            if not ok:
                continue
            if static_count > best_score:
                best = route
                best_params = params
                best_score = static_count
        return best, best_params


def discover_routes(app_dir):
    """Walk ``app_dir`` and build a RouteTable.

    A directory is a route when it contains ``route.py``. ``page.tsx``
    without a sibling ``route.py`` is a structure error. Two dynamic segments
    at the same position under the same parent are a discovery error.
    """
    table = RouteTable()
    if not os.path.isdir(app_dir):
        return table
    # Map (parent_url, position_index) -> the segment kind registered there.
    # "static:<literal>" for static, "dyn:<param>" for dynamic. Two "dyn:*"
    # entries at the same (parent, position) is an ambiguity error.
    dynamic_at = {}
    for root, dirs, files in os.walk(app_dir):
        if "route.py" not in files:
            if "page.tsx" in files:
                rel = os.path.relpath(root, app_dir)
                raise RouteError(
                    f"{rel}/page.tsx has no corresponding route.py "
                    "(a page requires a server boundary)"
                )
            continue
        rel = os.path.relpath(root, app_dir)
        if rel == ".":
            rel = ""
        pattern, params, url = _pattern_for(rel)
        # Detect ambiguous dynamic segments: two [x] dirs at the same
        # position under the same parent path.
        parent_segments = [s for s in url.rstrip("/").split("/") if s][:-1]
        parent_key = "/" + "/".join(parent_segments) if parent_segments else "/"
        for idx, seg in enumerate(pattern):
            if seg.startswith(":"):
                key = (parent_key, idx)
                prev = dynamic_at.get(key)
                if prev is not None and prev != seg:
                    raise RouteError(
                        f"ambiguous dynamic segment at position {idx} "
                        f"under {parent_key}: [{prev[1:]}] vs [{seg[1:]}]"
                    )
                dynamic_at[key] = seg
        module_name = "catba_app_" + url.strip("/").replace("/", "_") if url.strip("/") else "catba_app_root"
        route = Route(
            url=url,
            fs_path=os.path.join(root, "route.py"),
            module_name=module_name,
            pattern=pattern,
            params=params,
            has_page=("page.tsx" in files),
        )
        table.add(route)
    return table
