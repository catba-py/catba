# native/ - CatBa native C runtime

Status: in development. The platform abstraction is implemented. Other
components (arena, HTTP parser, socket transport, Python bridge) are added
in subsequent commits.

## Build

Requires a C compiler with C23 support (GCC 14+ or Clang 18+) and Python
development headers.

```bash
cd native
./build.sh tests     # build and run native tests
./build.sh server     # build the server binary
SAN=asan ./build.sh tests   # build with ASan + UBSan + LSan
```

The build discovers Python include and library paths from the active
Python interpreter. It does not bundle Python.

## Architecture

```
browser/curl
    |
    v
native C runtime (socket, HTTP parser, response serializer)
    |
    v
Python Core (route discovery, dispatch, return semantics)
    |
    v
route.py
```

The native runtime owns transport and low-level HTTP. The Python Core owns
application behavior. One crossing per request.

See [../docs/architecture/native-runtime.md](../docs/architecture/native-runtime.md)
for the full design.

## Platform support

Platform-specific code is isolated in `platform_win.c` and `platform_posix.c`.
The rest of the runtime uses the abstraction in `platform.h`.
