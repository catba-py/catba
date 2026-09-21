# Request Lifecycle

Status: specification. No runtime exists yet. This document defines the
intended request flow.

## Full lifecycle

```text
Browser
   ->
native HTTP runtime        (socket accept, TLS, parse request line + headers)
   ->
CatBa request layer        (build request record, resolve route)
   ->
Python route.py            (run handler, produce a result)
   ->
route result               (page data / HTTP response / JSON / redirect / error)
   ->
page or HTTP response      (render page.tsx, or serialize the response)
   ->
native response layer      (write status, headers, body to the wire)
   ->
Browser
```

The native runtime owns everything up to the request record and everything
from the response record onward. Python owns the middle: route resolution
result, handler execution, and result interpretation.

## The single crossing

There is one native -> Python -> native crossing per request:

1. Native parses the raw request (line, headers, body framing).
2. Native hands a request record to Python.
3. Python resolves the route, runs the handler, and interprets the result.
4. Python hands a response record back to native.
5. Native writes it to the wire.

The crossing is per request. It is not per byte, per header, or per chunk.
Headers and body are passed as already-parsed structures, not streamed
field by field across the boundary.

## Page request

A page route has both `route.py` and `page.tsx`.

```text
GET /users
   ->
native runtime parses request
   ->
Python resolves route -> app/users/route.py GET(ctx)
   ->
handler returns a dict (page props)
   ->
page.tsx rendered with props
   ->
SSR HTML (full load) or Inertia payload (Inertia request)
   ->
native writes response
   ->
Browser
```

For a full page load, the framework renders `page.tsx` to HTML on the
server (SSR) and sends a complete HTML document. The user does not call a
render API. The handler returns props; the framework renders.

## Inertia request

The same route serves an Inertia request. The framework detects an
Inertia request by its headers (the Inertia `X-Inertia-Request` header and
version header). No route code changes between modes.

```text
GET /users   (Inertia request)
   ->
native runtime parses request
   ->
Python resolves route -> app/users/route.py GET(ctx)
   ->
handler returns a dict (page props)
   ->
framework wraps props: component name (from page.tsx) + props
   ->
Inertia-compatible JSON response
   ->
native writes response
   ->
Browser (Inertia client handles it)
```

Inertia is a protocol and runtime capability, not a public page
architecture. The user writes `route.py` + `page.tsx`. The framework
decides whether to produce SSR HTML or an Inertia payload based on the
request. The user never manually switches modes.

## API request

An API route has `route.py` and no `page.tsx`.

```text
GET /api/users
   ->
native runtime parses request
   ->
Python resolves route -> app/api/users/route.py GET(ctx)
   ->
handler returns a dict (interpreted as JSON) or a Response/JSON object
   ->
JSON response (or the explicit response)
   ->
native writes response
   ->
Browser/client
```

A bare dict returned by an API route becomes a JSON response. See
[route-contract.md](route-contract.md) for the return contract.

## Static assets

Static files bypass Python entirely:

```text
GET /assets/app.css
   ->
native runtime resolves the file
   ->
native serves the file directly from disk
   ->
native writes response
   ->
Browser
```

No route resolution, no Python invocation. This keeps static asset traffic
off the Python path.

## Request-scoped lifetime

Everything created for one request lives only for that request:

- the `ctx` object and all its fields
- the request record built by native
- the response record returned to native
- request-scoped native buffers (the request arena)

When the response is written, the request ends. The native runtime
releases the request arena in a single cleanup step. Python drops `ctx`.
Nothing from one request leaks into the next.

See [native-memory.md](native-memory.md) for the ownership and cleanup
rules behind this.

## Error path

If a handler raises an exception, the framework maps it to an error
response (status code, body). The error response follows the same path
back through native as a normal response. Cleanup on the error path is
identical to cleanup on the success path: the request arena is released
and `ctx` is dropped regardless of outcome.

## Current implementation

None of this exists. The CLI surface (`catba dev`, `catba start`) is
defined but reports "not implemented yet". There is no native runtime, no
request layer, and no handler dispatch. This document defines the
contract that future phases implement.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
