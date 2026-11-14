"""Helpers for the private release and signing tests."""

from __future__ import annotations

import os
import pathlib
import sys

ROLES = ("app", "ota", "factory", "manifest")


def write(path: pathlib.Path, content: str, mode: int = 0o600) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)
    return path


def make_keys(base: pathlib.Path) -> dict[str, dict[str, pathlib.Path]]:
    keys: dict[str, dict[str, pathlib.Path]] = {}
    for role in ROLES:
        key = write(base / "keys" / f"{role}.pem", f"FAKE {role.upper()} KEY\n")
        cert = write(base / "keys" / f"{role}-cert.pem", f"FAKE {role.upper()} CERT\n", 0o644)
        keys[role] = {"key": key, "cert": cert}
    return keys


def make_signer(base: pathlib.Path) -> pathlib.Path:
    return write(
        base / "fake-signer.py",
        """#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
def value(flag):
    return args[args.index(flag) + 1]

source = pathlib.Path(value("--input"))
target = pathlib.Path(value("--output"))
target.write_bytes(source.read_bytes())
target.with_name(target.name + ".idsig").write_text(
    "fake detached signature for " + target.name + "\\n", encoding="utf-8"
)
""",
        0o700,
    )


def make_config(
    base: pathlib.Path,
    *,
    keys: dict[str, dict[str, pathlib.Path]] | None = None,
    signer: pathlib.Path | None = None,
    store_uri: str | None = None,
    checklist: str = "docs/release-checklist.md",
    min_approvers: int = 1,
    visibility: str = "private",
    access: str = "filesystem",
    approval_required: bool = True,
    extra_keys: str = "",
    extra_signers: str = "",
) -> pathlib.Path:
    keys = keys or make_keys(base)
    signer = signer or make_signer(base)
    store_uri = store_uri or (base / "store").as_uri()
    text = f"""schema = 1
project = "maria-padilha-de-castela-mobile"
release_channel = "private"

[store]
uri = "{store_uri}"
visibility = "{visibility}"
access = "{access}"

[approval]
required = {str(approval_required).lower()}
min_approvers = {min_approvers}
max_age_hours = 72
checklist = "{checklist}"

[[keys]]
id = "castela-app-release"
role = "app"
algorithm = "RSA-4096"
path = "{keys['app']['key']}"
certificate = "{keys['app']['cert']}"
alias = "castela-app"
custody = "test-offline"
sha256 = "{_sha(keys['app']['key'])}"

[[keys]]
id = "castela-ota-release"
role = "ota"
algorithm = "RSA-4096"
path = "{keys['ota']['key']}"
certificate = "{keys['ota']['cert']}"
custody = "test-offline"

[[keys]]
id = "castela-factory-release"
role = "factory"
algorithm = "RSA-4096"
path = "{keys['factory']['key']}"
certificate = "{keys['factory']['cert']}"
custody = "test-offline"

[[keys]]
id = "castela-manifest-release"
role = "manifest"
algorithm = "RSA-4096"
path = "{keys['manifest']['key']}"
certificate = "{keys['manifest']['cert']}"
custody = "test-offline"

[[signers]]
role = "app"
command = ["{sys.executable}", "{signer}", "--key", "{{key}}", "--input", "{{input}}", "--output", "{{output}}"]

[[signers]]
role = "ota"
command = ["{sys.executable}", "{signer}", "--key", "{{key}}", "--cert", "{{cert}}", "--input", "{{input}}", "--output", "{{output}}"]

[[signers]]
role = "factory"
command = ["{sys.executable}", "{signer}", "--key", "{{key}}", "--cert", "{{cert}}", "--input", "{{input}}", "--output", "{{output}}"]
{extra_keys}{extra_signers}"""
    return write(base / "signing.toml", text)


def _sha(path: pathlib.Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifacts(base: pathlib.Path) -> dict[str, pathlib.Path]:
    out = base / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    return {
        "Castela.apk": write(out / "Castela.apk", "fake apk bytes\n"),
        "castela-ota-tegu.zip": write(out / "castela-ota-tegu.zip", "fake ota bytes\n"),
        "factory-tegu.zip": write(out / "factory-tegu.zip", "fake factory bytes\n"),
    }
