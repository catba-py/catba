"""Python development transport.

A thin adapter over the standard library ``http.server`` that parses raw
HTTP into a :class:`~catba.context.Request`, invokes the CatBa core, and
writes the resulting ``(status, headers, body)`` tuple back to the client.

This is intentionally disposable. The future native C runtime will replace it
without touching route.py, the router, ctx, or return semantics. No routing
or application logic lives here.
"""

import asyncio
import json as _json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from catba.context import Headers, Request
from catba.runtime import App, to_http


def _parse_body(headers, raw):
    """Decode a raw request body: JSON dict, form dict, or raw bytes."""
    ctype = headers.get("Content-Type", "")
    if not raw:
        return b""
    if "application/json" in ctype:
        try:
            return _json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return raw
    if "application/x-www-form-urlencoded" in ctype:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw
        return {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(text).items()}
    return raw


def _parse_cookies(headers):
    """Parse a Cookie header into a name -> value mapping."""
    raw = headers.get("Cookie", "")
    if not raw:
        return {}
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


def _make_request(method, path, headers, raw_body):
    parsed = urlparse(path)
    query = {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(parsed.query).items()}
    h = Headers({k: v for k, v in headers.items()})
    body = _parse_body(h, raw_body)
    cookies = _parse_cookies(h)
    return Request(method, parsed.path, headers=h, query=query, cookies=cookies, body=body)


class _Handler(BaseHTTPRequestHandler):
    # quiet logging in tests
    def log_message(self, *args, **kwargs):
        pass

    def _serve(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        req = _make_request(self.command, self.path, dict(self.headers), raw)
        ssr = getattr(self.server, "ssr", None)
        status, headers, body = to_http(asyncio.run(self.server.app.handle(req)), ssr=ssr)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self): self._serve()
    def do_POST(self): self._serve()
    def do_PUT(self): self._serve()
    def do_PATCH(self): self._serve()
    def do_DELETE(self): self._serve()
    def do_HEAD(self): self._serve()
    def do_OPTIONS(self): self._serve()


class DevServer:
    """Runs the core behind an http.server. Disposable; replaced by native later."""

    def __init__(self, app, host="127.0.0.1", port=8000, ssr=None):
        self.app = app
        self.host = host
        self.port = port
        self.ssr = ssr

    def serve(self):
        server = ThreadingHTTPServer((self.host, self.port), _Handler)
        server.app = self.app
        server.ssr = self.ssr
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
