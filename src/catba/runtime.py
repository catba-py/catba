"""CatBa core: loads routes, dispatches HTTP methods, interprets results.

The core consumes a :class:`~catba.context.Request` and produces a
:class:`Result` (either :class:`HTTPResult` or :class:`PageData`). The
transport or SSR layer calls :func:`to_http` to serialize a Result into the
``(status, headers, body)`` tuple that goes on the wire. Nothing in route
handlers depends on any transport.
"""

import asyncio
import importlib.util
import inspect
import json
import os
import traceback
from dataclasses import dataclass, field

from catba.context import Context, Request
from catba.response import (
    HTTPError,
    JSON,
    MethodNotAllowed,
    NotFound,
    Redirect,
    Response,
)
from catba.routing import METHODS, Route, RouteTable, discover_routes


@dataclass
class HTTPResult:
    """A direct HTTP response: status, headers, body bytes."""
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""


@dataclass
class PageData:
    """Page data for a page route: the route URL and the handler's props.

    Produced when a page route (has page.tsx) returns a bare dict. The future
    SSR layer consumes this to render page.tsx. Without SSR, to_http
    serializes the props as JSON so the dev transport is usable.
    """
    page_path: str
    props: dict


Result = HTTPResult | PageData


def to_http(result):
    """Serialize a Result into an HTTP tuple (status, headers, body).

    PageData without an SSR layer becomes a JSON response of the props with a
    marker header. When SSR is implemented, the SSR layer intercepts PageData
    before this function is called.
    """
    if isinstance(result, HTTPResult):
        return result.status, dict(result.headers), result.body
    if isinstance(result, PageData):
        body = json.dumps(result.props).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-CatBa-Page": result.page_path,
        }
        return 200, headers, body
    raise TypeError(f"unknown result type: {type(result).__name__}")


def _load_module(route):
    """Import a route.py by filesystem path, cached by module name."""
    spec = importlib.util.spec_from_file_location(route.module_name, route.fs_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _methods_of(module):
    """Return the HTTP methods a route module actually defines."""
    found = []
    for m in METHODS:
        fn = getattr(module, m, None)
        if callable(fn):
            found.append(m)
    return found


class App:
    """The CatBa core. Holds the route table and dispatches requests."""

    def __init__(self, app_dir):
        self.app_dir = app_dir
        self.table = discover_routes(app_dir)
        self._modules = {}

    def _get_module(self, route):
        if route.module_name not in self._modules:
            self._modules[route.module_name] = _load_module(route)
        return self._modules[route.module_name]

    async def handle(self, request):
        """Dispatch a Request, return a Result (HTTPResult or PageData)."""
        route, params = self.table.match(request.path)
        if route is None:
            return _not_found()
        request.params = params
        try:
            module = self._get_module(route)
        except Exception:
            traceback.print_exc()
            return _server_error()
        available = _methods_of(module)
        return await self._dispatch(request, route, module, available)

    async def _dispatch(self, request, route, module, available):
        method = request.method
        if method == "HEAD":
            if "HEAD" in available:
                return await self._invoke(module, request, "HEAD", route)
            if "GET" in available:
                result = await self._invoke(module, request, "GET", route)
                if isinstance(result, HTTPResult):
                    return HTTPResult(result.status, dict(result.headers), b"")
                return result
            return _method_not_allowed(available)
        if method == "OPTIONS":
            if "OPTIONS" in available:
                return await self._invoke(module, request, "OPTIONS", route)
            allow = ",".join(available) if available else ""
            headers = {"Allow": allow} if allow else {}
            return HTTPResult(200, headers, b"")
        if method in available:
            return await self._invoke(module, request, method, route)
        return _method_not_allowed(available)

    async def _invoke(self, module, request, method, route):
        handler = getattr(module, method)
        ctx = Context(request)
        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(ctx)
            else:
                result = handler(ctx)
        except HTTPError as e:
            return _http_error(e)
        except Exception:
            traceback.print_exc()
            return _server_error()
        return _interpret(result, route)


def _interpret(result, route):
    """Turn a handler return value into a Result.

    A bare dict from a page route (has page.tsx) becomes PageData. A bare dict
    from an API route becomes an HTTPResult with a JSON body. Explicit
    Response/JSON/Redirect use their own serialization. None becomes 204.
    """
    if result is None:
        return HTTPResult(204, {}, b"")
    if isinstance(result, Response):
        status, headers, body = result.to_http()
        return HTTPResult(status, headers, body)
    if isinstance(result, JSON):
        status, headers, body = result.to_http()
        return HTTPResult(status, headers, body)
    if isinstance(result, Redirect):
        status, headers, body = result.to_http()
        return HTTPResult(status, headers, body)
    if isinstance(result, dict):
        if route.has_page:
            return PageData(page_path=route.url, props=result)
        return _json_ok(result)
    body = str(result).encode("utf-8")
    return HTTPResult(200, {"Content-Type": "text/plain; charset=utf-8",
                            "Content-Length": str(len(body))}, body)


def _json_ok(data):
    body = json.dumps(data).encode("utf-8")
    return HTTPResult(200, {"Content-Type": "application/json",
                            "Content-Length": str(len(body))}, body)


def _not_found():
    body = b"Not Found"
    return HTTPResult(404, {"Content-Type": "text/plain; charset=utf-8",
                            "Content-Length": str(len(body))}, body)


def _method_not_allowed(available):
    allow = ",".join(available)
    body = b"Method Not Allowed"
    return HTTPResult(405, {"Allow": allow,
                            "Content-Type": "text/plain; charset=utf-8",
                            "Content-Length": str(len(body))}, body)


def _http_error(e):
    body = e.message.encode("utf-8")
    headers = {"Content-Type": "text/plain; charset=utf-8",
               "Content-Length": str(len(body))}
    if isinstance(e, MethodNotAllowed) and e.allowed:
        headers["Allow"] = ",".join(e.allowed)
    return HTTPResult(e.status, headers, body)


def _server_error():
    body = b"Internal Server Error"
    return HTTPResult(500, {"Content-Type": "text/plain; charset=utf-8",
                            "Content-Length": str(len(body))}, body)


def serve_native(app, method, path, raw_headers, raw_body):
    """Single entry point for the native C runtime bridge.

    Takes raw request data from C, parses query string, cookies, and body
    (reusing the same logic as the Python transport), runs the handler, and
    returns ``(status, headers_dict, body_bytes)``. The C bridge calls this
    once per request: one native -> Python -> native crossing.
    """
    from urllib.parse import urlparse, parse_qs
    from catba.context import Headers

    parsed = urlparse(path)
    query = {k: (v[0] if len(v) == 1 else v)
             for k, v in parse_qs(parsed.query).items()}

    headers = Headers(raw_headers)

    # Parse cookies from the Cookie header.
    cookies = {}
    cookie_header = headers.get("Cookie", "")
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if "=" in part:
                name, value = part.split("=", 1)
                cookies[name.strip()] = value.strip()

    # Parse body: JSON, form, or raw bytes.
    body = raw_body if raw_body else b""
    if isinstance(body, str):
        body = body.encode("utf-8")
    ctype = headers.get("Content-Type", "")
    if body and "application/json" in ctype:
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            pass  # keep raw bytes
    elif body and "application/x-www-form-urlencoded" in ctype:
        try:
            text = body.decode("utf-8")
            body = {k: (v[0] if len(v) == 1 else v)
                    for k, v in parse_qs(text).items()}
        except UnicodeDecodeError:
            pass  # keep raw bytes

    request = Request(method, parsed.path, headers=headers, query=query,
                      cookies=cookies, body=body)
    result = asyncio.run(app.handle(request))
    return to_http(result)
