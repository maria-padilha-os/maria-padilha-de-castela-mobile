"""Preview references, offline behaviour, and local serving checks."""

from __future__ import annotations

import html.parser
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preview.serve import PreviewHandler  # noqa: E402
from tests.support import read_text  # noqa: E402

REMOTE_RE = re.compile(r"https?://", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)")
JS_IMPORT_RE = re.compile(r"(?:from|import)\s+[\"']([^\"']+)[\"']")


class ReferenceParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def local_reference(base: pathlib.Path, reference: str) -> pathlib.Path:
    reference = reference.split("#", 1)[0].split("?", 1)[0]
    return (base / reference).resolve()


class PreviewReferences(unittest.TestCase):
    def test_html_css_js_and_manifest_have_no_remote_requests(self) -> None:
        for name in (
            "index.html",
            "styles.css",
            "palette.js",
            "app.js",
            "palette-data.js",
            "manifest.webmanifest",
        ):
            text = read_text(ROOT / "preview" / name)
            self.assertIsNone(REMOTE_RE.search(text), f"{name} contains a remote URL")

    def test_all_local_references_exist(self) -> None:
        html = read_text(ROOT / "preview" / "index.html")
        parser = ReferenceParser()
        parser.feed(html)
        for reference in parser.references:
            if reference.startswith(("#", "mailto:", "data:")):
                continue
            with self.subTest(reference=reference):
                self.assertFalse(REMOTE_RE.search(reference), reference)
                self.assertTrue(local_reference(ROOT / "preview", reference).exists())

        css = read_text(ROOT / "preview" / "styles.css")
        for reference in CSS_URL_RE.findall(css):
            with self.subTest(css_reference=reference):
                self.assertFalse(REMOTE_RE.search(reference), reference)
                self.assertTrue(local_reference(ROOT / "preview", reference).exists())

        for script_name in ("palette.js", "app.js"):
            script = read_text(ROOT / "preview" / script_name)
            for reference in JS_IMPORT_RE.findall(script):
                if reference.startswith("."):
                    with self.subTest(js_reference=reference):
                        self.assertTrue(
                            local_reference(ROOT / "preview", reference).exists()
                        )

        manifest = json.loads(read_text(ROOT / "preview" / "manifest.webmanifest"))
        for icon in manifest["icons"]:
            with self.subTest(icon=icon["src"]):
                self.assertTrue(
                    local_reference(ROOT / "preview", icon["src"]).exists()
                )

    def test_preview_controls_and_disclaimer_are_present(self) -> None:
        html = read_text(ROOT / "preview" / "index.html")
        for value in ('value="system"', 'value="light"', 'value="dark"'):
            self.assertIn(value, html)
        self.assertIn('id="dynamic-accent"', html)
        self.assertIn('id="contrast-rows"', html)
        self.assertIn("Not official GrapheneOS", html)
        self.assertIn("no telemetry", html)

    def test_manifest_is_private_and_offline(self) -> None:
        manifest = json.loads(read_text(ROOT / "preview" / "manifest.webmanifest"))
        self.assertEqual(manifest["start_url"], "./index.html")
        self.assertEqual(manifest["scope"], "./")
        self.assertNotIn("https://", json.dumps(manifest))

    def test_python_server_defaults_to_loopback(self) -> None:
        server = read_text(ROOT / "preview" / "serve.py")
        self.assertIn('default="127.0.0.1"', server)
        self.assertIn("no-store", server)
        self.assertIn("DENY_PARTS", server)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_javascript_syntax(self) -> None:
        for name in ("palette.js", "app.js"):
            with tempfile.TemporaryDirectory() as directory:
                target = pathlib.Path(directory) / f"{name}.mjs"
                target.write_text(read_text(ROOT / "preview" / name), encoding="utf-8")
                result = subprocess.run(
                    ["node", "--check", str(target)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class PreviewServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def fetch(self, path: str) -> tuple[int, bytes, str]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                return response.status, response.read(), response.headers.get_content_type()
        except urllib.error.HTTPError as error:
            try:
                return error.code, error.read(), error.headers.get_content_type()
            finally:
                error.close()

    def test_preview_index_and_assets_are_served(self) -> None:
        status, body, content_type = self.fetch("/preview/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Padilha design system", body)

        for path, expected_type in (
            ("/preview/styles.css", "text/css"),
            ("/preview/palette.js", "text/javascript"),
            ("/preview/app.js", "text/javascript"),
            ("/preview/manifest.webmanifest", "application/manifest+json"),
            ("/assets/wallpapers/padilha-dark-1080x2424.webp", "image/webp"),
            ("/assets/fonts/Inter-Regular.woff2", "font/woff2"),
        ):
            with self.subTest(path=path):
                status, _body, content_type = self.fetch(path)
                self.assertEqual(status, 200, path)
                self.assertIn(expected_type, content_type)

    def test_dedicated_security_panel_route_is_served(self) -> None:
        status, body, content_type = self.fetch("/preview/security/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Padilha Security Panel", body)
        self.assertIn(b"Authorize lab mode", body)

        for path in (
            "/preview/security/security.css",
            "/preview/security/security.js",
            "/preview/security/security-panel.js",
            "/preview/security/network-inventory.js",
        ):
            with self.subTest(path=path):
                status, _body, _content_type = self.fetch(path)
                self.assertEqual(status, 200, path)

    def test_root_redirects_to_preview_and_private_paths_are_denied(self) -> None:
        status, body, _content_type = self.fetch("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Padilha design system", body)

        for path in ("/keys/test", "/signing/test", "/.git/config", "/artifacts/test.apk"):
            with self.subTest(path=path):
                status, _body, _content_type = self.fetch(path)
                self.assertEqual(status, 404, path)


if __name__ == "__main__":
    unittest.main()
