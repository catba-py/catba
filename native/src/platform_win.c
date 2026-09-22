/* platform_win.c - Windows implementation of the platform abstraction. */

#include "platform.h"

#include <stdio.h>

int cb_platform_init(void) {
    WSADATA wsa;
    int rc = WSAStartup(MAKEWORD(2, 2), &wsa);
    return (rc == 0) ? 0 : -1;
}

void cb_platform_finalize(void) {
    WSACleanup();
}

int cb_sock_close(cb_socket_t sock) {
    if (sock == CB_SOCKET_INVALID) return 0;
    int rc = closesocket(sock);
    return (rc == 0) ? 0 : -1;
}

int cb_sock_set_reuseaddr(cb_socket_t sock) {
    BOOL opt = TRUE;
    int rc = setsockopt(sock, SOL_SOCKET, SO_REUSEADDR,
                        (const char *)&opt, sizeof(opt));
    return (rc == 0) ? 0 : -1;
}

int cb_sock_last_error(void) {
    return WSAGetLastError();
}

long cb_sock_read(cb_socket_t sock, void *buf, size_t count) {
    int n = recv(sock, (char *)buf, (int)count, 0);
    if (n == CB_SOCKET_ERR) return -1;
    return (long)n;
}

long cb_sock_write(cb_socket_t sock, const void *buf, size_t count) {
    int n = send(sock, (const char *)buf, (int)count, 0);
    if (n == CB_SOCKET_ERR) return -1;
    return (long)n;
}
