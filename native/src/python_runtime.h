/* python_runtime.h - embedded CPython interpreter management.
 *
 * Initializes and finalizes an embedded CPython interpreter, and loads
 * the CatBa Python Core. The interpreter runs single-threaded; the GIL
 * is held for the lifetime of the server.
 *
 * Reference ownership:
 *   - Every PyObject* returned or stored is either owned (must Py_DECREF)
 *     or borrowed (valid only while the owner is alive). This is documented
 *     at each return site.
 *   - No reference ownership is ambiguous.
 */

#ifndef CATBA_PYTHON_RUNTIME_H
#define CATBA_PYTHON_RUNTIME_H

#include <Python.h>

/* The loaded CatBa app. `app` is an owned reference (released on finalize).
 * `handle` is a borrowed reference into app (valid while app is alive).
 * `to_http` is a borrowed reference into catba.runtime (valid while loaded). */
typedef struct {
    PyObject *app;       /* owned: catba.runtime.App instance */
    PyObject *handle;    /* borrowed: App.handle method */
    PyObject *to_http;   /* borrowed: catba.runtime.to_http function */
    int initialized;     /* 1 after successful cb_python_init */
} cb_python_ctx;

/* Initialize the embedded CPython interpreter. Returns 0 on success. */
int cb_python_init(void);

/* Finalize the embedded interpreter. Releases all owned references. */
void cb_python_finalize(cb_python_ctx *ctx);

/* Load the CatBa Core and create an App for the given app directory.
 * Returns 0 on success, -1 on error (Python exception printed to stderr). */
int cb_python_load_project(cb_python_ctx *ctx, const char *app_dir);

#endif /* CATBA_PYTHON_RUNTIME_H */
