"""Tests for the SSR worker manager.

Mock-based tests for the protocol and lifecycle. Real Node SSR tests
are in the integration test suite (commit 11).
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from catba.ssr import SSRError, SSRWorker


class TestSSRWorkerLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_raises_no_node(self):
        worker = SSRWorker(self.root)
        with patch("catba.ssr.find_node", return_value=None):
            with self.assertRaises(SSRError) as ctx:
                worker.start()
            self.assertIn("Node.js", str(ctx.exception))

    def test_start_raises_no_bundle(self):
        worker = SSRWorker(self.root)
        with patch("catba.ssr.find_node", return_value="/usr/bin/node"), \
             patch("catba.ssr.find_ssr_bundle", return_value=None):
            with self.assertRaises(SSRError) as ctx:
                worker.start()
            self.assertIn("bundle", str(ctx.exception))

    def test_start_and_stop(self):
        worker = SSRWorker(self.root)
        ssr_dir = os.path.join(self.root, ".catba", "generated", "ssr")
        os.makedirs(ssr_dir)
        with open(os.path.join(ssr_dir, "ssr-entry.js"), "w") as f:
            f.write("// fake bundle")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.return_value = json.dumps({"ready": True}) + "\n"

        with patch("catba.ssr.find_node", return_value="/usr/bin/node"), \
             patch("catba.ssr.find_ssr_bundle", return_value=os.path.join(ssr_dir, "ssr-entry.js")), \
             patch("catba.ssr.subprocess.Popen", return_value=mock_proc):
            worker.start()
            self.assertTrue(worker.is_running())
            worker.stop()
            self.assertIsNone(worker.proc)

    def test_stop_is_safe_when_not_started(self):
        worker = SSRWorker(self.root)
        worker.stop()

    def test_stop_terminates_process(self):
        worker = SSRWorker(self.root)
        ssr_dir = os.path.join(self.root, ".catba", "generated", "ssr")
        os.makedirs(ssr_dir)
        with open(os.path.join(ssr_dir, "ssr-entry.js"), "w") as f:
            f.write("// fake")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.return_value = json.dumps({"ready": True}) + "\n"

        with patch("catba.ssr.find_node", return_value="/usr/bin/node"), \
             patch("catba.ssr.find_ssr_bundle", return_value=os.path.join(ssr_dir, "ssr-entry.js")), \
             patch("catba.ssr.subprocess.Popen", return_value=mock_proc):
            worker.start()

        mock_proc.poll.return_value = None
        worker.stop()
        mock_proc.stdin.close.assert_called()
        mock_proc.wait.assert_called_once()


class TestSSRWorkerRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.worker = SSRWorker(self.root)
        self.mock_proc = MagicMock()
        self.mock_proc.poll.return_value = None
        self.mock_proc.stdout.readline.return_value = json.dumps({"ready": True}) + "\n"
        self.worker.proc = self.mock_proc

    def tearDown(self):
        self.worker.stop()
        self.tmp.cleanup()

    def test_render_returns_html(self):
        self.mock_proc.stdout.readline.return_value = json.dumps({
            "id": 1, "html": "<h1>Hello</h1>"
        }) + "\n"
        html = self.worker.render("/", {"message": "Hello"})
        self.assertEqual(html, "<h1>Hello</h1>")

    def test_render_sends_correct_request(self):
        self.mock_proc.stdout.readline.return_value = json.dumps({
            "id": 1, "html": "<div></div>"
        }) + "\n"
        self.worker.render("/users", {"id": "42"})
        written = self.mock_proc.stdin.write.call_args[0][0]
        req = json.loads(written.strip())
        self.assertEqual(req["page"], "/users")
        self.assertEqual(req["props"], {"id": "42"})
        self.assertIn("id", req)

    def test_render_raises_on_error_response(self):
        self.mock_proc.stdout.readline.return_value = json.dumps({
            "id": 1, "error": "Unknown page: /unknown"
        }) + "\n"
        with self.assertRaises(SSRError) as ctx:
            self.worker.render("/unknown", {})
        self.assertIn("Unknown page", str(ctx.exception))

    def test_render_raises_when_worker_not_running(self):
        self.mock_proc.poll.return_value = 1
        with self.assertRaises(SSRError) as ctx:
            self.worker.render("/", {})
        self.assertIn("not running", str(ctx.exception))

    def test_render_raises_on_empty_response(self):
        self.mock_proc.stdout.readline.return_value = ""
        with self.assertRaises(SSRError):
            self.worker.render("/", {})

    def test_render_raises_on_invalid_json(self):
        self.mock_proc.stdout.readline.return_value = "not json\n"
        with self.assertRaises(SSRError):
            self.worker.render("/", {})

    def test_render_raises_on_missing_html(self):
        self.mock_proc.stdout.readline.return_value = json.dumps({"id": 1}) + "\n"
        with self.assertRaises(SSRError) as ctx:
            self.worker.render("/", {})
        self.assertIn("missing html", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
