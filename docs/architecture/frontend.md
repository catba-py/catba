# Frontend Project Contract

Status: specification for the frontend layer. The SSR implementation is
described in [ssr.md](ssr.md) and hydration in [hydration.md](hydration.md).

## Overview

A CatBa project with page routes uses standard JavaScript frontend tooling:
React, React DOM, TypeScript, and Vite. CatBa does not invent a parallel
frontend dependency format. Frontend dependencies live in `package.json` and
are installed with the project's normal JavaScript package manager.

`catba install` remains a Python-only command: it installs dependencies from
`pyproject.toml`. It does not install frontend dependencies.

## Project structure

A CatBa project with pages:

```text
myapp/
+-- catba.py              # project launcher
+-- pyproject.toml        # Python project metadata and dependencies
+-- package.json          # frontend dependencies (React, Vite, etc.)
+-- tsconfig.json          # TypeScript configuration
+-- vite.config.ts        # Vite build configuration
+-- app/
    +-- route.py          # server boundary
    +-- page.tsx          # UI boundary
    +-- users/
        +-- route.py
        +-- page.tsx
    +-- users/
        +-- [id]/
            +-- route.py
            +-- page.tsx
```

A CatBa project with API routes only (no `page.tsx` files) does not need
any frontend files. No Node process is started.

## Frontend files are standard

`package.json`, `tsconfig.json`, and `vite.config.ts` are normal frontend
project files. CatBa does not introduce:

```text
catba.tsx
catba-js.toml
catba-vite.json
catba-frontend.lock
```

or any CatBa-specific frontend dependency format.

## Frontend dependencies

The frontend dependencies are standard:

```text
react
react-dom
typescript
vite
@vitejs/plugin-react
```

These are installed by the project's JavaScript package manager (npm, pnpm,
yarn, etc.). CatBa does not bundle or download them.

CatBa does not add React, Vite, or Node packages as Python runtime
dependencies. The Python package `catba` remains a Python package.

## Node.js runtime

React SSR requires a JavaScript runtime. CatBa uses the Node.js runtime
available in the project environment. CatBa does not bundle Node, download
Node automatically, or add an embedded JavaScript runtime.

If SSR is requested (a page route exists) but Node is not available, CatBa
reports a clear error. It never silently falls back to JSON for a page route.

## Page component contract

Every page module (`page.tsx`) must have a default export:

```tsx
export default function Page(props: Props) {
    ...
}
```

The default export is the component CatBa renders. Named exports may exist
but CatBa does not depend on them. A page without a default export produces
a deterministic build error.

CatBa does not require decorators, `export const route = ...`, or
framework-specific rendering calls.

## Props contract

`PageData.props` becomes the React component props. Props passed through
the SSR boundary must be JSON-serializable. If props cannot be serialized
safely, CatBa returns a controlled server error. CatBa does not use `repr()`
or `pickle` as a serialization fallback.

## Route identity

The SSR layer uses a stable page identifier derived from the route structure:

```text
/           -> /
/users      -> /users
/users/[id] -> /users/[id]
```

No random IDs, timestamps, or absolute filesystem paths are exposed to the
browser.

## Generated files

Generated SSR and client artifacts live in `.catba/generated/`. CatBa does
not mix generated files into `app/` or modify user source files.

## Vite responsibility

CatBa owns: route discovery, page identity, PageData, SSR request
orchestration.

Vite owns: TS/TSX transformation, React processing, module graph, frontend
bundling.

CatBa does not duplicate Vite's module resolution or write a custom TSX
transpiler.

---

Copyright (c) 2026 Le Hung Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../../LICENSE).
