# Page Contract

Status: specification. No rendering pipeline exists yet. This document
defines the contract that `page.tsx` files will follow.

## UI boundary

`page.tsx` is the UI boundary. It receives data produced by `route.py`
and renders it. The conceptual flow:

```text
request
  ->
route.py
  ->
page props
  ->
page.tsx
  ->
SSR HTML (full load) or Inertia payload (Inertia request)
```

The page component receives the dict returned by the route handler as
its props. That is the only data channel from the server to the page.

## How page props reach React

The handler returns a bare dict. The framework uses that dict as props.
For a page route (one that has `page.tsx`):

1. The handler returns `{"users": users}`.
2. The framework derives the component from the route's `page.tsx`.
3. For a full load, the framework renders the component with the props to
   HTML on the server (SSR).
4. For an Inertia request, the framework wraps the component name and
   props into an Inertia-compatible JSON payload.

The user does not call an Inertia API or a framework render API. There is
no `Inertia.page(...)`, `Inertia.render(...)`, `render_page(...)`, or
`render(...)` in the normal page path. The handler returns props; the
framework does the rest.

## Default export

`page.tsx` provides a default export: the React component for that route.

```tsx
export default function Page({ users }) {
  return (
    <ul>
      {users.map((u) => <li key={u.id}>{u.name}</li>)}
    </ul>
  );
}
```

The props are the keys of the dict returned by the route handler. If the
handler returns `{"users": users}`, the component receives `users` as a
prop.

## Page existence rule

A normal user-facing page requires both files:

```text
route.py  +  page.tsx
```

Neither file alone is a valid page:

- `page.tsx` without `route.py` is an invalid structure. It is not a
  route. The build/dev validation step rejects it (see below).
- `route.py` without `page.tsx` is an API route, not a page. See
  [API routes](#api-routes).

A `page.tsx` file must not silently become a valid route without its
server boundary. The data channel into a page is `route.py`. Without it,
there is no page.

## Invalid page structures: validation behavior

The intended `catba dev` and `catba build` commands validate the route
tree before running. A `page.tsx` without a sibling `route.py` is a
build error, not a silent skip:

```text
error: app/users/page.tsx has no corresponding route.py
       a page requires a server boundary
```

The validation runs at startup (dev) and at build time (build). It
fails fast. It does not produce a partially working route tree.

## API routes

A route may intentionally have no `page.tsx`:

```text
app/
└── api/
    └── users/
        └── route.py
```

This is a server endpoint (an API route). It is not a page. Its handler
returns HTTP responses: a bare dict becomes JSON, or an explicit
`Response`/`JSON` object.

CatBa distinguishes a page route from an API route by the presence of
`page.tsx`, not by a new file type or a config flag:

| Files present         | Route type | Bare dict return |
|-----------------------|------------|-------------------|
| `route.py` + `page.tsx` | page route | page props -> page.tsx |
| `route.py` only          | API route  | JSON response body     |
| `page.tsx` only          | invalid    | build error             |

No third file type is introduced. The pair (or absence) of the two files
is the entire distinction.

## Rendering is not user-facing

The user writes `page.tsx` as a React component. The user does not:

- import a CatBa render function
- call SSR directly
- construct an Inertia payload
- switch between SSR and Inertia modes

The framework picks the response shape from the request (full load vs
Inertia header). The page component is the same either way.

## Current implementation

None of this exists. There is no TSX compiler, no Vite integration, no
SSR engine, and no Inertia protocol integration. The template at
`templates/app/app/page.tsx` holds only a minimal placeholder component.
This document fixes the page contract so Phase 2 can implement rendering
without redesigning the page model.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
