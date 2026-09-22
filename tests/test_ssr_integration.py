"""Tests for PageData SSR integration and HTML document building."""

import json
import unittest
from unittest.mock import MagicMock

from catba.html import _safe_script_json, build_document
from catba.runtime import HTTPResult, PageData, to_http


class TestToHttpWithSSR(unittest.TestCase):
    def test_http_result_passes_through(self):
        result = HTTPResult(200, {"Content-Type": "text/plain"}, b"hello")
        status, headers, body = to_http(result, ssr=MagicMock())
        self.assertEqual(status, 200)
        self.assertEqual(body, b"hello")

    def test_page_data_with_ssr_renders_html(self):
        mock_ssr = MagicMock()
        mock_ssr.render.return_value = "<h1>Hello</h1>"
        result = PageData(page_path="/", props={"message": "Hello"})
        status, headers, body = to_http(result, ssr=mock_ssr)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        html = body.decode("utf-8")
        self.assertIn("<h1>Hello</h1>", html)
        self.assertIn("catba-root", html)
        self.assertIn("data-catba-page", html)
        mock_ssr.render.assert_called_once_with("/", {"message": "Hello"})

    def test_page_data_without_ssr_returns_json(self):
        result = PageData(page_path="/", props={"message": "Hello"})
        status, headers, body = to_http(result)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-CatBa-Page"], "/")
        self.assertEqual(json.loads(body), {"message": "Hello"})

    def test_ssr_error_returns_500(self):
        mock_ssr = MagicMock()
        mock_ssr.render.side_effect = Exception("render failed")
        result = PageData(page_path="/", props={"message": "Hello"})
        status, headers, body = to_http(result, ssr=mock_ssr)
        self.assertEqual(status, 500)
        self.assertEqual(body, b"Internal Server Error")


class TestHtmlDocument(unittest.TestCase):
    def test_contains_doctype_and_html(self):
        html = build_document("/", {}, "<div>test</div>")
        self.assertIn("<!doctype html>", html)
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)

    def test_contains_root_div_with_page_id(self):
        html = build_document("/users", {}, "<span>x</span>")
        self.assertIn('id="catba-root"', html)
        self.assertIn('data-catba-page="/users"', html)
        self.assertIn("<span>x</span>", html)

    def test_contains_props_script(self):
        html = build_document("/", {"msg": "hi"}, "<p>ok</p>")
        self.assertIn('id="catba-props"', html)
        self.assertIn('"msg"', html)
        self.assertIn("hi", html)

    def test_client_bundle_script(self):
        html = build_document("/", {}, "<div></div>", client_bundle="/assets/main.js")
        self.assertIn('<script type="module" src="/assets/main.js">', html)

    def test_no_client_bundle(self):
        html = build_document("/", {}, "<div></div>")
        self.assertNotIn('type="module"', html)


class TestScriptSafety(unittest.TestCase):
    def test_script_closing_tag_escaped(self):
        safe = _safe_script_json({"x": "</script><script>alert(1)"})
        # The < in </script> should be escaped to \u003c
        self.assertNotIn("</script>", safe)
        self.assertIn("\\u003c", safe)

    def test_normal_props_preserved(self):
        safe = _safe_script_json({"message": "Hello"})
        data = json.loads(safe)
        self.assertEqual(data, {"message": "Hello"})

    def test_unicode_preserved(self):
        safe = _safe_script_json({"name": "Xin Chao"})
        data = json.loads(safe)
        self.assertEqual(data["name"], "Xin Chao")

    def test_html_sensitive_characters(self):
        safe = _safe_script_json({"html": "<b>bold</b>&"})
        data = json.loads(safe)
        self.assertEqual(data["html"], "<b>bold</b>&")
        # The raw string should not contain unescaped <
        self.assertNotIn("<b>", safe)


if __name__ == "__main__":
    unittest.main()
