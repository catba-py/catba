"""CatBa: a Python web framework and runtime."""

__version__ = "0.1.0"

from catba.response import (
    BadRequest,
    HTTPError,
    InternalServerError,
    JSON,
    MethodNotAllowed,
    NotFound,
    Redirect,
    Response,
)

__all__ = [
    "__version__",
    "Response",
    "JSON",
    "Redirect",
    "HTTPError",
    "NotFound",
    "MethodNotAllowed",
    "BadRequest",
    "InternalServerError",
]
