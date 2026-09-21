# CatBa

CatBa is a Python web framework and runtime. This repository currently holds
the bootstrap foundation: package layout, command surface, project template,
test suite, and CI/release pipeline. The web runtime, router, server, and
rendering components are not implemented yet.

## Status

Repository bootstrap / pre-runtime.

## Quick start

CatBa requires Python 3.14 or later.

```bash
python -m pip install -e .
catba --version
catba --help
```

## CLI surface

The command names are established but not implemented yet:

| Command | Intent |
|---|---|
| `catba create` | Scaffold a new CatBa project from the template |
| `catba dev` | Run the project in development mode |
| `catba build` | Build the project for production |
| `catba start` | Run the built project |
| `catba install` | Install project dependencies from `pyproject.toml` |

`catba install` installs the dependencies declared by the project's
`pyproject.toml` using standard Python packaging behaviour. There is no
custom dependency resolver and no `catba install <package>` form.

## Documentation

See [`docs/`](docs/README.md) for the repository layout, the role of
`catba.py`, the `.catba/` bootstrap area, the release process, and which
parts are intentionally not implemented yet.

## License

Copyright (c) 2026 Lê Hùng Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0). See [LICENSE](LICENSE).
