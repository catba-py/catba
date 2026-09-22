/* test_socket.c - verify socket listener, accept, read, write, close. */

#include "socket.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_listener_accept_read_write(void)
{
    cb_platform_init();

    /* Create listener on an ephemeral port. */
    cb_listener l;
    assert(cb_listener_create(&l, "127.0.0.1", 0) == 0);

    /* Get the actual bound port. */
    struct sockaddr_in addr;
    socklen_t addr_len = sizeof(addr);
    getsockname(l.sock, (struct sockaddr *)&addr, &addr_len);
    int port = ntohs(addr.sin_port);
    assert(port > 0);

    /* Create a client socket and connect. */
    cb_socket_t client = socket(AF_INET, SOCK_STREAM, 0);
    assert(client != CB_SOCKET_INVALID);

    struct sockaddr_in srv;
    memset(&srv, 0, sizeof(srv));
    srv.sin_family = AF_INET;
    srv.sin_port = htons((unsigned short)port);
    inet_pton(AF_INET, "127.0.0.1", &srv.sin_addr);
    assert(connect(client, (struct sockaddr *)&srv, sizeof(srv)) == 0);

    /* Accept on the server side. */
    cb_socket_t server_sock;
    assert(cb_listener_accept(&l, &server_sock) == 0);
    assert(server_sock != CB_SOCKET_INVALID);

    /* Initialize connection from accepted socket. */
    cb_connection conn;
    assert(cb_connection_init(&conn, server_sock, 4096) == 0);

    /* Client sends a message. */
    const char *msg = "hello catba";
    long sent = cb_sock_write(client, msg, strlen(msg));
    assert(sent == (long)strlen(msg));

    /* Server reads it. */
    long n = cb_connection_read(&conn);
    assert(n == (long)strlen(msg));
    assert(memcmp(conn.read_buf, msg, strlen(msg)) == 0);

    /* Server echoes it back. */
    assert(cb_connection_write(&conn, conn.read_buf, conn.read_len) == 0);

    /* Client reads the echo. */
    char buf[256];
    long got = cb_sock_read(client, buf, sizeof(buf));
    assert(got == (long)strlen(msg));
    assert(memcmp(buf, msg, strlen(msg)) == 0);

    /* Consume the read data. */
    cb_connection_consume(&conn, conn.read_len);
    assert(conn.read_len == 0);

    /* Clean up. */
    cb_connection_close(&conn);
    cb_sock_close(client);
    cb_listener_close(&l);

    cb_platform_finalize();
    printf("  listener + accept + read + write + echo: ok\n");
}

static void test_connection_close_releases_buffer(void)
{
    cb_connection c;
    memset(&c, 0, sizeof(c));
    assert(cb_connection_init(&c, CB_SOCKET_INVALID, 1024) == 0);
    assert(c.read_buf != NULL);
    /* With invalid socket, close should still free the buffer. */
    cb_connection_close(&c);
    assert(c.read_buf == NULL);
    assert(c.sock == CB_SOCKET_INVALID);
    printf("  connection close releases buffer: ok\n");
}

int main(void)
{
    printf("test_socket:\n");
    test_listener_accept_read_write();
    test_connection_close_releases_buffer();
    printf("ALL SOCKET TESTS PASSED\n");
    return 0;
}
