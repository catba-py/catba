"""Architecture specification guards.

Verify the specification work did not break the published bootstrap
contract and that the architecture documentation is in place.

Checks the package version is unchanged, release metadata is intact,
the project template structure is intact, and the architecture documents
exist and reference the correct project structure.

Standard library only: no new dev dependencies.
"""

import os
import unittest

import catba

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO_ROOT, "docs", "architecture")

ARCH_DOCS = [
    "overview.md",
    "request-lifecycle.md",
    "route-contract.md",
    "page-contract.md",
    "routing.md",
    "native-memory.md",
]


class TestReleaseContract(unittest.TestCase):
    def test_version_unchanged(self):
        self.assertEqual(catba.__version__, "0.1.0")

    def test_pyproject_keeps_catba_script(self):
        path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('name = "catba"', text)
        self.assertIn('catba = "catba.cli:main"', text)

    def test_template_structure_intact(self):
        app_dir = os.path.join(REPO_ROOT, "templates", "app")
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "catba.py")))
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "pyproject.toml")))
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "app", "route.py")))
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "app", "page.tsx")))


class TestArchitectureDocs(unittest.TestCase):
    def test_all_docs_exist(self):
        for name in ARCH_DOCS:
            with self.subTest(name=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(DOCS, name)),
                    f"missing architecture doc: {name}",
                )

    def test_docs_reference_project_structure(self):
        pairs = {
            "route-contract.md": ["route.py", "ctx", "GET"],
            "page-contract.md": ["page.tsx", "props"],
            "routing.md": ["app/", "[id]"],
            "native-memory.md": ["arena", "owner"],
            "request-lifecycle.md": ["route.py", "page.tsx"],
            "overview.md": ["route.py", "page.tsx"],
        }
        for name, terms in pairs.items():
            path = os.path.join(DOCS, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for term in terms:
                with self.subTest(name=name, term=term):
                    self.assertIn(term, text)


class TestPythonCoreModules(unittest.TestCase):
    """Verify the Python core module structure is intact."""

    def test_context_exports(self):
        from catba.context import Context, Headers, Request
        self.assertTrue(callable(Context))
        self.assertTrue(callable(Headers))
        self.assertTrue(callable(Request))

    def test_response_exports(self):
        from catba import (
            BadRequest, HTTPError, InternalServerError, JSON,
            MethodNotAllowed, NotFound, Redirect, Response,
        )
        self.assertTrue(issubclass(BadRequest, HTTPError))
        self.assertTrue(issubclass(NotFound, HTTPError))
        self.assertTrue(issubclass(MethodNotAllowed, HTTPError))
        self.assertTrue(issubclass(InternalServerError, HTTPError))
        self.assertTrue(callable(JSON))
        self.assertTrue(callable(Redirect))
        self.assertTrue(callable(Response))

    def test_routing_exports(self):
        from catba.routing import Route, RouteError, RouteTable, discover_routes
        self.assertTrue(callable(Route))
        self.assertTrue(issubclass(RouteError, Exception))
        self.assertTrue(callable(RouteTable))
        self.assertTrue(callable(discover_routes))

    def test_runtime_exports(self):
        from catba.runtime import App, HTTPResult, PageData, to_http
        self.assertTrue(callable(App))
        self.assertTrue(callable(HTTPResult))
        self.assertTrue(callable(PageData))
        self.assertTrue(callable(to_http))

    def test_transport_exports(self):
        from catba.transport import DevServer
        self.assertTrue(callable(DevServer))

    def test_project_exports(self):
        from catba.project import find_project_root
        self.assertTrue(callable(find_project_root))


if __name__ == "__main__":
    unittest.main()
