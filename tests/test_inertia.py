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


if __name__ == "__main__":
    unittest.main()
