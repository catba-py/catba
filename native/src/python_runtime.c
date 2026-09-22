/* python_runtime.c - embedded CPython interpreter management.
 *
 * Initializes CPython, loads the CatBa package, and creates an App instance
 * for the given project. All PyObject* references are classified and
 * released on finalize.
 */

#include "python_runtime.h"

#include <stdio.h>

int cb_python_init(void)
{
    if (Py_IsInitialized())
        return 0;

    Py_Initialize();
    if (!Py_IsInitialized())
        return -1;
    return 0;
}

void cb_python_finalize(cb_python_ctx *ctx)
{
    if (!ctx)
        return;

    /* Release owned references. handle and to_http are owned references
     * obtained via PyObject_GetAttrString; app is owned via call. */
    Py_XDECREF(ctx->handle);
    Py_XDECREF(ctx->to_http);
    Py_XDECREF(ctx->app);
    ctx->handle = NULL;
    ctx->to_http = NULL;
    ctx->app = NULL;
    ctx->initialized = 0;

    if (Py_IsInitialized())
        Py_Finalize();
}

int cb_python_load_project(cb_python_ctx *ctx, const char *app_dir)
{
    if (!ctx)
        return -1;

    ctx->app = NULL;
    ctx->handle = NULL;
    ctx->to_http = NULL;

    /* Import catba.runtime module. */
    PyObject *mod = PyImport_ImportModule("catba.runtime");
    if (!mod) {
        if (PyErr_Occurred())
            PyErr_Print();
        fprintf(stderr, "catba: cannot import catba.runtime (is catba installed?)\n");
        return -1;
    }
    /* mod: owned (new reference). Released at end of this function. */

    /* Get App class from the module. */
    PyObject *app_class = PyObject_GetAttrString(mod, "App");
    if (!app_class) {
        if (PyErr_Occurred())
            PyErr_Print();
        Py_DECREF(mod);
        return -1;
    }
    /* app_class: owned (new reference). */

    /* Get to_http function from the module. */
    PyObject *to_http = PyObject_GetAttrString(mod, "to_http");
    if (!to_http) {
        if (PyErr_Occurred())
            PyErr_Print();
        Py_DECREF(app_class);
        Py_DECREF(mod);
        return -1;
    }
    /* to_http: owned (new reference). Kept in ctx. */

    /* Create App(app_dir) instance. */
    PyObject *dir_str = PyUnicode_FromString(app_dir);
    if (!dir_str) {
        Py_DECREF(to_http);
        Py_DECREF(app_class);
        Py_DECREF(mod);
        return -1;
    }
    /* dir_str: owned (new reference). Consumed by call. */

    PyObject *app = PyObject_CallOneArg(app_class, dir_str);
    Py_DECREF(dir_str);
    Py_DECREF(app_class);
    Py_DECREF(mod);

    if (!app) {
        if (PyErr_Occurred())
            PyErr_Print();
        Py_DECREF(to_http);
        return -1;
    }
    /* app: owned (new reference). Kept in ctx. */

    /* Get handle method from app. */
    PyObject *handle = PyObject_GetAttrString(app, "handle");
    if (!handle) {
        if (PyErr_Occurred())
            PyErr_Print();
        Py_DECREF(app);
        Py_DECREF(to_http);
        return -1;
    }
    /* handle: owned (new reference). Kept in ctx. */

    ctx->app = app;
    ctx->handle = handle;
    ctx->to_http = to_http;
    ctx->initialized = 1;
    return 0;
}
