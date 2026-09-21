import json
import unittest

from catba import (
    BadRequest,
    HTTPError,
    InternalServerError,
    JSON,
    MethodNotAllowed,
    NotFound,
    Redirect,
    Response,
)


class TestResponse(unittest.TestCase):
    def test_basic(self):
        status, headers, body = Response("Hello", status=200, headers={"X-CatBa": "1"}).to_http()
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-CatBa"], "1")
        self.assertEqual(body, b"Hello")
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(headers["Content-Length"], "5")

    def test_bytes_body(self):
        _, headers, body = Response(b"\x00\x01").to_http()
        self.assertEqual(body, b"\x00\x01")
        self.assertEqual(headers["Content-Length"], "2")

    def test_custom_content_type_not_overridden(self):
        _, headers, _ = Response("x", headers={"Content-Type": "text/html"}).to_http()
        self.assertEqual(headers["Content-Type"], "text/html")


class TestJSON(unittest.TestCase):
    def test_serializes(self):
        status, headers, body = JSON({"ok": True}, status=201).to_http()
        self.assertEqual(status, 201)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(body), {"ok": True})

    def test_custom_headers_kept(self):
        _, headers, _ = JSON({"a": 1}, headers={"X-T": "1"}).to_http()
        self.assertEqual(headers["X-T"], "1")


class TestRedirect(unittest.TestCase):
    def test_default_303(self):
        status, headers, body = Redirect("/login").to_http()
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/login")
        self.assertEqual(body, b"")

    def test_custom_status(self):
        status, _, _ = Redirect("/login", status=302).to_http()
        self.assertEqual(status, 302)


class TestErrors(unittest.TestCase):
    def test_not_found(self):
        e = NotFound("User not found")
        self.assertEqual(e.status, 404)
        self.assertEqual(e.message, "User not found")
        self.assertIsInstance(e, HTTPError)

    def test_method_not_allowed_carries_allowed(self):
        e = MethodNotAllowed(allowed=["GET", "POST"])
        self.assertEqual(e.status, 405)
        self.assertEqual(e.allowed, ["GET", "POST"])

    def test_bad_request_default(self):
        self.assertEqual(BadRequest().status, 400)

    def test_internal_server_error_default(self):
        self.assertEqual(InternalServerError().status, 500)


if __name__ == "__main__":
    unittest.main()
