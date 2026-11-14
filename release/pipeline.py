#!/usr/bin/env python3
"""Private Castela release pipeline.

The pipeline has five explicit stages:

``prepare``  hash the exact candidate artifacts and freeze the signing config;
``approve``  let a named human approve that candidate (never automation);
``sign``     sign each artifact and the final checksum manifest;
``verify``   verify the manifest, checksums, and optional detached signature;
``upload``   copy a verified release into a private, access-controlled store.

There is no public upload path. The only built-in transport is a private
``file://`` store with 0700/0600 permissions; the optional ``s3://`` transport
uses an authenticated AWS CLI session and forces object ACLs to private. Nothing
in this module invokes sudo, mounts a filesystem, or writes to a system
partition.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from release.approval import (
    APPROVAL_STATEMENT,
    AUTOMATION_NAMES,
    checklist_sha256,
    create_approval,
    load_approval,
    validate_approval,
    verify_candidate,
    write_approval,
)
from release.checksums import (
    RESERVED_NAMES,
    artifact_entry,
    build_manifest,
    digest_json,
    load_manifest,
    sha256_file,
    validate_release_id,
    verify_checksum_files,
    write_manifest_bundle,
)
from release.config import (
    REPO_ROOT,
    KeySpec,
    SigningConfig,
    load_config,
    verify_key_material,
)
from release.errors import PipelineError, ReleaseError

CommandRunner = Callable[[list[str], dict[str, str], pathlib.Path], None]
ManifestSigner = Callable[[pathlib.Path, pathlib.Path], None]
ARTIFACT_ROLES = {"app", "ota", "factory"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve(strict=False)
    root = REPO_ROOT.resolve()
    return resolved == root or resolved.is_relative_to(root)


def _require_outside_repo(path: pathlib.Path, label: str) -> pathlib.Path:
    resolved = path.resolve(strict=False)
    if _is_inside_repo(resolved):
        raise PipelineError(f"{label} must live outside the repository")
    return resolved


def _write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PipelineError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise PipelineError(f"{path.name} must be a JSON object")
    return value


def classify_role(path: pathlib.Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in {".apk", ".aab"}:
        return "app"
    if suffix == ".ota" or "ota" in name:
        return "ota"
    if suffix == ".img" or "factory" in name:
        return "factory"
    raise PipelineError(
        f"cannot infer the signing role for {path.name!r}; pass --role NAME=ROLE"
    )


def _artifact_specs(
    artifacts: Iterable[str], roles: Iterable[str]
) -> list[dict[str, Any]]:
    role_overrides: dict[str, str] = {}
    for item in roles:
        if "=" not in item:
            raise PipelineError("--role must use NAME=ROLE")
        name, role = item.split("=", 1)
        if role not in ARTIFACT_ROLES:
            raise PipelineError(f"artifact role must be one of {sorted(ARTIFACT_ROLES)}")
        role_overrides[name] = role

    specs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in artifacts:
        if "=" in item:
            name, raw_path = item.split("=", 1)
        else:
            raw_path = item
            name = pathlib.Path(item).name
        path = pathlib.Path(raw_path).resolve()
        if name in seen:
            raise PipelineError(f"duplicate artifact name {name!r}")
        seen.add(name)
        if not path.is_file():
            raise PipelineError(f"artifact not found: {path}")
        if _is_inside_repo(path):
            raise PipelineError(f"build artifact {name!r} must be produced outside the repository")
        role = role_overrides.get(name) or classify_role(path)
        if role not in ARTIFACT_ROLES:
            raise PipelineError(f"artifact {name!r} has unsupported role {role!r}")
        specs.append({"name": name, "path": path, "role": role})
    if not specs:
        raise PipelineError("at least one --artifact is required")
    return specs


def prepare_release(
    config: SigningConfig,
    release_id: str,
    artifacts: Iterable[str],
    candidate_path: pathlib.Path | str,
    *,
    roles: Iterable[str] = (),
    previous_manifest: pathlib.Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Hash candidate artifacts and freeze the config for human review."""

    validate_release_id(release_id)
    target = _require_outside_repo(pathlib.Path(candidate_path), "candidate manifest")
    specs = _artifact_specs(artifacts, roles)

    entries = []
    for spec in specs:
        config.key_for_role(spec["role"])
        config.signer_for_role(spec["role"])
        entry = artifact_entry(spec["path"], name=spec["name"], role=spec["role"])
        entry["source"] = str(spec["path"])
        entries.append(entry)
    entries.sort(key=lambda item: item["name"])

    previous = None
    if previous_manifest is not None:
        prior = load_manifest(previous_manifest)
        if prior["release_id"] == release_id:
            raise PipelineError("the previous release must have a different release id")
        previous = {
            "release_id": prior["release_id"],
            "manifest_sha256": prior["manifest_sha256"],
        }

    created = _timestamp(now or utc_now())
    candidate: dict[str, Any] = {
        "schema": 1,
        "release_id": release_id,
        "created": created,
        "config_sha256": config.fingerprint(),
        "checklist": config.approval.checklist,
        "checklist_sha256": checklist_sha256(config.approval.checklist_path),
        "signing": config.public_signing_plan(tuple(item["role"] for item in entries)),
        "artifacts": entries,
    }
    if previous is not None:
        candidate["previous_release"] = previous
    candidate["candidate_sha256"] = digest_json(candidate)
    _write_json(target, candidate)
    return candidate


def _render_command(
    template: Iterable[str],
    key: KeySpec,
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    *,
    redact: bool = False,
) -> list[str]:
    values = {
        "input": str(input_path),
        "output": str(output_path),
        "key": f"<key:{key.id}>" if redact else str(key.path),
        "key_id": key.id,
    }
    if key.certificate is not None:
        values["cert"] = f"<cert:{key.id}>" if redact else str(key.certificate)
    if key.alias is not None:
        values["alias"] = key.alias
    rendered = []
    for part in template:
        for name, replacement in values.items():
            part = part.replace("{" + name + "}", replacement)
        rendered.append(part)
    return rendered


def _default_runner(command: list[str], env: dict[str, str], cwd: pathlib.Path) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=60 * 60,
            check=False,
        )
    except FileNotFoundError as error:
        raise PipelineError("the configured signer executable was not found") from error
    except subprocess.TimeoutExpired as error:
        raise PipelineError("the configured signer timed out") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise PipelineError(f"signer failed with exit code {result.returncode}: {detail}")


def _openssl_sign(key: KeySpec, input_path: pathlib.Path, signature_path: pathlib.Path) -> None:
    executable = shutil.which("openssl")
    if executable is None:
        raise PipelineError("openssl is required to sign the release manifest")
    result = subprocess.run(
        [
            executable,
            "dgst",
            "-sha256",
            "-sign",
            str(key.path),
            "-out",
            str(signature_path),
            str(input_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PipelineError("manifest signing failed; check the manifest key and its custody")


def _openssl_verify(
    public_key: pathlib.Path, input_path: pathlib.Path, signature_path: pathlib.Path
) -> None:
    executable = shutil.which("openssl")
    if executable is None:
        raise PipelineError("openssl is required to verify a detached signature")
    result = subprocess.run(
        [
            executable,
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature_path),
            str(input_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PipelineError("manifest signature verification failed")


def _collect_artifacts(root: pathlib.Path, original_roles: dict[str, str]) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in RESERVED_NAMES:
            continue
        role = original_roles.get(relative)
        if role is None:
            role = "signature" if relative.endswith((".sig", ".idsig")) else "artifact"
        entries.append(artifact_entry(path, name=relative, role=role))
    if not entries:
        raise PipelineError("signing produced no artifacts")
    return entries


def verify_candidate_artifacts(candidate: dict[str, Any]) -> None:
    """Re-hash the build outputs immediately before a signer sees them."""

    for artifact in candidate["artifacts"]:
        source = pathlib.Path(str(artifact.get("source", "")))
        if not source.is_file():
            raise PipelineError(f"candidate artifact is missing: {artifact['name']!r}")
        if source.stat().st_size != artifact.get("size"):
            raise PipelineError(
                f"candidate artifact changed after prepare (size): {artifact['name']!r}"
            )
        if sha256_file(source) != artifact.get("sha256"):
            raise PipelineError(f"candidate artifact changed after prepare: {artifact['name']!r}")


def _approval_summary(approval: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_sha256": approval["candidate_sha256"],
        "checklist_sha256": approval["checklist_sha256"],
        "approvers": [item["name"] for item in approval["approvers"]],
        "approved_at": approval["approved_at"],
        "expires_at": approval.get("expires_at"),
    }


def sign_release(
    config: SigningConfig,
    candidate_path: pathlib.Path | str,
    approval_path: pathlib.Path | str,
    out_dir: pathlib.Path | str,
    *,
    dry_run: bool = False,
    command_runner: CommandRunner | None = None,
    manifest_signer: ManifestSigner | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Sign artifacts and the checksum manifest after validating approval."""

    candidate = _read_json(pathlib.Path(candidate_path))
    verify_candidate(candidate)
    if candidate.get("config_sha256") != config.fingerprint():
        raise PipelineError("signing configuration changed after the candidate was prepared")
    verify_candidate_artifacts(candidate)
    approval = load_approval(approval_path)
    validate_approval(
        approval,
        candidate,
        checklist_path=config.approval.checklist_path,
        min_approvers=config.approval.min_approvers,
        max_age_hours=config.approval.max_age_hours,
        now=now,
    )
    verify_key_material(
        config,
        {artifact["role"] for artifact in candidate["artifacts"]} | {"manifest"},
    )

    destination = _require_outside_repo(pathlib.Path(out_dir), "release output directory")
    if destination.exists():
        raise PipelineError("release output directory already exists; choose a new directory")
    if not destination.parent.exists():
        destination.parent.mkdir(parents=True, mode=0o700)

    original_roles = {item["name"]: item["role"] for item in candidate["artifacts"]}
    runner = command_runner or _default_runner
    env = {
        **os.environ,
        "CASTELA_RELEASE_ID": candidate["release_id"],
        "CASTELA_CONFIG_SHA256": candidate["config_sha256"],
    }

    if dry_run:
        planned = []
        for artifact in candidate["artifacts"]:
            key = config.key_for_role(artifact["role"])
            signer = config.signer_for_role(artifact["role"])
            planned.append(
                {
                    "name": artifact["name"],
                    "role": artifact["role"],
                    "key_id": key.id,
                    "command": _render_command(
                        signer.command,
                        key,
                        pathlib.Path(artifact["source"]),
                        destination / artifact["name"],
                        redact=True,
                    ),
                }
            )
        return {
            "dry_run": True,
            "release_id": candidate["release_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "planned": planned,
        }

    staging = pathlib.Path(
        tempfile.mkdtemp(prefix=".castela-sign-", dir=str(destination.parent))
    )
    os.chmod(staging, 0o700)
    try:
        _write_json(staging / "candidate.json", candidate)
        _write_json(staging / "approval.json", approval)

        for artifact in candidate["artifacts"]:
            key = config.key_for_role(artifact["role"])
            signer = config.signer_for_role(artifact["role"])
            output = staging / artifact["name"]
            if not output.resolve().is_relative_to(staging.resolve()):
                raise PipelineError(f"artifact name escapes the staging directory: {artifact['name']!r}")
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            command = _render_command(
                signer.command, key, pathlib.Path(artifact["source"]), output
            )
            runner(command, env, staging)
            if not output.is_file() or output.stat().st_size == 0:
                raise PipelineError(f"signer did not produce {artifact['name']!r}")

        roles = dict(original_roles)
        roles["candidate.json"] = "approval"
        roles["approval.json"] = "approval"
        entries = _collect_artifacts(staging, roles)
        used_roles = tuple(item["role"] for item in entries if item["role"] in {"app", "ota", "factory"})
        signing_plan = config.public_signing_plan(used_roles + ("manifest",))
        created = _timestamp(now or utc_now())
        manifest = build_manifest(
            candidate["release_id"],
            entries,
            signing=signing_plan,
            approval=_approval_summary(approval),
            previous_release=candidate.get("previous_release"),
            config_sha256=candidate["config_sha256"],
            created=created,
        )
        bundle = write_manifest_bundle(manifest, staging)
        manifest_path = bundle["manifest"]

        signature_path = staging / "manifest.sig"
        manifest_key = config.key_for_role("manifest")
        manifest_signer_spec = config.signers.get("manifest")
        if manifest_signer is not None:
            manifest_signer(manifest_path, signature_path)
        elif manifest_signer_spec is not None:
            command = _render_command(
                manifest_signer_spec.command, manifest_key, manifest_path, signature_path
            )
            runner(command, env, staging)
        else:
            _openssl_sign(manifest_key, manifest_path, signature_path)
        if not signature_path.is_file() or signature_path.stat().st_size == 0:
            raise PipelineError("the signed release manifest has no signature")
        os.chmod(signature_path, 0o600)
        signature_digest = sha256_file(signature_path)
        (staging / "manifest.sig.sha256").write_text(
            f"{signature_digest}  manifest.sig\n", encoding="utf-8"
        )
        os.chmod(staging / "manifest.sig.sha256", 0o600)

        record = {
            "schema": 1,
            "release_id": candidate["release_id"],
            "created": created,
            "config_sha256": candidate["config_sha256"],
            "candidate_sha256": candidate["candidate_sha256"],
            "checklist": candidate.get("checklist"),
            "checklist_sha256": candidate.get("checklist_sha256"),
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_sig_sha256": signature_digest,
            "approval": _approval_summary(approval),
            "signing": signing_plan,
            "previous_release": candidate.get("previous_release"),
            "artifacts": [
                {
                    "name": item["name"],
                    "role": item["role"],
                    "sha256": item["sha256"],
                    "size": item["size"],
                }
                for item in manifest["artifacts"]
            ],
        }
        _write_json(staging / "release-record.json", record)
        verify_checksum_files(staging / "manifest.json", staging)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    verify_checksum_files(destination / "manifest.json", destination)
    return record


def verify_release(
    manifest_path: pathlib.Path | str,
    artifacts_dir: pathlib.Path | str,
    *,
    signature: pathlib.Path | str | None = None,
    public_key: pathlib.Path | str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    verify_checksum_files(manifest_path, artifacts_dir)
    if signature is not None or public_key is not None:
        if signature is None or public_key is None:
            raise PipelineError("both --signature and --public-key are required")
        _openssl_verify(
            pathlib.Path(public_key),
            pathlib.Path(manifest_path),
            pathlib.Path(signature),
        )
    return manifest


def _copy_private_tree(source: pathlib.Path, destination: pathlib.Path) -> None:
    destination.mkdir(parents=True, mode=0o700)
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise PipelineError("release directories must not contain symlinks")
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(mode=0o700, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(path, target)
            os.chmod(target, 0o600)


def _upload_s3(
    config: SigningConfig,
    release_dir: pathlib.Path,
    release_id: str,
    *,
    dry_run: bool,
) -> str:
    assert config.store.bucket is not None
    prefix = "/".join(part for part in (config.store.prefix, release_id) if part)
    base = f"s3://{config.store.bucket}/{prefix}"
    if dry_run:
        return base
    executable = shutil.which("aws")
    if executable is None:
        raise PipelineError("the aws CLI is required for an s3:// private store")
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(release_dir).as_posix()
        result = subprocess.run(
            [
                executable,
                "s3",
                "cp",
                str(path),
                f"{base}/{relative}",
                "--acl",
                "private",
                "--only-show-errors",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PipelineError(
                f"private store upload failed for {relative!r}: "
                f"{(result.stderr or '').strip()[-300:]}"
            )
    return base


def upload_release(
    config: SigningConfig,
    release_dir: pathlib.Path | str,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> str:
    """Copy a verified release into the private store after re-checking approval."""

    source = pathlib.Path(release_dir).resolve()
    if _is_inside_repo(source):
        raise PipelineError("the signed release directory must live outside the repository")
    if not source.is_dir():
        raise PipelineError(f"signed release directory not found: {source}")
    manifest = load_manifest(source / "manifest.json")
    verify_checksum_files(source / "manifest.json", source)
    record = _read_json(source / "release-record.json")
    if record.get("release_id") != manifest.get("release_id"):
        raise PipelineError("release record and manifest disagree about the release id")
    if record.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise PipelineError("release record does not match the signed manifest")

    candidate = _read_json(source / "candidate.json")
    if candidate.get("config_sha256") != config.fingerprint():
        raise PipelineError("signing configuration changed after the candidate was prepared")
    approval = load_approval(source / "approval.json")
    validate_approval(
        approval,
        candidate,
        checklist_path=config.approval.checklist_path,
        min_approvers=config.approval.min_approvers,
        max_age_hours=config.approval.max_age_hours,
        now=now,
    )
    recorded_approval = record.get("approval", {})
    if recorded_approval.get("candidate_sha256") != candidate.get("candidate_sha256"):
        raise PipelineError("release record does not match the approved candidate")
    if recorded_approval.get("approvers") != [item["name"] for item in approval["approvers"]]:
        raise PipelineError("release record approvers do not match the approval record")

    release_id = manifest["release_id"]
    if config.store.scheme == "s3":
        return _upload_s3(config, source, release_id, dry_run=dry_run)

    assert config.store.path is not None
    config.store.path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config.store.path, 0o700)
    destination = config.store.path / release_id
    if destination.exists():
        raise PipelineError(f"release {release_id!r} already exists in the private store")
    if dry_run:
        return str(destination)
    _copy_private_tree(source, destination)
    verify_checksum_files(destination / "manifest.json", destination)
    return str(destination)


def rollback_release(
    config: SigningConfig,
    target_release_id: str,
    *,
    approver: str,
    reason: str,
    confirm_release_id: str,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Point the private channel back to a previously published release."""

    validate_release_id(target_release_id)
    if confirm_release_id != target_release_id:
        raise PipelineError("rollback confirmation does not match the target release id")
    name = approver.strip()
    if not name or name.lower() in AUTOMATION_NAMES:
        raise PipelineError("rollback requires a named human approver")
    if not reason.strip():
        raise PipelineError("rollback requires a written reason")
    if config.store.scheme != "file" or config.store.path is None:
        raise PipelineError("rollback pointer updates are implemented for file:// private stores")
    store = config.store.path
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(store, 0o700)
    target = store / target_release_id
    manifest = load_manifest(target / "manifest.json")
    if manifest["release_id"] != target_release_id:
        raise PipelineError("target release directory does not match its manifest release id")
    verify_checksum_files(target / "manifest.json", target)

    channel_dir = store / "channel"
    current_path = channel_dir / "current.json"
    previous_release = None
    if current_path.is_file():
        previous_release = _read_json(current_path).get("release_id")
    record = {
        "schema": 1,
        "status": "rollback",
        "release_id": target_release_id,
        "manifest_sha256": manifest["manifest_sha256"],
        "rolled_back_from": previous_release,
        "approved_by": name,
        "reason": reason.strip(),
        "created": _timestamp(now or utc_now()),
    }
    if dry_run:
        return record
    channel_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = record["created"].replace(":", "").replace("-", "")
    _write_json(channel_dir / "history" / f"{stamp}.json", record)
    temporary = channel_dir / ".current.json.tmp"
    _write_json(temporary, record)
    os.replace(temporary, current_path)
    return record


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, approve, sign, verify, and privately store Castela releases."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="validate signing configuration")
    validate.add_argument("--config", required=True)
    validate.add_argument("--require-material", action="store_true")

    prepare = sub.add_parser("prepare", help="freeze candidate artifact checksums")
    prepare.add_argument("--config", required=True)
    prepare.add_argument("--release-id", required=True)
    prepare.add_argument("--artifact", action="append", default=[], metavar="[NAME=]PATH")
    prepare.add_argument("--role", action="append", default=[], metavar="NAME=ROLE")
    prepare.add_argument("--candidate", required=True)
    prepare.add_argument("--previous-manifest")

    approve = sub.add_parser("approve", help="record explicit human approval")
    approve.add_argument("--config", required=True)
    approve.add_argument("--candidate", required=True)
    approve.add_argument("--approver", action="append", default=[])
    approve.add_argument("--confirm-release-id", required=True)
    approve.add_argument("--out", required=True)

    sign = sub.add_parser("sign", help="sign artifacts and the checksum manifest")
    sign.add_argument("--config", required=True)
    sign.add_argument("--candidate", required=True)
    sign.add_argument("--approval", required=True)
    sign.add_argument("--out", required=True)
    sign.add_argument("--dry-run", action="store_true")

    verify = sub.add_parser("verify", help="verify checksums and a signed manifest")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--artifacts", required=True)
    verify.add_argument("--signature")
    verify.add_argument("--public-key")

    upload = sub.add_parser("upload", help="copy a verified release to the private store")
    upload.add_argument("--config", required=True)
    upload.add_argument("--release-dir", required=True)
    upload.add_argument("--dry-run", action="store_true")

    rollback = sub.add_parser("rollback", help="point the private channel at a prior release")
    rollback.add_argument("--config", required=True)
    rollback.add_argument("--to", required=True)
    rollback.add_argument("--approver", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--confirm-release-id", required=True)
    rollback.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-config":
            config = _config(args.config, require_material=args.require_material)
            _print_json(config.public_summary())
        elif args.command == "prepare":
            config = _config(args.config)
            candidate = prepare_release(
                config,
                args.release_id,
                args.artifact,
                args.candidate,
                roles=args.role,
                previous_manifest=args.previous_manifest,
            )
            print(
                f"prepared {candidate['release_id']} candidate "
                f"sha256={candidate['candidate_sha256']}"
            )
            print("Review the checklist and candidate artifacts before running approve.")
        elif args.command == "approve":
            config = _config(args.config)
            candidate = _read_json(pathlib.Path(args.candidate))
            verify_candidate(candidate)
            approval = create_approval(
                candidate,
                approvers=args.approver,
                confirm_release_id=args.confirm_release_id,
                checklist_path=config.approval.checklist_path,
                valid_hours=config.approval.max_age_hours,
            )
            target = pathlib.Path(args.out).resolve()
            if _is_inside_repo(target):
                raise PipelineError("approval records must be stored outside the repository")
            write_approval(approval, target)
            print("Approval recorded by: " + ", ".join(item["name"] for item in approval["approvers"]))
            print(APPROVAL_STATEMENT)
        elif args.command == "sign":
            config = _config(args.config)
            result = sign_release(
                config,
                args.candidate,
                args.approval,
                args.out,
                dry_run=args.dry_run,
            )
            _print_json(result)
        elif args.command == "verify":
            manifest = verify_release(
                args.manifest,
                args.artifacts,
                signature=args.signature,
                public_key=args.public_key,
            )
            print(
                f"verified {manifest['release_id']} "
                f"manifest_sha256={manifest['manifest_sha256']}"
            )
        elif args.command == "upload":
            config = _config(args.config)
            destination = upload_release(config, args.release_dir, dry_run=args.dry_run)
            prefix = "would upload to" if args.dry_run else "uploaded to"
            print(f"{prefix} {destination}")
        elif args.command == "rollback":
            config = _config(args.config)
            record = rollback_release(
                config,
                args.to,
                approver=args.approver,
                reason=args.reason,
                confirm_release_id=args.confirm_release_id,
                dry_run=args.dry_run,
            )
            _print_json(record)
        return 0
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _config(path: str, *, require_material: bool = False) -> SigningConfig:
    return load_config(path, require_material=require_material)


if __name__ == "__main__":
    sys.exit(main())
