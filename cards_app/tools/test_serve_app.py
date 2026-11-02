import tempfile
import unittest
from pathlib import Path

from serve_app import cache_control, resolve


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()  # /var is a symlink on macOS
        (self.root / "index.html").write_text("x")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "app-1a2b.js").write_text("x")
        (self.root / "images").mkdir()
        (self.root / "images" / "s012.webp").write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_serves_index(self):
        self.assertEqual(resolve(self.root, "/"), self.root / "index.html")

    def test_files_and_query_strings(self):
        self.assertEqual(resolve(self.root, "/images/s012.webp?v=2"), self.root / "images" / "s012.webp")

    def test_missing_file_is_none(self):
        self.assertIsNone(resolve(self.root, "/nope.js"))

    def test_cannot_escape_the_folder(self):
        self.assertIsNone(resolve(self.root, "/../serve_app.py"))
        self.assertIsNone(resolve(self.root, "/%2e%2e/%2e%2e/etc/passwd"))

    def test_directories_are_not_listed(self):
        self.assertIsNone(resolve(self.root, "/images/"))


class CacheControlTest(unittest.TestCase):
    def test_app_shell_is_always_rechecked_so_updates_arrive(self):
        for name in ["index.html", "sw.js", "manifest.webmanifest"]:
            self.assertEqual(cache_control(name), "no-cache")

    def test_hashed_assets_and_slides_are_cached_for_good(self):
        self.assertIn("immutable", cache_control("assets/app-1a2b.js"))
        self.assertIn("max-age", cache_control("images/s012.webp"))


if __name__ == "__main__":
    unittest.main()
