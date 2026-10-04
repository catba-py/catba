"""Tests for Inertia request detection and protocol helpers."""

import unittest
from unittest.mock import MagicMock

from catba.context import Context, Headers, Request
from catba.inertia import (
    add_vary_inertia,
    build_page_object,
    filter_partial_props,
    get_inertia_version,
    get_partial_component,
    get_partial_data,
    get_partial_except,
    inertia_json_response,
    inertia_version_conflict,
    is_inertia_request,
)


def make_ctx(headers=None):
    req = Request("GET", "/", headers=Headers(headers or {}))
    return Context(req)


class TestRequestDetection(unittest.TestCase):
    def test_x_inertia_true(self):
        ctx = make_ctx({"X-Inertia": "true"})
        self.assertTrue(is_inertia_request(ctx))

    def test_x_inertia_true_uppercase(self):
        ctx = make_ctx({"X-Inertia": "TRUE"})
        self.assertTrue(is_inertia_request(ctx))

    def test_x_inertia_header_name_case_insensitive(self):
        ctx = make_ctx({"x-inertia": "true"})
        self.assertTrue(is_inertia_request(ctx))

    def test_no_x_inertia_header(self):
        ctx = make_ctx({})
        self.assertFalse(is_inertia_request(ctx))

    def test_x_inertia_false(self):
        ctx = make_ctx({"X-Inertia": "false"})
        self.assertFalse(is_inertia_request(ctx))

    def test_x_inertia_empty(self):
        ctx = make_ctx({"X-Inertia": ""})
        self.assertFalse(is_inertia_request(ctx))

    def test_x_inertia_with_whitespace(self):
        ctx = make_ctx({"X-Inertia": "  true  "})
        self.assertTrue(is_inertia_request(ctx))


class TestVersionHeader(unittest.TestCase):
    def test_get_version(self):
        ctx = make_ctx({"X-Inertia-Version": "abc123"})
        self.assertEqual(get_inertia_version(ctx), "abc123")

    def test_get_version_missing(self):
        ctx = make_ctx({})
        self.assertIsNone(get_inertia_version(ctx))


class TestPartialHeaders(unittest.TestCase):
    def test_get_partial_component(self):
        ctx = make_ctx({"X-Inertia-Partial-Component": "/users"})
        self.assertEqual(get_partial_component(ctx), "/users")

    def test_get_partial_component_missing(self):
        ctx = make_ctx({})
        self.assertIsNone(get_partial_component(ctx))

    def test_get_partial_data(self):
        ctx = make_ctx({"X-Inertia-Partial-Data": "users, stats"})
        self.assertEqual(get_partial_data(ctx), ["users", "stats"])

    def test_get_partial_data_missing(self):
        ctx = make_ctx({})
        self.assertIsNone(get_partial_data(ctx))

    def test_get_partial_except(self):
        ctx = make_ctx({"X-Inertia-Partial-Except": "auth, notifications"})
        self.assertEqual(get_partial_except(ctx), ["auth", "notifications"])

    def test_get_partial_except_missing(self):
        ctx = make_ctx({})
        self.assertIsNone(get_partial_except(ctx))


class TestPageObject(unittest.TestCase):
    def test_build_page_object(self):
        obj = build_page_object("/users/[id]", {"id": "42"}, "/users/42", "v1")
        self.assertEqual(obj["component"], "/users/[id]")
        self.assertEqual(obj["props"], {"id": "42"})
        self.assertEqual(obj["url"], "/users/42")
        self.assertEqual(obj["version"], "v1")


class TestPartialPropFiltering(unittest.TestCase):
    def test_partial_data_includes_only_requested(self):
        props = {"users": [1, 2], "auth": True, "stats": {"x": 1}}
        result = filter_partial_props(props, ["users", "stats"], None)
        self.assertEqual(set(result.keys()), {"users", "stats"})

    def test_partial_except_excludes_listed(self):
        props = {"users": [1, 2], "auth": True, "stats": {"x": 1}}
        result = filter_partial_props(props, None, ["auth"])
        self.assertEqual(set(result.keys()), {"users", "stats"})

    def test_both_data_and_except(self):
        props = {"users": [1, 2], "auth": True, "stats": {"x": 1}}
        result = filter_partial_props(props, ["users", "auth", "stats"], ["auth"])
        self.assertEqual(set(result.keys()), {"users", "stats"})

    def test_no_filtering(self):
        props = {"users": [1, 2], "auth": True}
        result = filter_partial_props(props, None, None)
        self.assertEqual(result, props)

    def test_partial_data_unknown_key_ignored(self):
        props = {"users": [1, 2]}
        result = filter_partial_props(props, ["users", "nonexistent"], None)
        self.assertEqual(set(result.keys()), {"users"})


class TestResponses(unittest.TestCase):
    def test_inertia_json_response(self):
        page = build_page_object("/", {"msg": "hi"}, "/", "v1")
        status, headers, body = inertia_json_response(page)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-Inertia"], "true")
        self.assertEqual(headers["Vary"], "X-Inertia")
        import json
        data = json.loads(body)
        self.assertEqual(data["component"], "/")

    def test_inertia_version_conflict(self):
        status, headers, body = inertia_version_conflict("/users/42", "v2")
        self.assertEqual(status, 409)
        self.assertEqual(headers["X-Inertia-Location"], "/users/42")
        self.assertEqual(headers["X-Inertia-Version"], "v2")
        self.assertEqual(headers["Vary"], "X-Inertia")
        self.assertEqual(body, b"")

    def test_add_vary_inertia_empty(self):
        headers = {}
        add_vary_inertia(headers)
        self.assertEqual(headers["Vary"], "X-Inertia")

    def test_add_vary_inertia_existing(self):
        headers = {"Vary": "Accept-Encoding"}
        add_vary_inertia(headers)
        self.assertIn("X-Inertia", headers["Vary"])
        self.assertIn("Accept-Encoding", headers["Vary"])

    def test_add_vary_inertia_already_present(self):
        headers = {"Vary": "X-Inertia"}
        add_vary_inertia(headers)
        self.assertEqual(headers["Vary"], "X-Inertia")


class TestInertiaToHttp(unittest.TestCase):
    def test_page_data_with_inertia_header(self):
        from catba.runtime import PageData, to_http
        import json

        req = Request("GET", "/about", headers=Headers({"X-Inertia": "true"}))
        page = PageData("/about", {"title": "About Us"})
        status, headers, body = to_http(page, request=req)

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-Inertia"], "true")
        self.assertEqual(headers["Vary"], "X-Inertia")
        data = json.loads(body)
        self.assertEqual(data["component"], "/about")
        self.assertEqual(data["props"], {"title": "About Us"})
        self.assertEqual(data["url"], "/about")

    def test_page_data_version_conflict_409(self):
        from catba.runtime import PageData, to_http

        req = Request(
            "GET",
            "/dashboard",
            headers=Headers({
                "X-Inertia": "true",
                "X-Inertia-Version": "outdated_v1",
            }),
            query={"tab": "1"},
        )
        page = PageData("/dashboard", {"user": "alice"})
        status, headers, body = to_http(page, request=req)

        self.assertEqual(status, 409)
        self.assertEqual(headers["X-Inertia-Location"], "/dashboard?tab=1")
        self.assertEqual(headers["Vary"], "X-Inertia")
        self.assertEqual(body, b"")

    def test_page_data_partial_reload(self):
        from catba.runtime import PageData, to_http
        import json

        req = Request(
            "GET",
            "/users",
            headers=Headers({
                "X-Inertia": "true",
                "X-Inertia-Partial-Component": "/users",
                "X-Inertia-Partial-Data": "users",
            }),
        )
        page = PageData("/users", {"users": ["alice", "bob"], "notifications": [1, 2]})
        status, headers, body = to_http(page, request=req)

        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["props"], {"users": ["alice", "bob"]})

    def test_http_result_passes_through_regardless_of_inertia(self):
        from catba.runtime import HTTPResult, to_http

        req = Request("GET", "/api/data", headers=Headers({"X-Inertia": "true"}))
        res = HTTPResult(status=201, headers={"Content-Type": "application/json"}, body=b"{}")
        status, headers, body = to_http(res, request=req)

        self.assertEqual(status, 201)
        self.assertNotIn("X-Inertia", headers)
        self.assertEqual(body, b"{}")

    def test_inertia_external_redirect_returns_409(self):
        from catba.runtime import HTTPResult, to_http
        from catba.response import Redirect

        req = Request(
            "POST",
            "/login",
            headers=Headers({"X-Inertia": "true", "Host": "localhost:8000"}),
        )
        res = HTTPResult(*Redirect("https://github.com/login/oauth").to_http())
        status, headers, body = to_http(res, request=req)

        self.assertEqual(status, 409)
        self.assertEqual(headers["X-Inertia-Location"], "https://github.com/login/oauth")
        self.assertEqual(headers["Vary"], "X-Inertia")
        self.assertEqual(body, b"")

    def test_inertia_internal_redirect_preserves_303(self):
        from catba.runtime import HTTPResult, to_http
        from catba.response import Redirect

        req = Request(
            "POST",
            "/todos",
            headers=Headers({"X-Inertia": "true", "Host": "localhost:8000"}),
        )
        res = HTTPResult(*Redirect("/todos").to_http())
        status, headers, body = to_http(res, request=req)

        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/todos")
        self.assertEqual(headers["Vary"], "X-Inertia")

    def test_inertia_validation_error_422(self):
        from catba.runtime import HTTPResult, to_http
        import json

        req = Request(
            "POST",
            "/register",
            headers=Headers({"X-Inertia": "true"}),
        )
        body = json.dumps({"errors": {"email": "Taken"}}).encode("utf-8")
        res = HTTPResult(status=422, headers={"Content-Type": "application/json"}, body=body)
        status, headers, body_out = to_http(res, request=req)

        self.assertEqual(status, 422)
        self.assertEqual(headers["X-Inertia"], "true")
        self.assertEqual(headers["Vary"], "X-Inertia")
        self.assertEqual(json.loads(body_out)["errors"]["email"], "Taken")


class TestExternalUrl(unittest.TestCase):
    def test_is_external_url(self):
        from catba.inertia import is_external_url
        from catba.context import Request, Headers

        req = Request("GET", "/", headers=Headers({"Host": "catba.dev"}))
        self.assertFalse(is_external_url("/local", req))
        self.assertFalse(is_external_url("http://catba.dev/dashboard", req))
        self.assertTrue(is_external_url("https://other.com/path", req))
        self.assertTrue(is_external_url("//cdn.other.com/file", req))
        self.assertFalse(is_external_url("", req))


if __name__ == "__main__":
    unittest.main()

