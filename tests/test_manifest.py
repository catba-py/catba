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

    def test_client_entry_with_inertia(self):
        path = generate_client_entry(self._pages(), self.gen, use_inertia=True)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('import { createInertiaApp } from "@inertiajs/react"', content)
        self.assertIn('createInertiaApp({', content)
        self.assertIn('id: "catba-root"', content)
        self.assertIn('hydrateRoot(el, createElement(App, props))', content)

    def test_ssr_entry_supports_layout(self):
        path = generate_ssr_entry(self._pages(), self.gen)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('typeof Component.layout === "function"', content)
        self.assertIn('Component.layout(page)', content)

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
        gen = os.path.join(self.root, "fresh", "generated")
        generate_manifest(self._pages(), gen)
        self.assertTrue(os.path.isdir(gen))

    def test_layout_wiring_in_ssr(self):
        pages = [
            PageModule(page_id="/", module_path="app/page.tsx", layout_paths=["app/layout.tsx"]),
            PageModule(
                page_id="/dashboard",
                module_path="app/dashboard/page.tsx",
                layout_paths=["app/layout.tsx", "app/dashboard/layout.tsx"],
            ),
        ]
        path = generate_ssr_entry(pages, self.gen, use_inertia=True)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('import Layout0 from "../../app/layout.tsx"', content)
        self.assertIn('import Layout1 from "../../app/dashboard/layout.tsx"', content)
        self.assertIn('Page0.layout = (page) => createElement(Layout0, null, page)', content)
        self.assertIn('Page1.layout = (page) => createElement(Layout0, null, createElement(Layout1, null, page))', content)

    def test_layout_wiring_in_client(self):
        pages = [
            PageModule(page_id="/", module_path="app/page.tsx", layout_paths=["app/layout.tsx"]),
        ]
        path = generate_client_entry(pages, self.gen, use_inertia=True)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('import Layout0 from "../../app/layout.tsx"', content)
        self.assertIn('Page0.layout = (page) => createElement(Layout0, null, page)', content)


if __name__ == "__main__":
    unittest.main()
