# Hydration

Status: implemented. Server-rendered pages include hydration state and a
client bundle that hydrates the DOM into a live React application.

## How hydration works

```text
Server:
  PageData
    ->
  SSR (React renderToString)
    ->
  HTML fragment
    ->
  HTML document with:
    <div id="catba-root" data-catba-page="/">{fragment}</div>
    <script id="catba-props" type="application/json">{safe props}</script>
    <script type="module" src="/__catba/client-bundle.js"></script>

Browser:
  HTML loaded
    ->
  client-entry.js runs
    ->
  reads data-catba-page from #catba-root
    ->
  reads props from #catba-props script
    ->
  hydrateRoot(root, createElement(Component, props))
    ->
  live React app
```

## Page identifier

The server-rendered root div carries `data-catba-page` with the route URL
identifier (e.g. `/`, `/users`, `/users/[id]`). The client entry reads this
to find the matching page component from the generated page map.

The page identifier is derived from the route structure, not from random
IDs, timestamps, or absolute filesystem paths.

## Props serialization

Props are serialized as JSON inside a `<script type="application/json">`
element. The serialization function escapes `<` to `\u003c` so that
`</script>` inside user-controlled props cannot terminate the script
element.

Never use raw string concatenation for props. The function `_safe_script_json`
in `html.py` is the only correct way to embed props in HTML.

## Client bundle

The client bundle is built by Vite from the generated `client-entry.js`.
It imports all page modules and calls `hydrateRoot` from `react-dom/client`.

The client bundle is served from `/__catba/` to avoid colliding with user
routes. The Python transport and the native C runtime both serve assets
from this path.

## What hydration does NOT do

- No client-side navigation (no SPA routing)
- No Inertia page object
- No data refetching on hydration (props come from the server)
- No partial hydration or RSC

After hydration, the page behaves as a normal React application. Client
interactions (useState, onClick, etc.) work as expected.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
