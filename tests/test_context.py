import unittest

from catba.context import Context, Headers, Request


class TestHeaders(unittest.TestCase):
    def test_case_insensitive_get(self):
        h = Headers({"Content-Type": "text/html", "X-Custom": "1"})
        self.assertEqual(h["content-type"], "text/html")
        self.assertEqual(h["CONTENT-TYPE"], "text/html")
        self.assertEqual(h.get("x-custom"), "1")
        self.assertIn("Content-Type", h)

    def test_set_preserves_original_casing(self):
        h = Headers()
        h["X-Test"] = "yes"
        self.assertEqual(h["x-test"], "yes")
        self.assertEqual(list(h), ["X-Test"])

    def test_len_and_items(self):
        h = Headers({"A": "1", "B": "2"})
        self.assertEqual(len(h), 2)
        self.assertEqual(dict(h.items()), {"A": "1", "B": "2"})

    def test_missing_key(self):
        h = Headers({"A": "1"})
        self.assertIsNone(h.get("missing"))
        with self.assertRaises(KeyError):
            _ = h["missing"]


class TestRequest(unittest.TestCase):
    def test_defaults(self):
        r = Request("GET", "/")
        self.assertEqual(r.method, "GET")
        self.assertEqual(r.path, "/")
        self.assertEqual(r.query, {})
        self.assertEqual(r.cookies, {})
        self.assertEqual(r.body, b"")
        self.assertEqual(r.params, {})
        self.assertIsInstance(r.headers, Headers)

    def test_carries_data(self):
        r = Request(
            "POST", "/users",
            headers={"Content-Type": "application/json"},
            query={"q": "1"},
            cookies={"sid": "abc"},
            body={"x": 1},
            params={"id": "42"},
        )
        self.assertEqual(r.headers["content-type"], "application/json")
        self.assertEqual(r.query["q"], "1")
        self.assertEqual(r.cookies["sid"], "abc")
        self.assertEqual(r.body, {"x": 1})
        self.assertEqual(r.params["id"], "42")


class TestContext(unittest.TestCase):
    def test_exposes_request_fields(self):
        req = Request(
            "GET", "/",
            headers={"X-A": "1"},
            query={"q": "2"},
            cookies={"sid": "s"},
            body={"k": "v"},
            params={"id": "9"},
        )
        ctx = Context(req)
        self.assertIs(ctx.request, req)
        self.assertEqual(ctx.params["id"], "9")
        self.assertEqual(ctx.query["q"], "2")
        self.assertEqual(ctx.headers["x-a"], "1")
        self.assertEqual(ctx.cookies["sid"], "s")
        self.assertEqual(ctx.body, {"k": "v"})
        self.assertIsNone(ctx.session)
        self.assertEqual(ctx.state, {})

    def test_state_is_mutable_and_independent(self):
        ctx1 = Context(Request("GET", "/"))
        ctx2 = Context(Request("GET", "/"))
        ctx1.state["user"] = "a"
        self.assertNotIn("user", ctx2.state)


if __name__ == "__main__":
    unittest.main()
