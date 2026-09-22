"""End-to-end React SSR integration tests.

Creates a real CatBa project, installs npm dependencies, builds the frontend
with Vite, starts the SSR worker, and verifies that page routes produce real
HTML and API routes produce JSON. Skipped if Node.js is not available.
"""

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from catba.frontend import find_node, prepare_frontend
from catba.runtime import App, to_http
from catba.ssr import SSRWorker
from catba.transport import _Handler

from tests.helpers import write_tree


PROJECT_FILES = {
    "pyproject.toml": (
        '[project]\nname = "test-app"\nversion = "0.1.0"\n'
        'requires-python = ">=3.14"\n'
    ),
    "catba.py": (
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "_here = os.path.dirname(os.path.abspath(__file__))\n"
        "sys.path = [p for p in sys.path if os.path.abspath(p) != _here]\n"
        "from catba.cli import main\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n"
    ),
    "package.json": (
        '{"name": "test-app", "version": "0.1.0", "private": true, '
        '"type": "module", "scripts": {}, '
        '"dependencies": {"react": "^19.2.0", "react-dom": "^19.2.0"}, '
        '"devDependencies": {"@types/react": "^19.2.0", '
        '"@types/react-dom": "^19.2.0", '
        '"@vitejs/plugin-react": "^5.0.0", "typescript": "^5.9.0", '
        '"vite": "^7.1.0"}}'
    ),
    "tsconfig.json": (
        '{"compilerOptions": {"target": "ES2022", "module": "ESNext", '
        '"moduleResolution": "bundler", "jsx": "react-jsx", "strict": true, '
        '"esModuleInterop": true, "skipLibCheck": true}, '
        '"include": ["app", ".catba/generated"]}'
    ),
    "vite.config.ts": (
        'import { defineConfig } from "vite"\n'
        'import react from "@vitejs/plugin-react"\n'
        'import { resolve } from "path"\n'
        'import { fileURLToPath } from "url"\n'
        'import { dirname } from "path"\n'
        'const __dirname = dirname(fileURLToPath(import.meta.url))\n'
        'export default defineConfig({\n'
        '  plugins: [react()],\n'
        '  resolve: { alias: { "@catba/pages": resolve(__dirname, "app") } },\n'
        '  build: { emptyOutDir: true, '
        '    rollupOptions: { input: resolve(__dirname, ".catba/generated/client-entry.js") } }\n'
        '})\n'
    ),
    # Root page route
    "app/route.py": (
        "async def GET(ctx):\n"
        "    return {\"message\": \"Hello, CatBa\"}\n"
    ),
    "app/page.tsx": (
        'type Props = { message: string }\n'
        'export default function Page({ message }: Props) {\n'
        '    return (\n'
        '        <main>\n'
        '            <h1>{message}</h1>\n'
        '        </main>\n'
        '    )\n'
        '}\n'
    ),
    # Dynamic page route
    "app/users/[id]/route.py": (
        "async def GET(ctx):\n"
        "    return {\"id\": ctx.params[\"id\"], \"name\": \"User \" + ctx.params[\"id\"]}\n"
    ),
    "app/users/[id]/page.tsx": (
        'type Props = { id: string; name: string }\n'
        'export default function Page({ id, name }: Props) {\n'
        '    return (\n'
        '        <div>\n'
        '            <p>ID: {id}</p>\n'
        '            <p>Name: {name}</p>\n'
        '        </div>\n'
        '    )\n'
        '}\n'
    ),
    # API route (no page.tsx)
    "app/api/users/route.py": (
        "async def GET(ctx):\n"
        "    return {\"users\": [{\"id\": 1, \"name\": \"Alice\"}]}\n"
    ),
    # Explicit JSON from page route
    "app/json-test/route.py": (
        "from catba import JSON\n"
        "async def GET(ctx):\n"
        "    return JSON({\"explicit\": True})\n"
    ),
    "app/json-test/page.tsx": (
        'export default function Page() { return <div>should not render</div> }\n'
    ),
}


def _has_node():
    return find_node() is not None


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSSRIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        write_tree(cls.root, PROJECT_FILES)

        # Install npm dependencies.
        npm = shutil.which("npm")
        if npm:
            subprocess.call([npm, "install", "--silent"], cwd=cls.root, timeout=120)

        # Prepare frontend (generate entries + build bundles).
        app_dir = os.path.join(cls.root, "app")
        prepare_frontend(app_dir, cls.root)

        # Create the App with project_root for asset serving.
        cls.app = App(app_dir, project_root=cls.root)

        # Start SSR worker.
        cls.ssr = SSRWorker(cls.root)
        cls.ssr.start()

        # Start HTTP server.
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.app = cls.app
        httpd.ssr = cls.ssr
        httpd.project_root = cls.root
        cls.port = httpd.server_address[1]
        cls.httpd = httpd
        cls.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.ssr.stop()
        cls.tmp.cleanup()

    def _request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, hdrs, data

    def test_root_page_returns_html(self):
        status, headers, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        html = body.decode("utf-8")
        self.assertIn("<!doctype html>", html)
        self.assertIn("catba-root", html)
        self.assertIn("Hello, CatBa", html)
        self.assertIn("<h1>", html)

    def test_root_page_has_hydration_state(self):
        status, _, body = self._request("GET", "/")
        html = body.decode("utf-8")
        self.assertIn("data-catba-page", html)
        self.assertIn("catba-props", html)
        self.assertIn("Hello, CatBa", html)

    def test_dynamic_page_renders(self):
        status, _, body = self._request("GET", "/users/42")
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertIn("42", html)
        self.assertIn("User 42", html)

    def test_api_route_returns_json(self):
        status, headers, body = self._request("GET", "/api/users")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body)
        self.assertIn("users", data)

    def test_explicit_json_bypasses_ssr(self):
        status, headers, body = self._request("GET", "/json-test")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body)
        self.assertEqual(data, {"explicit": True})

    def test_404_remains_404(self):
        status, _, _ = self._request("GET", "/nonexistent")
        self.assertEqual(status, 404)

    def test_405_remains_405(self):
        status, headers, _ = self._request("DELETE", "/")
        self.assertEqual(status, 405)
        self.assertIn("allow", headers)

    def test_head_returns_headers_no_body(self):
        status, _, body = self._request("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    def test_options_advertises_methods(self):
        status, headers, _ = self._request("OPTIONS", "/")
        self.assertEqual(status, 200)
        self.assertIn("allow", headers)

    def test_script_injection_blocked(self):
        """Props containing </script> must not break the hydration payload."""
        from catba.html import _safe_script_json
        safe = _safe_script_json({"x": "</script><script>alert(1)"})
        self.assertNotIn("</script>", safe)

    def test_client_bundle_served(self):
        status, headers, body = self._request("GET", "/__catba/")
        # The asset path needs a filename; empty path returns 404 or None.
        # Check that the asset dir exists.
        client_dir = os.path.join(self.root, ".catba", "generated", "client")
        self.assertTrue(os.path.isdir(client_dir))
        js_files = [f for f in os.listdir(client_dir) if f.endswith(".js")]
        self.assertTrue(len(js_files) > 0)
        if js_files:
            status, headers, body = self._request("GET", f"/__catba/{js_files[0]}")
            self.assertEqual(status, 200)
            self.assertIn("javascript", headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
