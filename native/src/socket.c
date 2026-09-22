/* socket.c - TCP socket listener and connection handling. */

#include "socket.h"

#include <stdlib.h>
#include <string.h>

/* --- listener --- */

int cb_listener_create(cb_listener *l, const char *host, int port)
{
    memset(l, 0, sizeof(*l));

    l->sock = socket(AF_INET, SOCK_STREAM, 0);
    if (l->sock == CB_SOCKET_INVALID)
        return -1;

    if (cb_sock_set_reuseaddr(l->sock) != 0) {
        cb_sock_close(l->sock);
        l->sock = CB_SOCKET_INVALID;
        return -1;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        cb_sock_close(l->sock);
        l->sock = CB_SOCKET_INVALID;
        return -1;
    }

    if (bind(l->sock, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        cb_sock_close(l->sock);
        l->sock = CB_SOCKET_INVALID;
        return -1;
    }

    if (listen(l->sock, 128) != 0) {
        cb_sock_close(l->sock);
        l->sock = CB_SOCKET_INVALID;
        return -1;
    }

    l->host = host;
    l->port = port;
    return 0;
}

int cb_listener_accept(const cb_listener *l, cb_socket_t *out_sock)
{
    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);
    *out_sock = accept(l->sock, (struct sockaddr *)&client_addr, &addr_len);
    if (*out_sock == CB_SOCKET_INVALID)
        return -1;
    return 0;
}

void cb_listener_close(cb_listener *l)
{
    if (l->sock != CB_SOCKET_INVALID) {
        cb_sock_close(l->sock);
        l->sock = CB_SOCKET_INVALID;
    }
}

/* --- connection --- */

int cb_connection_init(cb_connection *c, cb_socket_t sock, size_t buf_cap)
{
    memset(c, 0, sizeof(*c));
    c->sock = sock;
    c->read_cap = buf_cap;
    c->read_buf = (char *)malloc(buf_cap);
    if (!c->read_buf)
        return -1;
    c->read_len = 0;
    c->keep_alive = 1;
    return 0;
}

long cb_connection_read(cb_connection *c)
{
    /* Shift unconsumed bytes to the front. */
    if (c->read_len > 0 && c->read_len < c->read_cap) {
        /* Not needed: consume() already shifts. But keep as safety. */
    }

    if (c->read_len >= c->read_cap)
        return -1;  /* buffer full: caller must consume first */

    long n = cb_sock_read(c->sock, c->read_buf + c->read_len,
                          c->read_cap - c->read_len);
    if (n < 0)
        return -1;
    c->read_len += (size_t)n;
    return n;
}

void cb_connection_consume(cb_connection *c, size_t n)
{
    if (n >= c->read_len) {
        c->read_len = 0;
    } else {
        memmove(c->read_buf, c->read_buf + n, c->read_len - n);
        c->read_len -= n;
    }
}

int cb_connection_write(cb_connection *c, const void *data, size_t len)
{
    const char *p = (const char *)data;
    size_t remaining = len;
    while (remaining > 0) {
        long n = cb_sock_write(c->sock, p, remaining);
        if (n < 0)
            return -1;
        p += n;
        remaining -= (size_t)n;
    }
    return 0;
}

void cb_connection_close(cb_connection *c)
{
    if (c->read_buf) {
        free(c->read_buf);
        c->read_buf = NULL;
    }
    if (c->sock != CB_SOCKET_INVALID) {
        cb_sock_close(c->sock);
        c->sock = CB_SOCKET_INVALID;
    }
}
