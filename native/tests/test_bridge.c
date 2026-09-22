/* test_bridge.c - verify the native-to-Python bridge. */

#include "bridge.h"
#include "python_runtime.h"
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
    #include <sys/stat.h>
    #include <unistd.h>
    #define PATH_SEP "/"
    #define MKDIR(p) mkdir(p, 0755)
#endif

static char tmp_dir[512];

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
    snprintf(tmp_dir, sizeof(tmp_dir), "%s\\catba_bridge_test_%d", base, (int)GetCurrentProcessId());
#else
    snprintf(tmp_dir, sizeof(tmp_dir), "/tmp/catba_bridge_test_%d", (int)getpid());
#endif
    cleanup_tmp();
    if (MKDIR(tmp_dir) != 0) return -1;

    char app_dir[600];
    snprintf(app_dir, sizeof(app_dir), "%s" PATH_SEP "app", tmp_dir);
    if (MKDIR(app_dir) != 0) return -1;

    char route_path[700];
    snprintf(route_path, sizeof(route_path), "%s" PATH_SEP "route.py", app_dir);
    FILE *f = fopen(route_path, "w");
    if (!f) return -1;
    fprintf(f, "%s", route_code);
    fclose(f);

    return 0;
}

static cb_python_ctx ctx;
static int ctx_loaded = 0;

static int setup(const char *route_code)
{
    if (create_project(route_code) != 0) return -1;
    if (cb_python_init() != 0) return -1;
    memset(&ctx, 0, sizeof(ctx));
    char app_dir[600];
    snprintf(app_dir, sizeof(app_dir), "%s" PATH_SEP "app", tmp_dir);
    if (cb_python_load_project(&ctx, app_dir) != 0) return -1;
    ctx_loaded = 1;
    return 0;
}

static void teardown(void)
{
    if (ctx_loaded) {
        cb_python_finalize(&ctx);
        ctx_loaded = 0;
    }
    cleanup_tmp();
}

/* Parse a raw request, call the bridge, and check the response. */
static void test_bridge_get_dict_page(void)
{
    /* Page route: dict -> PageData -> JSON with X-CatBa-Page header. */
    if (setup("async def GET(ctx):\n    return {\"message\": \"hello\"}\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }
    /* Also create page.tsx to make it a page route. */
    char page_path[700];
    snprintf(page_path, sizeof(page_path), "%s" PATH_SEP "app" PATH_SEP "page.tsx", tmp_dir);
    FILE *f = fopen(page_path, "w");
    if (f) { fprintf(f, "export default function Page() {}\n"); fclose(f); }

    cb_arena *arena = cb_arena_create();
    assert(arena);

    const char *raw = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n";
    cb_request req;
    size_t consumed;
    assert(cb_http_parse(raw, strlen(raw), arena, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    assert(cb_bridge_handle(&ctx, &req, arena, &resp) == 0);
    assert(resp.status == 200);
    assert(resp.body != NULL);
    assert(strstr(resp.body, "hello") != NULL);

    cb_arena_release(arena);
    teardown();
    printf("  bridge GET dict (page): ok\n");
}

static void test_bridge_get_api(void)
{
    /* API route: dict -> JSON response. */
    if (setup("async def GET(ctx):\n    return {\"api\": True}\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }

    cb_arena *arena = cb_arena_create();
    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_request req;
    size_t consumed;
    assert(cb_http_parse(raw, strlen(raw), arena, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    assert(cb_bridge_handle(&ctx, &req, arena, &resp) == 0);
    assert(resp.status == 200);
    assert(strstr(resp.body, "api") != NULL);

    cb_arena_release(arena);
    teardown();
    printf("  bridge GET dict (api): ok\n");
}

static void test_bridge_post_body(void)
{
    if (setup("async def POST(ctx):\n    return {\"echo\": ctx.body}\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }

    cb_arena *arena = cb_arena_create();
    const char *body = "{\"name\":\"cat\"}";
    char raw[512];
    int n = snprintf(raw, sizeof(raw),
        "POST / HTTP/1.1\r\n"
        "Host: x\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %zu\r\n"
        "\r\n%s", strlen(body), body);

    cb_request req;
    size_t consumed;
    assert(cb_http_parse(raw, (size_t)n, arena, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    assert(cb_bridge_handle(&ctx, &req, arena, &resp) == 0);
    assert(resp.status == 200);
    assert(strstr(resp.body, "cat") != NULL);

    cb_arena_release(arena);
    teardown();
    printf("  bridge POST body: ok\n");
}

static void test_bridge_404(void)
{
    if (setup("async def GET(ctx):\n    return {}\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }

    cb_arena *arena = cb_arena_create();
    const char *raw = "GET /nonexistent HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_request req;
    size_t consumed;
    assert(cb_http_parse(raw, strlen(raw), arena, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    assert(cb_bridge_handle(&ctx, &req, arena, &resp) == 0);
    assert(resp.status == 404);

    cb_arena_release(arena);
    teardown();
    printf("  bridge 404: ok\n");
}

static void test_bridge_500(void)
{
    if (setup("async def GET(ctx):\n    raise RuntimeError('boom')\n") != 0) {
        printf("  [skipped: setup failed]\n");
        return;
    }

    cb_arena *arena = cb_arena_create();
    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_request req;
    size_t consumed;
    assert(cb_http_parse(raw, strlen(raw), arena, &req, &consumed) == CB_PARSE_OK);

    cb_response resp;
    assert(cb_bridge_handle(&ctx, &req, arena, &resp) == 0);
    assert(resp.status == 500);

    cb_arena_release(arena);
    teardown();
    printf("  bridge 500: ok\n");
}

int main(void)
{
    printf("test_bridge:\n");
    test_bridge_get_dict_page();
    test_bridge_get_api();
    test_bridge_post_body();
    test_bridge_404();
    test_bridge_500();
    printf("ALL BRIDGE TESTS PASSED\n");
    return 0;
}
