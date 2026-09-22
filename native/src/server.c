/* server.c - the native request loop.
 *
 * The request loop: accept connection, read data, parse HTTP, bridge to
 * Python Core, serialize response, write to connection, cleanup arena.
 * Repeats for keep-alive requests on the same connection. On any error or
 * connection close, all resources are released.
 */

#include "server.h"

#include "arena.h"
#include "bridge.h"
#include "http_parser.h"
#include "platform.h"
#include "serializer.h"
#include "socket.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Buffer size for reading into a connection. */
#define CB_READ_BUF_SIZE (64 * 1024)

/* Process one request on a connection. Returns:
 *   1 = request handled, connection may continue (keep-alive)
 *   0 = connection should close
 *  -1 = error, connection should close
 */
static int process_request(cb_python_ctx *ctx, cb_connection *conn)
{
    /* Read until we have a complete request or an error. */
    for (;;) {
        /* Try to parse what we have. */
        cb_arena *arena = cb_arena_create();
        if (!arena) {
            cb_serializer_send_error(conn, 500, "Internal Server Error");
            return 0;
        }

        cb_request req;
        size_t consumed = 0;
        cb_parse_result pr = cb_http_parse(conn->read_buf, conn->read_len,
                                          arena, &req, &consumed);

        if (pr == CB_PARSE_OK) {
            /* We have a complete request. Bridge to Python Core. */
            cb_response resp;
            cb_bridge_handle(ctx, &req, arena, &resp);

            /* Determine if HEAD: suppress body. */
            int head_only = (strcmp(req.method, "HEAD") == 0);

            /* Serialize and write. */
            int rc = cb_serializer_write(conn, &resp, head_only);

            /* Track keep-alive from the parsed request. */
            int keep = req.keep_alive;

            /* Consume the parsed bytes from the connection buffer. */
            cb_connection_consume(conn, consumed);

            /* Release the arena (one release, all request memory freed). */
            cb_arena_release(arena);

            if (rc != 0)
                return 0;  /* write failed: close */

            return keep ? 1 : 0;
        }

        if (pr == CB_PARSE_INCOMPLETE) {
            /* Need more data. Read another chunk. */
            long n = cb_connection_read(conn);
            if (n <= 0) {
                /* EOF or error. */
                cb_arena_release(arena);
                return 0;
            }
            cb_arena_release(arena);
            continue;
        }

        /* CB_PARSE_MALFORMED or CB_PARSE_TOO_LARGE. */
        if (pr == CB_PARSE_TOO_LARGE)
            cb_serializer_send_error(conn, 413, "Request Too Large");
        else
            cb_serializer_send_error(conn, 400, "Bad Request");
        cb_arena_release(arena);
        return 0;
    }
}

int cb_server_run(cb_python_ctx *ctx, const char *host, int port)
{
    cb_platform_init();

    cb_listener listener;
    if (cb_listener_create(&listener, host, port) != 0) {
        fprintf(stderr, "catba: cannot bind to %s:%d\n", host, port);
        cb_platform_finalize();
        return -1;
    }
    fprintf(stderr, "catba start: http://%s:%d\n", host, port);

    for (;;) {
        cb_socket_t client_sock;
        if (cb_listener_accept(&listener, &client_sock) != 0) {
            /* Accept failed: log and continue. */
            fprintf(stderr, "catba: accept failed (err=%d)\n", cb_sock_last_error());
            continue;
        }

        /* Initialize the connection. */
        cb_connection conn;
        if (cb_connection_init(&conn, client_sock, CB_READ_BUF_SIZE) != 0) {
            cb_sock_close(client_sock);
            continue;
        }

        /* Process requests on this connection (keep-alive loop). */
        int keep_going = 1;
        while (keep_going) {
            keep_going = process_request(ctx, &conn);
        }

        /* Connection cleanup: close socket, free buffer. */
        cb_connection_close(&conn);
    }

    /* Unreachable in normal operation. Clean up on shutdown. */
    cb_listener_close(&listener);
    cb_platform_finalize();
    return 0;
}
