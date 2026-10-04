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
    ValidationError,
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


def to_http(result, ssr=None, request=None):
    """Serialize a Result into an HTTP tuple (status, headers, body).

    PageData with an SSR worker is rendered to HTML. Without an SSR worker,
    PageData becomes a JSON response of the props with a marker header (the
    pre-SSR dev behavior). HTTPResult is always passed through directly.

    If the request has X-Inertia: true and the result is PageData, an
    Inertia JSON page object is returned instead of HTML.
    """
    if isinstance(result, HTTPResult):
        headers = dict(result.headers)
        if request is not None:
            from catba.inertia import (
                add_vary_inertia,
                inertia_location,
                is_external_url,
                is_inertia_request,
            )
            ctx = Context(request)
            if is_inertia_request(ctx):
                headers = add_vary_inertia(headers)
                if result.status in (301, 302, 303, 307, 308):
                    loc = headers.get("Location", "")
                    if is_external_url(loc, request):
                        return inertia_location(loc)
                elif result.status == 422:
                    headers["X-Inertia"] = "true"
        return result.status, headers, result.body
    if isinstance(result, PageData):
        if request is not None:
            from catba.inertia import is_inertia_request
            ctx = Context(request)
            if is_inertia_request(ctx):
                return _page_data_to_inertia(result, request, ctx, ssr)
        if ssr is not None:
            return _page_data_to_html(result, ssr, request=request)
        body = json.dumps(result.props).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-CatBa-Page": result.page_path,
        }
        return 200, headers, body
    raise TypeError(f"unknown result type: {type(result).__name__}")


def _page_data_to_inertia(page_data, request, ctx, ssr):
    """Convert PageData to an Inertia JSON page object response.

    Checks for version conflicts and partial reloads before building the
    page object. The SSR worker is not invoked for Inertia requests.
    """
    from catba.inertia import (
        build_page_object,
        get_asset_version,
        get_inertia_version,
        get_partial_component,
        get_partial_data,
        get_partial_except,
        filter_partial_props,
        inertia_json_response,
        inertia_version_conflict,
    )

    project_root = getattr(ssr, "project_root", None) if ssr else None
    if project_root is None:
        project_root = getattr(request, "_project_root", None)
    if project_root is None:
        project_root = os.getcwd()

    asset_version = get_asset_version(project_root)

    # Version conflict check (GET only).
    if request.method == "GET":
        client_version = get_inertia_version(ctx)
        if client_version is not None and client_version != asset_version:
            url = request.path
            if request.query:
                from urllib.parse import urlencode
                url = url + "?" + urlencode(request.query, doseq=True)
            return inertia_version_conflict(url, asset_version)

    props = page_data.props

    # Partial reload filtering.
    partial_component = get_partial_component(ctx)
    if partial_component is not None and partial_component == page_data.page_path:
        partial_data = get_partial_data(ctx)
        partial_except = get_partial_except(ctx)
        props = filter_partial_props(props, partial_data, partial_except)

    # Build the URL with query string.
    url = request.path
    if request.query:
        from urllib.parse import urlencode
        url = url + "?" + urlencode(request.query, doseq=True)

    page_object = build_page_object(
        component=page_data.page_path,
        props=props,
        url=url,
        version=asset_version,
    )
    return inertia_json_response(page_object)


def _page_data_to_html(page_data, ssr, request=None):
    """Render PageData through the SSR worker into an HTML HTTP response.

    Calls the SSR worker to render the React component, wraps the HTML
    fragment in a full HTML document with hydration state, and returns
    the HTTP tuple.
    """
    from catba.html import build_document
    from catba.inertia import get_asset_version

    url = page_data.page_path
    if request is not None:
        url = request.path
        if request.query:
            from urllib.parse import urlencode
            url = url + "?" + urlencode(request.query, doseq=True)

    project_root = getattr(ssr, "project_root", None) if ssr else None
    if project_root is None and request is not None:
        project_root = getattr(request, "_project_root", None)
    if project_root is None:
        project_root = os.getcwd()

    version = get_asset_version(project_root)

    try:
        if request is not None:
            html_fragment = ssr.render(page_data.page_path, page_data.props, url=url, version=version)
        else:
            html_fragment = ssr.render(page_data.page_path, page_data.props)
    except Exception as e:
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        body = b"Internal Server Error"
        return 500, {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
        }, body

    head = getattr(ssr, "last_head", None)

    html = build_document(
        page_data.page_path,
        page_data.props,
        html_fragment,
        client_bundle=getattr(ssr, "client_bundle_url", None),
        url=url,
        version=version,
        head=head,
    )
    body = html.encode("utf-8")
    return 200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": str(len(body)),
    }, body


def _load_module(module_name_or_route, fs_path=None):
    """Import a route or layout module by filesystem path."""
    if fs_path is None:
        module_name = module_name_or_route.module_name
        fs_path = module_name_or_route.fs_path
    else:
        module_name = module_name_or_route
    spec = importlib.util.spec_from_file_location(module_name, fs_path)
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

    def __init__(self, app_dir, project_root=None):
        self.app_dir = app_dir
        self.project_root = project_root
        self.table = discover_routes(app_dir)
        self._modules = {}
        self._layout_modules = {}

    def _get_module(self, route):
        if route.module_name not in self._modules:
            self._modules[route.module_name] = _load_module(route)
        return self._modules[route.module_name]

    def _get_layout_module(self, fs_path):
        if fs_path not in self._layout_modules:
            mod_name = "catba_layout_" + str(abs(hash(fs_path)))
            self._layout_modules[fs_path] = _load_module(mod_name, fs_path)
        return self._layout_modules[fs_path]

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
        ctx = Context(request)

        # 1. Run layout before() guards (root to leaf)
        try:
            for layout_path in getattr(route, "layout_paths", []):
                layout_mod = self._get_layout_module(layout_path)
                before_fn = getattr(layout_mod, "before", None)
                if callable(before_fn):
                    if inspect.iscoroutinefunction(before_fn):
                        res = await before_fn(ctx)
                    else:
                        res = before_fn(ctx)
                    if res is not None:
                        return _interpret(res, route)
        except Redirect as r:
            return _interpret(r, route)
        except HTTPError as e:
            return _http_error(e)
        except Exception:
            traceback.print_exc()
            return _server_error()

        # 2. Run layout data fetching for GET / HEAD requests
        layout_props = {}
        if method in ("GET", "HEAD"):
            try:
                for layout_path in getattr(route, "layout_paths", []):
                    layout_mod = self._get_layout_module(layout_path)
                    data_fn = (
                        getattr(layout_mod, "GET", None)
                        or getattr(layout_mod, "get", None)
                        or getattr(layout_mod, "layout", None)
                        or getattr(layout_mod, "data", None)
                    )
                    if callable(data_fn):
                        if inspect.iscoroutinefunction(data_fn):
                            res = await data_fn(ctx)
                        else:
                            res = data_fn(ctx)
                        if isinstance(res, (Response, Redirect, HTTPError)):
                            return _interpret(res, route)
                        if isinstance(res, dict):
                            layout_props.update(res)
            except Redirect as r:
                return _interpret(r, route)
            except HTTPError as e:
                return _http_error(e)
            except Exception:
                traceback.print_exc()
                return _server_error()

        # 3. Run route handler
        handler = getattr(module, method)
        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(ctx)
            else:
                result = handler(ctx)
        except Redirect as r:
            return _interpret(r, route)
        except HTTPError as e:
            return _http_error(e)
        except Exception:
            traceback.print_exc()
            return _server_error()

        # 4. Merge layout props if handler returned a dict
        if isinstance(result, dict) and layout_props:
            result = {**layout_props, **result}

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
    if isinstance(result, HTTPError):
        return _http_error(result)
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
    if isinstance(e, ValidationError) or (isinstance(e, HTTPError) and getattr(e, "errors", None) is not None):
        body = json.dumps({"errors": e.errors}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        return HTTPResult(e.status, headers, body)
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


def serve_native(app, method, path, raw_headers, raw_body, ssr=None):
    """Single entry point for the native C runtime bridge.

    Takes raw request data from C, parses query string, cookies, and body
    (reusing the same logic as the Python transport), runs the handler, and
    returns ``(status, headers, body_bytes)``. The C bridge calls this
    once per request: one native -> Python -> native crossing.

    When ``ssr`` is provided (an SSRWorker), PageData is rendered to HTML.
    Without ``ssr``, PageData falls back to the JSON dev representation.
    """
    from urllib.parse import urlparse, parse_qs
    from catba.context import Headers

    # Serve static assets (client bundle) before route dispatch.
    project_root = getattr(app, "project_root", None)
    if project_root:
        from catba.assets import serve_asset
        asset_resp = serve_asset(path, project_root)
        if asset_resp is not None:
            status, headers_dict, body_bytes = asset_resp
            return status, headers_dict, body_bytes

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
    if ssr is None:
        ssr = getattr(app, "ssr", None)
    return to_http(result, ssr=ssr, request=request)


def prepare_native_ssr(app, app_dir, project_root):
    """Prepare frontend and start SSR worker for the native runtime.

    Called by the C runtime after loading the project. Returns True if SSR
    was prepared, False if no page routes exist. Sets app.ssr on success.
    """
    from catba.pages import has_page_routes
    from catba.routing import discover_routes
    from catba.ssr import SSRWorker
    from catba.frontend import prepare_frontend, FrontendError

    table = discover_routes(app_dir)
    if not has_page_routes(table):
        return False

    try:
        if not prepare_frontend(app_dir, project_root):
            return False
    except FrontendError as e:
        import sys
        print(f"catba: frontend build failed: {e}", file=sys.stderr)
        return False

    try:
        worker = SSRWorker(project_root)
        worker.start()
        app.ssr = worker
        return True
    except Exception as e:
        import sys
        print(f"catba: SSR worker failed to start: {e}", file=sys.stderr)
        return False


def stop_native_ssr(app):
    """Stop the SSR worker if one is running. Called on native shutdown."""
    worker = getattr(app, "ssr", None)
    if worker:
        worker.stop()
        app.ssr = None
