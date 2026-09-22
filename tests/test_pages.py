"""Tests for page module discovery."""

import os
import tempfile
import unittest

from catba.pages import PageModule, discover_pages, has_page_routes
from catba.routing import discover_routes

from tests.helpers import write_tree


class TestPageDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _table(self, files):
        write_tree(self.root, files)
        return discover_routes(os.path.join(self.root, "app"))

    def test_project_with_pages(self):
        table = self._table({
            "app/route.py": "",
            "app/page.tsx": "",
            "app/users/route.py": "",
            "app/users/page.tsx": "",
            "app/users/[id]/route.py": "",
            "app/users/[id]/page.tsx": "",
        })
        pages = discover_pages(table, self.root)
        ids = [p.page_id for p in pages]
        self.assertEqual(ids, ["/", "/users", "/users/[id]"])
        self.assertEqual(pages[0].module_path, "app/page.tsx")
        self.assertTrue(pages[2].module_path.endswith("users/[id]/page.tsx"))

    def test_api_only_project_has_no_pages(self):
        table = self._table({
            "app/api/route.py": "",
            "app/api/users/route.py": "",
        })
        pages = discover_pages(table, self.root)
        self.assertEqual(pages, [])
        self.assertFalse(has_page_routes(table))

    def test_mixed_project(self):
        table = self._table({
            "app/route.py": "",
            "app/page.tsx": "",
            "app/api/route.py": "",
        })
        pages = discover_pages(table, self.root)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_id, "/")
        self.assertTrue(has_page_routes(table))

    def test_module_path_is_project_relative(self):
        table = self._table({
            "app/route.py": "",
            "app/page.tsx": "",
        })
        pages = discover_pages(table, self.root)
        self.assertEqual(pages[0].module_path, "app/page.tsx")
        self.assertFalse(os.path.isabs(pages[0].module_path))

    def test_pages_sorted_by_id(self):
        table = self._table({
            "app/z/route.py": "",
            "app/z/page.tsx": "",
            "app/a/route.py": "",
            "app/a/page.tsx": "",
            "app/route.py": "",
            "app/page.tsx": "",
        })
        pages = discover_pages(table, self.root)
        ids = [p.page_id for p in pages]
        self.assertEqual(ids, ["/", "/a", "/z"])


if __name__ == "__main__":
    unittest.main()
