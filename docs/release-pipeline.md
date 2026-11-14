# Private release and signing pipeline

- **Status:** Implemented release tooling; no release has been produced
- **Date:** 2026-11-14
- **Scope:** `maria-padilha-de-castela-mobile`
- **Decision record:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- **Checklist:** [Release checklist](release-checklist.md)
- **Legal rules:** [Attribution, trademark, and redistribution](legal/grapheneos-aosp-attribution.md)
- **Configuration example:** [`release/signing.example.toml`](../release/signing.example.toml)

This document defines how a Castela Mobile artifact is built, approved, signed,
checksummed, and made available to the private project. It adds the release and
signing layer described by ADR 0001. It does **not** authorize a public release,
a ROM build, a bootloader unlock, a device flash, or a change to verified boot.

The short rule is: **the artifact store is private, the keys are outside the
repository, and a named human approves the exact bytes before a signing key is
used.**

## 1. What the pipeline covers

| Artifact | Signed by | Typical input | Notes |
| --- | --- | --- | --- |
| Castela app APK/AAB | `app` key, normally through `apksigner` | Gradle output from a private CI job | Separate keys per app in the full suite; this example uses one app-release identity |
| OTA update package | `ota` key through the audited image signer | OTA ZIP produced by the private image build | The signer must produce the update format the updater verifies, not a generic checksum |
| Factory image | `factory` key through the audited image signer | Device image or factory ZIP produced by the private image build | A changed factory-image trust root requires a new ADR and a migration plan |
| Checksum manifest | `manifest` key through `openssl dgst` or a configured manifest signer | Final `manifest.json` | Separates release metadata signing from the OTA/factory trust root |

The repository does not contain an Android SDK, a Gradle wrapper, a ROM source
tree, or an image builder. The pipeline operates on artifacts produced by the
private build job. The OTA/factory signer commands in
[`release/signing.example.toml`](../release/signing.example.toml) are placeholders
for the audited image-build tools; they are not a substitute for that build and
they do not unlock, flash, or modify a device.

## 2. Trust boundaries

| Material | Location | Access |
| --- | --- | --- |
| Repository source | Private Git remote | Maintainers only |
| Signing configuration | Private signing host, outside the checkout | Release engineers only |
| Private keys and certificates | Offline HSM or encrypted offline media, outside the checkout | Named key custodians only |
| Candidate artifacts | Private build staging directory, outside the checkout | Build and release jobs |
| Approval records | Private signing host or private store, never Git | Release owner and security reviewer |
| Signed releases | Private authenticated store, never a public page | Private project members only |

The repository's `.gitignore` excludes keys, keystores, PKCS#12 files, release
bundles, images, and packet captures. The configuration loader adds a second,
independent guard: a key or certificate path that resolves inside the checkout
is rejected even if it matches an ignored name.

## 3. Key custody

- Use one offline release key per app, plus separate OTA, factory-image, and
  manifest keys. Do not reuse the debug key, an app key for an OTA, or a
  GrapheneOS OS key for a Castela artifact.
- Keep keys on an offline HSM, a hardware token, or encrypted offline media.
  Keep an encrypted, tested backup in a separate physical location.
- The signing host is isolated, has no public inbound access, and writes only to
  the private artifact store.
- Key files must be regular files with no group or world permission bits, in a
  directory that is not group or world writable. The pipeline refuses otherwise.
- The configuration can pin a key's SHA-256. The release job verifies it before
  signing and records only key identifiers and public certificate digests, never
  key paths or key contents.
- Never print a key, password, keystore, or certificate private key in a build
  log. Never place one in a commit, an issue, a screenshot, or a chat message.

## 4. Pipeline stages

All commands run from the repository root and never need root. Build outputs,
candidate files, approval records, and signed releases must live outside the
checkout.

### 4.1 Build and prepare

The private build job produces the app, OTA, and factory-image inputs. Then:

```sh
python3 -m release.pipeline prepare \
  --config /srv/castela-private/signing.toml \
  --release-id 2026.11.14-tegu.1 \
  --artifact /srv/castela-build/out/Castela.apk \
  --artifact /srv/castela-build/out/castela-ota-tegu.zip \
  --artifact /srv/castela-build/out/factory-tegu.zip \
  --candidate /srv/castela-build/out/candidate.json \
  --previous-manifest /srv/castela-private/releases/2026.10.31-tegu.1/manifest.json
```

`prepare` writes a candidate manifest that freezes the exact artifact SHA-256
values, sizes, artifact roles, signing key identifiers, checklist digest, and
configuration fingerprint. It does not sign and does not call a key. The
`--previous-manifest` value records the build that a rollback would restore.

### 4.2 Explicit human approval

A named human reviews the [release checklist](release-checklist.md), the
candidate artifact hashes, the diff, the test results, and the prior release.
That human then runs:

```sh
python3 -m release.pipeline approve \
  --config /srv/castela-private/signing.toml \
  --candidate /srv/castela-build/out/candidate.json \
  --approver "Release Owner Name" \
  --confirm-release-id 2026.11.14-tegu.1 \
  --out /srv/castela-private/approvals/2026.11.14-tegu.1.json
```

The confirmation string must match the candidate release ID exactly. Approval
records name the human, bind the exact candidate digest, bind the checklist
version, and expire. Automation accounts (`agent`, `ci`, `bot`, and similar
names) are rejected. If the candidate, checklist, or configuration changes after
approval, `sign` refuses to proceed.

The approval record is not a substitute for the release-key signature. The key
is used only after the approval validates.

### 4.3 Sign and checksum

```sh
python3 -m release.pipeline sign \
  --config /srv/castela-private/signing.toml \
  --candidate /srv/castela-build/out/candidate.json \
  --approval /srv/castela-private/approvals/2026.11.14-tegu.1.json \
  --out /srv/castela-build/out/release-2026.11.14-tegu.1
```

`sign` invokes the configured signer for each artifact without a shell, then
re-hashes the signed outputs. It writes:

- `manifest.json`: the deterministic checksum manifest;
- `SHA256SUMS`: one `sha256  name` line per artifact;
- `manifest.json.sha256`: the manifest digest;
- `manifest.sig`: the detached signature over `manifest.json`;
- `manifest.sig.sha256`: the signature digest;
- `candidate.json` and `approval.json`: the exact approved inputs;
- `release-record.json`: release, approval, configuration, previous-build, and
  signature metadata.

A `--dry-run` prints the planned signer invocations with key paths redacted and
does not create a release directory.

### 4.4 Verify

```sh
python3 -m release.pipeline verify \
  --manifest /srv/castela-build/out/release-2026.11.14-tegu.1/manifest.json \
  --artifacts /srv/castela-build/out/release-2026.11.14-tegu.1 \
  --signature /srv/castela-build/out/release-2026.11.14-tegu.1/manifest.sig \
  --public-key /srv/castela-private/keys/manifest-release-cert.pem
```

Verification fails on a changed artifact, a changed manifest, a stale checksum
list, or an invalid signature. The update server must perform the same check
before serving an artifact.

### 4.5 Private upload

```sh
python3 -m release.pipeline upload \
  --config /srv/castela-private/signing.toml \
  --release-dir /srv/castela-build/out/release-2026.11.14-tegu.1
```

For a `file://` store, the pipeline copies the verified release into a new
release directory with `0700` directories and `0600` files, then verifies the
checksums at the destination. For an `s3://` store it requires an authenticated
AWS CLI session, forces `--acl private`, and writes only to the configured
private bucket. It never configures a public bucket policy.

Do not make the store reachable through GitHub Pages, a public release page, a
package mirror, an unauthenticated static server, or a forwarded link. The only
acceptable access is an authenticated private project channel with audit logs
and time-limited tester access.

## 5. Checksum manifest format

`manifest.json` is sorted, deterministic JSON with this shape:

```json
{
  "schema": 1,
  "release_id": "2026.11.14-tegu.1",
  "artifacts": [
    {
      "name": "Castela.apk",
      "role": "app",
      "sha256": "64 hexadecimal characters",
      "size": 123456
    }
  ],
  "total_size": 123456,
  "config_sha256": "64 hexadecimal characters",
  "signing": [{"id": "castela-app-release", "role": "app", "algorithm": "RSA-4096", "custody": "offline-hsm-with-encrypted-backup"}],
  "approval": {"candidate_sha256": "64 hexadecimal characters", "checklist_sha256": "64 hexadecimal characters", "approvers": ["Release Owner Name"]},
  "previous_release": {"release_id": "2026.10.31-tegu.1", "manifest_sha256": "64 hexadecimal characters"},
  "manifest_sha256": "64 hexadecimal characters"
}
```

The manifest digest is the SHA-256 of the canonical manifest with the
`manifest_sha256` field removed. `SHA256SUMS` is derived from the same artifact
list. The detached manifest signature is verified against the manifest key's
public certificate. Record the manifest digest and certificate fingerprint in
the release record so a later audit can identify the exact signed bytes.

## 6. Rollback to the prior build

Every `prepare` records the previous release manifest when one is supplied, and
the private store keeps the prior release directory intact. A rollback is a
private channel-pointer change, never a public "latest" URL:

```sh
python3 -m release.pipeline rollback \
  --config /srv/castela-private/signing.toml \
  --to 2026.10.31-tegu.1 \
  --approver "Release Owner Name" \
  --reason "Regression found in 2026.11.14-tegu.1; restoring the last known good build" \
  --confirm-release-id 2026.10.31-tegu.1
```

The tool verifies the target manifest and all of its checksums before writing
`channel/current.json`, keeps a history entry, and requires a named human and a
written reason. The full rollback and downgrade procedure, including Android
downgrade limits and tester communication, is in the
[release checklist](release-checklist.md#rollback-to-the-prior-build).

## 7. Key rotation and revocation

Rotation and revocation are release events, not a quiet edit to a path.

### 7.1 App signing key rotation

1. Create the new key in the same offline custody class and record its
   certificate fingerprint.
2. Test the upgrade path from the current release to a build signed with the new
   key on the reference device.
3. Use Android's app-signing key-rotation lineage where the installed app
   supports it, or ship a migration release signed by the old key that trusts the
   new key.
4. Update the private configuration and release both public certificates in the
   signed release record.
5. Keep the old key available for rollback until the supported upgrade window
   has passed, then revoke it.

### 7.2 OTA and factory-image key rotation

OTA and factory-image keys are a verified-boot and update trust-root change.
They are **not** rotated like an app key. A rotation requires a new ADR, a
reviewed trust-anchor transition, a tested recovery path, and a plan for devices
that cannot receive the new trust anchor. A lost OTA or factory key can strand
devices; assume a factory reset is required unless the transition was designed
and tested in advance.

### 7.3 Revocation

- On suspected compromise, stop signing immediately and mark the key revoked in
  the private key inventory.
- Preserve audit logs, the key inventory entry, and the affected release
  manifests. Do not destroy evidence.
- Revoke the certificate or key in the store and block further uploads that
  reference the revoked key id.
- Rotate to a new key and publish a signed advisory to the private project.
- For an app key, ship a re-signed release and test the upgrade from every
  supported version. For an OTA/factory key, follow the new-ADR trust-anchor
  transition and accept that some devices may need a wipe.
- Re-check every artifact signed by the compromised key, not only the latest.
- Record the incident, notification list, and recovery verification in the
  release record.

## 8. No public distribution

There is no public Pages site, public release, package mirror, public artifact
bucket, or unauthenticated artifact URL in this pipeline. The pipeline rejects
HTTP(S) stores, public visibility, anonymous access, and store URIs that resolve
inside the checkout. Testers receive time-limited, authenticated access; a link
that works without authentication is not private, even if it is hard to guess.

The repository and all build artifacts remain private. Do not push this branch
or any release branch to a public remote.

## 9. Tests and recurring checks

`tests/all.sh` runs the release tests together with the design, security-panel,
network-inventory, and pcap checks. The release tests cover:

- rejection of keys and certificates inside the repository;
- key file permissions and expected key digests;
- rejection of public or unauthenticated stores and disabled approval;
- deterministic SHA-256 manifest generation, checksum files, tamper detection,
  traversal rejection, and duplicate rejection;
- approval binding to the exact candidate, checklist, configuration, and human
  identity; expired and automation approvals fail;
- signing with an injected test signer, manifest verification, private upload
  permissions, and rollback pointer creation.

Before every release, run the full checklist and `tests/all.sh`. A release that
has not passed the repository tests is not eligible for approval.

## 10. Limitations and follow-up work

- The actual Gradle build, Android SDK, image builder, and image-signing tools
  are private build-host dependencies, not checked into this repository.
- The sample OTA/factory signer commands must be replaced with the audited
  image-build signers before a real image release. A generic digest signature is
  not an Android recovery OTA signature.
- No device is flashed by this pipeline. Device flashing remains outside this
  task and requires the separate safety and recovery review described by
  ADR 0001.
- The private store's retention, audit-log, and tester-access configuration are
  operational responsibilities of the private project. They are documented in
  the checklist but cannot be enforced by a repository test alone.
