"""Tests for frontend manifest and entry generation."""

import json
import os
import tempfile
import unittest

from catba.manifest import (
    generate_client_entry,
    generate_manifest,
    generate_ssr_entry,
)
from catba.pages import PageModule

from tests.helpers import write_tree


class TestManifestGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.gen = os.path.join(self.root, ".catba", "generated")

    def tearDown(self):
        self.tmp.cleanup()

    def _pages(self):
        return [
            PageModule(page_id="/", module_path="app/page.tsx"),
            PageModule(page_id="/users", module_path="app/users/page.tsx"),
            PageModule(page_id="/users/[id]", module_path="app/users/[id]/page.tsx"),
        ]

    def test_manifest_json(self):
        path = generate_manifest(self._pages(), self.gen)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["/"], "app/page.tsx")
        self.assertEqual(manifest["/users"], "app/users/page.tsx")
        self.assertEqual(manifest["/users/[id]"], "app/users/[id]/page.tsx")

    def test_ssr_entry_imports_all_pages(self):
        path = generate_ssr_entry(self._pages(), self.gen)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("renderToString", content)
        self.assertIn('import Page0 from "../../app/page.tsx"', content)
        self.assertIn('import Page1 from "../../app/users/page.tsx"', content)
        self.assertIn('import Page2 from "../../app/users/[id]/page.tsx"', content)
        self.assertIn('"/": Page0', content)
        self.assertIn('"/users": Page1', content)
        self.assertIn('"/users/[id]": Page2', content)
        self.assertIn("export function render(pageId, props)", content)

    def test_client_entry_imports_all_pages(self):
        path = generate_client_entry(self._pages(), self.gen)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("hydrateRoot", content)
        self.assertIn('import Page0 from "../../app/page.tsx"', content)
        self.assertIn('import Page1 from "../../app/users/page.tsx"', content)
        self.assertIn('import Page2 from "../../app/users/[id]/page.tsx"', content)
        self.assertIn("catba-root", content)
        self.assertIn("catba-props", content)

    def test_empty_pages(self):
        pages = []
        generate_manifest(pages, self.gen)
        generate_ssr_entry(pages, self.gen)
        generate_client_entry(pages, self.gen)
        with open(os.path.join(self.gen, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest, {})
        with open(os.path.join(self.gen, "ssr-entry.js"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("const pages = {", content)

    def test_generated_dir_created(self):
        # Should create the directory if it does not exist.
        gen = os.path.join(self.root, "fresh", "generated")
        generate_manifest(self._pages(), gen)
        self.assertTrue(os.path.isdir(gen))


if __name__ == "__main__":
    unittest.main()
