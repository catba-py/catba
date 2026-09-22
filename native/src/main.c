/* main.c - native server entry point.
 *
 * Initializes Python, loads the CatBa Core for the project, and runs
 * the native server. The project root is discovered by calling the Python
 * Core's find_project_root, so project discovery logic stays in Python.
 *
 * Usage:
 *   catba-native --app-dir <path> [--host 127.0.0.1] [--port 8000]
 *
 * The app-dir is the "app/" directory of a CatBa project.
 */

#include "python_runtime.h"
#include "server.h"

#include <Python.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
    #include <windows.h>
#else
    #include <unistd.h>
    #include <signal.h>
#endif

static void usage(const char *prog)
{
    fprintf(stderr, "usage: %s --app-dir <path> [--host 127.0.0.1] [--port 8000]\n", prog);
}

int main(int argc, char **argv)
{
    const char *app_dir = NULL;
    const char *host = "127.0.0.1";
    int port = 8000;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--app-dir") == 0 && i + 1 < argc) {
            app_dir = argv[++i];
        } else if (strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
            host = argv[++i];
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            port = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        }
    }

    if (!app_dir) {
        fprintf(stderr, "catba: --app-dir is required\n");
        usage(argv[0]);
        return 1;
    }

    /* Initialize Python. */
    if (cb_python_init() != 0) {
        fprintf(stderr, "catba: cannot initialize Python\n");
        return 1;
    }

    /* Load the CatBa Core for this project. */
    cb_python_ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    if (cb_python_load_project(&ctx, app_dir) != 0) {
        fprintf(stderr, "catba: cannot load project at %s\n", app_dir);
        cb_python_finalize(&ctx);
        return 1;
    }

    /* Run the server (blocks). */
    int rc = cb_server_run(&ctx, host, port);

    /* Clean shutdown. */
    cb_python_finalize(&ctx);
    return rc;
}
