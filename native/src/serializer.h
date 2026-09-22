/* serializer.h - serialize a cb_response into HTTP wire format.
 *
 * Converts the bridge's cb_response (status, headers, body) into a raw
 * HTTP/1.1 response and writes it to a connection. This is the final
 * step in the native request path: Python Core result -> native serializer
 * -> wire.
 */

#ifndef CATBA_SERIALIZER_H
#define CATBA_SERIALIZER_H

#include "bridge.h"
#include "socket.h"

/* Serialize a response to the connection. Returns 0 on success, -1 on error. */
int cb_serializer_write(cb_connection *conn, const cb_response *resp, int head_only);

/* Send a bare error response (for parse failures before the bridge runs). */
int cb_serializer_send_error(cb_connection *conn, int status, const char *reason);

#endif /* CATBA_SERIALIZER_H */
