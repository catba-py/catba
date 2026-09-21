"""Response primitives: Response, JSON, Redirect, and HTTP errors.

These are the public response objects route handlers return. They are
representations, not a template or renderer system. Each one knows how to
serialize to ``(status, headers, body_bytes)`` via ``to_http()``.
"""

import json


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def _has_header(headers, name):
    return name.lower() in {k.lower() for k in headers}


class Response:
    """A raw HTTP response: explicit status, headers, body."""

    def __init__(self, body="", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = dict(headers) if headers else {}

    def to_http(self):
        headers = dict(self.headers)
        if not _has_header(headers, "Content-Type"):
            headers["Content-Type"] = "text/plain; charset=utf-8"
        body = _to_bytes(self.body)
        headers["Content-Length"] = str(len(body))
        return self.status, headers, body


class JSON:
    """A JSON response. ``data`` is serialized with ``json.dumps``."""

    def __init__(self, data, status=200, headers=None):
        self.data = data
        self.status = status
        self.headers = dict(headers) if headers else {}

    def to_http(self):
        body = json.dumps(self.data).encode("utf-8")
        headers = dict(self.headers)
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return self.status, headers, body


class Redirect:
    """An HTTP redirect. Default status 303 See Other."""

    def __init__(self, location, status=303):
        self.location = location
        self.status = status

    def to_http(self):
        return self.status, {"Location": self.location, "Content-Length": "0"}, b""


class HTTPError(Exception):
    """Base for HTTP errors raised by application code.

    Raising a typed HTTPError lets the framework map an exception to a
    response with the correct status code without the handler building the
    response by hand.
    """

    def __init__(self, status, message=""):
        self.status = status
        self.message = message or f"HTTP {status}"
        super().__init__(self.message)


class BadRequest(HTTPError):
    def __init__(self, message="Bad Request"):
        super().__init__(400, message)


class NotFound(HTTPError):
    def __init__(self, message="Not Found"):
        super().__init__(404, message)


class MethodNotAllowed(HTTPError):
    def __init__(self, allowed=None, message="Method Not Allowed"):
        super().__init__(405, message)
        self.allowed = list(allowed) if allowed else []


class InternalServerError(HTTPError):
    def __init__(self, message="Internal Server Error"):
        super().__init__(500, message)
