# SSR Architecture

Status: implemented. React TSX SSR is working through both `catba dev` and
`catba start`.

## Overview

```text
HTTP request
  ->
native or Python transport
  ->
Python Core
  ->
route.py
  ->
PageData
  ->
SSR adapter
  ->
React TSX SSR
  ->
HTML
  ->
HTTP response
```

The C runtime is unaware of React, TSX, or SSR. It only sees the final HTTP
response from the Python layer.

## Components

| Module | Responsibility |
|--------|----------------|
| `pages.py` | Page module discovery (reuses route table) |
| `manifest.py` | Generate manifest.json, ssr-entry.js, client-entry.js |
| `frontend.py` | Node detection, npm install, Vite SSR/client builds |
| `ssr.py` | Persistent Node SSR worker (newline-delimited JSON protocol) |
| `ssr-worker.mjs` | Node script that loads the SSR bundle and renders |
| `html.py` | HTML document shell with safe hydration state |
| `assets.py` | Static asset serving for client bundles |

## SSR worker

A persistent Node process that loads the Vite-built SSR bundle and renders
React pages on request. The protocol is newline-delimited JSON:

```text
Request:  {"id": 1, "page": "/", "props": {...}}
Response: {"id": 1, "html": "..."}
Error:    {"id": 1, "error": "..."}
```

Python owns the worker process:

- who starts it: `SSRWorker.start()`
- who owns it: the `SSRWorker` instance
- who writes to it: `SSRWorker.render()` writes to `proc.stdin`
- who reads from it: `SSRWorker.render()` reads from `proc.stdout`
- who terminates it: `SSRWorker.stop()`
- when it terminates: on shutdown, on error, on worker crash

No Python request objects cross the boundary. Only JSON-serializable props
are sent. Once a request completes, Python request objects are eligible
for cleanup immediately.

## PageData to props flow

```text
route.py GET(ctx) returns dict
  ->
Python Core: PageData(page_path, props)
  ->
to_http(result, ssr=worker)
  ->
ssr.render(page_path, props)
  ->
Node: React renderToString
  ->
HTML fragment
  ->
html.build_document(page_path, props, fragment)
  ->
Full HTML document with hydration state
```

## What bypasses SSR

Only `PageData` enters SSR. All other result types pass through directly:

- `HTTPResult` (from `Response`, `JSON`, `Redirect`, errors) bypasses SSR
- API route bare dicts (no `page.tsx`) produce JSON, never HTML
- Explicit `JSON(...)` from a page route returns JSON, not HTML

## Error handling

- React rendering error: 500 Internal Server Error
- Node worker crash: 500 for current request, worker may restart
- No React stack traces in the response body
- Node process is terminated cleanly on shutdown (no orphans)

## Current limitations

- Single-threaded SSR worker (one render at a time)
- No streaming SSR
- No HMR in development
- No Inertia
- No SPA navigation
- No production packaging
- No React Server Components

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
