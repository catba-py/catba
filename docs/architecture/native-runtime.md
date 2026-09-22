# Native Runtime

Status: implemented (Phase 3). This document describes the native C HTTP
runtime that replaces the Python development transport for `catba start`.

## Responsibilities

The native C runtime owns:

```text
TCP socket
HTTP request parsing
request buffers
connection handling
response serialization
socket writes
connection lifetime
native resources
```

The Python Core continues to own:

```text
project loading
route discovery
route matching
method dispatch
Context
route.py execution
return semantics
HTTPError mapping
PageData
Response / JSON / Redirect
```

## Architecture

```text
Browser / curl
    |
    v
Native C runtime (socket, HTTP parser, serializer)
    |
    v
Python Core (serve_native: route discovery, dispatch, return semantics)
    |
    v
route.py
    |
    v
Python Core (to_http: result interpretation)
    |
    v
Native C runtime (response serialization)
    |
    v
Browser / curl
```

One native -> Python -> native crossing per request. The C runtime does not
duplicate routing, dispatch, or return-interpretation logic.

## Components

| File | Responsibility |
|------|----------------|
| `platform.h` | Socket abstraction (Windows/POSIX) |
| `platform_win.c` | Winsock implementation |
| `platform_posix.c` | POSIX socket implementation |
| `arena.h/c` | Request-scoped memory arena (bump allocator) |
| `http_parser.h/c` | HTTP/1.1 request line, header, body parsing with limits |
| `socket.h/c` | TCP listener, connection, read/write |
| `python_runtime.h/c` | CPython init/finalize, project loading |
| `bridge.h/c` | Native request -> Python Core bridge (serve_native) |
| `serializer.h/c` | cb_response -> HTTP/1.1 wire format |
| `server.h/c` | Request loop: accept, parse, bridge, serialize, cleanup |
| `main.c` | Entry point for `catba-native` executable |

## Two transports

```text
catba dev    -> Python transport (http.server, disposable)
catba start  -> Native C runtime (production path)
```

Both use the same Python Core. The same `route.py` works under both.

## HTTP/1.1 scope

Implemented:

```text
GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
request line, headers, Content-Length, Host, Connection, Cookie, Content-Type
query string, request body
keep-alive within a connection
```

Not implemented:

```text
HTTP/2, HTTP/3, WebSocket, TLS, chunked request decoding, compression,
proxy protocol, multipart upload, upgrade handling
```

## Size limits

```text
max request line:     8192 bytes
max header count:     100
max header block:     65536 bytes
max body size:        10 MB
```

Malformed input produces a controlled 400 or 413 response. The process
never crashes from malformed input.

## Current limitations

- Single-threaded: one connection at a time.
- No TLS.
- No chunked transfer encoding for requests.
- No WebSocket.
- No compression.
- The development transport (`catba dev`) remains the Python http.server.
- Native binaries are not published to PyPI.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
