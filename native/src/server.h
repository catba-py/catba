/* server.h - the native request loop.
 *
 * Connects the socket transport, HTTP parser, Python bridge, serializer,
 * and request arena into one working runtime. Accepts connections, reads
 * requests, dispatches them through the Python Core, and writes responses.
 *
 * Single-threaded: one connection at a time. Keep-alive is supported within
 * a single connection. The GIL is held for the lifetime of the server.
 */

#ifndef CATBA_SERVER_H
#define CATBA_SERVER_H

#include "python_runtime.h"

/* Run the native server. Blocks until interrupted (Ctrl-C) or error.
 *
 * Parameters:
 *   ctx       - loaded Python context
 *   host      - bind address
 *   port      - bind port
 *
 * Returns 0 on clean shutdown, -1 on error.
 */
int cb_server_run(cb_python_ctx *ctx, const char *host, int port);

#endif /* CATBA_SERVER_H */
