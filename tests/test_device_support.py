"""Device matrix, runbook, and read-only flash-preflight tests."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.support import read_text  # noqa: E402
from tools import check_flash_inputs as checker  # noqa: E402

DOC = ROOT / "docs" / "device-support-and-flashing.md"
SCRIPT = ROOT / "tools" / "check_flash_inputs.py"

INSTALL = "tegu-install-2026110800.zip"
INSTALL_SIG = "tegu-install-2026110800.zip.sig"
OTA = "tegu-ota_update-2026110800.zip"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_line(filename: str, data: bytes) -> str:
    return f"{digest(data)}  {filename}\n"


def write_image(directory: pathlib.Path, filename: str, data: bytes) -> str:
    (directory / filename).write_bytes(data)
    return manifest_line(filename, data)


class DeviceMatrix(unittest.TestCase):
    def test_every_matrix_device_is_documented(self) -> None:
        text = read_text(DOC)
        self.assertIn(f"`{checker.REFERENCE_DEVICE}`", text)
        for codename, name in checker.SUPPORTED_DEVICES.items():
            with self.subTest(codename=codename):
                self.assertIn(f"`{codename}`", text)
                self.assertIn(name, text)

    def test_reference_device_is_pixel_9a(self) -> None:
        self.assertEqual(checker.REFERENCE_DEVICE, "tegu")
        self.assertEqual(checker.SUPPORTED_DEVICES[checker.REFERENCE_DEVICE], "Pixel 9a")
        self.assertIn("Pixel 9a (`tegu`)", read_text(DOC))

    def test_unknown_and_empty_devices_are_refused(self) -> None:
        for codename in ("barbet", "generic", "", "   ", "tegu; rm -rf /"):
            with self.subTest(codename=codename):
                with self.assertRaises(checker.PreflightError) as raised:
                    checker.normalize_device(codename)
                self.assertEqual(raised.exception.code, "unsupported-device")

    def test_runbook_has_required_safety_statements(self) -> None:
        text = read_text(DOC).lower()
        for term in (
            "not official grapheneos",
            "security consequences",
            "bootloader",
            "backup",
            "recovery",
            "sha-256",
            "check_flash_inputs.py",
            "never flashes",
            "no castela system image",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)


class ManifestValidation(unittest.TestCase):
    def test_valid_manifest_parses_without_touching_files(self) -> None:
        text = (
            "# release images\n"
            f"{'a' * 64}  {INSTALL}\n"
            f"{'b' * 64}  {INSTALL_SIG}\n"
            f"{'c' * 64} *{OTA}\n"
        )
        entries = checker.parse_manifest(text, "tegu")
        self.assertEqual([entry.filename for entry in entries], [INSTALL, INSTALL_SIG, OTA])
        self.assertEqual(entries[0].kind, "install")
        self.assertFalse(entries[0].signature)
        self.assertTrue(entries[1].signature)
        self.assertEqual(entries[2].kind, "ota_update")
        self.assertEqual(entries[2].version, "2026110800")

    def test_path_traversal_absolute_and_nested_names_are_refused(self) -> None:
        names = (
            "../tegu-install-2026110800.zip",
            "../../etc/passwd",
            "/tegu-install-2026110800.zip",
            "nested/tegu-install-2026110800.zip",
            "nested\\tegu-install-2026110800.zip",
            ".",
            "..",
        )
        for name in names:
            with self.subTest(name=name):
                with self.assertRaises(checker.PreflightError) as raised:
                    checker.parse_manifest(f"{'a' * 64}  {name}\n", "tegu")
                self.assertEqual(raised.exception.code, "unsafe-image-name")

    def test_wrong_device_and_unexpected_artifacts_are_refused(self) -> None:
        cases = {
            "raven-install-2026110800.zip": "wrong-device",
            "tegu-install-latest.zip": "unexpected-image-name",
            "tegu-factory-2026110800.zip": "unexpected-image-name",
            "tegu-ota_update-2026110800.zip.sig": "unexpected-signature",
            "tegu-install-2026110800.img": "unexpected-image-name",
            "TEGU-install-2026110800.zip": "unexpected-image-name",
        }
        for name, code in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(checker.PreflightError) as raised:
                    checker.parse_manifest(f"{'a' * 64}  {name}\n", "tegu")
                self.assertEqual(raised.exception.code, code)

    def test_bad_digest_duplicate_and_empty_manifests_are_refused(self) -> None:
        cases = (
            (f"{'a' * 63}  {INSTALL}\n", "invalid-digest"),
            (f"not-a-digest  {INSTALL}\n", "invalid-digest"),
            (f"{'a' * 64}  {INSTALL}\n{'a' * 64}  {INSTALL}\n", "duplicate-image"),
            ("# only comments\n\n", "empty-manifest"),
            (f"{'a' * 64}  {OTA}\n", "missing-install-image"),
            (f"{'a' * 64}  {INSTALL_SIG}\n", "missing-install-image"),
            (f"{'a' * 64}  {INSTALL}  extra\n", "invalid-manifest-line"),
        )
        for text, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(checker.PreflightError) as raised:
                    checker.parse_manifest(text, "tegu")
                self.assertEqual(raised.exception.code, code)


class PreflightVerification(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)
        self.manifest = self.directory / "SHA256SUMS"

    def write_manifest(self, lines: list[str]) -> None:
        self.manifest.write_text("".join(lines), encoding="utf-8")

    def test_matching_checksums_and_device_paths_pass(self) -> None:
        lines = [
            write_image(self.directory, INSTALL, b"install image"),
            write_image(self.directory, INSTALL_SIG, b"signature"),
        ]
        self.write_manifest(lines)
        result = checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(result.device, "tegu")
        self.assertEqual(result.device_name, "Pixel 9a")
        self.assertEqual(
            [entry.filename for entry in result.entries], [INSTALL, INSTALL_SIG]
        )
        self.assertEqual(result.entries[0].size, len(b"install image"))
        self.assertEqual(result.entries[0].digest, digest(b"install image"))

    def test_checksum_mismatch_is_refused(self) -> None:
        write_image(self.directory, INSTALL, b"install image")
        self.write_manifest([f"{'0' * 64}  {INSTALL}\n"])
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "checksum-mismatch")

    def test_missing_empty_and_non_regular_images_are_refused(self) -> None:
        self.write_manifest([f"{'a' * 64}  {INSTALL}\n"])
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "missing-image")

        (self.directory / INSTALL).write_bytes(b"")
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "empty-image")

        (self.directory / INSTALL).unlink()
        (self.directory / INSTALL).mkdir()
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "image-not-regular")

    def test_symbolic_links_are_refused(self) -> None:
        real = self.directory / "real.zip"
        real.write_bytes(b"install image")
        (self.directory / INSTALL).symlink_to(real)
        self.write_manifest([manifest_line(INSTALL, b"install image")])
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "image-symlink")

    def test_manifest_must_be_a_regular_non_symlink_file(self) -> None:
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "invalid-manifest")

        target = self.directory / "real-manifest"
        target.write_text(f"{'a' * 64}  {INSTALL}\n", encoding="utf-8")
        self.manifest.symlink_to(target)
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight("tegu", self.directory, self.manifest)
        self.assertEqual(raised.exception.code, "invalid-manifest")

    def test_image_directory_must_exist(self) -> None:
        self.write_manifest([f"{'a' * 64}  {INSTALL}\n"])
        with self.assertRaises(checker.PreflightError) as raised:
            checker.verify_preflight(
                "tegu", self.directory / "missing", self.manifest
            )
        self.assertEqual(raised.exception.code, "invalid-image-dir")

    def test_cli_reports_success_and_failure_without_writing_images(self) -> None:
        write_image(self.directory, INSTALL, b"install image")
        self.write_manifest([manifest_line(INSTALL, b"install image")])
        before = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.directory.iterdir()
            if path.name != self.manifest.name
        }

        success = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--device",
                "tegu",
                "--image-dir",
                str(self.directory),
                "--manifest",
                str(self.manifest),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("preflight ok: tegu (Pixel 9a)", success.stdout)
        self.assertIn("No write, USB access, bootloader command, or flash", success.stdout)

        self.write_manifest([f"{'0' * 64}  {INSTALL}\n"])
        failure = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--device",
                "tegu",
                "--image-dir",
                str(self.directory),
                "--manifest",
                str(self.manifest),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(failure.returncode, 2)
        self.assertIn("checksum-mismatch", failure.stderr)

        after = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.directory.iterdir()
            if path.name != self.manifest.name
        }
        self.assertEqual(before, after)

    def test_checker_has_no_process_or_write_path(self) -> None:
        source = read_text(SCRIPT)
        for term in (
            "subprocess",
            "os.system",
            "Popen",
            "fastboot",
            "adb",
            "write_text",
            "write_bytes",
            'open("w',
            "open('w",
        ):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
