import os
import tempfile
import unittest

from catba.routing import RouteError, RouteTable, discover_routes

from tests.helpers import write_tree


class TestRouteDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_route(self):
        write_tree(self.root, {"app/route.py": "async def GET(ctx): pass\n"})
        table = discover_routes(os.path.join(self.root, "app"))
        self.assertEqual(len(table.routes), 1)
        r = table.routes[0]
        self.assertEqual(r.url, "/")
        self.assertEqual(r.params, [])
        self.assertFalse(r.has_page)

    def test_nested_static_route(self):
        write_tree(self.root, {
            "app/route.py": "",
            "app/users/route.py": "",
        })
        table = discover_routes(os.path.join(self.root, "app"))
        urls = sorted(r.url for r in table.routes)
        self.assertEqual(urls, ["/", "/users"])

    def test_dynamic_route(self):
        write_tree(self.root, {"app/users/[id]/route.py": ""})
        table = discover_routes(os.path.join(self.root, "app"))
        r = table.routes[0]
        self.assertEqual(r.url, "/users/[id]")
        self.assertEqual(r.params, ["id"])
        self.assertEqual(r.pattern, ["users", ":id"])

    def test_has_page_flag(self):
        write_tree(self.root, {
            "app/route.py": "",
            "app/page.tsx": "",
        })
        table = discover_routes(os.path.join(self.root, "app"))
        self.assertTrue(table.routes[0].has_page)

    def test_page_without_route_py_is_error(self):
        write_tree(self.root, {"app/page.tsx": ""})
        with self.assertRaises(RouteError):
            discover_routes(os.path.join(self.root, "app"))

    def test_ambiguous_dynamic_segments_error(self):
        write_tree(self.root, {
            "app/users/[id]/route.py": "",
            "app/users/[slug]/route.py": "",
        })
        with self.assertRaises(RouteError):
            discover_routes(os.path.join(self.root, "app"))

    def test_distinct_dynamic_under_different_parents_ok(self):
        write_tree(self.root, {
            "app/users/[id]/route.py": "",
            "app/posts/[id]/route.py": "",
        })
        table = discover_routes(os.path.join(self.root, "app"))
        self.assertEqual(len(table.routes), 2)

    def test_empty_app_dir(self):
        write_tree(self.root, {"app/.gitkeep": ""})
        table = discover_routes(os.path.join(self.root, "app"))
        self.assertEqual(table.routes, [])

    def test_missing_app_dir(self):
        table = discover_routes(os.path.join(self.root, "nope"))
        self.assertEqual(table.routes, [])


class TestRouteMatching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write_tree(self.root, {
            "app/route.py": "",
            "app/users/route.py": "",
            "app/users/me/route.py": "",
            "app/users/[id]/route.py": "",
        })
        self.table = discover_routes(os.path.join(self.root, "app"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_match(self):
        route, params = self.table.match("/")
        self.assertIsNotNone(route)
        self.assertEqual(route.url, "/")
        self.assertEqual(params, {})

    def test_static_match(self):
        route, params = self.table.match("/users")
        self.assertEqual(route.url, "/users")
        self.assertEqual(params, {})

    def test_dynamic_match_captures_param(self):
        route, params = self.table.match("/users/42")
        self.assertEqual(route.url, "/users/[id]")
        self.assertEqual(params, {"id": "42"})

    def test_static_beats_dynamic(self):
        # /users/me must beat /users/[id]
        route, params = self.table.match("/users/me")
        self.assertEqual(route.url, "/users/me")
        self.assertEqual(params, {})

    def test_no_match_returns_none(self):
        route, params = self.table.match("/nonexistent")
        self.assertIsNone(route)
        self.assertEqual(params, {})

    def test_no_match_wrong_depth(self):
        route, _ = self.table.match("/users/42/extra")
        self.assertIsNone(route)


if __name__ == "__main__":
    unittest.main()
