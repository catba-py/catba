import os
import tempfile
import unittest

from catba.project import find_project_root

from tests.helpers import write_tree


class TestProjectDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_current_dir_is_root(self):
        write_tree(self.root, {"pyproject.toml": "", "catba.py": ""})
        self.assertEqual(find_project_root(self.root), self.root)

    def test_finds_root_from_subdirectory(self):
        write_tree(self.root, {
            "pyproject.toml": "",
            "catba.py": "",
            "app/route.py": "",
        })
        start = os.path.join(self.root, "app")
        self.assertEqual(find_project_root(start), self.root)

    def test_no_project_returns_none(self):
        self.assertIsNone(find_project_root(self.root))

    def test_needs_both_files(self):
        write_tree(self.root, {"pyproject.toml": ""})
        self.assertIsNone(find_project_root(self.root))


if __name__ == "__main__":
    unittest.main()
