/* platform_posix.c - POSIX implementation of the platform abstraction. */

#include "platform.h"

#include <fcntl.h>
#include <string.h>

int cb_platform_init(void) {
    return 0;  /* no global init needed on POSIX */
}

void cb_platform_finalize(void) {
    /* nothing to clean up */
}

int cb_sock_close(cb_socket_t sock) {
    if (sock == CB_SOCKET_INVALID) return 0;
    int rc = close(sock);
    return (rc == 0) ? 0 : -1;
}

int cb_sock_set_reuseaddr(cb_socket_t sock) {
    int opt = 1;
    int rc = setsockopt(sock, SOL_SOCKET, SO_REUSEADDR,
                        &opt, sizeof(opt));
    return (rc == 0) ? 0 : -1;
}

int cb_sock_last_error(void) {
    return errno;
}

long cb_sock_read(cb_socket_t sock, void *buf, size_t count) {
    ssize_t n = recv(sock, buf, count, 0);
    if (n < 0) return -1;
    return (long)n;
}

long cb_sock_write(cb_socket_t sock, const void *buf, size_t count) {
    ssize_t n = send(sock, buf, count, 0);
    if (n < 0) return -1;
    return (long)n;
}
