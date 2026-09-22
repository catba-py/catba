/* http_parser.h - HTTP/1.1 request parser with strict size limits.
 *
 * Parses a raw HTTP/1.1 request from a buffer into a structured request.
 * All parsed strings are arena-allocated and owned by the request arena.
 * Borrowed pointers into the arena are valid until arena_release().
 *
 * The parser does NOT do socket I/O. It consumes a complete or partial
 * raw buffer and reports how many bytes it consumed.
 */

#ifndef CATBA_HTTP_PARSER_H
#define CATBA_HTTP_PARSER_H

#include "arena.h"
#include <stddef.h>

/* --- configurable size limits --- */

#define CB_MAX_REQUEST_LINE 8192    /* max bytes in the request line */
#define CB_MAX_HEADER_COUNT 100     /* max number of headers */
#define CB_MAX_HEADER_BLOCK 65536   /* max bytes in the total header block */
#define CB_MAX_BODY_SIZE    (10 * 1024 * 1024)  /* max request body: 10 MB */

/* --- parsed header --- */

typedef struct {
    const char *name;   /* arena-owned, original casing */
    const char *value;  /* arena-owned */
} cb_header;

/* --- parsed request --- */

typedef struct {
    const char *method;    /* arena-owned, e.g. "GET" */
    const char *path;      /* arena-owned, e.g. "/users/42" */
    const char *query;     /* arena-owned, e.g. "page=2&q=x", or "" */
    const char *version;   /* arena-owned, e.g. "HTTP/1.1" */

    cb_header *headers;    /* arena-owned array */
    int header_count;
    int header_cap;

    const char *body;      /* arena-owned, or NULL if no body */
    size_t body_len;
    long content_length;  /* -1 if no Content-Length header */

    int keep_alive;       /* 1 if Connection: keep-alive, 0 if close */
} cb_request;

/* --- parse result --- */

typedef enum {
    CB_PARSE_OK = 0,
    CB_PARSE_INCOMPLETE,     /* need more data */
    CB_PARSE_MALFORMED,      /* the request is invalid */
    CB_PARSE_TOO_LARGE,      /* exceeded a size limit */
} cb_parse_result;

/* Parse a raw HTTP/1.1 request from a buffer.
 *
 * Parameters:
 *   buf      - raw request bytes
 *   len      - number of bytes in buf
 *   arena    - request arena (owns all parsed strings)
 *   req      - output: filled on success
 *   consumed - output: number of bytes consumed from buf
 *
 * Returns CB_PARSE_OK, CB_PARSE_INCOMPLETE, CB_PARSE_MALFORMED, or
 * CB_PARSE_TOO_LARGE. On non-OK results, `req` may be partially filled
 * but all its pointers are arena-owned and freed by arena_release().
 */
cb_parse_result cb_http_parse(const char *buf, size_t len,
                              cb_arena *arena, cb_request *req,
                              size_t *consumed);

/* Look up a header by name (case-insensitive). Returns the value or NULL. */
const char *cb_request_header(const cb_request *req, const char *name);

#endif /* CATBA_HTTP_PARSER_H */
