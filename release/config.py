"""Validate private Castela release and signing configuration.

Signing material is deliberately kept outside the checkout. This module only
reads a configuration file inside the repository; private keys and certificates
are referenced by absolute paths that are rejected if they resolve anywhere
inside the repository. The tools never print or copy key material.

The configuration is a small TOML file. See ``release/signing.example.toml`` for
a complete example and ``docs/release-pipeline.md`` for the custody rules.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import stat
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import tomllib

from release.errors import ConfigError

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
VALID_ROLES = ("app", "ota", "factory", "manifest")
VALID_ACCESS = {"filesystem", "iam", "mtls", "oidc"}
PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
FORBIDDEN_EXECUTABLES = {
    "doas",
    "mount",
    "pacman",
    "pkexec",
    "runuser",
    "su",
    "sudo",
    "systemctl",
}
SIGNER_REQUIRED_PLACEHOLDERS = {"input", "output", "key"}
SIGNER_OPTIONAL_PLACEHOLDERS = {"alias", "cert", "key_id"}


def canonical_json(value: Any) -> str:
    """Return canonical JSON used for stable configuration fingerprints."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KeySpec:
    id: str
    role: str
    algorithm: str
    path: pathlib.Path
    certificate: pathlib.Path | None
    expected_sha256: str | None
    alias: str | None
    custody: str

    def public_summary(self) -> dict[str, str]:
        summary = {
            "id": self.id,
            "role": self.role,
            "algorithm": self.algorithm,
            "custody": self.custody,
        }
        if self.expected_sha256:
            summary["key_sha256"] = self.expected_sha256
        return summary


@dataclass(frozen=True)
class SignerSpec:
    role: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class StoreSpec:
    uri: str
    visibility: str
    access: str
    path: pathlib.Path | None
    bucket: str | None
    prefix: str
    scheme: str


@dataclass(frozen=True)
class ApprovalSpec:
    required: bool
    min_approvers: int
    max_age_hours: int
    checklist: str
    checklist_path: pathlib.Path


@dataclass(frozen=True)
class SigningConfig:
    source: pathlib.Path
    project: str
    release_channel: str
    schema: int
    store: StoreSpec
    approval: ApprovalSpec
    keys: tuple[KeySpec, ...]
    signers: dict[str, SignerSpec]

    def key_for_role(self, role: str) -> KeySpec:
        for key in self.keys:
            if key.role == role:
                return key
        raise ConfigError(f"no signing key is configured for the {role!r} role")

    def signer_for_role(self, role: str) -> SignerSpec:
        try:
            return self.signers[role]
        except KeyError as error:
            raise ConfigError(f"no signer command is configured for the {role!r} role") from error

    def public_signing_plan(self, roles: tuple[str, ...]) -> list[dict[str, str]]:
        plan = []
        for role in sorted(set(roles)):
            key = self.key_for_role(role)
            plan.append(key.public_summary())
        return plan

    def fingerprint(self) -> str:
        payload = {
            "schema": self.schema,
            "project": self.project,
            "release_channel": self.release_channel,
            "store": {
                "uri_sha256": sha256_text(self.store.uri),
                "visibility": self.store.visibility,
                "access": self.store.access,
            },
            "approval": {
                "required": self.approval.required,
                "min_approvers": self.approval.min_approvers,
                "max_age_hours": self.approval.max_age_hours,
                "checklist": self.approval.checklist,
            },
            "keys": [key.public_summary() for key in self.keys],
            "signers": [
                {"role": role, "command": list(spec.command)}
                for role, spec in sorted(self.signers.items())
            ],
        }
        return sha256_text(canonical_json(payload))

    def public_summary(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "release_channel": self.release_channel,
            "store": {
                "scheme": self.store.scheme,
                "visibility": self.store.visibility,
                "access": self.store.access,
            },
            "approval": {
                "required": self.approval.required,
                "min_approvers": self.approval.min_approvers,
                "max_age_hours": self.approval.max_age_hours,
                "checklist": self.approval.checklist,
            },
            "keys": [key.public_summary() for key in self.keys],
            "signer_roles": sorted(self.signers),
            "config_sha256": self.fingerprint(),
        }


def _table(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a TOML table")
    return value


def _string(table: dict[str, Any], key: str, label: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _boolean(table: dict[str, Any], key: str, label: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{label}.{key} must be true or false")
    return value


def _integer(table: dict[str, Any], key: str, label: str) -> int:
    value = table.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{label}.{key} must be an integer")
    return value


def _outside_repo(raw: str, repo_root: pathlib.Path, label: str) -> pathlib.Path:
    expanded = os.path.expanduser(raw.strip())
    path = pathlib.Path(expanded)
    if not path.is_absolute():
        raise ConfigError(f"{label} must be an absolute path outside the repository")
    resolved = path.resolve(strict=False)
    if resolved == repo_root or resolved.is_relative_to(repo_root):
        raise ConfigError(f"{label} must live outside the repository")
    return resolved


def _parse_keys(raw: Any, repo_root: pathlib.Path) -> tuple[KeySpec, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("at least one [[keys]] entry is required")
    keys: list[KeySpec] = []
    ids: set[str] = set()
    roles: set[str] = set()
    for index, item in enumerate(raw):
        table = _table(item, f"keys[{index}]")
        key_id = _string(table, "id", f"keys[{index}]")
        role = _string(table, "role", f"keys[{index}]")
        if role not in VALID_ROLES:
            raise ConfigError(f"key {key_id!r} has unsupported role {role!r}")
        if key_id in ids:
            raise ConfigError(f"duplicate signing key id {key_id!r}")
        if role in roles:
            raise ConfigError(f"more than one signing key is configured for role {role!r}")
        ids.add(key_id)
        roles.add(role)

        algorithm = _string(table, "algorithm", f"keys[{index}]")
        custody = _string(table, "custody", f"keys[{index}]")
        key_path = _outside_repo(
            _string(table, "path", f"keys[{index}]"),
            repo_root,
            f"signing key {key_id!r}",
        )
        certificate_raw = table.get("certificate")
        certificate = None
        if certificate_raw is not None:
            certificate = _outside_repo(
                _string(table, "certificate", f"keys[{index}]"),
                repo_root,
                f"certificate for {key_id!r}",
            )
        expected = table.get("sha256")
        if expected is not None:
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                raise ConfigError(f"key {key_id!r} has a malformed expected sha256")
            expected = expected.lower()
        alias = table.get("alias")
        if alias is not None and (not isinstance(alias, str) or not alias.strip()):
            raise ConfigError(f"key {key_id!r} has a malformed alias")
        keys.append(
            KeySpec(
                id=key_id,
                role=role,
                algorithm=algorithm,
                path=key_path,
                certificate=certificate,
                expected_sha256=expected,
                alias=alias.strip() if isinstance(alias, str) else None,
                custody=custody,
            )
        )

    if "manifest" not in roles:
        raise ConfigError("a manifest signing key is required for the release checksum manifest")
    return tuple(keys)


def _validate_command(command: Any, role: str, keys: dict[str, KeySpec]) -> tuple[str, ...]:
    if not isinstance(command, list) or not command:
        raise ConfigError(f"signer {role!r} must have a non-empty command list")
    if not all(isinstance(part, str) and part for part in command):
        raise ConfigError(f"signer {role!r} command parts must be non-empty strings")
    tokens = tuple(command)
    executable = pathlib.PurePath(tokens[0]).name.lower()
    if executable in FORBIDDEN_EXECUTABLES:
        raise ConfigError(f"signer {role!r} must not invoke a privileged command")
    for token in tokens[1:]:
        if pathlib.PurePath(token).name.lower() in FORBIDDEN_EXECUTABLES:
            raise ConfigError(f"signer {role!r} must not invoke a privileged command")

    placeholders = set(PLACEHOLDER_RE.findall(" ".join(tokens)))
    unknown = placeholders - SIGNER_REQUIRED_PLACEHOLDERS - SIGNER_OPTIONAL_PLACEHOLDERS
    if unknown:
        raise ConfigError(f"signer {role!r} uses unsupported placeholders: {sorted(unknown)}")
    missing = SIGNER_REQUIRED_PLACEHOLDERS - placeholders
    if missing:
        raise ConfigError(f"signer {role!r} is missing placeholders: {sorted(missing)}")
    key = keys.get(role)
    if key is None:
        raise ConfigError(f"signer {role!r} has no matching signing key")
    if "cert" in placeholders and key.certificate is None:
        raise ConfigError(f"signer {role!r} uses {{cert}} but the key has no certificate")
    if "alias" in placeholders and key.alias is None:
        raise ConfigError(f"signer {role!r} uses {{alias}} but the key has no alias")
    return tokens


def _parse_signers(raw: Any, keys: tuple[KeySpec, ...]) -> dict[str, SignerSpec]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ConfigError("[[signers]] must be a list")
    by_role = {key.role: key for key in keys}
    signers: dict[str, SignerSpec] = {}
    for index, item in enumerate(raw):
        table = _table(item, f"signers[{index}]")
        role = _string(table, "role", f"signers[{index}]")
        if role not in VALID_ROLES:
            raise ConfigError(f"signer has unsupported role {role!r}")
        if role in signers:
            raise ConfigError(f"duplicate signer role {role!r}")
        signers[role] = SignerSpec(
            role=role,
            command=_validate_command(table.get("command"), role, by_role),
        )
    for role in by_role:
        if role != "manifest" and role not in signers:
            raise ConfigError(f"no signer command is configured for the {role!r} role")
    return signers


def _parse_store(raw: Any, repo_root: pathlib.Path) -> StoreSpec:
    table = _table(raw, "store")
    uri = _string(table, "uri", "store")
    visibility = _string(table, "visibility", "store").lower()
    access = _string(table, "access", "store").lower()
    if visibility != "private":
        raise ConfigError("store.visibility must be 'private'")
    if access not in VALID_ACCESS:
        raise ConfigError(f"store.access must be one of {sorted(VALID_ACCESS)}")
    for key in ("public", "anonymous", "allow_public"):
        if table.get(key):
            raise ConfigError(f"store.{key} is not allowed")
    parsed = urllib.parse.urlsplit(uri)
    if parsed.username or parsed.password:
        raise ConfigError("store.uri must not embed credentials")
    if parsed.query or parsed.fragment:
        raise ConfigError("store.uri must not contain a query or fragment")

    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ConfigError("file store URI must be a local absolute path")
        if access != "filesystem":
            raise ConfigError("file store URI requires store.access = 'filesystem'")
        path = pathlib.Path(urllib.parse.unquote(parsed.path))
        if not path.is_absolute():
            raise ConfigError("file store URI must contain an absolute path")
        path = path.resolve(strict=False)
        if path == repo_root or path.is_relative_to(repo_root):
            raise ConfigError("the private artifact store must live outside the repository")
        return StoreSpec(uri, visibility, access, path, None, "", "file")

    if parsed.scheme == "s3":
        if access not in {"iam", "mtls"}:
            raise ConfigError("s3 store URI requires store.access = 'iam' or 'mtls'")
        bucket = parsed.netloc
        if not bucket:
            raise ConfigError("s3 store URI must name a bucket")
        return StoreSpec(
            uri,
            visibility,
            access,
            None,
            bucket,
            parsed.path.lstrip("/").rstrip("/"),
            "s3",
        )

    raise ConfigError(
        "store.uri must be file:// (private mount) or s3:// (authenticated private bucket); "
        "http(s), Pages, and package-mirror URLs are not allowed"
    )


def _parse_approval(raw: Any, repo_root: pathlib.Path) -> ApprovalSpec:
    table = _table(raw, "approval")
    required = _boolean(table, "required", "approval")
    if not required:
        raise ConfigError("approval.required must be true; releases cannot bypass human approval")
    min_approvers = _integer(table, "min_approvers", "approval")
    if min_approvers < 1 or min_approvers > 4:
        raise ConfigError("approval.min_approvers must be between 1 and 4")
    max_age_hours = _integer(table, "max_age_hours", "approval")
    if max_age_hours < 1 or max_age_hours > 24 * 30:
        raise ConfigError("approval.max_age_hours must be between 1 and 720")
    checklist = _string(table, "checklist", "approval").replace("\\", "/")
    checklist_path = (repo_root / checklist).resolve()
    if not checklist_path.is_relative_to(repo_root):
        raise ConfigError("approval.checklist must be a repository-relative file")
    if not checklist_path.is_file():
        raise ConfigError(f"approval checklist does not exist: {checklist}")
    return ApprovalSpec(required, min_approvers, max_age_hours, checklist, checklist_path)


def load_config(
    path: pathlib.Path | str,
    *,
    repo_root: pathlib.Path | str = REPO_ROOT,
    require_material: bool = False,
) -> SigningConfig:
    """Load and validate a signing configuration.

    ``require_material`` additionally checks that every key exists, is a regular
    file, is not group/world readable or writable, and matches its expected
    SHA-256 when one is configured.
    """

    source = pathlib.Path(path).resolve()
    root = pathlib.Path(repo_root).resolve()
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"signing configuration not found: {source}") from error
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read signing configuration: {error}") from error

    schema = data.get("schema")
    if schema != 1:
        raise ConfigError("signing configuration schema must be 1")
    project = _string(data, "project", "config")
    release_channel = _string(data, "release_channel", "config").lower()
    if release_channel not in {"private", "internal"}:
        raise ConfigError("release_channel must be 'private' or 'internal'")

    keys = _parse_keys(data.get("keys"), root)
    signers = _parse_signers(data.get("signers"), keys)
    store = _parse_store(data.get("store"), root)
    approval = _parse_approval(data.get("approval"), root)
    config = SigningConfig(
        source=source,
        project=project,
        release_channel=release_channel,
        schema=schema,
        store=store,
        approval=approval,
        keys=keys,
        signers=signers,
    )
    if require_material:
        verify_key_material(config)
    return config


def verify_key_material(
    config: SigningConfig, roles: Iterable[str] | None = None
) -> None:
    """Check key custody without reading key contents into logs.

    ``roles`` limits the check to the keys needed by one signing job. Config
    validation passes no roles so a signing-host setup check still covers every
    configured key.
    """

    wanted = set(roles) if roles is not None else None
    for key in config.keys:
        if wanted is not None and key.role not in wanted:
            continue
        try:
            info = key.path.stat()
        except OSError as error:
            raise ConfigError(f"signing key {key.id!r} is not available") from error
        if not stat.S_ISREG(info.st_mode):
            raise ConfigError(f"signing key {key.id!r} is not a regular file")
        if info.st_mode & 0o077:
            raise ConfigError(f"signing key {key.id!r} must not be group/world readable")
        try:
            parent_mode = key.path.parent.stat().st_mode
        except OSError as error:
            raise ConfigError(f"signing key {key.id!r} has no accessible parent directory") from error
        if parent_mode & 0o022:
            raise ConfigError(f"signing key {key.id!r} must not sit in a group/world writable directory")
        if key.expected_sha256:
            digest = hashlib.sha256(key.path.read_bytes()).hexdigest()
            if digest != key.expected_sha256:
                raise ConfigError(f"signing key {key.id!r} does not match its expected SHA-256")
        if key.certificate is not None and not key.certificate.is_file():
            raise ConfigError(f"certificate for {key.id!r} is not available")


def public_config_summary(config: SigningConfig) -> dict[str, Any]:
    return config.public_summary()
