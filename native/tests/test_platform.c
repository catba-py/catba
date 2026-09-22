/* test_platform.c - verify the platform abstraction compiles and links. */

#include "platform.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    assert(cb_platform_init() == 0);
    printf("platform init: ok\n");

    /* Create a TCP socket, close it. */
    cb_socket_t sock = socket(AF_INET, SOCK_STREAM, 0);
    assert(sock != CB_SOCKET_INVALID);

    int rc = cb_sock_set_reuseaddr(sock);
    assert(rc == 0);
    printf("set_reuseaddr: ok\n");

    rc = cb_sock_close(sock);
    assert(rc == 0);
    printf("close: ok\n");

    /* Error code is accessible. */
    int err = cb_sock_last_error();
    (void)err;  /* just verify the function exists */

    cb_platform_finalize();
    printf("platform finalize: ok\n");
    printf("ALL PLATFORM TESTS PASSED\n");
    return 0;
}
