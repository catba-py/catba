"""Tests for frontend build infrastructure.

Tests Node detection and error handling. Real Vite build tests are in
the integration test suite (commit 11).
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from catba.frontend import (
    FrontendError,
    check_node,
    ensure_dependencies,
    find_client_bundle,
    find_node,
    find_ssr_bundle,
)


class TestNodeDetection(unittest.TestCase):
    def test_find_node_returns_string_or_none(self):
        result = find_node()
        self.assertTrue(result is None or isinstance(result, str))

    def test_check_node_raises_when_missing(self):
        with patch("catba.frontend.find_node", return_value=None):
            with self.assertRaises(FrontendError) as ctx:
                check_node()
            self.assertIn("Node.js", str(ctx.exception))

    def test_check_node_passes_when_found(self):
        with patch("catba.frontend.find_node", return_value="/usr/bin/node"):
            check_node()  # should not raise


class TestEnsureDependencies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_skips_when_node_modules_exists(self):
        os.makedirs(os.path.join(self.root, "node_modules"))
        # Should return 0 without calling npm.
        rc = ensure_dependencies(self.root)
        self.assertEqual(rc, 0)

    def test_raises_when_no_package_json(self):
        with patch("catba.frontend.find_npm", return_value="/usr/bin/npm"):
            with self.assertRaises(FrontendError) as ctx:
                ensure_dependencies(self.root)
            self.assertIn("package.json", str(ctx.exception))

    def test_raises_when_no_npm(self):
        from tests.helpers import write_tree
        write_tree(self.root, {"package.json": "{}"})
        with patch("catba.frontend.find_npm", return_value=None):
            with self.assertRaises(FrontendError) as ctx:
                ensure_dependencies(self.root)
            self.assertIn("npm", str(ctx.exception))


class TestFindBundles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_ssr_bundle_missing(self):
        self.assertIsNone(find_ssr_bundle(self.root))

    def test_find_ssr_bundle_found(self):
        ssr_dir = os.path.join(self.root, ".catba", "generated", "ssr")
        os.makedirs(ssr_dir)
        path = os.path.join(ssr_dir, "ssr-entry.js")
        with open(path, "w") as f:
            f.write("// bundle")
        result = find_ssr_bundle(self.root)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("ssr-entry.js"))

    def test_find_client_bundle_missing(self):
        self.assertIsNone(find_client_bundle(self.root))

    def test_find_client_bundle_found(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        path = os.path.join(client_dir, "main.js")
        with open(path, "w") as f:
            f.write("// bundle")
        result = find_client_bundle(self.root)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".js"))


if __name__ == "__main__":
    unittest.main()
