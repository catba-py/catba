# Routing Model

Status: specification. No router exists yet. This document defines the
intended filesystem routing semantics.

## The filesystem is the route model

A CatBa application is a directory tree. Each directory with a `route.py`
is a route. The URL is derived from the directory path. There is no
central route table to register.

```text
app/
├── route.py          -> /
├── page.tsx
├── users/
│   ├── route.py      -> /users
│   └── page.tsx
└── users/
    └── [id]/
        ├── route.py  -> /users/[id]
        └── page.tsx
```

`app/` is the route root. The URL of a route is its path relative to
`app/`, with `route.py` stripped.

## Static routes

A directory whose name is a literal segment matches that segment exactly.

```text
app/users/route.py        -> /users
app/api/users/route.py    -> /api/users
```

## Dynamic segments

A directory named `[name]` matches any single path segment and captures
it as a path parameter named `name`.

```text
app/users/[id]/route.py   -> /users/[id]
```

A request to `/users/42` matches this route and sets `ctx.params["id"]`
to `"42"`.

Dynamic path parameters are represented as a string mapping on
`ctx.params`. The key is the name inside the brackets (without the
brackets). The value is the matched URL segment, as a string. The
handler is responsible for converting it to another type if needed.

Rules:

- `[id]` captures one segment. It does not match across `/`.
- The captured value is always a string in `ctx.params`.
- A segment matches at most one dynamic parameter.

## Nested routes

Routes nest by directory nesting. There is no explicit nesting
declaration. A parent route and a child route are independent routes at
different paths:

```text
app/users/route.py        -> /users
app/users/[id]/route.py   -> /users/[id]
```

`/users` and `/users/42` are separate routes. Each has its own
`route.py` and its own handlers. One does not wrap or call the other by
default.

## Page route vs API route

The distinction is the presence of `page.tsx`, not a separate file type
or config flag. See [page-contract.md](page-contract.md):

| Files in the directory    | Route type | URL behavior                  |
|--------------------------|------------|-------------------------------|
| `route.py` + `page.tsx`  | page route | can render a page or return a response |
| `route.py` only          | API route  | returns HTTP/JSON, never a page |
| `page.tsx` only          | invalid    | rejected by build/dev validation |

There is no `server.py`, `controller.py`, or `view.py`. The two files
are the whole page model.

## Route resolution

Given a request path, the router:

1. Splits the path into segments.
2. Walks the `app/` tree, matching each segment against directory names.
3. A literal directory name matches only that segment.
4. A `[name]` directory matches any segment and captures it.
5. The matched directory must contain `route.py`.
6. The captured parameters populate `ctx.params`.

If no directory matches, the response is `404 Not Found`.

## Matching precedence

When multiple patterns could match, static segments take precedence over
dynamic segments. A request to `/users/me` matches a literal
`app/users/me/route.py` before it matches `app/users/[id]/route.py`.

Ambiguity (two dynamic segments at the same position, such as
`[id]` vs `[slug]` in sibling directories) is a build error. The
validation step rejects it. There is no priority among dynamic
parameters; they must not compete.

## Validation

The intended `catba dev` and `catba build` commands validate the route
tree before running:

- A `page.tsx` with no sibling `route.py` is an error.
- Conflicting dynamic segments at the same position are an error.
- A `route.py` that defines no recognized HTTP methods is a warning (the
  route matches but every method returns 405).

Validation fails fast. It does not silently produce a partial route tree.

## What is not implemented

The router itself, route resolution, and the validation step do not
exist. The CLI commands `catba dev` and `catba build` report "not
implemented yet". This document fixes the routing semantics so the router
can be implemented later without redesigning the route model.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
