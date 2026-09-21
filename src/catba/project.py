"""Project discovery: locate the CatBa project root.

A CatBa project root is a directory containing both ``pyproject.toml`` and
``catba.py``. Discovery walks up from the current directory (or a given
start directory) and stops at the first match. It does not search the
entire filesystem and does not silently pick an unrelated parent.
"""

import os


def find_project_root(start=None):
    """Return the nearest enclosing project root, or None.

    Walks upward from ``start`` (default: current directory). A directory is
    the project root when it contains both ``pyproject.toml`` and
    ``catba.py``. Stops at the first match.
    """
    here = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(here, "pyproject.toml")) and \
           os.path.isfile(os.path.join(here, "catba.py")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
