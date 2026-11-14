"""Deterministic SHA-256 manifests for private Castela release artifacts.

The manifest is deliberately simple, reproducible JSON. It records the exact
bytes that were signed, not a mutable build directory. ``SHA256SUMS`` is emitted
for operators and older verification scripts; ``manifest.json.sha256`` covers the
manifest itself so a checksum file cannot be silently replaced with one for a
different release.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from collections.abc import Iterable
from typing import Any

from release.errors import ChecksumError

SCHEMA = 1
RELEASE_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$")
RESERVED_NAMES = {
    "approval.json",
    "candidate.json",
    "manifest.json",
    "manifest.json.sha256",
    "manifest.sig",
    "manifest.sig.sha256",
    "release-record.json",
    "SHA256SUMS",
}
_HASH_CHUNK = 1024 * 1024


def sha256_file(path: pathlib.Path | str) -> str:
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_release_id(release_id: str) -> str:
    if not isinstance(release_id, str) or not RELEASE_ID_RE.fullmatch(release_id):
        raise ChecksumError(
            "release id must be 1-64 characters of letters, digits, dot, dash, or underscore"
        )
    return release_id


def validate_artifact_name(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ChecksumError("artifact name is empty or contains an unsafe character")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ChecksumError("artifact name contains a control character")
    if name.startswith("/"):
        raise ChecksumError(f"artifact name must be relative: {name!r}")
    if pathlib.PurePosixPath(name).as_posix() != name:
        raise ChecksumError(f"artifact name is not canonical: {name!r}")
    parts = pathlib.PurePosixPath(name).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ChecksumError(f"artifact name contains a traversal segment: {name!r}")
    if name in RESERVED_NAMES:
        raise ChecksumError(f"artifact name {name!r} is reserved for release metadata")
    return name


def artifact_entry(
    path: pathlib.Path | str,
    *,
    name: str | None = None,
    role: str = "artifact",
) -> dict[str, Any]:
    source = pathlib.Path(path)
    if not source.is_file():
        raise ChecksumError(f"artifact is not a regular file: {source}")
    artifact_name = validate_artifact_name(name or source.name)
    return {
        "name": artifact_name,
        "role": role,
        "sha256": sha256_file(source),
        "size": source.stat().st_size,
    }


def build_manifest(
    release_id: str,
    artifacts: Iterable[dict[str, Any]],
    *,
    signing: Iterable[dict[str, Any]] | None = None,
    approval: dict[str, Any] | None = None,
    previous_release: dict[str, Any] | None = None,
    config_sha256: str | None = None,
    created: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest from artifacts that already exist."""

    validate_release_id(release_id)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        entry = dict(artifact)
        name = validate_artifact_name(entry.get("name", ""))
        if name in seen:
            raise ChecksumError(f"duplicate artifact name {name!r}")
        seen.add(name)
        digest = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ChecksumError(f"artifact {name!r} has no valid SHA-256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ChecksumError(f"artifact {name!r} has no valid size")
        entries.append(
            {
                "name": name,
                "role": str(entry.get("role", "artifact")),
                "sha256": digest,
                "size": size,
            }
        )
    if not entries:
        raise ChecksumError("a release manifest needs at least one artifact")
    entries.sort(key=lambda item: item["name"])

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "release_id": release_id,
        "artifacts": entries,
        "total_size": sum(entry["size"] for entry in entries),
    }
    if config_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", config_sha256):
            raise ChecksumError("config_sha256 must be a lowercase SHA-256")
        manifest["config_sha256"] = config_sha256
    if signing is not None:
        manifest["signing"] = list(signing)
    if approval is not None:
        manifest["approval"] = approval
    if previous_release is not None:
        manifest["previous_release"] = previous_release
    if created is not None:
        manifest["created"] = created
    manifest["manifest_sha256"] = digest_json(manifest)
    return manifest


def verify_manifest_digest(manifest: dict[str, Any]) -> None:
    expected = manifest.get("manifest_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ChecksumError("manifest has no valid manifest_sha256")
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    actual = digest_json(payload)
    if actual != expected:
        raise ChecksumError("manifest_sha256 does not match the manifest contents")


def write_manifest_bundle(manifest: dict[str, Any], out_dir: pathlib.Path | str) -> dict[str, pathlib.Path]:
    """Write ``manifest.json``, ``SHA256SUMS``, and ``manifest.json.sha256``."""

    verify_manifest_digest(manifest)
    target = pathlib.Path(out_dir)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = target / "manifest.json"
    sums_path = target / "SHA256SUMS"
    digest_path = target / "manifest.json.sha256"

    manifest_text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    os.chmod(manifest_path, 0o600)

    lines = [
        f"{artifact['sha256']}  {artifact['name']}\n"
        for artifact in sorted(manifest["artifacts"], key=lambda item: item["name"])
    ]
    sums_path.write_text("".join(lines), encoding="utf-8")
    os.chmod(sums_path, 0o600)

    digest_line = f"{manifest['manifest_sha256']}  manifest.json\n"
    digest_path.write_text(digest_line, encoding="utf-8")
    os.chmod(digest_path, 0o600)
    return {
        "manifest": manifest_path,
        "sums": sums_path,
        "digest": digest_path,
    }


def load_manifest(path: pathlib.Path | str) -> dict[str, Any]:
    source = pathlib.Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ChecksumError(f"manifest not found: {source}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChecksumError(f"cannot read manifest: {error}") from error
    if not isinstance(data, dict):
        raise ChecksumError("manifest must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise ChecksumError("manifest schema is not supported")
    validate_release_id(data.get("release_id"))
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ChecksumError("manifest has no artifacts")
    verify_manifest_digest(data)
    return data


def _resolve_artifact(root: pathlib.Path, name: str) -> pathlib.Path:
    validate_artifact_name(name)
    target = (root / name).resolve()
    root_resolved = root.resolve()
    if target == root_resolved or not target.is_relative_to(root_resolved):
        raise ChecksumError(f"artifact path escapes the release directory: {name!r}")
    return target


def verify_artifacts(
    manifest: dict[str, Any],
    artifacts_dir: pathlib.Path | str,
    *,
    allow_extra: bool = True,
) -> None:
    """Verify every manifest entry against the files on disk."""

    verify_manifest_digest(manifest)
    root = pathlib.Path(artifacts_dir)
    if not root.is_dir():
        raise ChecksumError(f"artifact directory does not exist: {root}")
    expected_names: set[str] = set()
    for artifact in manifest["artifacts"]:
        name = validate_artifact_name(artifact.get("name", ""))
        expected_names.add(name)
        target = _resolve_artifact(root, name)
        if not target.is_file():
            raise ChecksumError(f"artifact is missing: {name}")
        actual_size = target.stat().st_size
        if actual_size != artifact.get("size"):
            raise ChecksumError(f"artifact size mismatch: {name}")
        actual_digest = sha256_file(target)
        if actual_digest != artifact.get("sha256"):
            raise ChecksumError(f"artifact checksum mismatch: {name}")

    if not allow_extra:
        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        extra = present - expected_names - RESERVED_NAMES
        if extra:
            raise ChecksumError(f"unexpected files in release directory: {sorted(extra)}")


def verify_checksum_files(
    manifest_path: pathlib.Path | str,
    artifacts_dir: pathlib.Path | str,
) -> None:
    """Verify the on-disk manifest, checksum list, and every artifact."""

    manifest = load_manifest(manifest_path)
    root = pathlib.Path(artifacts_dir)
    verify_artifacts(manifest, root)
    digest_path = root / "manifest.json.sha256"
    if digest_path.is_file():
        line = digest_path.read_text(encoding="utf-8").strip()
        expected = f"{manifest['manifest_sha256']}  manifest.json"
        if line != expected:
            raise ChecksumError("manifest.json.sha256 does not match manifest.json")
    sums_path = root / "SHA256SUMS"
    if sums_path.is_file():
        lines = [line for line in sums_path.read_text(encoding="utf-8").splitlines() if line]
        expected_lines = [
            f"{artifact['sha256']}  {artifact['name']}"
            for artifact in sorted(manifest["artifacts"], key=lambda item: item["name"])
        ]
        if lines != expected_lines:
            raise ChecksumError("SHA256SUMS does not match the manifest")

    signature_path = root / "manifest.sig"
    signature_digest_path = root / "manifest.sig.sha256"
    if signature_path.is_file() != signature_digest_path.is_file():
        raise ChecksumError("manifest.sig and manifest.sig.sha256 must be present together")
    if signature_path.is_file() and signature_digest_path.is_file():
        expected_signature = f"{sha256_file(signature_path)}  manifest.sig"
        if signature_digest_path.read_text(encoding="utf-8").strip() != expected_signature:
            raise ChecksumError("manifest.sig.sha256 does not match manifest.sig")
