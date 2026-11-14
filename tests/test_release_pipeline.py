"""End-to-end release pipeline, approval, private upload, and rollback tests."""

from __future__ import annotations

import json
import pathlib
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from release.approval import (
    APPROVAL_STATEMENT,
    create_approval,
    load_approval,
    validate_approval,
    write_approval,
)
from release.checksums import load_manifest, verify_checksum_files
from release.config import load_config
from release.errors import ApprovalError, PipelineError
from release.pipeline import (
    prepare_release,
    rollback_release,
    sign_release,
    upload_release,
    verify_release,
)
from tests.release_support import make_config, make_keys, write_artifacts

RELEASE_ID = "2026.11.14-tegu.1"


def fake_manifest_signature(manifest_path: pathlib.Path, signature_path: pathlib.Path) -> None:
    signature_path.write_text(
        "fake manifest signature for " + manifest_path.name + "\n", encoding="utf-8"
    )


class ReleasePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temporary.name)
        self.keys = make_keys(self.base)
        self.config_path = make_config(self.base, keys=self.keys)
        self.config = load_config(self.config_path, require_material=True)
        self.artifacts = write_artifacts(self.base)
        self.candidate_path = self.base / "candidate.json"
        self.candidate = prepare_release(
            self.config,
            RELEASE_ID,
            [str(path) for path in self.artifacts.values()],
            self.candidate_path,
        )
        self.approval_path = self.base / "approval.json"
        self.approval = create_approval(
            self.candidate,
            approvers=["Release Owner"],
            confirm_release_id=RELEASE_ID,
            checklist_path=self.config.approval.checklist_path,
        )
        write_approval(self.approval, self.approval_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def sign(self) -> tuple[pathlib.Path, dict[str, object]]:
        release = self.base / "release"
        record = sign_release(
            self.config,
            self.candidate_path,
            self.approval_path,
            release,
            manifest_signer=fake_manifest_signature,
        )
        return release, record

    def test_prepare_freezes_artifact_hashes_and_config(self) -> None:
        self.assertEqual(self.candidate["release_id"], RELEASE_ID)
        self.assertEqual(self.candidate["config_sha256"], self.config.fingerprint())
        self.assertEqual(len(self.candidate["artifacts"]), 3)
        self.assertEqual(
            {item["role"] for item in self.candidate["artifacts"]},
            {"app", "ota", "factory"},
        )
        self.assertTrue(self.candidate["candidate_sha256"])

    def test_approval_requires_exact_human_confirmation(self) -> None:
        with self.assertRaisesRegex(ApprovalError, "confirmation"):
            create_approval(
                self.candidate,
                approvers=["Release Owner"],
                confirm_release_id="wrong-release",
                checklist_path=self.config.approval.checklist_path,
            )
        with self.assertRaisesRegex(ApprovalError, "human"):
            create_approval(
                self.candidate,
                approvers=["ci"],
                confirm_release_id=RELEASE_ID,
                checklist_path=self.config.approval.checklist_path,
            )

    def test_approval_rejects_expired_and_stale_records(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(hours=100)
        old_approval = create_approval(
            self.candidate,
            approvers=["Release Owner"],
            confirm_release_id=RELEASE_ID,
            checklist_path=self.config.approval.checklist_path,
            now=old,
        )
        with self.assertRaisesRegex(ApprovalError, "older"):
            validate_approval(
                old_approval,
                self.candidate,
                checklist_path=self.config.approval.checklist_path,
                min_approvers=1,
                max_age_hours=72,
            )
        changed = json.loads(json.dumps(self.approval))
        changed["candidate_sha256"] = "0" * 64
        with self.assertRaisesRegex(ApprovalError, "candidate"):
            validate_approval(
                changed,
                self.candidate,
                checklist_path=self.config.approval.checklist_path,
                min_approvers=1,
                max_age_hours=72,
            )

    def test_sign_rejects_artifact_changed_after_prepare(self) -> None:
        self.artifacts["Castela.apk"].write_bytes(b"changed after approval\n")
        with self.assertRaisesRegex(PipelineError, "changed after prepare"):
            self.sign()

    def test_sign_rejects_config_changed_after_prepare(self) -> None:
        changed = self.config_path.read_text(encoding="utf-8")
        changed = changed.replace("min_approvers = 1", "min_approvers = 2", 1)
        self.config_path.write_text(changed, encoding="utf-8")
        changed_config = load_config(self.config_path, require_material=True)
        with self.assertRaisesRegex(PipelineError, "configuration changed"):
            sign_release(
                changed_config,
                self.candidate_path,
                self.approval_path,
                self.base / "release",
                manifest_signer=fake_manifest_signature,
            )

    def test_sign_and_verify_release(self) -> None:
        release, record = self.sign()
        manifest = load_manifest(release / "manifest.json")
        self.assertEqual(manifest["release_id"], RELEASE_ID)
        self.assertEqual(record["release_id"], RELEASE_ID)
        self.assertEqual(record["approval"]["approvers"], ["Release Owner"])
        self.assertTrue((release / "manifest.sig").is_file())
        self.assertTrue((release / "manifest.sig.sha256").is_file())
        self.assertTrue((release / "SHA256SUMS").is_file())
        self.assertTrue((release / "candidate.json").is_file())
        self.assertTrue((release / "approval.json").is_file())
        self.assertTrue(any(item["name"].endswith(".idsig") for item in manifest["artifacts"]))
        verify_checksum_files(release / "manifest.json", release)
        verify_release(release / "manifest.json", release)
        self.assertNotIn(str(self.keys["app"]["key"]), (release / "manifest.json").read_text())
        self.assertNotIn(str(self.keys["app"]["key"]), (release / "release-record.json").read_text())

    def test_tampered_signed_artifact_fails_verification(self) -> None:
        release, _record = self.sign()
        (release / "Castela.apk").write_bytes(b"tampered after signing\n")
        with self.assertRaisesRegex(Exception, "size mismatch|checksum mismatch"):
            verify_release(release / "manifest.json", release)

    def test_upload_uses_private_permissions_and_verifies(self) -> None:
        release, _record = self.sign()
        destination = pathlib.Path(upload_release(self.config, release))
        self.assertTrue(destination.is_dir())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.config.store.path.stat().st_mode), 0o700)
        for path in destination.rglob("*"):
            if path.is_file():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)
        verify_checksum_files(destination / "manifest.json", destination)
        with self.assertRaisesRegex(PipelineError, "already exists"):
            upload_release(self.config, release)

    def test_dry_run_does_not_create_release(self) -> None:
        result = sign_release(
            self.config,
            self.candidate_path,
            self.approval_path,
            self.base / "dry-release",
            dry_run=True,
        )
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["planned"]), 3)
        self.assertFalse((self.base / "dry-release").exists())
        self.assertNotIn(str(self.keys["app"]["key"]), json.dumps(result))

    def test_rollback_points_private_channel_to_target(self) -> None:
        release, _record = self.sign()
        upload_release(self.config, release)
        record = rollback_release(
            self.config,
            RELEASE_ID,
            approver="Release Owner",
            reason="rollback rehearsal",
            confirm_release_id=RELEASE_ID,
        )
        self.assertEqual(record["release_id"], RELEASE_ID)
        current = self.config.store.path / "channel" / "current.json"
        self.assertTrue(current.is_file())
        self.assertEqual(json.loads(current.read_text())["release_id"], RELEASE_ID)
        self.assertTrue(any((self.config.store.path / "channel" / "history").iterdir()))
        with self.assertRaisesRegex(PipelineError, "confirmation"):
            rollback_release(
                self.config,
                RELEASE_ID,
                approver="Release Owner",
                reason="wrong target",
                confirm_release_id="another-release",
            )

    def test_upload_rechecks_expired_approval(self) -> None:
        release, _record = self.sign()
        expired = json.loads((release / "approval.json").read_text())
        expired["approved_at"] = "2000-01-01T00:00:00Z"
        for item in expired["approvers"]:
            item["approved_at"] = "2000-01-01T00:00:00Z"
        (release / "approval.json").write_text(json.dumps(expired, indent=2) + "\n")
        with self.assertRaisesRegex(Exception, "older|checksum|manifest"):
            upload_release(self.config, release)

    def test_approval_statement_is_explicit(self) -> None:
        loaded = load_approval(self.approval_path)
        self.assertEqual(loaded["statement"], APPROVAL_STATEMENT)
        self.assertEqual(loaded["approvers"][0]["statement"], APPROVAL_STATEMENT)
        self.assertEqual(loaded["candidate_sha256"], self.candidate["candidate_sha256"])


if __name__ == "__main__":
    unittest.main()
