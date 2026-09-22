/* socket.h - TCP socket listener and connection handling.
 *
 * The socket transport owns the listener and connection lifecycle.
 * It reads raw bytes from the socket into a buffer and writes response
 * bytes back. HTTP parsing is done by http_parser; the socket layer does
 * not interpret the bytes.
 *
 * Ownership:
 *   - cb_listener owns the listening socket. Closed by cb_listener_close.
 *   - cb_connection owns the connection socket and its read buffer. Closed
 *     by cb_connection_close. No request pointers survive past close.
 */

#ifndef CATBA_SOCKET_H
#define CATBA_SOCKET_H

#include "platform.h"
#include <stddef.h>

/* --- listener --- */

typedef struct {
    cb_socket_t sock;
    const char *host;
    int port;
} cb_listener;

/* Create a listener bound to host:port. Returns 0 on success, -1 on error. */
int cb_listener_create(cb_listener *l, const char *host, int port);

/* Accept a new connection. Returns 0 on success, -1 on error.
 * The accepted socket is stored in conn->sock. */
int cb_listener_accept(const cb_listener *l, cb_socket_t *out_sock);

/* Close the listening socket. */
void cb_listener_close(cb_listener *l);

/* --- connection --- */

typedef struct {
    cb_socket_t sock;
    char *read_buf;    /* heap-allocated read buffer */
    size_t read_cap;   /* capacity of read_buf */
    size_t read_len;   /* bytes currently in read_buf */
    int keep_alive;    /* 1 if the connection should stay open */
} cb_connection;

/* Initialize a connection from an accepted socket. Returns 0 on success. */
int cb_connection_init(cb_connection *c, cb_socket_t sock, size_t buf_cap);

/* Read more data into the connection's read buffer. Returns bytes read
 * (0 = EOF, -1 = error). Also shifts unconsumed bytes to the front of
 * the buffer before reading. */
long cb_connection_read(cb_connection *c);

/* Consume `n` bytes from the front of the read buffer. */
void cb_connection_consume(cb_connection *c, size_t n);

/* Write `len` bytes to the connection. Returns 0 on success, -1 on error. */
int cb_connection_write(cb_connection *c, const void *data, size_t len);

/* Close the connection and free its buffer. */
void cb_connection_close(cb_connection *c);

#endif /* CATBA_SOCKET_H */
