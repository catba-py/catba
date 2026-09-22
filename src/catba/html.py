"""HTML document shell builder.

Wraps a React SSR HTML fragment in a full HTML document with hydration
state. The document shell is deterministic and internal: users do not
modify it via a public API.
"""

import html as _html_module
import json


def _safe_script_json(data):
    """Serialize data as JSON, safe for embedding inside a <script> element.

    Escapes ``</`` to ``<\\/`` so that ``</script>`` inside user-controlled
    props cannot terminate the script element. This is the deliberate safe
    serialization function: never use raw string concatenation for props.
    """
    raw = json.dumps(data, ensure_ascii=False)
    # Replace </ with <\/ to prevent </script> from breaking out.
    safe = raw.replace("<", "\\u003c")
    return safe


def build_document(page_id, props, html_fragment, client_bundle=None):
    """Build a full HTML document with SSR content and hydration state.

    Parameters:
        page_id       - the route URL identifier (e.g. "/", "/users/[id]")
        props         - the page props dict (JSON-serializable)
        html_fragment - the React SSR HTML string
        client_bundle - optional URL or path to the client JS bundle

    Returns a complete HTML document string.
    """
    props_json = _safe_script_json(props)
    escaped_page_id = _html_module.escape(page_id)

    script_tag = ""
    if client_bundle:
        script_tag = f'<script type="module" src="{_html_module.escape(client_bundle)}"></script>'

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CatBa</title>
</head>
<body>
<div id="catba-root" data-catba-page="{escaped_page_id}">{html_fragment}</div>
<script id="catba-props" type="application/json">{props_json}</script>
{script_tag}
</body>
</html>"""
