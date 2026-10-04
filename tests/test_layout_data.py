"""Tests for layout.py server-side data fetching and guards."""

import asyncio
import os
import shutil
import tempfile
import unittest

from catba.context import Context, Headers, Request
from catba.response import HTTPError, Redirect, ValidationError
from catba.routing import discover_routes
from catba.runtime import App, PageData, to_http


class TestLayoutData(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.app_dir = os.path.join(self.tmpdir, "app")
        os.makedirs(self.app_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_layout_props_merging(self):
        # app/layout.py
        with open(os.path.join(self.app_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'site': 'CatBa', 'theme': 'dark'}\n"
            )

        # app/route.py
        with open(os.path.join(self.app_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'page': 'Home'}\n"
            )

        # app/dashboard/layout.py
        dash_dir = os.path.join(self.app_dir, "dashboard")
        os.makedirs(dash_dir)
        with open(os.path.join(dash_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'theme': 'light', 'section': 'Admin'}\n"
            )

        # app/dashboard/route.py
        with open(os.path.join(dash_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'stats': [10, 20]}\n"
            )

        app = App(self.app_dir)

        # Test root route
        req_root = Request("GET", "/")
        res_root = asyncio.run(app.handle(req_root))
        status, headers, body = to_http(res_root)
        import json
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"site": "CatBa", "theme": "dark", "page": "Home"})

        # Test dashboard route: theme should be overridden to 'light'
        req_dash = Request("GET", "/dashboard")
        res_dash = asyncio.run(app.handle(req_dash))
        status, headers, body = to_http(res_dash)
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {"site": "CatBa", "theme": "light", "section": "Admin", "stats": [10, 20]},
        )

    def test_layout_async_and_alternative_fn_names(self):
        # Test async def layout(ctx)
        with open(os.path.join(self.app_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write(
                "async def layout(ctx):\n"
                "    return {'async_key': 'async_value'}\n"
            )

        with open(os.path.join(self.app_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "async def GET(ctx):\n"
                "    return {'page_key': 123}\n"
            )

        app = App(self.app_dir)
        req = Request("GET", "/")
        res = asyncio.run(app.handle(req))
        import json
        status, _, body = to_http(res)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"async_key": "async_value", "page_key": 123})

    def test_layout_before_guard_redirect(self):
        # app/admin/layout.py
        admin_dir = os.path.join(self.app_dir, "admin")
        os.makedirs(admin_dir)
        with open(os.path.join(admin_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write(
                "from catba import Redirect\n"
                "def before(ctx):\n"
                "    if not ctx.headers.get('Authorization'):\n"
                "        return Redirect('/login')\n"
            )

        with open(os.path.join(admin_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'secret': 42}\n"
                "def POST(ctx):\n"
                "    return {'created': True}\n"
            )

        app = App(self.app_dir)

        # Unauthorized GET -> 303 Redirect to /login
        req_unauth = Request("GET", "/admin")
        res_unauth = asyncio.run(app.handle(req_unauth))
        status, headers, _ = to_http(res_unauth)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/login")

        # Unauthorized POST -> 303 Redirect to /login
        req_post_unauth = Request("POST", "/admin")
        res_post_unauth = asyncio.run(app.handle(req_post_unauth))
        status, headers, _ = to_http(res_post_unauth)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/login")

        # Authorized GET -> 200 OK
        req_auth = Request("GET", "/admin", headers=Headers({"Authorization": "Bearer 123"}))
        res_auth = asyncio.run(app.handle(req_auth))
        status, _, body = to_http(res_auth)
        import json
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"secret": 42})

    def test_layout_raising_http_error(self):
        with open(os.path.join(self.app_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write(
                "from catba import HTTPError\n"
                "def before(ctx):\n"
                "    if ctx.headers.get('X-Block'):\n"
                "        raise HTTPError(403, 'Forbidden by Layout')\n"
            )

        with open(os.path.join(self.app_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "def GET(ctx):\n"
                "    return {'ok': True}\n"
            )

        app = App(self.app_dir)
        req_blocked = Request("GET", "/", headers=Headers({"X-Block": "1"}))
        res_blocked = asyncio.run(app.handle(req_blocked))
        status, _, body = to_http(res_blocked)
        self.assertEqual(status, 403)
        self.assertIn(b"Forbidden by Layout", body)

    def test_page_route_with_layout_returns_pagedata(self):
        # When page.tsx is present, result is PageData with merged props
        with open(os.path.join(self.app_dir, "layout.py"), "w", encoding="utf-8") as f:
            f.write("def GET(ctx): return {'global': 1}\n")

        with open(os.path.join(self.app_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write("def GET(ctx): return {'local': 2}\n")

        with open(os.path.join(self.app_dir, "page.tsx"), "w", encoding="utf-8") as f:
            f.write("export default function Page() { return null; }\n")

        app = App(self.app_dir)
        req = Request("GET", "/")
        res = asyncio.run(app.handle(req))
        self.assertIsInstance(res, PageData)
        self.assertEqual(res.props, {"global": 1, "local": 2})

    def test_validation_error_mutation(self):
        with open(os.path.join(self.app_dir, "route.py"), "w", encoding="utf-8") as f:
            f.write(
                "from catba import ValidationError, Redirect\n"
                "def POST(ctx):\n"
                "    body = ctx.body if isinstance(ctx.body, dict) else {}\n"
                "    if not body.get('title'):\n"
                "        raise ValidationError({'title': 'Title is required'})\n"
                "    return Redirect('/items')\n"
            )

        app = App(self.app_dir)

        # Invalid POST
        req_invalid = Request("POST", "/", headers=Headers({"X-Inertia": "true"}), body={})
        res_invalid = asyncio.run(app.handle(req_invalid))
        status, headers, body = to_http(res_invalid, request=req_invalid)
        import json
        self.assertEqual(status, 422)
        self.assertEqual(headers["X-Inertia"], "true")
        self.assertEqual(json.loads(body), {"errors": {"title": "Title is required"}})

        # Valid POST
        req_valid = Request("POST", "/", headers=Headers({"X-Inertia": "true"}), body={"title": "Test"})
        res_valid = asyncio.run(app.handle(req_valid))
        status, headers, _ = to_http(res_valid, request=req_valid)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/items")


if __name__ == "__main__":
    unittest.main()
