"""Checksum manifests must be deterministic and tamper-evident."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from release.checksums import (
    artifact_entry,
    build_manifest,
    digest_json,
    load_manifest,
    sha256_file,
    verify_artifacts,
    verify_checksum_files,
    verify_manifest_digest,
    write_manifest_bundle,
)
from release.errors import ChecksumError


def make_entries(directory: pathlib.Path) -> list[dict[str, object]]:
    first = directory / "Castela.apk"
    second = directory / "castela-ota-tegu.zip"
    first.write_bytes(b"apk bytes\n")
    second.write_bytes(b"ota bytes\n")
    return [
        artifact_entry(first, role="app"),
        artifact_entry(second, role="ota"),
    ]


class ChecksumManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_hashes_every_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            entries = make_entries(base)
            manifest = build_manifest("2026.11.14-tegu.1", entries)
            repeated = build_manifest("2026.11.14-tegu.1", list(reversed(entries)))
            self.assertEqual(manifest, repeated)
            self.assertEqual(manifest["release_id"], "2026.11.14-tegu.1")
            self.assertEqual(
                [item["name"] for item in manifest["artifacts"]],
                ["Castela.apk", "castela-ota-tegu.zip"],
            )
            for item in manifest["artifacts"]:
                self.assertEqual(item["sha256"], sha256_file(base / item["name"]))
            self.assertEqual(manifest["total_size"], len(b"apk bytes\n") + len(b"ota bytes\n"))
            verify_manifest_digest(manifest)

    def test_manifest_digest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            manifest = build_manifest("2026.11.14-tegu.1", make_entries(base))
            manifest["artifacts"][0]["size"] += 1
            with self.assertRaisesRegex(ChecksumError, "manifest_sha256"):
                verify_manifest_digest(manifest)

    def test_checksum_bundle_round_trips_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            manifest = build_manifest("2026.11.14-tegu.1", make_entries(base))
            paths = write_manifest_bundle(manifest, base)
            self.assertTrue(paths["manifest"].is_file())
            self.assertTrue(paths["sums"].is_file())
            self.assertTrue(paths["digest"].is_file())

            loaded = load_manifest(paths["manifest"])
            self.assertEqual(loaded, manifest)
            verify_checksum_files(paths["manifest"], base)

            sums = paths["sums"].read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(sums), 2)
            for line in sums:
                digest, name = line.split("  ", 1)
                self.assertEqual(digest, sha256_file(base / name))

    def test_manifest_detects_changed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            manifest = build_manifest("2026.11.14-tegu.1", make_entries(base))
            write_manifest_bundle(manifest, base)
            (base / "Castela.apk").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(ChecksumError, "size mismatch|checksum mismatch"):
                verify_checksum_files(base / "manifest.json", base)

    def test_duplicate_and_traversal_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            entries = make_entries(base)
            with self.assertRaisesRegex(ChecksumError, "duplicate"):
                build_manifest("2026.11.14-tegu.1", entries + [entries[0]])
            for name in ("../escape.apk", "/absolute.apk", "a/../../escape.apk", "a\\b.apk"):
                with self.subTest(name=name):
                    entry = dict(entries[0])
                    entry["name"] = name
                    with self.assertRaises(ChecksumError):
                        build_manifest("2026.11.14-tegu.1", [entry])

    def test_invalid_release_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            entries = make_entries(base)
            for release_id in ("", "../release", "release one", "x" * 65):
                with self.subTest(release_id=release_id), self.assertRaises(ChecksumError):
                    build_manifest(release_id, entries)

    def test_extra_file_fails_strict_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            manifest = build_manifest("2026.11.14-tegu.1", make_entries(base))
            verify_artifacts(manifest, base)
            (base / "unexpected.txt").write_text("extra\n", encoding="utf-8")
            with self.assertRaisesRegex(ChecksumError, "unexpected files"):
                verify_artifacts(manifest, base, allow_extra=False)

    def test_manifest_json_is_sorted_and_ends_with_newline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            manifest = build_manifest("2026.11.14-tegu.1", make_entries(base))
            paths = write_manifest_bundle(manifest, base)
            text = paths["manifest"].read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertEqual(json.loads(text), manifest)
            self.assertEqual(manifest["manifest_sha256"], digest_json(
                {key: value for key, value in manifest.items() if key != "manifest_sha256"}
            ))

    def test_sha256_file_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "blob"
            data = b"castela" * 1000
            path.write_bytes(data)
            self.assertEqual(sha256_file(path), hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
