/* serializer.c - serialize a cb_response into HTTP/1.1 wire format. */

#include "serializer.h"

#include <stdio.h>
#include <string.h>

static const char *status_text(int status)
{
    switch (status) {
    case 200: return "OK";
    case 201: return "Created";
    case 204: return "No Content";
    case 303: return "See Other";
    case 400: return "Bad Request";
    case 404: return "Not Found";
    case 405: return "Method Not Allowed";
    case 500: return "Internal Server Error";
    default: return "Unknown";
    }
}

int cb_serializer_write(cb_connection *conn, const cb_response *resp, int head_only)
{
    /* Build the status line + headers into a buffer, then write. */
    /* Use a stack buffer for the header block; the body is written separately. */
    char header_buf[8192];
    int pos = 0;

    /* Status line. */
    pos += snprintf(header_buf + pos, sizeof(header_buf) - pos,
                    "HTTP/1.1 %d %s\r\n", resp->status, status_text(resp->status));

    /* Headers from the response. */
    for (int i = 0; i < resp->header_count && pos < (int)sizeof(header_buf) - 128; i++) {
        if (resp->header_names[i] && resp->header_values[i]) {
            pos += snprintf(header_buf + pos, sizeof(header_buf) - pos,
                            "%s: %s\r\n", resp->header_names[i], resp->header_values[i]);
        }
    }

    /* End of headers. */
    pos += snprintf(header_buf + pos, sizeof(header_buf) - pos, "\r\n");

    /* Write the header block. */
    if (cb_connection_write(conn, header_buf, (size_t)pos) != 0)
        return -1;

    /* Write the body (unless HEAD). */
    if (!head_only && resp->body && resp->body_len > 0) {
        if (cb_connection_write(conn, resp->body, resp->body_len) != 0)
            return -1;
    }

    return 0;
}

int cb_serializer_send_error(cb_connection *conn, int status, const char *reason)
{
    char body[256];
    int body_len = snprintf(body, sizeof(body), "%s\r\n", reason);

    char header[512];
    int pos = 0;
    pos += snprintf(header + pos, sizeof(header) - pos,
                    "HTTP/1.1 %d %s\r\n", status, status_text(status));
    pos += snprintf(header + pos, sizeof(header) - pos,
                    "Content-Type: text/plain; charset=utf-8\r\n");
    pos += snprintf(header + pos, sizeof(header) - pos,
                    "Content-Length: %d\r\n", body_len);
    pos += snprintf(header + pos, sizeof(header) - pos,
                    "Connection: close\r\n\r\n");

    if (cb_connection_write(conn, header, (size_t)pos) != 0)
        return -1;
    if (cb_connection_write(conn, body, (size_t)body_len) != 0)
        return -1;
    return 0;
}
