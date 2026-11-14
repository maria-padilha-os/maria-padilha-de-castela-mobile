#!/usr/bin/env python3
"""Read-only preflight for official GrapheneOS installation images.

This checker verifies a local image directory and a SHA-256 manifest before a
human runs the official GrapheneOS installer. It never writes files, downloads
images, opens a USB device, invokes the bootloader, or flashes anything. It is a
guard rail, not an installer.

The normal use is:

    python3 tools/check_flash_inputs.py \
        --device tegu \
        --image-dir /secure/staging/tegu \
        --manifest /secure/staging/tegu/SHA256SUMS

The manifest uses the standard ``sha256sum`` format: a 64-character SHA-256
digest, whitespace, and a bare image filename. Image names must belong to the
selected device and match the official release shape
``<codename>-install-<version>.zip`` (optionally ``.sig``) or
``<codename>-ota_update-<version>.zip``.

SHA-256 proves that the local bytes match the manifest. It does not prove that
the release came from GrapheneOS. Verify the official OpenSSH signature first,
as described in docs/device-support-and-flashing.md.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import pathlib
import re
import sys
from dataclasses import dataclass

SUPPORTED_DEVICES: dict[str, str] = {
    "tegu": "Pixel 9a",
    "akita": "Pixel 8a",
    "shiba": "Pixel 8",
    "husky": "Pixel 8 Pro",
    "tokay": "Pixel 9",
    "caiman": "Pixel 9 Pro",
    "komodo": "Pixel 9 Pro XL",
    "comet": "Pixel 9 Pro Fold",
    "frankel": "Pixel 10",
    "blazer": "Pixel 10 Pro",
    "mustang": "Pixel 10 Pro XL",
    "rango": "Pixel 10 Pro Fold",
    "stallion": "Pixel 10a",
    "panther": "Pixel 7",
    "cheetah": "Pixel 7 Pro",
    "lynx": "Pixel 7a",
    "oriole": "Pixel 6",
    "raven": "Pixel 6 Pro",
    "bluejay": "Pixel 6a",
    "felix": "Pixel Fold",
    "tangorpro": "Pixel Tablet",
}

REFERENCE_DEVICE = "tegu"
MAX_MANIFEST_BYTES = 1024 * 1024
HASH_CHUNK = 1024 * 1024
HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
IMAGE_RE = re.compile(
    r"^(?P<codename>[a-z][a-z0-9_]{2,31})-"
    r"(?P<kind>install|ota_update)-"
    r"(?P<version>[0-9]{10})"
    r"(?P<extension>\.zip(?:\.sig)?)$"
)


class PreflightError(ValueError):
    """A safe, user-facing preflight failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ManifestEntry:
    filename: str
    digest: str
    kind: str
    version: str
    signature: bool
    path: pathlib.Path
    size: int


@dataclass(frozen=True)
class PreflightResult:
    device: str
    device_name: str
    image_dir: pathlib.Path
    manifest: pathlib.Path
    entries: tuple[ManifestEntry, ...]


def normalize_device(codename: str) -> str:
    """Return a supported device codename or fail closed."""

    if not isinstance(codename, str) or not codename.strip():
        raise PreflightError(
            "unsupported-device",
            "provide a supported Pixel codename such as tegu.",
        )
    normalized = codename.strip().lower()
    if normalized not in SUPPORTED_DEVICES:
        raise PreflightError(
            "unsupported-device",
            f"{codename!r} is not in the Castela device matrix; "
            "use an officially supported Pixel codename.",
        )
    return normalized


def _validate_image_name(filename: str, device: str) -> re.Match[str]:
    if not filename or filename != filename.strip():
        raise PreflightError(
            "unsafe-image-name",
            "image filenames must be non-empty and must not contain padding.",
        )
    if (
        filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or pathlib.PurePosixPath(filename).is_absolute()
        or pathlib.PureWindowsPath(filename).is_absolute()
    ):
        raise PreflightError(
            "unsafe-image-name",
            f"{filename!r} must be a bare filename inside the image directory.",
        )

    match = IMAGE_RE.fullmatch(filename)
    if match is None:
        raise PreflightError(
            "unexpected-image-name",
            f"{filename!r} does not match the official GrapheneOS release name "
            f"for a device such as {device}.",
        )
    if match.group("codename") != device:
        raise PreflightError(
            "wrong-device",
            f"{filename!r} belongs to {match.group('codename')!r}, not {device!r}.",
        )
    if match.group("kind") == "ota_update" and match.group("extension") != ".zip":
        raise PreflightError(
            "unexpected-signature",
            f"{filename!r} is not a valid update-package name.",
        )
    return match


def parse_manifest(text: str, device: str) -> tuple[ManifestEntry, ...]:
    """Parse and validate a sha256sum-style manifest without touching files."""

    entries: list[ManifestEntry] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) != 2:
            raise PreflightError(
                "invalid-manifest-line",
                f"line {line_number}: expected '<sha256>  <filename>'.",
            )
        digest, filename = parts
        if filename.startswith("*"):
            filename = filename[1:]
        if not HASH_RE.fullmatch(digest):
            raise PreflightError(
                "invalid-digest",
                f"line {line_number}: SHA-256 must be exactly 64 hexadecimal characters.",
            )

        match = _validate_image_name(filename, device)
        if filename in seen:
            raise PreflightError(
                "duplicate-image",
                f"line {line_number}: {filename!r} appears more than once.",
            )
        seen.add(filename)
        entries.append(
            ManifestEntry(
                filename=filename,
                digest=digest.lower(),
                kind=match.group("kind"),
                version=match.group("version"),
                signature=match.group("extension").endswith(".sig"),
                path=pathlib.Path(filename),
                size=0,
            )
        )

    if not entries:
        raise PreflightError(
            "empty-manifest",
            "the manifest contains no image entries.",
        )
    if not any(entry.kind == "install" and not entry.signature for entry in entries):
        raise PreflightError(
            "missing-install-image",
            "the manifest must include an install zip; an OTA package or signature "
            "alone cannot perform an initial installation.",
        )
    return tuple(entries)


def sha256_file(path: pathlib.Path) -> str:
    """Return the SHA-256 of a file using read-only streaming."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_preflight(
    device: str,
    image_dir: pathlib.Path | str,
    manifest: pathlib.Path | str,
) -> PreflightResult:
    """Verify device-specific image paths and every SHA-256 in the manifest."""

    codename = normalize_device(device)
    image_path = pathlib.Path(image_dir)
    manifest_path = pathlib.Path(manifest)

    if not image_path.exists() or not image_path.is_dir():
        raise PreflightError(
            "invalid-image-dir",
            f"{str(image_path)!r} is not a directory.",
        )
    resolved_image_dir = image_path.resolve()

    if manifest_path.is_symlink():
        raise PreflightError(
            "invalid-manifest",
            "the manifest must not be a symbolic link.",
        )
    if not manifest_path.exists() or not manifest_path.is_file():
        raise PreflightError(
            "invalid-manifest",
            f"{str(manifest_path)!r} is not a regular file.",
        )
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PreflightError(
            "manifest-too-large",
            "the manifest is larger than the 1 MiB safety limit.",
        )

    try:
        text = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PreflightError(
            "invalid-manifest",
            f"could not read the manifest as UTF-8: {error}",
        ) from error

    entries = parse_manifest(text, codename)
    verified: list[ManifestEntry] = []

    for entry in entries:
        candidate = resolved_image_dir / entry.filename
        if candidate.is_symlink():
            raise PreflightError(
                "image-symlink",
                f"{entry.filename!r} is a symbolic link; use the real file.",
            )
        if not candidate.exists():
            raise PreflightError(
                "missing-image",
                f"{entry.filename!r} is listed in the manifest but is missing.",
            )
        if not candidate.is_file():
            raise PreflightError(
                "image-not-regular",
                f"{entry.filename!r} is not a regular file.",
            )
        size = candidate.stat().st_size
        if size == 0:
            raise PreflightError(
                "empty-image",
                f"{entry.filename!r} is empty.",
            )

        actual = sha256_file(candidate)
        if not hmac.compare_digest(actual, entry.digest):
            raise PreflightError(
                "checksum-mismatch",
                f"{entry.filename!r} has SHA-256 {actual}, expected {entry.digest}.",
            )

        verified.append(
            ManifestEntry(
                filename=entry.filename,
                digest=entry.digest,
                kind=entry.kind,
                version=entry.version,
                signature=entry.signature,
                path=candidate,
                size=size,
            )
        )

    return PreflightResult(
        device=codename,
        device_name=SUPPORTED_DEVICES[codename],
        image_dir=resolved_image_dir,
        manifest=manifest_path.resolve(),
        entries=tuple(verified),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only preflight for official GrapheneOS installation images. "
            "Checks device paths and SHA-256 digests, then stops. It never "
            "flashes, writes, downloads, or opens a USB device."
        )
    )
    parser.add_argument(
        "--device",
        required=True,
        help="supported Pixel codename, for example tegu",
    )
    parser.add_argument(
        "--image-dir",
        required=True,
        type=pathlib.Path,
        help="directory containing the device-specific image files",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=pathlib.Path,
        help="sha256sum-style manifest for the image files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        result = verify_preflight(args.device, args.image_dir, args.manifest)
    except PreflightError as error:
        print(f"check_flash_inputs: {error.code}: {error.message}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"check_flash_inputs: read-failed: {error}", file=sys.stderr)
        return 2

    print(f"preflight ok: {result.device} ({result.device_name})")
    print(f"images: {result.image_dir}")
    print(f"manifest: {result.manifest}")
    for entry in result.entries:
        print(f"  {entry.filename}  {entry.size} bytes  sha256 {entry.digest}")
    print(
        "note: SHA-256 verifies the local copy, not the publisher. Verify the "
        "official GrapheneOS OpenSSH signature separately."
    )
    print("No write, USB access, bootloader command, or flash was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
