/* test_python_runtime.c - verify CPython embedding init, project load, finalize. */

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
    /* Best-effort cleanup of the temp directory. */
    char cmd[1024];
#ifdef _WIN32
    snprintf(cmd, sizeof(cmd), "rmdir /s /q \"%s\" 2>nul", tmp_dir);
#else
    snprintf(cmd, sizeof(cmd), "rm -rf %s", tmp_dir);
#endif
    system(cmd);
}

static int create_test_project(void)
{
    /* Create a temp directory with app/route.py. */
#ifdef _WIN32
    char *base = getenv("TEMP");
    if (!base) base = getenv("TMP");
    if (!base) base = "C:\\Temp";
    snprintf(tmp_dir, sizeof(tmp_dir), "%s\\catba_native_test_%d", base, (int)GetCurrentProcessId());
#else
    snprintf(tmp_dir, sizeof(tmp_dir), "/tmp/catba_native_test_%d", (int)getpid());
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
    fprintf(f, "async def GET(ctx):\n    return {\"message\": \"hello from native\"}\n");
    fclose(f);

    char page_path[700];
    snprintf(page_path, sizeof(page_path), "%s" PATH_SEP "page.tsx", app_dir);
    f = fopen(page_path, "w");
    if (!f) return -1;
    fprintf(f, "export default function Page() { return null }\n");
    fclose(f);

    return 0;
}

static void test_init_finalize(void)
{
    assert(cb_python_init() == 0);
    assert(Py_IsInitialized());
    printf("  python init: ok\n");

    Py_Finalize();
    assert(!Py_IsInitialized());
    printf("  python finalize: ok\n");
}

static void test_load_project(void)
{
    assert(cb_python_init() == 0);

    assert(create_test_project() == 0);
    char app_dir[600];
    snprintf(app_dir, sizeof(app_dir), "%s" PATH_SEP "app", tmp_dir);

    cb_python_ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    assert(cb_python_load_project(&ctx, app_dir) == 0);
    assert(ctx.app != NULL);
    assert(ctx.handle != NULL);
    assert(ctx.to_http != NULL);
    assert(ctx.initialized == 1);

    printf("  load project: ok\n");

    cb_python_finalize(&ctx);
    assert(ctx.app == NULL);
    assert(ctx.handle == NULL);
    assert(ctx.to_http == NULL);

    printf("  finalize after load: ok\n");

    cleanup_tmp();
}

int main(void)
{
    printf("test_python_runtime:\n");
    test_init_finalize();
    test_load_project();
    printf("ALL PYTHON RUNTIME TESTS PASSED\n");
    return 0;
}
