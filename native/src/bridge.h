/* bridge.h - native-to-Python Core bridge.
 *
 * Converts a parsed native request into a call to the Python Core's
 * serve_native function, and unpacks the result into a native response.
 *
 * One crossing per request: native request -> Python Core -> native response.
 * No routing, dispatch, or return-interpretation logic lives in C.
 */

#ifndef CATBA_BRIDGE_H
#define CATBA_BRIDGE_H

#include "arena.h"
#include "http_parser.h"
#include "python_runtime.h"
#include <stddef.h>

/* A native response: status, headers, body. All strings are arena-owned. */
typedef struct {
    int status;
    const char **header_names;   /* arena-owned array of strings */
    const char **header_values;  /* arena-owned array of strings */
    int header_count;
    const char *body;            /* arena-owned, or NULL */
    size_t body_len;
} cb_response;

/* Bridge a native request to the Python Core and unpack the result.
 *
 * Parameters:
 *   ctx  - the loaded Python context (app + handle + to_http)
 *   req  - the parsed HTTP request
 *   arena - request arena (owns all response strings)
 *   resp - output: filled on success
 *
 * Returns 0 on success, -1 on error (Python exception printed to stderr).
 * On error, resp is filled with a 500 response.
 */
int cb_bridge_handle(cb_python_ctx *ctx, cb_request *req,
                     cb_arena *arena, cb_response *resp);

#endif /* CATBA_BRIDGE_H */
