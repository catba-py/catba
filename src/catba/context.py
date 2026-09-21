"""Request context and request representation for the CatBa core.

These types are the contract between the transport layer and route handlers.
The transport builds a Request; the core wraps it in a Context and hands it
to the handler. Neither depends on any transport implementation.
"""


class Headers:
    """Case-insensitive, order-preserving header mapping.

    Header names compare case-insensitively (``h["content-type"]`` and
    ``h["Content-Type"]`` refer to the same entry) but the original casing of
    the last assignment is preserved for iteration and serialization.
    """

    def __init__(self, items=None):
        self._items = {}  # lowercased name -> (original_casing, value)
        if items is not None:
            if hasattr(items, "items"):
                items = items.items()
            for key, value in items:
                self._items[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._items[key.lower()][1]

    def __setitem__(self, key, value):
        self._items[key.lower()] = (key, value)

    def __delitem__(self, key):
        del self._items[key.lower()]

    def __contains__(self, key):
        return key.lower() in self._items

    def __iter__(self):
        return (original for original, _ in self._items.values())

    def __len__(self):
        return len(self._items)

    def get(self, key, default=None):
        pair = self._items.get(key.lower())
        return pair[1] if pair is not None else default

    def items(self):
        return [(original, value) for original, value in self._items.values()]

    def keys(self):
        return [original for original, _ in self._items.values()]

    def values(self):
        return [value for _, value in self._items.values()]


class Request:
    """The internal Python request representation.

    Built by the transport from the raw HTTP request. ``params`` is populated
    by the router (empty until a route matches). ``body`` is the parsed body
    when the content type was JSON or form data, otherwise raw bytes.
    """

    def __init__(self, method, path, headers=None, query=None, cookies=None,
                 body=b"", params=None):
        self.method = method
        self.path = path
        if isinstance(headers, Headers):
            self.headers = headers
        else:
            self.headers = Headers(headers)
        self.query = query if query is not None else {}
        self.cookies = cookies if cookies is not None else {}
        self.body = body
        self.params = params if params is not None else {}


class Context:
    """Request-scoped context handed to route handlers.

    A Context exists only for the request that produced it. Every field is
    request-scoped: ``request``, ``headers``, ``cookies``, ``query``,
    ``params`` and ``body`` are read from the request, ``session`` is a
    reserved hook (no real session system yet), and ``state`` is a mutable
    per-request bag for middleware and handlers to share data without globals.

    Storing a Context on a long-lived object is a bug.
    """

    def __init__(self, request, session=None, state=None):
        self.request = request
        self.headers = request.headers
        self.cookies = request.cookies
        self.query = request.query
        self.params = request.params
        self.body = request.body
        self.session = session
        self.state = state if state is not None else {}
