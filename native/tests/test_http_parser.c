/* test_http_parser.c - verify HTTP/1.1 request parsing. */

#include "http_parser.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_valid_get(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    const char *raw = "GET /users/42?page=2 HTTP/1.1\r\n"
                      "Host: localhost:8000\r\n"
                      "User-Agent: test/1.0\r\n"
                      "\r\n";
    size_t len = strlen(raw);

    cb_parse_result r = cb_http_parse(raw, len, a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    assert(consumed == len);
    assert(strcmp(req.method, "GET") == 0);
    assert(strcmp(req.path, "/users/42") == 0);
    assert(strcmp(req.query, "page=2") == 0);
    assert(strcmp(req.version, "HTTP/1.1") == 0);
    assert(req.header_count == 2);
    assert(strcmp(cb_request_header(&req, "Host"), "localhost:8000") == 0);
    assert(strcmp(cb_request_header(&req, "host"), "localhost:8000") == 0);
    assert(strcmp(cb_request_header(&req, "USER-AGENT"), "test/1.0") == 0);
    assert(req.content_length == -1);
    assert(req.body == NULL);
    assert(req.keep_alive == 1);

    cb_arena_release(a);
    printf("  valid GET: ok\n");
}

static void test_post_with_body(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    const char *body = "{\"name\":\"cat\"}";
    char raw[512];
    int n = snprintf(raw, sizeof(raw),
        "POST /users HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %zu\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s", strlen(body), body);
    assert(n > 0 && (size_t)n < sizeof(raw));

    cb_parse_result r = cb_http_parse(raw, (size_t)n, a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    assert(strcmp(req.method, "POST") == 0);
    assert(strcmp(req.path, "/users") == 0);
    assert(req.content_length == (long)strlen(body));
    assert(req.body_len == strlen(body));
    assert(strncmp(req.body, body, strlen(body)) == 0);
    assert(req.keep_alive == 0);

    cb_arena_release(a);
    printf("  POST with body: ok\n");
}

static void test_query_string_empty(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    assert(strcmp(req.path, "/") == 0);
    assert(strcmp(req.query, "") == 0);

    cb_arena_release(a);
    printf("  empty query: ok\n");
}

static void test_incomplete(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* Missing the final \r\n. */
    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_INCOMPLETE);

    cb_arena_release(a);
    printf("  incomplete: ok\n");
}

static void test_incomplete_body(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* Content-Length says 10 but only 5 bytes follow. */
    const char *raw = "POST / HTTP/1.1\r\nContent-Length: 10\r\n\r\nhello";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_INCOMPLETE);

    cb_arena_release(a);
    printf("  incomplete body: ok\n");
}

static void test_malformed(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* No method. */
    const char *raw = " / HTTP/1.1\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_MALFORMED);

    cb_arena_release(a);
    printf("  malformed (no method): ok\n");
}

static void test_malformed_no_colon(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* Header without a colon. */
    const char *raw = "GET / HTTP/1.1\r\nBadHeader\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_MALFORMED);

    cb_arena_release(a);
    printf("  malformed (no colon): ok\n");
}

static void test_cookie_header(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    const char *raw = "GET / HTTP/1.1\r\nCookie: sid=abc; theme=dark\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    const char *cookie = cb_request_header(&req, "Cookie");
    assert(cookie != NULL);
    assert(strstr(cookie, "sid=abc") != NULL);
    assert(strstr(cookie, "theme=dark") != NULL);

    cb_arena_release(a);
    printf("  cookie header: ok\n");
}

static void test_keep_alive_default(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    /* HTTP/1.1 without Connection header defaults to keep-alive. */
    const char *raw = "GET / HTTP/1.1\r\nHost: x\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    assert(req.keep_alive == 1);

    cb_arena_release(a);
    printf("  keep-alive default: ok\n");
}

static void test_connection_close(void)
{
    cb_arena *a = cb_arena_create();
    cb_request req;
    size_t consumed = 0;

    const char *raw = "GET / HTTP/1.1\r\nConnection: close\r\n\r\n";
    cb_parse_result r = cb_http_parse(raw, strlen(raw), a, &req, &consumed);
    assert(r == CB_PARSE_OK);
    assert(req.keep_alive == 0);

    cb_arena_release(a);
    printf("  connection close: ok\n");
}

int main(void)
{
    printf("test_http_parser:\n");
    test_valid_get();
    test_post_with_body();
    test_query_string_empty();
    test_incomplete();
    test_incomplete_body();
    test_malformed();
    test_malformed_no_colon();
    test_cookie_header();
    test_keep_alive_default();
    test_connection_close();
    printf("ALL HTTP PARSER TESTS PASSED\n");
    return 0;
}
