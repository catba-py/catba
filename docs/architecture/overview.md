# CatBa Architecture Overview

Status: specification. The runtime is not implemented. This document
describes the intended architecture, not a working one.

## What CatBa is

CatBa is a Python web framework and runtime. Python is the primary
application language. User application logic is written in Python. There is
no second Python-like language.

The application model uses two files per page:

```text
route.py  -> server behavior and data
page.tsx  -> React UI
```

`route.py` is the server boundary. `page.tsx` is the UI boundary. Their
responsibilities are strictly separated.

## Three layers

```text
                CATBA
                  |
        +---------+---------+
        |                   |
   Native runtime       Python layer
        |                   |
    HTTP/socket           route.py
    TLS/static               |
    connection               |
    transport              data
        |                   |
        +---------+---------+
                  |
               frontend
                  |
               page.tsx
```

The native runtime owns transport and low-level web infrastructure. Python
owns application behavior. React/TSX owns UI.

Application logic is not moved into C for speed. Web transport is not moved
into Python because Python makes it easier. The boundary is explicit.

### Native runtime (future)

Written in C. Owns:

- socket and connection accept
- TLS
- HTTP request parsing (request line, headers, body framing)
- static file serving
- response serialization to the wire
- connection keep-alive and lifecycle
- graceful shutdown of listeners

### Python layer

Owns:

- route dispatch
- handler execution (business logic, data access)
- page props assembly
- response object construction (Response, JSON, Redirect)
- error mapping
- session resolution (application logic)

### Frontend

Owns:

- React/TSX component rendering
- client hydration
- UI state

## The native/Python crossing

There is one crossing per request: the native runtime builds a request
record from the parsed request, hands it to Python once, Python runs the
route handler and returns a result, and the native runtime writes the
response. The crossing is per request, not per byte or per header.

Static files and assets bypass Python entirely. The native runtime serves
them without invoking Python.

See [native-memory.md](native-memory.md) for the ownership rules behind the
crossing, and [request-lifecycle.md](request-lifecycle.md) for the full
request flow.

## Standard Python packaging

`pyproject.toml` is the canonical project metadata and dependency source.
CatBa uses existing Python packaging standards wherever they solve the
problem. There is no `catba.toml`, `catba.lock`, `requirements.txt`, or any
parallel dependency format.

`catba install` means: install dependencies declared by `pyproject.toml`.
It is not a package manager and does not support `catba install <package>`.

## Page model

A normal user-facing page requires both files:

```text
route.py  +  page.tsx
```

`route.py` without `page.tsx` is an API route (a server endpoint).
`page.tsx` without `route.py` is an invalid structure. The filesystem is
the route model. See [routing.md](routing.md) and
[page-contract.md](page-contract.md).

## Current implementation

What exists today:

- the `catba` Python package (installable, on PyPI as 0.1.0)
- the CLI surface (`create`, `dev`, `build`, `start`, `install`), all
  reporting "not implemented yet"
- the project template (`templates/app/`)
- the `.catba/` bootstrap area (reserved)
- the `native/` directory (reserved)
- tests and CI/release pipeline

What does not exist yet:

- the native C runtime
- the C/Python bridge
- the filesystem router
- the React/TSX compiler
- Vite integration
- the SSR engine
- the Inertia protocol integration
- any runtime, server, or request handling

## Key principles

1. Python first. Application logic is Python.
2. Standard Python packaging. No parallel formats.
3. Two files per page: `route.py` (server) and `page.tsx` (UI).
4. The filesystem is the route model.
5. `route.py` is the server boundary. Methods are plain functions named
   after HTTP verbs.
6. `page.tsx` is the UI boundary. It receives props from `route.py`. The
   user does not call a render API.
7. The return value of a handler determines the response category. The
   framework interprets it; the user does not pick a renderer per page.
8. The native runtime owns transport. Python owns behavior. The boundary is
   one crossing per request.
9. Native memory has explicit ownership. No casual allocation. See
   [native-memory.md](native-memory.md).

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
