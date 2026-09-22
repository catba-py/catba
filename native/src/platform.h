/* platform.h - platform abstraction for sockets and system calls.
 *
 * Isolates Windows vs POSIX socket differences behind a small interface.
 * Platform-specific code lives here and in platform_win.c / platform_posix.c.
 * The rest of the runtime uses cb_socket_t and the cb_sock_* functions.
 */

#ifndef CATBA_PLATFORM_H
#define CATBA_PLATFORM_H

#include <stddef.h>

/* --- socket type --- */

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    typedef SOCKET cb_socket_t;
    #define CB_SOCKET_INVALID (INVALID_SOCKET)
    #define CB_SOCKET_ERR SOCKET_ERROR
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <errno.h>
    typedef int cb_socket_t;
    #define CB_SOCKET_INVALID (-1)
    #define CB_SOCKET_ERR (-1)
#endif

/* --- platform init/finalize --- */

/* On Windows: initialize Winsock. On POSIX: no-op. */
int cb_platform_init(void);
void cb_platform_finalize(void);

/* --- socket operations --- */

/* Close a socket. Returns 0 on success, -1 on error. */
int cb_sock_close(cb_socket_t sock);

/* Set SO_REUSEADDR on a socket. Returns 0 on success, -1 on error. */
int cb_sock_set_reuseaddr(cb_socket_t sock);

/* Get last socket error code (for diagnostics). */
int cb_sock_last_error(void);

/* Read up to count bytes into buf. Returns bytes read, 0 on EOF, -1 on error. */
long cb_sock_read(cb_socket_t sock, void *buf, size_t count);

/* Write up to count bytes from buf. Returns bytes written, -1 on error. */
long cb_sock_write(cb_socket_t sock, const void *buf, size_t count);

#endif /* CATBA_PLATFORM_H */
