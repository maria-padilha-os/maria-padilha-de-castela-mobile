"""Signing configuration must fail closed on keys, stores, and approval."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from release.config import load_config
from release.errors import ConfigError
from tests.release_support import make_config, make_keys


class ReleaseConfigTests(unittest.TestCase):
    def test_sample_config_is_private_and_loads(self) -> None:
        config = load_config(ROOT / "release" / "signing.example.toml")
        self.assertEqual(config.project, "maria-padilha-de-castela-mobile")
        self.assertEqual(config.store.visibility, "private")
        self.assertEqual(config.store.scheme, "file")
        self.assertTrue(config.approval.required)
        self.assertEqual({key.role for key in config.keys}, {"app", "ota", "factory", "manifest"})
        self.assertEqual(set(config.signers), {"app", "ota", "factory"})

    def test_valid_config_has_stable_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base)
            first = load_config(path, require_material=True)
            second = load_config(path, require_material=True)
            self.assertEqual(first.fingerprint(), second.fingerprint())
            self.assertIn("config_sha256", first.public_summary())
            self.assertNotIn(str(base / "keys"), repr(first.public_summary()))

    def test_key_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base)
            text = path.read_text(encoding="utf-8")
            inside = ROOT / "release" / "never-a-real-key.pem"
            text = text.replace(str(base / "keys" / "app.pem"), str(inside), 1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "outside the repository"):
                load_config(path)

    def test_certificate_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base)
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                str(base / "keys" / "app-cert.pem"),
                str(ROOT / "release" / "never-a-real-cert.pem"),
                1,
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "outside the repository"):
                load_config(path)

    def test_store_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base, store_uri=(ROOT / "release").as_uri())
            with self.assertRaisesRegex(ConfigError, "outside the repository"):
                load_config(path)

    def test_public_or_unauthenticated_store_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            for uri in (
                "https://example.invalid/releases",
                "http://example.invalid/releases",
                "s3://private-bucket/releases",
            ):
                with self.subTest(uri=uri):
                    path = make_config(
                        base / uri.replace(":", "_").replace("/", "_"),
                        store_uri=uri,
                        access="iam" if uri.startswith("s3://") else "filesystem",
                    )
                    if uri.startswith("s3://"):
                        config = load_config(path)
                        self.assertEqual(config.store.visibility, "private")
                    else:
                        with self.assertRaisesRegex(ConfigError, "file://|Pages|package"):
                            load_config(path)

    def test_non_private_visibility_and_anonymous_access_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base, visibility="public")
            with self.assertRaisesRegex(ConfigError, "visibility"):
                load_config(path)

    def test_approval_cannot_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base, approval_required=False)
            with self.assertRaisesRegex(ConfigError, "required"):
                load_config(path)

    def test_world_readable_key_is_rejected_when_material_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            keys = make_keys(base)
            path = make_config(base, keys=keys)
            os.chmod(keys["app"]["key"], 0o644)
            with self.assertRaisesRegex(ConfigError, "group/world"):
                load_config(path, require_material=True)

    def test_expected_key_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            keys = make_keys(base)
            path = make_config(base, keys=keys)
            keys["app"]["key"].write_text("different key material\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "expected SHA-256"):
                load_config(path, require_material=True)

    def test_privileged_signer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base)
            text = path.read_text(encoding="utf-8")
            text = text.replace(f'"{sys.executable}"', '"sudo"', 1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "privileged"):
                load_config(path)

    def test_unknown_signer_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(base)
            text = path.read_text(encoding="utf-8")
            text = text.replace('"--key", "{key}"', '"--key", "{secret}"', 1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "placeholder"):
                load_config(path)

    def test_duplicate_signer_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            path = make_config(
                base,
                extra_signers="""
[[signers]]
role = "app"
command = ["/bin/true", "--key", "{key}", "--input", "{input}", "--output", "{output}"]
""",
            )
            with self.assertRaisesRegex(ConfigError, "duplicate signer"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
