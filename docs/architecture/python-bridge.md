# Python Bridge

Status: implemented (Phase 3). This document describes the native-to-Python
Core bridge.

## Responsibility

The bridge converts a parsed native request into a call to the Python Core's
`serve_native` function, and unpacks the result into a native response. It is
the single crossing point between native and Python per request.

```text
native request (cb_request)
    |
    v
bridge: build Python args (method, path, headers dict, body bytes)
    |
    v
Python Core: serve_native(app, method, path, headers, body)
    |
    v
Python Core: app.handle(request) -> Result
    |
    v
Python Core: to_http(result) -> (status, headers, body)
    |
    v
bridge: unpack tuple into cb_response (arena-owned strings)
    |
    v
native serializer
```

## serve_native

The Python entry point (`catba.runtime.serve_native`) takes raw request data
from C and returns a `(status, headers_dict, body_bytes)` tuple. It reuses the
same query string parsing, cookie parsing, and body parsing logic as the
Python transport, ensuring semantic compatibility.

The C bridge calls this function once per request. No routing, dispatch, or
return-interpretation logic lives in C.

## CPython reference ownership

Every `PyObject *` in the bridge has an explicit ownership classification:

- **owned** (new reference): must be `Py_DECREF`'d when no longer needed.
  - `mod`, `serve`, `method_str`, `path_str`, `headers_dict`, `body_bytes`,
    `result`
- **borrowed** (valid while the owner is alive): do not `Py_DECREF`.
  - `status_obj`, `headers_obj`, `body_obj` (borrowed from `result`)
  - `key`, `value` in `PyDict_Next` (borrowed from `headers_obj`)
- The `ctx->app`, `ctx->handle`, `ctx->to_http` are owned by `cb_python_ctx`
  and released on `cb_python_finalize`.

All temporary owned references are released at a single `cleanup:` label
before returning. No reference leaks on any code path.

## GIL

The bridge acquires the GIL via `PyGILState_Ensure()` on entry and releases
it via `PyGILState_Release()` on exit. This is safe whether the calling
thread already holds the GIL (main thread in single-threaded mode) or not
(background thread in tests).

The `serve_native` call runs Python code (route discovery, dispatch, handler
execution, return interpretation) under the GIL.

## Error handling

If any CPython API call fails:

1. The exception is printed to stderr (for development).
2. All owned references are released.
3. The GIL is released.
4. The response is filled with a 500 Internal Server Error.
5. The function returns 0 (success with a 500 response, not a C error).

A Python exception never leaves the interpreter in an undefined state.

## What the bridge does NOT do

- Routing (path matching is in the Python Core)
- HTTP method dispatch (in the Python Core)
- Return value interpretation (in the Python Core)
- Socket I/O (in the socket transport)
- HTTP parsing (in the HTTP parser)

The bridge is deliberately narrow: convert, call, unpack.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
