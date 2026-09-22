/* test_integration.c - end-to-end HTTP tests against the native server.
 *
 * Starts the native server on a background thread, then sends real HTTP
 * requests via a client socket and checks the responses. This exercises
 * the full pipeline: socket -> parser -> bridge -> Python Core -> serializer
 * -> socket.
 */

#ifdef __GNUC__
    #pragma GCC diagnostic ignored "-Wformat-truncation"
#endif

#include "arena.h"
#include "bridge.h"
#include "http_parser.h"
#include "platform.h"
#include "python_runtime.h"
#include "server.h"
#include "serializer.h"
#include "socket.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
    #include <windows.h>
    #include <direct.h>
    #include <process.h>
    #define PATH_SEP "\\"
    #define MKDIR(p) _mkdir(p)
    typedef HANDLE thread_t;
    #define THREAD_RET DWORD WINAPI
    static thread_t thread_create(THREAD_RET (*fn)(LPVOID), void *arg) {
        return CreateThread(NULL, 0, fn, arg, 0, NULL);
    }
#else
    #include <pthread.h>
    #include <unistd.h>
    #include <sys/stat.h>
    #define PATH_SEP "/"
    #define MKDIR(p) mkdir(p, 0755)
    typedef pthread_t thread_t;
    #define THREAD_RET void *
    static thread_t thread_create(THREAD_RET (*fn)(void *), void *arg) {
        thread_t t; pthread_create(&t, NULL, fn, arg); return t;
    }
#endif

static char tmp_dir[512];
static char app_dir[1024];
static char udir[1024];
static char iddir[1024];
static char medir[1024];
static cb_python_ctx g_ctx;
static int g_port;

/* Build a test project with various routes. */
static int create_project(void)
{
#ifdef _WIN32
    char *base = getenv("TEMP");
    if (!base) base = "C:\\Temp";
    snprintf(tmp_dir, sizeof(tmp_dir), "%s\\catba_integ_%d", base, (int)GetCurrentProcessId());
#else
    snprintf(tmp_dir, sizeof(tmp_dir), "/tmp/catba_integ_%d", (int)getpid());
#endif
    char cmd[1024];
#ifdef _WIN32
    snprintf(cmd, sizeof(cmd), "rmdir /s /q \"%s\" 2>nul", tmp_dir);
#else
    snprintf(cmd, sizeof(cmd), "rm -rf %s", tmp_dir);
#endif
    system(cmd);
    if (MKDIR(tmp_dir) != 0) return -1;

    snprintf(app_dir, sizeof(app_dir), "%s" PATH_SEP "app", tmp_dir);
    if (MKDIR(app_dir) != 0) return -1;
    snprintf(udir, sizeof(udir), "%s" PATH_SEP "users", app_dir);
    if (MKDIR(udir) != 0) return -1;
    snprintf(iddir, sizeof(iddir), "%s" PATH_SEP "[id]", udir);
    if (MKDIR(iddir) != 0) return -1;

    /* app/route.py: page route with GET and POST. */
    char p[1024]; snprintf(p, sizeof(p), "%s" PATH_SEP "route.py", app_dir);
    FILE *f = fopen(p, "w"); if (!f) return -1;
    fprintf(f,
        "async def GET(ctx):\n"
        "    return {\"message\": \"Hello, CatBa\"}\n"
        "async def POST(ctx):\n"
        "    return {\"received\": ctx.body}\n"
    );
    fclose(f);
    snprintf(p, sizeof(p), "%s" PATH_SEP "page.tsx", app_dir);
    f = fopen(p, "w"); if (!f) return -1;
    fprintf(f, "export default function Page() {}\n");
    fclose(f);

    /* app/users/[id]/route.py: dynamic route. */
    snprintf(p, sizeof(p), "%s" PATH_SEP "route.py", iddir);
    f = fopen(p, "w"); if (!f) return -1;
    fprintf(f,
        "async def GET(ctx):\n"
        "    return {\"id\": ctx.params[\"id\"]}\n"
    );
    fclose(f);

    /* app/users/me/route.py: static beats dynamic. */
    snprintf(medir, sizeof(medir), "%s" PATH_SEP "me", udir);
    if (MKDIR(medir) != 0) return -1;
    snprintf(p, sizeof(p), "%s" PATH_SEP "route.py", medir);
    f = fopen(p, "w"); if (!f) return -1;
    fprintf(f, "async def GET(ctx):\n    return {\"static\": True}\n");
    fclose(f);

    return 0;
}

/* Server thread function. */
static THREAD_RET server_thread(void *arg)
{
    (void)arg;
    cb_server_run(&g_ctx, "127.0.0.1", g_port);
    return 0;
}

/* Send a raw HTTP request and read the response. */
static int send_request(const char *raw, size_t raw_len, char *resp_buf, size_t resp_cap)
{
    cb_platform_init();
    cb_socket_t sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == CB_SOCKET_INVALID) return -1;

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)g_port);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        cb_sock_close(sock);
        return -1;
    }

    if (cb_sock_write(sock, raw, raw_len) < 0) {
        cb_sock_close(sock);
        return -1;
    }

    /* Read response. */
    size_t total = 0;
    while (total < resp_cap - 1) {
        long n = cb_sock_read(sock, resp_buf + total, resp_cap - 1 - total);
        if (n <= 0) break;
        total += (size_t)n;
    }
    resp_buf[total] = '\0';
    cb_sock_close(sock);
    cb_platform_finalize();
    return (int)total;
}

/* Check if a response contains a substring. */
static int contains(const char *hay, const char *needle)
{
    return strstr(hay, needle) != NULL;
}

/* Check HTTP status line. */
static int has_status(const char *resp, int status)
{
    char line[32];
    snprintf(line, sizeof(line), "HTTP/1.1 %d", status);
    return strstr(resp, line) != NULL;
}

static void test_get_root(void)
{
    char resp[4096];
    const char *req = "GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 200));
    assert(contains(resp, "Hello, CatBa"));
    printf("  GET /: ok\n");
}

static void test_get_dynamic(void)
{
    char resp[4096];
    const char *req = "GET /users/42 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 200));
    assert(contains(resp, "42"));
    printf("  GET /users/42: ok\n");
}

static void test_post_root(void)
{
    char resp[4096];
    const char *body = "{\"test\": true}";
    char req[512];
    int n = snprintf(req, sizeof(req),
        "POST / HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
        "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
        strlen(body), body);
    int rn = send_request(req, (size_t)n, resp, sizeof(resp));
    assert(rn > 0);
    assert(has_status(resp, 200));
    assert(contains(resp, "test"));
    printf("  POST /: ok\n");
}

static void test_404(void)
{
    char resp[4096];
    const char *req = "GET /nonexistent HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 404));
    printf("  404: ok\n");
}

static void test_405(void)
{
    char resp[4096];
    const char *req = "DELETE / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 405));
    assert(contains(resp, "Allow"));
    printf("  405: ok\n");
}

static void test_head(void)
{
    char resp[4096];
    const char *req = "HEAD / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 200));
    /* HEAD should not have a body. */
    /* Find the end of headers. */
    const char *body_start = strstr(resp, "\r\n\r\n");
    if (body_start) {
        body_start += 4;
        assert(*body_start == '\0' || strlen(body_start) == 0);
    }
    printf("  HEAD: ok\n");
}

static void test_options(void)
{
    char resp[4096];
    const char *req = "OPTIONS / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 200));
    assert(contains(resp, "Allow"));
    printf("  OPTIONS: ok\n");
}

static void test_static_beats_dynamic(void)
{
    char resp[4096];
    const char *req = "GET /users/me HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    assert(n > 0);
    assert(has_status(resp, 200));
    assert(contains(resp, "static"));
    assert(!contains(resp, "\"id\": \"me\""));
    printf("  static beats dynamic: ok\n");
}

static void test_malformed_no_crash(void)
{
    char resp[4096];
    const char *req = "GARBAGE\r\n\r\n";
    int n = send_request(req, strlen(req), resp, sizeof(resp));
    /* Should get a 400 or connection close, but must not crash the server. */
    assert(n >= 0);
    if (n > 0) {
        assert(has_status(resp, 400) || has_status(resp, 404) || has_status(resp, 500));
    }
    printf("  malformed (no crash): ok\n");
}

int main(void)
{
    printf("test_integration:\n");

    if (create_project() != 0) {
        printf("  [skipped: cannot create test project]\n");
        return 0;
    }

    cb_python_init();
    memset(&g_ctx, 0, sizeof(g_ctx));
    if (cb_python_load_project(&g_ctx, app_dir) != 0) {
        printf("  [skipped: cannot load project]\n");
        return 0;
    }

    /* Release the GIL so the server thread can acquire it via PyGILState. */
    PyThreadState *main_thread = PyEval_SaveThread();

    /* Use a fixed port. */
    g_port = 18099;

    /* Start server on a background thread. */
    thread_t t = thread_create(server_thread, NULL);
    (void)t;
    /* Give the server time to bind. */
#ifdef _WIN32
    Sleep(500);
#else
    usleep(500000);
#endif

    test_get_root();
    test_get_dynamic();
    test_post_root();
    test_404();
    test_405();
    test_head();
    test_options();
    test_static_beats_dynamic();
    test_malformed_no_crash();

    /* Re-acquire the GIL before finalizing Python. */
    PyEval_RestoreThread(main_thread);

    /* Cleanup. */
    cb_python_finalize(&g_ctx);
    char cmd[2048];
#ifdef _WIN32
    snprintf(cmd, sizeof(cmd), "rmdir /s /q \"%s\" 2>nul", tmp_dir);
#else
    snprintf(cmd, sizeof(cmd), "rm -rf %s", tmp_dir);
#endif
    system(cmd);

    printf("ALL INTEGRATION TESTS PASSED\n");
    return 0;
}
