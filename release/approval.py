"""Explicit human approval records for a private Castela release.

An approval binds a named human to the exact candidate manifest, checklist
version, and configuration digest that were reviewed. It is not a signature made
with the release key: the private release key signs the final manifest only after
this record validates. Automation must never write an approval record with a
human's name.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from release.checksums import digest_json, sha256_file, validate_release_id
from release.errors import ApprovalError, ChecksumError

SCHEMA = 1
APPROVAL_STATEMENT = (
    "I reviewed the release checklist and the exact candidate artifacts, and I "
    "explicitly approve this private Castela release for signing."
)
AUTOMATION_NAMES = {
    "agent",
    "automation",
    "bot",
    "ci",
    "github-actions",
    "release-bot",
    "robot",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ApprovalError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ApprovalError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ApprovalError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def checklist_sha256(checklist_path: pathlib.Path | str) -> str:
    path = pathlib.Path(checklist_path)
    if not path.is_file():
        raise ApprovalError(f"release checklist not found: {path}")
    return sha256_file(path)


def verify_candidate(candidate: dict[str, Any]) -> str:
    """Verify a candidate manifest and return its stable digest."""

    if not isinstance(candidate, dict):
        raise ApprovalError("candidate manifest must be a JSON object")
    if candidate.get("schema") != SCHEMA:
        raise ApprovalError("candidate schema is not supported")
    try:
        validate_release_id(candidate.get("release_id"))
    except ChecksumError as error:
        raise ApprovalError(str(error)) from error
    expected = candidate.get("candidate_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ApprovalError("candidate has no valid candidate_sha256")
    payload = dict(candidate)
    payload.pop("candidate_sha256", None)
    actual = digest_json(payload)
    if actual != expected:
        raise ApprovalError("candidate manifest has changed since it was prepared")
    artifacts = candidate.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ApprovalError("candidate has no artifacts")
    names: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ApprovalError("candidate artifact entry is malformed")
        name = artifact.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ApprovalError("candidate has a missing or duplicate artifact name")
        names.add(name)
        if not isinstance(artifact.get("sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", artifact["sha256"]
        ):
            raise ApprovalError(f"candidate artifact {name!r} has no valid SHA-256")
    return expected


def create_approval(
    candidate: dict[str, Any],
    *,
    approvers: Iterable[str],
    confirm_release_id: str,
    checklist_path: pathlib.Path | str,
    now: datetime | None = None,
    valid_hours: int = 72,
) -> dict[str, Any]:
    """Create an approval record only after an exact release-id confirmation."""

    candidate_sha256 = verify_candidate(candidate)
    release_id = candidate.get("release_id")
    if confirm_release_id != release_id:
        raise ApprovalError("confirmation does not match the candidate release id")
    if valid_hours < 1 or valid_hours > 24 * 30:
        raise ApprovalError("approval validity must be between 1 and 720 hours")

    if isinstance(approvers, str):
        raise ApprovalError("approvers must be a list of human names")
    names: list[str] = []
    for raw in approvers:
        name = raw.strip()
        if not name:
            raise ApprovalError("an approver name is required")
        if name.lower() in AUTOMATION_NAMES:
            raise ApprovalError("approval must name a human, not an automation account")
        if name in names:
            raise ApprovalError(f"approver {name!r} is listed more than once")
        names.append(name)
    if not names:
        raise ApprovalError("at least one human approver is required")

    timestamp = (now or utc_now()).astimezone(timezone.utc)
    expires = timestamp + timedelta(hours=valid_hours)
    checklist_digest = checklist_sha256(checklist_path)
    approval = {
        "schema": SCHEMA,
        "release_id": release_id,
        "candidate_sha256": candidate_sha256,
        "config_sha256": candidate.get("config_sha256"),
        "checklist_sha256": checklist_digest,
        "checklist": candidate.get("checklist", pathlib.Path(checklist_path).name),
        "statement": APPROVAL_STATEMENT,
        "approvers": [
            {
                "name": name,
                "approved_at": timestamp.isoformat().replace("+00:00", "Z"),
                "statement": APPROVAL_STATEMENT,
            }
            for name in names
        ],
        "approved_at": timestamp.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "artifacts": [
            {"name": artifact["name"], "sha256": artifact["sha256"]}
            for artifact in sorted(candidate["artifacts"], key=lambda item: item["name"])
        ],
    }
    return approval


def write_approval(approval: dict[str, Any], path: pathlib.Path | str) -> pathlib.Path:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(
        json.dumps(approval, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(target, 0o600)
    return target


def load_approval(path: pathlib.Path | str) -> dict[str, Any]:
    source = pathlib.Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ApprovalError(f"approval record not found: {source}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApprovalError(f"cannot read approval record: {error}") from error
    if not isinstance(data, dict):
        raise ApprovalError("approval record must be a JSON object")
    return data


def validate_approval(
    approval: dict[str, Any],
    candidate: dict[str, Any],
    *,
    checklist_path: pathlib.Path | str,
    min_approvers: int,
    max_age_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fail closed unless this approval matches the exact candidate."""

    if min_approvers < 1:
        raise ApprovalError("min_approvers must be at least 1")
    if max_age_hours < 1:
        raise ApprovalError("max_age_hours must be at least 1")
    candidate_sha256 = verify_candidate(candidate)
    if approval.get("schema") != SCHEMA:
        raise ApprovalError("approval schema is not supported")
    if approval.get("release_id") != candidate.get("release_id"):
        raise ApprovalError("approval release id does not match the candidate")
    if approval.get("candidate_sha256") != candidate_sha256:
        raise ApprovalError("approval does not cover this candidate manifest")
    if approval.get("config_sha256") != candidate.get("config_sha256"):
        raise ApprovalError("approval does not cover this signing configuration")
    if approval.get("statement") != APPROVAL_STATEMENT:
        raise ApprovalError("approval statement is missing or was altered")

    expected_checklist = checklist_sha256(checklist_path)
    if approval.get("checklist_sha256") != expected_checklist:
        raise ApprovalError("the release checklist changed after approval; review it again")
    if "checklist" in candidate and approval.get("checklist") != candidate.get("checklist"):
        raise ApprovalError("approval was made against a different checklist file")

    expected_artifacts = [
        {"name": artifact["name"], "sha256": artifact["sha256"]}
        for artifact in sorted(candidate["artifacts"], key=lambda item: item["name"])
    ]
    if approval.get("artifacts") != expected_artifacts:
        raise ApprovalError("approval artifacts do not match the candidate artifacts")

    approvers = approval.get("approvers")
    if not isinstance(approvers, list):
        raise ApprovalError("approval record has no approvers list")
    names: list[str] = []
    current = (now or utc_now()).astimezone(timezone.utc)
    for item in approvers:
        if not isinstance(item, dict):
            raise ApprovalError("approval approver entry is malformed")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ApprovalError("approval approver name is missing")
        name = name.strip()
        if name.lower() in AUTOMATION_NAMES:
            raise ApprovalError("approval must name a human, not an automation account")
        if name in names:
            raise ApprovalError(f"approver {name!r} is duplicated")
        names.append(name)
        if item.get("statement") != APPROVAL_STATEMENT:
            raise ApprovalError(f"approval statement for {name!r} was altered")
        approved_at = parse_timestamp(item.get("approved_at"), f"approval time for {name!r}")
        if approved_at > current + timedelta(minutes=5):
            raise ApprovalError(f"approval time for {name!r} is in the future")
        if current - approved_at > timedelta(hours=max_age_hours):
            raise ApprovalError(f"approval for {name!r} is older than {max_age_hours} hours")
    if len(names) < min_approvers:
        raise ApprovalError(
            f"this release requires at least {min_approvers} human approver(s); found {len(names)}"
        )

    expires = approval.get("expires_at")
    if expires is not None and current > parse_timestamp(expires, "approval expiry"):
        raise ApprovalError("approval record has expired")

    return approval
