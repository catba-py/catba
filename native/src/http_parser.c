/* http_parser.c - HTTP/1.1 request parser implementation.
 *
 * Parses a raw HTTP/1.1 request from a buffer. All parsed strings are
 * arena-allocated copies. The parser enforces strict size limits to reject
 * pathological input.
 */

#include "http_parser.h"

#include <string.h>
#include <stdlib.h>

/* Find the first occurrence of needle in buf, scanning up to len bytes.
 * Returns the index or -1 if not found. */
static long find_bytes(const char *buf, size_t len, const char *needle, size_t needle_len)
{
    if (len < needle_len)
        return -1;
    for (size_t i = 0; i <= len - needle_len; i++) {
        if (memcmp(buf + i, needle, needle_len) == 0)
            return (long)i;
    }
    return -1;
}

/* Find the end of the header block (\r\n\r\n). Returns the index of the
 * first \r of the terminating \r\n\r\n, or -1 if not found. */
static long find_header_end(const char *buf, size_t len)
{
    return find_bytes(buf, len, "\r\n\r\n", 4);
}

/* Skip leading and trailing whitespace. Returns a pointer into buf. */
static const char *trim(const char *start, const char *end, const char **out_end)
{
    while (start < end && (*start == ' ' || *start == '\t'))
        start++;
    const char *e = end;
    while (e > start && (e[-1] == ' ' || e[-1] == '\t'))
        e--;
    *out_end = e;
    return start;
}

/* Parse the request line: METHOD SP TARGET SP VERSION\r\n
 * Returns 0 on success, -1 on malformed. */
static int parse_request_line(const char *line, size_t len,
                              cb_arena *arena, cb_request *req)
{
    /* Find first space (end of method). */
    long sp1 = -1;
    for (size_t i = 0; i < len; i++) {
        if (line[i] == ' ') {
            sp1 = (long)i;
            break;
        }
    }
    if (sp1 < 1)
        return -1;

    /* Find second space (end of target). */
    long sp2 = -1;
    for (size_t i = (size_t)sp1 + 1; i < len; i++) {
        if (line[i] == ' ') {
            sp2 = (long)i;
            break;
        }
    }
    if (sp2 < 0 || sp2 <= sp1 + 1)
        return -1;

    /* Version is the rest. */
    size_t vlen = len - (size_t)sp2 - 1;
    if (vlen < 5)
        return -1;
    if (memcmp(line + sp2 + 1, "HTTP/", 5) != 0)
        return -1;

    /* Copy method, target, version into the arena. */
    req->method = cb_arena_dup(arena, line, (size_t)sp1);
    if (!req->method)
        return -1;

    /* Split target into path and query. */
    const char *target = line + sp1 + 1;
    size_t tlen = (size_t)(sp2 - sp1 - 1);

    long qi = -1;
    for (size_t i = 0; i < tlen; i++) {
        if (target[i] == '?') {
            qi = (long)i;
            break;
        }
    }

    if (qi >= 0) {
        req->path = cb_arena_dup(arena, target, (size_t)qi);
        req->query = cb_arena_dup(arena, target + qi + 1, tlen - (size_t)qi - 1);
    } else {
        req->path = cb_arena_dup(arena, target, tlen);
        req->query = cb_arena_dup_str(arena, "");
    }
    if (!req->path || !req->query)
        return -1;

    req->version = cb_arena_dup(arena, line + sp2 + 1, vlen);
    if (!req->version)
        return -1;

    return 0;
}

/* Add a header to the request. Returns 0 on success, -1 on failure. */
static int add_header(cb_arena *arena, cb_request *req,
                      const char *name, size_t name_len,
                      const char *value, size_t value_len)
{
    if (req->header_count >= CB_MAX_HEADER_COUNT)
        return -1;

    /* Grow the array if needed. */
    if (req->header_count >= req->header_cap) {
        int new_cap = req->header_cap == 0 ? 16 : req->header_cap * 2;
        if (new_cap > CB_MAX_HEADER_COUNT)
            new_cap = CB_MAX_HEADER_COUNT;
        cb_header *arr = (cb_header *)cb_arena_calloc(arena, (size_t)new_cap,
                                                       sizeof(cb_header));
        if (!arr)
            return -1;
        if (req->header_count > 0)
            memcpy(arr, req->headers, (size_t)req->header_count * sizeof(cb_header));
        req->headers = arr;
        req->header_cap = new_cap;
    }

    cb_header *h = &req->headers[req->header_count];
    h->name = cb_arena_dup(arena, name, name_len);
    h->value = cb_arena_dup(arena, value, value_len);
    if (!h->name || !h->value)
        return -1;

    req->header_count++;
    return 0;
}

/* Parse headers from the buffer, starting after the request line.
 * `hdr_start` points to the first header line, `hdr_end` points to the
 * \r\n that terminates the header block (the first \r of \r\n\r\n).
 * Returns 0 on success, -1 on malformed. */
static int parse_headers(const char *hdr_start, const char *hdr_end,
                         cb_arena *arena, cb_request *req)
{
    const char *p = hdr_start;
    while (p < hdr_end) {
        /* Find end of this header line. */
        const char *line_end = p;
        while (line_end < hdr_end && memcmp(line_end, "\r\n", 2) != 0)
            line_end++;
        if (line_end >= hdr_end)
            break;

        /* Find the colon separating name and value. */
        const char *colon = p;
        while (colon < line_end && *colon != ':')
            colon++;
        if (colon >= line_end)
            return -1;  /* no colon in header line */

        /* Trim name and value. */
        const char *name_end;
        const char *name = trim(p, colon, &name_end);
        const char *val_end;
        const char *value = trim(colon + 1, line_end, &val_end);

        size_t name_len = (size_t)(name_end - name);
        size_t val_len = (size_t)(val_end - value);

        if (name_len == 0)
            return -1;

        if (add_header(arena, req, name, name_len, value, val_len) != 0)
            return -1;

        p = line_end + 2;  /* skip \r\n */
    }
    return 0;
}

/* Process special headers: Content-Length and Connection. */
static void process_special_headers(cb_request *req)
{
    req->content_length = -1;
    req->keep_alive = 1;  /* HTTP/1.1 defaults to keep-alive */

    const char *cl = cb_request_header(req, "Content-Length");
    if (cl) {
        /* Parse as long. Simple manual parse to avoid atoi issues. */
        long val = 0;
        const char *p = cl;
        while (*p >= '0' && *p <= '9') {
            if (val > (LONG_MAX - (*p - '0')) / 10)
                return;  /* overflow: leave as -1 */
            val = val * 10 + (*p - '0');
            p++;
        }
        if (*p == '\0' && p != cl)
            req->content_length = val;
    }

    const char *conn = cb_request_header(req, "Connection");
    if (conn) {
        /* Case-insensitive comparison. */
        if (strcasecmp(conn, "close") == 0)
            req->keep_alive = 0;
        else if (strcasecmp(conn, "keep-alive") == 0)
            req->keep_alive = 1;
    }
}

cb_parse_result cb_http_parse(const char *buf, size_t len,
                              cb_arena *arena, cb_request *req,
                              size_t *consumed)
{
    *consumed = 0;
    memset(req, 0, sizeof(*req));
    req->content_length = -1;

    if (len == 0)
        return CB_PARSE_INCOMPLETE;

    /* Find the end of the header block. */
    long hdr_end_idx = find_header_end(buf, len);
    if (hdr_end_idx < 0) {
        /* Not enough data yet, or request too large. */
        if (len > CB_MAX_HEADER_BLOCK)
            return CB_PARSE_TOO_LARGE;
        return CB_PARSE_INCOMPLETE;
    }

    size_t hdr_block_size = (size_t)hdr_end_idx + 4;
    if (hdr_block_size > CB_MAX_HEADER_BLOCK)
        return CB_PARSE_TOO_LARGE;

    /* Find the request line end (first \r\n). */
    long line_end_idx = find_bytes(buf, (size_t)hdr_end_idx, "\r\n", 2);
    if (line_end_idx < 0)
        return CB_PARSE_MALFORMED;

    if ((size_t)line_end_idx > CB_MAX_REQUEST_LINE)
        return CB_PARSE_TOO_LARGE;

    /* Parse the request line. */
    if (parse_request_line(buf, (size_t)line_end_idx, arena, req) != 0)
        return CB_PARSE_MALFORMED;

    /* Parse headers (from after request line to the end of header block).
     * hdr_end_idx points at the first \r of \r\n\r\n. The last header's
     * terminating \r\n is the first \r\n of that \r\n\r\n, so the parse
     * range must include it. */
    const char *hdr_start = buf + line_end_idx + 2;
    const char *hdr_end = buf + hdr_end_idx + 2;  /* include last header \r\n */
    if (parse_headers(hdr_start, hdr_end, arena, req) != 0)
        return CB_PARSE_MALFORMED;

    /* Process Content-Length and Connection. */
    process_special_headers(req);

    /* Capture body if Content-Length is present. */
    size_t body_start = hdr_block_size;
    if (req->content_length > 0) {
        if ((size_t)req->content_length > CB_MAX_BODY_SIZE)
            return CB_PARSE_TOO_LARGE;

        size_t need = body_start + (size_t)req->content_length;
        if (len < need)
            return CB_PARSE_INCOMPLETE;  /* need more data */

        req->body = cb_arena_dup(arena, buf + body_start, (size_t)req->content_length);
        if (!req->body)
            return CB_PARSE_MALFORMED;
        req->body_len = (size_t)req->content_length;
        *consumed = need;
    } else {
        req->body = NULL;
        req->body_len = 0;
        *consumed = body_start;
    }

    return CB_PARSE_OK;
}

const char *cb_request_header(const cb_request *req, const char *name)
{
    for (int i = 0; i < req->header_count; i++) {
        if (strcasecmp(req->headers[i].name, name) == 0)
            return req->headers[i].value;
    }
    return NULL;
}
