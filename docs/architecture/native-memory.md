# Native Memory Policy

Status: specification. No native runtime exists yet. This document is part
of the architecture, not a testing preference. It fixes the ownership rules
that the future C runtime must follow.

This policy is mandatory. A future native implementation that violates it is
a defect, not an optimization.

## Why this exists

The native runtime is written in C. C has no garbage collector and no
borrow checker. Memory bugs (leaks, use-after-free, double-free, dangling
pointers) are the dominant class of native defects. CatBa is designed so
native code has maximum practical protection against these. The protection
comes from structure, not from discipline: the ownership model makes it
possible to reason about every allocation.

## Ownership principles

1. Every heap allocation has exactly one clearly identifiable owner.
2. Ownership transfer is explicit, never implicit.
3. Every allocation path has a corresponding cleanup path.
4. Error paths release resources exactly like success paths.
5. Request-scoped allocations use a request lifetime strategy, so cleanup
   does not depend on dozens of scattered manual frees.
6. Long-lived allocations have explicit ownership and destruction rules.
7. No hidden ownership.
8. No undocumented borrowed pointers.
9. No silent ownership transfer.
10. No production memory leak is acceptable.
11. Native objects have explicit lifetime rules.
12. Leak detection runs during development and CI wherever practical.
13. Reference counting is avoided unless a concrete ownership problem
    requires it. Simple ownership and deterministic cleanup are preferred
    over clever memory management.

For every important native resource the architecture must answer:

```text
who allocated it
who owns it
when ownership ends
who frees it
```

## Two allocation lifetimes

There are exactly two allocation lifetimes in the native runtime. Every
allocation belongs to one of them.

### Request lifetime (the arena)

A request is short-lived. All memory that exists only to serve one request
is allocated from a per-request arena. The arena is a single owning region.
At request end, the whole arena is released in one step. Individual frees
inside the arena are not needed and not tracked.

What lives in the request arena:

- the parsed request record (method, path, headers, body)
- the captured path parameters
- the response record being assembled
- per-request buffers (parse buffers, scratch space)

The arena is the owner. Nothing inside it is freed individually. When the
request ends, the arena is freed. This is the answer to "where does
request-scoped native memory get cleaned up": one release at request end,
not many.

An error during request handling does not change this. The arena is
released on the error path the same way as the success path. There is no
per-buffer error cleanup.

### Process lifetime (long-lived)

Some allocations outlive every request. Each has a single named owner and
an explicit destruction point.

What is long-lived:

| Resource           | Owner                | Destroyed at        |
|--------------------|----------------------|---------------------|
| server config      | the server object    | shutdown            |
| listener sockets   | the server object    | shutdown            |
| the route table    | the runtime          | shutdown            |
| the compiled page registry | the runtime  | shutdown            |
| a live connection  | the connection list  | connection close    |
| TLS state          | the connection       | connection close    |

Long-lived objects are not reference counted unless a concrete ownership
problem requires it. A connection is owned by the connection list and
destroyed when the list removes it on close. There is one owner.

## Borrowed vs owned pointers

An owned pointer is the one that will be freed. A borrowed pointer is a
non-owning reference into memory that someone else owns and will free.

Borrowed pointers are allowed, but:

- every borrowed pointer is documented as borrowed, and
- it is only valid for as long as the owner has not freed the backing
  memory.

The request record passed to Python is borrowed from the request arena.
Python may read it during the request. When the request ends, the arena
is freed and the borrowed pointers become invalid. The crossing contract
(see below) ensures Python has finished before the arena is released.

## The native/Python crossing

The boundary between native and Python is one crossing per request. This
avoids repeated native -> Python -> native -> Python transitions in the
common request path.

```text
native: parse request, build request record (in the request arena)
   |
   v
crossing: hand the request record to Python (borrowed)
   |
   v
Python: resolve route, run handler, build a result
   |
   v
crossing: receive the result back from Python
   |
   v
native: serialize the response, write to the wire
   |
   v
native: release the request arena (single free)
```

Headers and body are passed as already-parsed structures. The boundary is
not streamed field by field. This keeps the common request path at one
crossing, not many.

## What is native-only

- socket and connection accept
- TLS handshake and state
- HTTP request line and header parsing
- request body framing
- static file serving (reads the file, writes the response, no Python)
- response serialization to the wire
- connection keep-alive management
- graceful shutdown of listeners
- the request arena allocation and release

## What is Python-only

- route dispatch (matching a path to a route module)
- handler execution (the GET/POST/... functions)
- business logic and data access
- page props assembly (building the dict returned to the framework)
- response object construction (Response, JSON, Redirect)
- error mapping (exception type to status code)
- session resolution (application logic)

## What is frontend-only

- React/TSX component rendering
- client hydration
- UI state
- TSX compilation to JS (at build time, by Vite)

The native runtime does not render React. Python does not write to the
socket. The frontend does not call the native runtime directly.

## Exact boundary between native and Python

The boundary is a request record in, a result out:

- In: a parsed request (method, path, headers as a mapping, body,
  captured params). Borrowed from the request arena.
- Out: a result the framework interprets (page props dict, an explicit
  response, JSON, redirect, or an error). Owned by Python until handed
  back, then native serializes it.

Native owns transport and parsing. Python owns behavior. Neither crosses
the boundary more than once per request in the common path.

## Leak detection and CI (future)

Native CI should use appropriate tooling where the platform supports it.
Tools are chosen later based on platform support. None are added in
Phase 1. Candidates, to be evaluated per platform:

```text
AddressSanitizer
LeakSanitizer
UndefinedBehaviorSanitizer
Valgrind
```

A fake or redundant toolchain is not added now. When there is real C code
to build, the toolchain is chosen to match the code and the platform.

## Future native tests

Future C tests should cover the cleanup paths, not just the happy path:

```text
allocation failure paths
error paths
normal cleanup
connection cleanup
request cleanup
buffer cleanup
parser cleanup
shutdown cleanup
```

The arena design makes request cleanup trivial to test: allocate many
things into the arena, end the request, assert the arena is empty. Error
paths are tested by injecting failures and asserting the arena is still
released. This is why the arena exists: cleanup correctness does not
depend on every call site remembering to free.

## Current implementation

No native runtime exists. The `native/` directory is reserved and
documented. No C source, build system, or toolchain is present. This
document fixes the memory policy so the future native implementation can
be evaluated against it.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
