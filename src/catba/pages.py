"""Page module discovery.

Reuses the existing Python route table to identify which routes have
page.tsx files. This is a filter over the route table, not a second
route scanner. The route table remains the single source of truth.

A PageModule has:
- page_id: the route URL (e.g. "/", "/users", "/users/[id]")
- module_path: the project-relative path to page.tsx (e.g. "app/page.tsx")
"""

import os
from dataclasses import dataclass

from catba.routing import Route, RouteTable


@dataclass
class PageModule:
    """One page route identified by the route table."""

    page_id: str      # the route URL, used as a stable identifier
    module_path: str  # project-relative path to page.tsx


def discover_pages(table, project_root):
    """Collect all page modules from the route table.

    Returns a list of PageModule, ordered by URL for deterministic output.
    Returns an empty list if there are no page routes (API-only project).
    """
    if not project_root:
        return []
    pages = []
    for route in table.routes:
        if not route.has_page:
            continue
        page_fs = os.path.join(os.path.dirname(route.fs_path), "page.tsx")
        rel = os.path.relpath(page_fs, project_root)
        rel = rel.replace(os.sep, "/")
        pages.append(PageModule(page_id=route.url, module_path=rel))
    pages.sort(key=lambda p: p.page_id)
    return pages


def has_page_routes(table):
    """Return True if the route table contains at least one page route."""
    return any(r.has_page for r in table.routes)
