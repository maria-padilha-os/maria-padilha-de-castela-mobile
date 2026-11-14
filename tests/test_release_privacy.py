"""Release sources stay private and the standalone checksum CLI works."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from release.checksums import load_manifest, verify_artifacts


class ReleasePrivacyTests(unittest.TestCase):
    def test_release_sources_have_no_public_artifact_urls(self) -> None:
        files = [
            ROOT / "release" / "README.md",
            ROOT / "release" / "signing.example.toml",
            ROOT / "docs" / "release-pipeline.md",
            ROOT / "docs" / "release-checklist.md",
        ]
        forbidden = (
            "http://",
            "https://",
            "github.io",
            "/releases/download/",
            "pages.dev",
            "public-release",
        )
        for path in files:
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_release_docs_require_private_store_and_human_gate(self) -> None:
        pipeline = (ROOT / "docs" / "release-pipeline.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
        for term in ("private", "No public distribution", "keys are outside", "checksum manifest"):
            self.assertIn(term, pipeline)
        for term in (
            "Explicit human approval",
            "Rollback to the prior build",
            "Key rotation and revocation notes",
            "No GitHub Pages",
        ):
            self.assertIn(term, checklist)


class StandaloneManifestToolTests(unittest.TestCase):
    def test_cli_generates_a_verifiable_manifest_outside_the_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            artifacts = base / "artifacts"
            output = base / "manifest"
            artifacts.mkdir()
            (artifacts / "Castela.apk").write_bytes(b"apk\n")
            (artifacts / "castela-ota-tegu.zip").write_bytes(b"ota\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "release_manifest.py"),
                    "--release-id",
                    "2026.11.14-tegu.1",
                    "--artifacts",
                    str(artifacts),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = load_manifest(output / "manifest.json")
            self.assertEqual(manifest["release_id"], "2026.11.14-tegu.1")
            self.assertEqual(len(manifest["artifacts"]), 2)
            verify_artifacts(manifest, artifacts)
            self.assertTrue((output / "SHA256SUMS").is_file())
            self.assertTrue((output / "manifest.json.sha256").is_file())
            payload = json.loads(result.stdout)
            self.assertEqual(payload["manifest_sha256"], manifest["manifest_sha256"])

    def test_cli_refuses_to_write_inside_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            artifacts = base / "artifacts"
            artifacts.mkdir()
            (artifacts / "Castela.apk").write_bytes(b"apk\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "release_manifest.py"),
                    "--release-id",
                    "2026.11.14-tegu.1",
                    "--artifacts",
                    str(artifacts),
                    "--output",
                    str(ROOT / "release" / "never-write-here"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("outside the repository", result.stderr)
            self.assertFalse((ROOT / "release" / "never-write-here").exists())


if __name__ == "__main__":
    unittest.main()
