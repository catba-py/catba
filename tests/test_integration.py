"""Full HTTP integration tests through the dev transport.

Exercise the whole Python request path: transport parses raw HTTP into a
Request, the core dispatches to a route handler, the handler reads ctx fields
and returns a value, the core interprets it, and the transport serializes
the response. This file covers context fields, sync/async handlers, return
contracts, and errors through real HTTP round-trips.
"""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from catba.runtime import App
from catba.transport import _Handler

from tests.helpers import write_tree


ROUTES = {
    # root: page route (has page.tsx), async GET returns page data
    "app/route.py": (
        "async def GET(ctx):\n"
        "    return {'message': 'Hello, CatBa'}\n"
    ),
    "app/page.tsx": "",
    # params + query
    "app/users/[id]/route.py": (
        "async def GET(ctx):\n"
        "    return {'id': ctx.params['id'], 'q': ctx.query.get('q')}\n"
        "async def POST(ctx):\n"
        "    return {'id': ctx.params['id'], 'body': ctx.body}\n"
    ),
    "app/users/[id]/page.tsx": "",
    # headers + cookies
    "app/headers/route.py": (
        "async def GET(ctx):\n"
        "    return {'agent': ctx.headers.get('user-agent'),"
        " 'cookie': ctx.cookies.get('sid')}\n"
    ),
    # state
    "app/state/route.py": (
        "async def GET(ctx):\n"
        "    ctx.state['counter'] = ctx.state.get('counter', 0) + 1\n"
        "    return {'counter': ctx.state['counter']}\n"
    ),
    # sync handler
    "app/sync/route.py": (
        "def GET(ctx):\n"
        "    return {'sync': True}\n"
    ),
    # API route (no page.tsx): dict -> JSON
    "app/api/route.py": (
        "async def GET(ctx):\n"
        "    return {'api': True}\n"
    ),
    # explicit Response
    "app/raw/route.py": (
        "from catba import Response\n"
        "async def GET(ctx):\n"
        "    return Response('plain', status=201, headers={'X-Test': '1'})\n"
    ),
    # explicit JSON from a page route
    "app/explicit-json/route.py": (
        "from catba import JSON\n"
        "async def GET(ctx):\n"
        "    return JSON({'explicit': True})\n"
    ),
    "app/explicit-json/page.tsx": "",
    # redirect
    "app/redirect/route.py": (
        "from catba import Redirect\n"
        "async def POST(ctx):\n"
        "    return Redirect('/users')\n"
    ),
    # application HTTP error
    "app/notfound/route.py": (
        "from catba import NotFound\n"
        "async def GET(ctx):\n"
        "    raise NotFound('no such page')\n"
    ),
    # internal error
    "app/crash/route.py": (
        "async def GET(ctx):\n"
        "    raise RuntimeError('boom')\n"
    ),
    # static beats dynamic
    "app/users/me/route.py": (
        "async def GET(ctx):\n"
        "    return {'static': True}\n"
    ),
}


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        write_tree(cls.root, ROUTES)
        cls.app = App(os.path.join(cls.root, "app"))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.app = cls.app
        cls.port = httpd.server_address[1]
        cls.httpd = httpd
        cls.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def _request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, hdrs, data

    # --- real HTTP paths ---

    def test_get_root(self):
        status, _, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"message": "Hello, CatBa"})

    def test_get_dynamic(self):
        status, _, body = self._request("GET", "/users/42")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["id"], "42")

    def test_post_with_body(self):
        status, _, body = self._request(
            "POST", "/users/7",
            body=json.dumps({"name": "x"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["id"], "7")
        self.assertEqual(data["body"], {"name": "x"})

    # --- context fields ---

    def test_query_params(self):
        status, _, body = self._request("GET", "/users/42?q=search")
        data = json.loads(body)
        self.assertEqual(data["q"], "search")

    def test_headers_and_cookies(self):
        status, _, body = self._request(
            "GET", "/headers",
            headers={"User-Agent": "test/1.0", "Cookie": "sid=abc123"},
        )
        data = json.loads(body)
        self.assertEqual(data["agent"], "test/1.0")
        self.assertEqual(data["cookie"], "abc123")

    def test_state_is_request_scoped(self):
        # Two independent requests: state must not persist between them.
        status1, _, body1 = self._request("GET", "/state")
        status2, _, body2 = self._request("GET", "/state")
        self.assertEqual(json.loads(body1)["counter"], 1)
        self.assertEqual(json.loads(body2)["counter"], 1)

    def test_sync_handler(self):
        status, _, body = self._request("GET", "/sync")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"sync": True})

    # --- return contracts ---

    def test_api_dict_is_json(self):
        status, headers, body = self._request("GET", "/api")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(json.loads(body), {"api": True})

    def test_explicit_response(self):
        status, headers, body = self._request("GET", "/raw")
        self.assertEqual(status, 201)
        self.assertEqual(headers["x-test"], "1")
        self.assertEqual(body, b"plain")

    def test_explicit_json_from_page_route(self):
        status, headers, body = self._request("GET", "/explicit-json")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(json.loads(body), {"explicit": True})

    def test_redirect(self):
        status, headers, _ = self._request("POST", "/redirect")
        self.assertEqual(status, 303)
        self.assertEqual(headers["location"], "/users")

    def test_page_data_has_marker_header(self):
        status, headers, body = self._request("GET", "/")
        self.assertEqual(headers.get("x-catba-page"), "/")

    # --- errors ---

    def test_404_no_route(self):
        status, _, _ = self._request("GET", "/nonexistent")
        self.assertEqual(status, 404)

    def test_405_with_allow(self):
        status, headers, _ = self._request("DELETE", "/")
        self.assertEqual(status, 405)
        self.assertIn("allow", headers)

    def test_500_internal_error(self):
        status, _, body = self._request("GET", "/crash")
        self.assertEqual(status, 500)
        self.assertEqual(body, b"Internal Server Error")

    def test_application_http_error(self):
        status, _, body = self._request("GET", "/notfound")
        self.assertEqual(status, 404)
        self.assertEqual(body, b"no such page")

    # --- routing precedence ---

    def test_static_beats_dynamic(self):
        status, _, body = self._request("GET", "/users/me")
        data = json.loads(body)
        self.assertEqual(data, {"static": True})


if __name__ == "__main__":
    unittest.main()
