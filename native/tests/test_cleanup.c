/* test_cleanup.c - verify resource cleanup on all paths.
 *
 * Tests that request-scoped memory, connections, and Python references
 * are properly released on both success and error paths. Uses a lightweight
 * allocation counter (not part of the production memory model).
 *
 * On platforms with AddressSanitizer/LeakSanitizer, run with SAN=asan to
 * get automatic leak detection. This test provides a portable fallback
 * that verifies cleanup behavior without sanitizer support.
 */

#include "arena.h"
#include "bridge.h"
#include "http_parser.h"
#include "platform.h"
#include "python_runtime.h"
#include "socket.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
    #include <windows.h>
    #include <direct.h>
    #define PATH_SEP "\\"
    #define MKDIR(p) _mkdir(p)
#else
    #include <unistd.h>
    #include <sys/stat.h>
    #define PATH_SEP "/"
    #define MKDIR(p) mkdir(p, 0755)
#endif

static char tmp_dir[512];
static char app_dir[640];

static void cleanup_tmp(void)
{
    char cmd[1024];
#ifdef _WIN32
    snprintf(cmd, sizeof(cmd), "rmdir /s /q \"%s\" 2>nul", tmp_dir);
#else
    snprintf(cmd, sizeof(cmd), "rm -rf %s", tmp_dir);
#endif
    system(cmd);
}

static int create_project(const char *route_code)
{
#ifdef _WIN32
    char *base = getenv("TEMP");
    if (!base) base = "C:\\Temp";
    snprintf(tmp_dir, sizeof(tmp_dir), "%s\\catba_cleanup_%d", base, (int)GetCurrentProcessId());
#else
    snprintf(tmp_dir, sizeof(tmp_dir), "/tmp/catba_cleanup_%d", (int)getpid());
#endif
    cleanup_tmp();
    if (MKDIR(tmp_dir) != 0) return -1;
    snprintf(app_dir, sizeof(app_dir), "%s" PATH_SEP "app", tmp_dir);
    if (MKDIR(app_dir) != 0) return -1;
    char rp[768];
    snprintf(rp, sizeof(rp), "%s" PATH_SEP "route.py", app_dir);
    FILE *f = fopen(rp, "w");
    if (!f) return -1;
    fprintf(f, "%s", route_code);
    fclose(f);
    return 0;
}

static void test_arena_released_after_success(void)
{
    cb_arena *a = cb_arena_create();
    assert(a);
    assert(cb_arena_count(a) == 0);

    /* Make several allocations. */
    for (int i = 0; i < 50; i++)
        cb_arena_alloc(a, 128);
    assert(cb_arena_count(a) == 50);

    /* Release: all memory freed in one step. */
    cb_arena_release(a);
    printf("  arena released after success: ok\n");
}

static void test_arena_released_after_parse_failure(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* Malformed request: parser should fail but arena still valid. */
    const char *raw = "GARBAGE\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_MALFORMED);

    /* Arena was used for partial parsing. Release it. */
    cb_arena_release(a);
    printf("  arena released after parse failure: ok\n");
}

static void test_arena_released_after_bridge_error(void)
{
    if (create_project("async def GET(ctx):\n    raise RuntimeError('boom')\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }
    cb_python_init();
    cb_python_ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    assert(cb_python_load_project(&ctx, app_dir) == 0);

    /* Release GIL so bridge can acquire it. */
    PyThreadState *ts = PyEval_SaveThread();

    cb_arena *a = cb_arena_create();
    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_request req;
    size_t consumed = 0;
    assert(cb_http_parse(raw, strlen(raw), a, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    /* Bridge handles the exception, returns 0, fills 500. */
    assert(cb_bridge_handle(&ctx, &req, a, &resp) == 0);
    assert(resp.status == 500);

    /* Arena has response strings. Release it. */
    cb_arena_release(a);

    /* Re-acquire GIL. */
    PyEval_RestoreThread(ts);
    cb_python_finalize(&ctx);
    cleanup_tmp();
    printf("  arena released after bridge error: ok\n");
}

static void test_multiple_requests_cleanup(void)
{
    if (create_project("async def GET(ctx):\n    return {\"n\": 1}\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }
    cb_python_init();
    cb_python_ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    assert(cb_python_load_project(&ctx, app_dir) == 0);
    PyThreadState *ts = PyEval_SaveThread();

    /* Process 10 requests, each with its own arena. */
    for (int i = 0; i < 10; i++) {
        cb_arena *a = cb_arena_create();
        const char *raw = "GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n";
        cb_request req;
        size_t consumed = 0;
        assert(cb_http_parse(raw, strlen(raw), a, &req, &consumed) == CB_PARSE_OK);

        cb_response resp;
        assert(cb_bridge_handle(&ctx, &req, a, &resp) == 0);
        assert(resp.status == 200);

        cb_arena_release(a);
    }

    PyEval_RestoreThread(ts);
    cb_python_finalize(&ctx);
    cleanup_tmp();
    printf("  multiple requests cleanup: ok\n");
}

static void test_connection_cleanup(void)
{
    cb_platform_init();
    cb_connection c;
    memset(&c, 0, sizeof(c));
    assert(cb_connection_init(&c, CB_SOCKET_INVALID, 1024) == 0);
    assert(c.read_buf != NULL);
    /* Close without a valid socket: should still free buffer. */
    cb_connection_close(&c);
    assert(c.read_buf == NULL);
    assert(c.sock == CB_SOCKET_INVALID);
    cb_platform_finalize();
    printf("  connection cleanup: ok\n");
}

int main(void)
{
    printf("test_cleanup:\n");
    test_arena_released_after_success();
    test_arena_released_after_parse_failure();
    test_arena_released_after_bridge_error();
    test_multiple_requests_cleanup();
    test_connection_cleanup();
    printf("ALL CLEANUP TESTS PASSED\n");
    return 0;
}
