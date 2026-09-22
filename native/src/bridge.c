/* bridge.c - native-to-Python Core bridge implementation.
 *
 * Calls the Python Core's serve_native function with data from a parsed
 * native request, and unpacks the result into a native response. All
 * response strings are arena-owned.
 *
 * Reference ownership:
 *   - Temporary Python objects (method_str, path_str, headers_dict,
 *     body_bytes) are owned (new reference) and Py_DECREF'd after the call.
 *   - The result tuple is owned (new reference) and Py_DECREF'd after unpacking.
 *   - Items extracted from the tuple are borrowed (valid while the tuple is alive).
 *   - All C strings in the response are arena-owned (no individual frees).
 *
 * GIL: the bridge acquires the GIL via PyGILState_Ensure on entry and
 * releases it on exit. This is safe whether the caller already holds the
 * GIL (main thread) or not (background thread).
 */

#include "bridge.h"

#include <stdio.h>
#include <string.h>

/* Fill resp with a 500 Internal Server Error. */
static void fill_500(cb_arena *arena, cb_response *resp)
{
    resp->status = 500;
    resp->header_count = 2;
    resp->header_names = (const char **)cb_arena_calloc(arena, 2, sizeof(char *));
    resp->header_values = (const char **)cb_arena_calloc(arena, 2, sizeof(char *));
    if (resp->header_names && resp->header_values) {
        resp->header_names[0] = cb_arena_dup_str(arena, "Content-Type");
        resp->header_values[0] = cb_arena_dup_str(arena, "text/plain; charset=utf-8");
        resp->header_names[1] = cb_arena_dup_str(arena, "Content-Length");
        resp->header_values[1] = cb_arena_dup_str(arena, "21");
        resp->body = cb_arena_dup(arena, "Internal Server Error", 21);
        resp->body_len = 21;
    } else {
        resp->header_count = 0;
        resp->body = NULL;
        resp->body_len = 0;
    }
}

int cb_bridge_handle(cb_python_ctx *ctx, cb_request *req,
                     cb_arena *arena, cb_response *resp)
{
    memset(resp, 0, sizeof(*resp));

    if (!ctx || !ctx->initialized || !req || !arena) {
        fill_500(arena, resp);
        return -1;
    }

    /* Acquire the GIL. Safe whether or not the calling thread already holds it. */
    PyGILState_STATE gstate = PyGILState_Ensure();

    int ret = 0;
    PyObject *mod = NULL;
    PyObject *serve = NULL;
    PyObject *method_str = NULL;
    PyObject *path_str = NULL;
    PyObject *headers_dict = NULL;
    PyObject *body_bytes = NULL;
    PyObject *result = NULL;

    /* Look up serve_native in catba.runtime. */
    mod = PyImport_ImportModule("catba.runtime");
    if (!mod) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    serve = PyObject_GetAttrString(mod, "serve_native");
    if (!serve) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    /* Build Python method string. */
    method_str = PyUnicode_FromString(req->method);
    if (!method_str) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    /* Build Python path+query string. Python side parses the query. */
    char full_target[4096];
    if (req->query && req->query[0])
        snprintf(full_target, sizeof(full_target), "%s?%s", req->path, req->query);
    else
        snprintf(full_target, sizeof(full_target), "%s", req->path);

    path_str = PyUnicode_FromString(full_target);
    if (!path_str) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    /* Build Python headers dict from native headers. */
    headers_dict = PyDict_New();
    if (!headers_dict) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }
    for (int i = 0; i < req->header_count; i++) {
        PyObject *k = PyUnicode_FromString(req->headers[i].name);
        PyObject *v = PyUnicode_FromString(req->headers[i].value);
        if (k && v)
            PyDict_SetItem(headers_dict, k, v);  /* borrows k and v */
        Py_XDECREF(k);
        Py_XDECREF(v);
    }

    /* Build Python body bytes. */
    if (req->body && req->body_len > 0)
        body_bytes = PyBytes_FromStringAndSize(req->body, (Py_ssize_t)req->body_len);
    else
        body_bytes = PyBytes_FromStringAndSize("", 0);
    if (!body_bytes) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    /* Call serve_native(app, method, path, headers, body). One crossing. */
    result = PyObject_CallFunctionObjArgs(
        serve, ctx->app, method_str, path_str, headers_dict, body_bytes, NULL);

    if (!result) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }
    /* result: owned (new reference). Tuple of (status, headers, body). */

    /* Unpack the result tuple. Items are borrowed from result. */
    PyObject *status_obj = PyTuple_GetItem(result, 0);
    PyObject *headers_obj = PyTuple_GetItem(result, 1);
    PyObject *body_obj = PyTuple_GetItem(result, 2);

    if (!status_obj || !headers_obj || !body_obj) {
        if (PyErr_Occurred()) PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }

    /* Extract status as int. */
    long status = PyLong_AsLong(status_obj);
    if (status == -1 && PyErr_Occurred()) {
        PyErr_Print();
        fill_500(arena, resp);
        ret = -1;
        goto cleanup;
    }
    resp->status = (int)status;

    /* Extract headers dict. Iterate and copy into arena. */
    int hcount = (int)PyDict_Size(headers_obj);
    resp->header_count = hcount;
    if (hcount > 0) {
        resp->header_names = (const char **)cb_arena_calloc(arena, (size_t)hcount, sizeof(char *));
        resp->header_values = (const char **)cb_arena_calloc(arena, (size_t)hcount, sizeof(char *));
        if (!resp->header_names || !resp->header_values) {
            fill_500(arena, resp);
            ret = -1;
            goto cleanup;
        }
        PyObject *key, *value;
        Py_ssize_t pos = 0;
        int idx = 0;
        while (PyDict_Next(headers_obj, &pos, &key, &value) && idx < hcount) {
            const char *k = PyUnicode_AsUTF8(key);
            const char *v = PyUnicode_AsUTF8(value);
            if (k && v) {
                resp->header_names[idx] = cb_arena_dup_str(arena, k);
                resp->header_values[idx] = cb_arena_dup_str(arena, v);
            }
            idx++;
        }
    }

    /* Extract body as bytes. Copy into arena. */
    char *body_buf;
    Py_ssize_t body_size;
    if (PyBytes_AsStringAndSize(body_obj, &body_buf, &body_size) == 0) {
        if (body_size > 0) {
            resp->body = cb_arena_dup(arena, body_buf, (size_t)body_size);
            resp->body_len = (size_t)body_size;
        }
    } else {
        if (PyErr_Occurred()) PyErr_Clear();
    }

cleanup:
    Py_XDECREF(result);
    Py_XDECREF(body_bytes);
    Py_XDECREF(headers_dict);
    Py_XDECREF(path_str);
    Py_XDECREF(method_str);
    Py_XDECREF(serve);
    Py_XDECREF(mod);
    PyGILState_Release(gstate);
    return ret;
}
