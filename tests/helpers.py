"""Test helpers: build temporary CatBa app trees."""

import os


def write_tree(root, files):
    """Write a dict of {relpath: content} under root, creating directories."""
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
