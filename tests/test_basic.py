"""Basic CatBa repository bootstrap tests.

Covers the three things that must already work at this stage:

- importing the ``catba`` package,
- version availability,
- the CLI entrypoint behavior (``--version``, ``--help``, bare invocation,
  and the not-implemented command surface).

Uses only the standard library so the project picks up no dev dependencies.
"""

import io
import contextlib
import unittest

import catba
from catba import cli


class TestPackage(unittest.TestCase):
    def test_import_catba(self):
        self.assertTrue(hasattr(catba, "__version__"))

    def test_version_is_string(self):
        self.assertIsInstance(catba.__version__, str)
        self.assertTrue(catba.__version__)

    def test_version_value(self):
        self.assertEqual(catba.__version__, "0.1.0")


class TestCli(unittest.TestCase):
    def test_version_flag(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("catba", out.getvalue())
        self.assertIn(catba.__version__, out.getvalue())

    def test_help_flag(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("CatBa", out.getvalue())

    def test_no_args_prints_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cli.main([])
        self.assertEqual(rc, 0)
        self.assertIn("CatBa", out.getvalue())

    def test_command_surface_present(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        help_text = out.getvalue()
        for command in ("create", "dev", "build", "start", "install"):
            self.assertIn(command, help_text)

    def test_subcommand_not_implemented(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cli.main(["build"])
        self.assertEqual(rc, 1)
        self.assertIn("not implemented", err.getvalue())

    def test_unknown_flag_errors(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--nope"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
