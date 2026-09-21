# Route Contract

Status: specification. No router or runtime exists yet. This document
defines the contract that `route.py` files will follow.

## Server boundary

`route.py` is the server boundary. It declares HTTP methods as plain
functions named after HTTP verbs:

```python
async def GET(ctx):
    return {"users": users}

async def POST(ctx):
    return Redirect("/users")

async def PUT(ctx):
    ...

async def DELETE(ctx):
    ...
```

Decorators are not required to mark HTTP methods. The function name is the
method. The router discovers exported functions whose names match HTTP
verbs.

## Method discovery

The router looks for module-level functions in `route.py` named after
HTTP methods. Recognized names:

```text
GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
```

Case matters: the names are uppercase. A function named `get` (lowercase)
is not a handler. Only the exact verb names are matched; everything else in
the module is ignored by the router.

## ctx is mandatory

Every handler takes exactly one argument: `ctx`. There is no second
optional argument and no global. `ctx` is the request context. See
[Context fields](#context-fields) below.

## Sync and async handlers

Both are supported:

```python
async def GET(ctx):      # awaited by the runtime
    ...

def GET(ctx):            # called directly
    ...
```

The runtime detects whether the handler is a coroutine function. `async
def` handlers are awaited. Plain `def` handlers are called directly. The
runtime does not force one style. Async is the preferred form for I/O
bound handlers.

`ctx` is the same object either way. A sync handler receives the same
parsed request as an async handler.

## Missing methods

If a request uses a method that the route's `route.py` does not define,
the framework returns `405 Method Not Allowed`. The `Allow` response
header lists the methods the route does define.

Example: `route.py` defines `GET` and `POST`. A `DELETE` request to that
route returns `405` with `Allow: GET, POST`.

## Return contract

The return value of a handler determines the response. The framework
interprets the value. The user does not select a renderer for every page.

There are five conceptual response categories:

```text
Page Data        a bare dict/mapping
HTTP Response    a Response object (explicit status, headers, body)
JSON Response    a JSON object, or a bare dict from an API route
Redirect         a Redirect object
Error Response   a raised exception, or an error object
```

### Page Data

A bare dict (or mapping) returned by a page route becomes the page props.
The framework renders the route's `page.tsx` with those props.

```python
async def GET(ctx):
    return {"users": users}     # page props -> page.tsx
```

Whether a bare dict is "page data" or "JSON" depends on the route
structure, not the return type:

- A page route (has `page.tsx`): bare dict = page data -> page.tsx.
- An API route (no `page.tsx`): bare dict = JSON response body.

This is the key rule: the route's file structure determines how a bare
dict is interpreted. The user returns data; the framework knows what it
means.

### HTTP Response

A `Response` object is an explicit HTTP response: status, headers, body.
It bypasses page rendering.

```python
async def GET(ctx):
    return Response(status=200, headers={"X-Custom": "1"}, body=b"...")
```

A `Response` works the same for page routes and API routes. It always
means "send exactly this to the client, do not render a page."

### JSON Response

A `JSON` object is an explicit JSON response. It is independent of the
route structure.

```python
async def GET(ctx):
    return JSON({"users": users})
```

For an API route, a bare dict already means JSON, so `JSON(...)` is only
needed when the route is a page route but you want to return JSON
instead of rendering the page.

### Redirect

A `Redirect` object is a redirect response.

```python
async def POST(ctx):
    return Redirect("/users", status=303)
```

The default redirect status is `303 See Other`, which is correct for the
POST -> GET redirect pattern. An explicit status may be given.

### Error Response

Errors are raised, not returned. An exception with an associated HTTP
status becomes that status response. Unhandled exceptions become `500`.

```python
async def GET(ctx):
    raise NotFound()            # -> 404
    raise BadRequest("no id")   # -> 400
```

The framework maps exception types to status codes. A handler should
raise a typed error, not return a manually built error response.

### Return value summary

| Return value            | Page route (has page.tsx) | API route (no page.tsx) |
|-------------------------|---------------------------|--------------------------|
| bare dict / mapping     | page props -> page.tsx    | JSON response body       |
| `Response(...)`         | explicit HTTP response    | explicit HTTP response   |
| `JSON(...)`             | explicit JSON response    | explicit JSON response   |
| `Redirect(...)`         | redirect                  | redirect                 |
| exception raised        | error response (mapped)  | error response (mapped)  |
| `None`                  | 204 No Content            | 204 No Content           |

## Context fields

`ctx` is request-scoped. It is created when the request starts and
released when the request ends. Every field has a concrete purpose in
the request lifecycle.

```python
ctx.request    # the request: method, path, http_version
ctx.headers    # request headers, case-insensitive mapping
ctx.cookies    # request cookies, mapping of name -> value
ctx.query      # parsed query parameters, mapping of key -> value
ctx.params     # path parameters from dynamic segments, mapping
ctx.body       # parsed request body (JSON dict, form dict, or raw bytes)
ctx.session    # session handle (only when sessions are configured)
ctx.state      # request-scoped mutable state (middleware/handler chaining)
```

Each field:

- `ctx.request`: identifies what was asked. Method, path, and HTTP
  version. Needed to route and to make method-dependent decisions.
- `ctx.headers`: request headers. Case-insensitive so handlers do not
  break on header casing differences. Needed for content negotiation,
  Inertia detection, auth headers.
- `ctx.cookies`: request cookies. Needed for session identifiers and
  user preferences. Reading is on `ctx`; writing is on the response.
- `ctx.query`: parsed query string. Needed because query parameters are
  part of the request URL and drive filtering, pagination, and search.
- `ctx.params`: path parameters from dynamic segments like `[id]`.
  Needed because the route matched a pattern and the captured values
  must reach the handler.
- `ctx.body`: parsed request body. JSON is parsed to a dict, form data to
  a dict, raw otherwise. Needed for `POST`/`PUT`/`PATCH` payloads.
- `ctx.session`: session handle. Present only when sessions are
  configured. Needed for authenticated request state across requests.
- `ctx.state`: request-scoped mutable bag for middleware and handlers to
  share data within one request without globals. It dies with the
  request.

## Lifetime of ctx

`ctx` is request-scoped. It is created at the start of request
processing and released at the end. It does not persist across requests.
It must not be stored on a long-lived object. The native request arena
backs the request-scoped fields; both are released together at request
end. See [native-memory.md](native-memory.md).

## What is guaranteed to be request-scoped

- `ctx` and every field above
- the request record built by native
- the response record returned to native
- request-scoped native buffers (the request arena)
- `ctx.state`

None of these survive past the request. Storing a reference to `ctx` on
a module-level or long-lived object is a bug.

## Current implementation

None of this exists. The marker types (`Response`, `JSON`, `Redirect`,
error types) are not yet defined in code. This document fixes their
conceptual contract so Phase 2 can implement them without redesigning
the return model.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
