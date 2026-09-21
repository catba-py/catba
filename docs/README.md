# CatBa — Bootstrap Documentation

## Status

Repository bootstrap / pre-runtime.

## What CatBa is

CatBa is a Python web framework and runtime. The long-term direction includes
a React + TSX frontend (with Vite as an implementation detail), a native C
runtime, and a Cython bridge between Python and native code. None of that
exists yet. What exists now is the repository foundation that later work
builds on: package layout, command surface, project template, tests, and
CI/release pipeline.

## Repository layout

```text
catba/
├── .github/workflows/   CI and tag-driven release
├── .catba/             project-local bootstrap area (reserved)
├── docs/               this documentation
├── examples/           future example projects (reserved)
├── native/             future C runtime (reserved)
├── src/catba/           the installable Python package
│   ├── __init__.py      package metadata, __version__
│   └── cli.py           command-line interface
├── templates/app/       the project template
│   ├── catba.py         project-local launcher
│   ├── pyproject.toml   template project metadata
│   └── app/
│       ├── route.py     placeholder route definitions
│       └── page.tsx     placeholder React component
├── tests/               standard-library unittest suite
├── .editorconfig
├── .gitignore
├── LICENSE             MPL-2.0
├── README.md
└── pyproject.toml       canonical project metadata and dependencies
```

## The role of `catba.py`

A CatBa project ships a small `catba.py` launcher at its root (copied from
`templates/app/catba.py`). It is not the CLI and contains no business logic.
It forwards execution to the installed `catba` package:

```text
catba.py
    |
    v
CatBa package / runtime
    |
    v
run project
```

Run it directly:

```bash
python catba.py --help
./catba.py dev      # once the executable bit is set
```

Because the file is named `catba.py`, it would shadow the installed package
on `sys.path`. The launcher drops its own directory from `sys.path` before
importing so the installed `catba` package resolves.

## The role of `.catba/`

`.catba/` is reserved for the small project-local bootstrap bundle used by
`catba.py`:

```text
catba.py
    |
    v
.catba bootstrap
    |
    v
prepare CatBa environment
    |
    v
run project
```

The bootstrap prepares the environment a CatBa project needs before the
runtime starts. It is **not** a package manager and does not introduce a
custom dependency format — dependencies come from `pyproject.toml`, resolved
with standard Python packaging/pip behaviour. Nothing in `.catba/` is
implemented yet.

## `pyproject.toml` is canonical

`pyproject.toml` is the single source of project metadata and dependencies.
CatBa uses existing Python packaging standards wherever they already solve
the problem. There is no `catba.toml`, no `catba.lock`, no `requirements.txt`,
and no parallel dependency manifest.

## Current CLI surface

```
catba --version          print version and exit
catba --help             print help and exit
catba create             scaffold a new project (not implemented yet)
catba dev                development mode (not implemented yet)
catba build              production build (not implemented yet)
catba start              run the built project (not implemented yet)
catba install            install pyproject.toml dependencies (not implemented yet)
```

Every subcommand exists as a named entry point but reports
"not implemented yet" and exits non-zero. `--version` and `--help` are
fully wired.

## Development commands

```bash
# install the package in editable mode
python -m pip install -e .

# run the test suite
python -m unittest discover -v

# build the sdist and wheel
python -m pip install build
python -m build
```

## Release process

Releases are tag-driven:

```text
git tag v0.1.0
        |
        v
GitHub Actions (.github/workflows/release.yml)
        |
        v
build sdist + wheel
        |
        v
GitHub Release (with artifacts attached)
        |
        v
PyPI publishing (Trusted Publishing, OIDC)
```

Pushing a `v*` tag triggers the release workflow, which builds the package,
verifies the artifacts, creates a GitHub Release, and is wired for PyPI
Trusted Publishing. The PyPI publishing step is gated off until a Trusted
Publisher is registered for the `catba` project on PyPI; see the comment in
`.github/workflows/release.yml`.

## What is intentionally not implemented yet

- The web runtime, HTTP server, and request/response handling.
- The router and route registration.
- Server-side rendering and the React/TSX compilation pipeline.
- Vite integration.
- The native C runtime and the Python ↔ native Cython bridge.
- The `catba create / dev / build / start / install` command behaviours.
- The `.catba/` bootstrap bundle.

These are reserved as empty, documented areas, not stubs that pretend to work.

---

Copyright (c) 2026 Lê Hùng Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](../LICENSE).
