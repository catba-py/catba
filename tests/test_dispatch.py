import asyncio
import os
import tempfile
import unittest

from catba.context import Request
from catba.runtime import App
from catba.response import NotFound

from tests.helpers import write_tree


def run(coro):
    return asyncio.run(coro)


class TestMethodDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _app(self, files):
        write_tree(self.root, files)
        return App(os.path.join(self.root, "app"))

    def test_async_get(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    return {'ok': True}\n",
        })
        status, headers, body = run(app.handle(Request("GET", "/")))
        self.assertEqual(status, 200)
        self.assertIn(b"ok", body)

    def test_sync_get(self):
        app = self._app({
            "app/route.py": "def GET(ctx):\n    return {'ok': True}\n",
        })
        status, _, body = run(app.handle(Request("GET", "/")))
        self.assertEqual(status, 200)
        self.assertIn(b"ok", body)

    def test_post(self):
        app = self._app({
            "app/route.py": "async def POST(ctx):\n    return {'created': True}\n",
        })
        status, _, _ = run(app.handle(Request("POST", "/")))
        self.assertEqual(status, 200)

    def test_put_patch_delete(self):
        app = self._app({
            "app/route.py": (
                "async def PUT(ctx): return {'m': 'PUT'}\n"
                "async def PATCH(ctx): return {'m': 'PATCH'}\n"
                "async def DELETE(ctx): return {'m': 'DELETE'}\n"
            ),
        })
        for method in ("PUT", "PATCH", "DELETE"):
            status, _, _ = run(app.handle(Request(method, "/")))
            self.assertEqual(status, 200)

    def test_404_no_route(self):
        app = self._app({"app/route.py": "async def GET(ctx): pass\n"})
        status, _, _ = run(app.handle(Request("GET", "/missing")))
        self.assertEqual(status, 404)

    def test_405_with_allow(self):
        app = self._app({
            "app/route.py": (
                "async def GET(ctx): return {}\n"
                "async def POST(ctx): return {}\n"
            ),
        })
        status, headers, _ = run(app.handle(Request("DELETE", "/")))
        self.assertEqual(status, 405)
        allow = set(headers["Allow"].split(","))
        self.assertEqual(allow, {"GET", "POST"})

    def test_head_uses_get_suppresses_body(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    return {'message': 'hello'}\n",
        })
        status, headers, body = run(app.handle(Request("HEAD", "/")))
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    def test_head_explicit_handler(self):
        app = self._app({
            "app/route.py": (
                "async def GET(ctx): return {'a': 1}\n"
                "async def HEAD(ctx): return None\n"
            ),
        })
        status, _, body = run(app.handle(Request("HEAD", "/")))
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")

    def test_options_advertises_methods(self):
        app = self._app({
            "app/route.py": (
                "async def GET(ctx): return {}\n"
                "async def POST(ctx): return {}\n"
            ),
        })
        status, headers, _ = run(app.handle(Request("OPTIONS", "/")))
        self.assertEqual(status, 200)
        allow = set(headers["Allow"].split(","))
        self.assertEqual(allow, {"GET", "POST"})

    def test_options_explicit_handler(self):
        app = self._app({
            "app/route.py": (
                "async def GET(ctx): return {}\n"
                "async def OPTIONS(ctx): return {'custom': True}\n"
            ),
        })
        status, _, body = run(app.handle(Request("OPTIONS", "/")))
        self.assertEqual(status, 200)
        self.assertIn(b"custom", body)

    def test_handler_exception_becomes_500(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    raise ValueError('boom')\n",
        })
        status, _, body = run(app.handle(Request("GET", "/")))
        self.assertEqual(status, 500)
        self.assertEqual(body, b"Internal Server Error")

    def test_http_error_mapped(self):
        app = self._app({
            "app/route.py": (
                "from catba import NotFound\n"
                "async def GET(ctx):\n    raise NotFound('no user')\n"
            ),
        })
        status, _, body = run(app.handle(Request("GET", "/")))
        self.assertEqual(status, 404)
        self.assertEqual(body, b"no user")


if __name__ == "__main__":
    unittest.main()
