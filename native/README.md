# native/

Reserved for the future native C runtime of CatBa.

Nothing is implemented here yet. In particular there is no C source, no
HTTP server, and no build system (CMake, Meson, Autotools, or otherwise).
Those will be added when there is actual C code to build.

Intended future architecture:

```text
browser
    |
    v
native C runtime
    |
    v
Python application
```

The native runtime will eventually serve as the high-performance layer
between the browser and the Python application. The Python ↔ native bridge
will use Cython where useful. None of that pipeline exists yet — this
directory only reserves its home.
