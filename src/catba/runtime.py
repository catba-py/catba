"""CatBa core: loads routes, dispatches HTTP methods, interprets results.

The core consumes a :class:`~catba.context.Request` and produces an HTTP
response tuple ``(status, headers, body_bytes)``. The transport layer is a
thin adapter that parses raw HTTP into a Request and serializes the tuple
back to the wire. Nothing in route handlers depends on any transport.
"""

import asyncio
import importlib.util
import json
import os
import traceback

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
        """Dispatch a Request to a route handler, return (status, headers, body)."""
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
        # HEAD: prefer an explicit HEAD handler, fall back to GET with no body.
        if method == "HEAD":
            if "HEAD" in available:
                return await self._invoke(module, request, "HEAD", route)
            if "GET" in available:
                status, headers, body = await self._invoke(module, request, "GET", route)
                return status, headers, b""
            return _method_not_allowed(available)
        # OPTIONS: prefer an explicit handler, else advertise available methods.
        if method == "OPTIONS":
            if "OPTIONS" in available:
                return await self._invoke(module, request, "OPTIONS", route)
            allow = ",".join(available) if available else ""
            headers = {"Allow": allow} if allow else {}
            return 200, headers, b""
        if method in available:
            return await self._invoke(module, request, method, route)
        return _method_not_allowed(available)

    async def _invoke(self, module, request, method, route):
        handler = getattr(module, method)
        ctx = Context(request)
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(ctx)
            else:
                result = handler(ctx)
        except HTTPError as e:
            return _http_error(e)
        except Exception:
            traceback.print_exc()
            return _server_error()
        return _interpret(result, route)


# --- return interpretation ------------------------------------------------

def _interpret(result, route):
    """Turn a handler return value into an HTTP tuple (status, headers, body).

    Minimal interpretation: bare dict becomes JSON, Response/JSON/Redirect use
    their own serialization, None becomes 204. The page-data vs JSON
    distinction (based on has_page) is refined later.
    """
    if result is None:
        return 204, {}, b""
    if isinstance(result, Response):
        return result.to_http()
    if isinstance(result, JSON):
        return result.to_http()
    if isinstance(result, Redirect):
        return result.to_http()
    if isinstance(result, dict):
        body = json.dumps(result).encode("utf-8")
        return 200, {"Content-Type": "application/json", "Content-Length": str(len(body))}, body
    # Fallback: stringify.
    body = str(result).encode("utf-8")
    return 200, {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body))}, body


# --- error responses -----------------------------------------------------

def _not_found():
    body = b"Not Found"
    return 404, {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body))}, body


def _method_not_allowed(available):
    allow = ",".join(available)
    body = b"Method Not Allowed"
    headers = {
        "Allow": allow,
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(body)),
    }
    return 405, headers, body


def _http_error(e):
    body = e.message.encode("utf-8")
    headers = {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body))}
    if isinstance(e, MethodNotAllowed) and e.allowed:
        headers["Allow"] = ",".join(e.allowed)
    return e.status, headers, body


def _server_error():
    body = b"Internal Server Error"
    return 500, {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body))}, body
