import http.client
import os
import tempfile
import unittest

from catba.runtime import App
from catba.transport import DevServer, _parse_body, _parse_cookies, _make_request
from catba.context import Headers, Request

from tests.helpers import write_tree


class TestBodyParsing(unittest.TestCase):
    def test_json_body(self):
        h = Headers({"Content-Type": "application/json"})
        self.assertEqual(_parse_body(h, b'{"x": 1}'), {"x": 1})

    def test_form_body(self):
        h = Headers({"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(_parse_body(h, b"a=1&b=2"), {"a": "1", "b": "2"})

    def test_raw_body(self):
        h = Headers({"Content-Type": "text/plain"})
        self.assertEqual(_parse_body(h, b"hello"), b"hello")

    def test_empty_body(self):
        self.assertEqual(_parse_body(Headers(), b""), b"")


class TestCookieParsing(unittest.TestCase):
    def test_parse_cookies(self):
        h = Headers({"Cookie": "sid=abc; theme=dark"})
        self.assertEqual(_parse_cookies(h), {"sid": "abc", "theme": "dark"})

    def test_no_cookies(self):
        self.assertEqual(_parse_cookies(Headers()), {})


class TestMakeRequest(unittest.TestCase):
    def test_query_parsed(self):
        req = _make_request("GET", "/users?q=1&page=2", {}, b"")
        self.assertEqual(req.path, "/users")
        self.assertEqual(req.query["q"], "1")
        self.assertEqual(req.query["page"], "2")

    def test_headers_case_insensitive(self):
        req = _make_request("GET", "/", {"Content-Type": "text/html"}, b"")
        self.assertEqual(req.headers["content-type"], "text/html")


class TestDevServerHTTP(unittest.TestCase):
    """Full HTTP round-trip through the dev transport."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write_tree(self.root, {
            "app/route.py": (
                "async def GET(ctx):\n"
                "    return {'message': 'Hello, CatBa'}\n"
            ),
            "app/page.tsx": "",
            "app/users/[id]/route.py": (
                "async def GET(ctx):\n"
                "    return {'id': ctx.params['id']}\n"
            ),
            "app/users/[id]/page.tsx": "",
            "app/echo/route.py": (
                "async def POST(ctx):\n"
                "    return {'echoed': ctx.body}\n"
            ),
        })
        self.app = App(os.path.join(self.root, "app"))
        self.server = DevServer(self.app, host="127.0.0.1", port=0)
        import threading
        from http.server import ThreadingHTTPServer
        from catba.transport import _Handler
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.app = self.app
        self.httpd = httpd
        self.port = httpd.server_address[1]
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _conn(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)

    def test_get_root(self):
        c = self._conn()
        c.request("GET", "/")
        resp = c.getresponse()
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.read())
        self.assertEqual(data["message"], "Hello, CatBa")

    def test_get_dynamic(self):
        c = self._conn()
        c.request("GET", "/users/42")
        resp = c.getresponse()
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.read())
        self.assertEqual(data["id"], "42")

    def test_post_body(self):
        c = self._conn()
        body = '{"text": "hi"}'
        c.request("POST", "/echo", body=body,
                  headers={"Content-Type": "application/json"})
        resp = c.getresponse()
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.read())
        self.assertEqual(data["echoed"], {"text": "hi"})

    def test_404(self):
        c = self._conn()
        c.request("GET", "/nonexistent")
        resp = c.getresponse()
        self.assertEqual(resp.status, 404)

    def test_405(self):
        c = self._conn()
        c.request("DELETE", "/")
        resp = c.getresponse()
        self.assertEqual(resp.status, 405)
        self.assertIn("Allow", {k: v for k, v in resp.getheaders()})


if __name__ == "__main__":
    unittest.main()
