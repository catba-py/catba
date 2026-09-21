import asyncio
import os
import tempfile
import unittest

from catba.context import Request
from catba.runtime import App, HTTPResult, PageData, to_http

from tests.helpers import write_tree


def run(coro):
    return asyncio.run(coro)


class TestReturnSemantics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _app(self, files):
        write_tree(self.root, files)
        return App(os.path.join(self.root, "app"))

    def _result(self, app, method, path, body=None):
        return run(app.handle(Request(method, path, body=body)))

    def test_dict_from_page_route_is_page_data(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    return {'message': 'hi'}\n",
            "app/page.tsx": "",
        })
        result = self._result(app, "GET", "/")
        self.assertIsInstance(result, PageData)
        self.assertEqual(result.page_path, "/")
        self.assertEqual(result.props, {"message": "hi"})

    def test_dict_from_api_route_is_json(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    return {'message': 'hi'}\n",
        })
        result = self._result(app, "GET", "/")
        self.assertIsInstance(result, HTTPResult)
        self.assertEqual(result.status, 200)
        self.assertIn(b"message", result.body)

    def test_response_object_is_raw_http(self):
        app = self._app({
            "app/route.py": (
                "from catba import Response\n"
                "async def GET(ctx):\n"
                "    return Response('Hello', status=201, headers={'X-T': '1'})\n"
            ),
            "app/page.tsx": "",
        })
        result = self._result(app, "GET", "/")
        self.assertIsInstance(result, HTTPResult)
        self.assertEqual(result.status, 201)
        self.assertEqual(result.headers["X-T"], "1")
        self.assertEqual(result.body, b"Hello")

    def test_json_object_always_json(self):
        app = self._app({
            "app/route.py": (
                "from catba import JSON\n"
                "async def GET(ctx):\n    return JSON({'ok': True}, status=201)\n"
            ),
            "app/page.tsx": "",
        })
        result = self._result(app, "GET", "/")
        self.assertIsInstance(result, HTTPResult)
        self.assertEqual(result.status, 201)
        self.assertEqual(result.headers["Content-Type"], "application/json")

    def test_redirect_object_is_redirect(self):
        app = self._app({
            "app/route.py": (
                "from catba import Redirect\n"
                "async def POST(ctx):\n    return Redirect('/users')\n"
            ),
        })
        result = self._result(app, "POST", "/")
        self.assertIsInstance(result, HTTPResult)
        self.assertEqual(result.status, 303)
        self.assertEqual(result.headers["Location"], "/users")

    def test_none_returns_204(self):
        app = self._app({
            "app/route.py": "async def DELETE(ctx):\n    return None\n",
        })
        result = self._result(app, "DELETE", "/")
        self.assertIsInstance(result, HTTPResult)
        self.assertEqual(result.status, 204)

    def test_page_data_to_http_serializes_props(self):
        app = self._app({
            "app/route.py": "async def GET(ctx):\n    return {'message': 'hi'}\n",
            "app/page.tsx": "",
        })
        result = self._result(app, "GET", "/")
        status, headers, body = to_http(result)
        self.assertEqual(status, 200)
        self.assertIn(b"message", body)
        self.assertEqual(headers["X-CatBa-Page"], "/")


if __name__ == "__main__":
    unittest.main()
