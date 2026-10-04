"""Page module discovery.

Reuses the existing Python route table to identify which routes have
page.tsx files. This is a filter over the route table, not a second
route scanner. The route table remains the single source of truth.

A PageModule has:
- page_id: the route URL (e.g. "/", "/users", "/users/[id]")
- module_path: the project-relative path to page.tsx (e.g. "app/page.tsx")
"""

import os
from dataclasses import dataclass, field

from catba.routing import Route, RouteTable


@dataclass
class PageModule:
    """One page route identified by the route table."""

    page_id: str      # the route URL, used as a stable identifier
    module_path: str  # project-relative path to page.tsx
    layout_paths: list = field(default_factory=list)  # project-relative paths to layout.tsx from root down to page


def discover_pages(table, project_root, app_dir=None):
    """Collect all page modules from the route table.

    Returns a list of PageModule, ordered by URL for deterministic output.
    Returns an empty list if there are no page routes (API-only project).
    """
    if not project_root:
        return []
    if app_dir is None:
        app_dir = os.path.join(project_root, "app")

    pages = []
    for route in table.routes:
        if not route.has_page:
            continue
        page_dir = os.path.dirname(route.fs_path)
        page_fs = os.path.join(page_dir, "page.tsx")
        rel = os.path.relpath(page_fs, project_root).replace(os.sep, "/")

        # Discover all layout.tsx files from app_dir down to page_dir in hierarchy order
        layouts = []
        if os.path.isdir(app_dir):
            try:
                rel_dir = os.path.relpath(page_dir, app_dir)
            except ValueError:
                rel_dir = "."

            dirs_to_check = [app_dir]
            if rel_dir not in (".", ""):
                current = app_dir
                for part in rel_dir.split(os.sep):
                    current = os.path.join(current, part)
                    dirs_to_check.append(current)

            for d in dirs_to_check:
                layout_file = os.path.join(d, "layout.tsx")
                if os.path.isfile(layout_file):
                    rel_layout = os.path.relpath(layout_file, project_root).replace(os.sep, "/")
                    if rel_layout not in layouts:
                        layouts.append(rel_layout)

        pages.append(PageModule(page_id=route.url, module_path=rel, layout_paths=layouts))
    pages.sort(key=lambda p: p.page_id)
    return pages


def has_page_routes(table):
    """Return True if the route table contains at least one page route."""
    return any(r.has_page for r in table.routes)
