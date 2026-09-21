# .catba/

Reserved for the small project-local bootstrap bundle used by the project
launcher (`catba.py`).

Intended responsibility:

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
custom dependency format: dependencies come from the project's
`pyproject.toml`, resolved with standard Python packaging/pip behaviour.

Nothing in this directory is implemented yet. It only reserves the area so
the future bootstrap has a home.
