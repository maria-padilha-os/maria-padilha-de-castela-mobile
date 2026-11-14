#!/usr/bin/env python3
"""Generate a checksum manifest for an already-built private release directory.

This helper does not sign, approve, or upload anything. Use
``python3 -m release.pipeline`` for the signed release flow. It is useful when
the build host needs to hand a deterministic SHA-256 manifest to the release
owner before approval.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from release.checksums import (
    RESERVED_NAMES,
    artifact_entry,
    build_manifest,
    load_manifest,
    validate_release_id,
    write_manifest_bundle,
)
from release.errors import ReleaseError

ARTIFACT_ROLES = {"app", "ota", "factory", "artifact"}


def infer_role(path: pathlib.Path) -> str:
    name = path.name.lower()
    if path.suffix.lower() in {".apk", ".aab"}:
        return "app"
    if path.suffix.lower() == ".ota" or "ota" in name:
        return "ota"
    if path.suffix.lower() == ".img" or "factory" in name:
        return "factory"
    return "artifact"


def is_inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve(strict=False)
    root = ROOT.resolve()
    return resolved == root or resolved.is_relative_to(root)


def collect(directory: pathlib.Path, overrides: dict[str, str]) -> list[dict[str, object]]:
    entries = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(directory).as_posix()
        if relative in RESERVED_NAMES:
            continue
        role = overrides.get(relative, infer_role(path))
        entries.append(artifact_entry(path, name=relative, role=role))
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--artifacts", required=True, help="directory of built artifacts")
    parser.add_argument("--output", required=True, help="directory for the manifest bundle")
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        metavar="NAME=ROLE",
        help="override an artifact role (app, ota, factory, artifact)",
    )
    parser.add_argument("--previous-manifest")
    args = parser.parse_args(argv)

    try:
        validate_release_id(args.release_id)
        source = pathlib.Path(args.artifacts).resolve()
        output = pathlib.Path(args.output).resolve()
        if not source.is_dir():
            raise ReleaseError(f"artifact directory not found: {source}")
        if is_inside_repo(source) or is_inside_repo(output):
            raise ReleaseError("artifacts and manifest output must live outside the repository")
        overrides: dict[str, str] = {}
        for item in args.role:
            if "=" not in item:
                raise ReleaseError("--role must use NAME=ROLE")
            name, role = item.split("=", 1)
            if role not in ARTIFACT_ROLES:
                raise ReleaseError(f"artifact role must be one of {sorted(ARTIFACT_ROLES)}")
            overrides[name] = role
        entries = collect(source, overrides)
        if not entries:
            raise ReleaseError("no artifacts found")
        previous = None
        if args.previous_manifest:
            prior = load_manifest(args.previous_manifest)
            if prior["release_id"] == args.release_id:
                raise ReleaseError("the previous release must have a different release id")
            previous = {
                "release_id": prior["release_id"],
                "manifest_sha256": prior["manifest_sha256"],
            }
        manifest = build_manifest(
            args.release_id,
            entries,
            previous_release=previous,
        )
        bundle = write_manifest_bundle(manifest, output)
        print(json.dumps(
            {
                "release_id": manifest["release_id"],
                "manifest": str(bundle["manifest"]),
                "manifest_sha256": manifest["manifest_sha256"],
                "artifacts": len(manifest["artifacts"]),
            },
            indent=2,
            sort_keys=True,
        ))
        return 0
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
