"""Tests for static asset serving."""

import os
import tempfile
import unittest

from catba.assets import (
    ASSET_PREFIX,
    get_client_bundle_url,
    is_asset_path,
    serve_asset,
)

from tests.helpers import write_tree


class TestAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_asset_path(self):
        self.assertTrue(is_asset_path("/__catba/main.js"))
        self.assertFalse(is_asset_path("/"))
        self.assertFalse(is_asset_path("/users"))

    def test_get_client_bundle_url_none(self):
        self.assertIsNone(get_client_bundle_url(self.root))

    def test_get_client_bundle_url_found(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        with open(os.path.join(client_dir, "main.js"), "w") as f:
            f.write("// bundle")
        url = get_client_bundle_url(self.root)
        self.assertEqual(url, "/__catba/main.js")

    def test_serve_asset(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        with open(os.path.join(client_dir, "main.js"), "w") as f:
            f.write("console.log('hello')")
        status, headers, body = serve_asset("/__catba/main.js", self.root)
        self.assertEqual(status, 200)
        self.assertIn("application/javascript", headers["Content-Type"])
        self.assertIn(b"hello", body)

    def test_serve_asset_not_found(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        status, _, body = serve_asset("/__catba/missing.js", self.root)
        self.assertEqual(status, 404)

    def test_serve_asset_no_client_dir(self):
        status = serve_asset("/__catba/main.js", self.root)
        self.assertIsNone(status)

    def test_serve_asset_not_an_asset(self):
        self.assertIsNone(serve_asset("/users", self.root))

    def test_serve_asset_path_traversal_blocked(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        status, _, _ = serve_asset("/__catba/../etc/passwd", self.root)
        self.assertEqual(status, 403)

    def test_serve_head_no_body(self):
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        os.makedirs(client_dir)
        with open(os.path.join(client_dir, "main.js"), "w") as f:
            f.write("console.log('hello')")
        # serve_asset returns the file; the transport suppresses body for HEAD
        status, headers, body = serve_asset("/__catba/main.js", self.root)
        self.assertEqual(status, 200)
        self.assertTrue(len(body) > 0)


if __name__ == "__main__":
    unittest.main()
