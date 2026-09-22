# Inertia Protocol

Status: implemented (Phase 5). CatBa speaks the standard Inertia protocol
while preserving the existing CatBa programming model.

## What Inertia changes

The user still writes:

```python
async def GET(ctx):
    return {"users": users}
```

They do not write `Inertia.render(...)` or `Inertia.page(...)`. The
filesystem still determines the page component. The server still owns
routing and data fetching.

Inertia changes how a page response is transported after the client has
booted. A normal request returns SSR HTML. An Inertia request (detected
by `X-Inertia: true`) returns a JSON page object instead of HTML.

## Request detection

An Inertia request is detected by the `X-Inertia` header:

```http
X-Inertia: true
```

The check is case-insensitive on the header name. The value `true` is
accepted case-insensitively. No other signal (User-Agent, Accept, URL
parameters, cookies) is used to detect Inertia.

Helper: `catba.inertia.is_inertia_request(ctx)`.

## Page object

Every page route produces an Inertia page object:

```json
{
    "component": "/users/[id]",
    "props": {
        "id": "42"
    },
    "url": "/users/42",
    "version": "..."
}
```

- `component`: the stable page identifier from the route table (e.g.
  `/`, `/users`, `/users/[id]`). Not a filesystem path or random ID.
- `props`: the dict returned by the route handler. Must be
  JSON-serializable.
- `url`: the current request URL including query string.
- `version`: the deterministic asset version (see below).

## Full page request

A request without `X-Inertia: true` returns SSR HTML as before. The HTML
contains the Inertia page object in a `<script type="application/json"
data-page>` element so the official React adapter can boot.

## Inertia JSON request

A request with `X-Inertia: true` returns:

```text
200 OK
Content-Type: application/json
X-Inertia: true
Vary: X-Inertia
```

with the page object as JSON. React SSR is not invoked for Inertia
requests. The SSR worker is not touched.

## Response headers

A valid Inertia page response includes:

```http
X-Inertia: true
Vary: X-Inertia
Content-Type: application/json
```

The `Vary` header preserves existing values if set by other layers.

## Asset version

The asset version is a deterministic hash derived from the generated
frontend build metadata. It is stable across requests for the same build
and changes when the frontend assets change.

The version does not use timestamps, random values, process IDs, or
machine-specific paths.

## Version mismatch

For a page route and an Inertia GET request:

If the client version (from `X-Inertia-Version`) does not match the
current server asset version, the response is:

```text
409 Conflict
X-Inertia-Location: <current requested URL>
X-Inertia-Version: <current server version>
Vary: X-Inertia
```

This tells the Inertia client to perform a full page reload. React is not
rendered. The page component is not executed.

Version checking happens before page rendering.

## Partial reloads

Partial reloads use:

```http
X-Inertia-Partial-Component: /users
X-Inertia-Partial-Data: users,stats
```

A partial request is valid only when the requested component matches the
currently resolved page component. The response contains only the
requested props.

`X-Inertia-Partial-Except` excludes the listed props from the response.

The server filters the resulting props. Future lazy/deferred evaluation
is a separate optimization.

## Redirects

CatBa's `Redirect(...)` default of 303 is preserved. Inertia requests
receive redirects compatible with the Inertia client. No global redirect
semantics are changed.

## API routes

API routes (no `page.tsx`) remain API routes. A bare dict from an API
route returns JSON regardless of `X-Inertia`. Inertia applies only to
page routes.

## Explicit responses

`Response(...)`, `JSON(...)`, and `Redirect(...)` bypass Inertia. Only
`PageData` (a bare dict from a page route) is transformed into an Inertia
page object.

## C/Python boundary

The C runtime does not implement Inertia semantics. All Inertia logic
lives in the Python layer. The C runtime receives an ordinary HTTP
result and serializes it. The single C/Python crossing is preserved.

## Current limitations

Implemented:
- Base Inertia protocol
- Initial React adapter boot
- Asset version
- Partial prop filtering
- Version conflict (409)

Not implemented:
- Client navigation (Link, router.visit)
- Forms
- Validation UX
- Prefetching
- Polling
- Deferred props
- Infinite scrolling
- Shared props system

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
