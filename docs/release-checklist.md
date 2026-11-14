# Private release checklist

- **Applies to:** every Castela Mobile app, OTA, or factory-image release
- **Release owner:** a named human, not an automation account
- **Required reviewers:** release owner plus security reviewer; OTA/factory
  promotion requires both
- **Pipeline:** [Private release and signing pipeline](release-pipeline.md)
- **Configuration:** [`release/signing.example.toml`](../release/signing.example.toml)

Complete this checklist in the private release record. Do not paste key
passwords, private key material, keystore contents, or tester personal data into
it. A checked box is not approval; the named humans must sign the approval
record described in section 8.

## 1. Release identity

- [ ] Version name and monotonic version code are recorded: `__________`
- [ ] Release ID follows the pipeline format: `__________`
- [ ] Source commit on the private branch is recorded: `__________`
- [ ] Build host and isolated signing host are identified: `__________`
- [ ] Reference device and supported-device matrix are recorded: `__________`
- [ ] Release notes state the minimum Android/GrapheneOS version and migration
      notes.
- [ ] This release is app-layer only, unless a separate system-image ADR was
      approved. No bootloader, verified-boot, or OS trust-root change is smuggled
      into an app release.

## 2. Scope and legal gates

- [ ] The build contains only Castela code, assets, and permitted dependencies.
- [ ] No GrapheneOS OS image, vendor blob, proprietary firmware, or OS update
      package is redistributed in the bundle.
- [ ] The product is described as "Castela Mobile, an independent project that
      runs on GrapheneOS", not as GrapheneOS or an official/unofficial
      GrapheneOS build.
- [ ] Third-party license texts, NOTICE material, and the SBOM are present.
- [ ] The asset provenance record covers new or changed artwork and fonts.
- [ ] The legal review required by the
      [redistribution rules](legal/grapheneos-aosp-attribution.md) is complete
      for this recipient group.
- [ ] Tester distribution, if any, is authenticated, time-limited, logged, and
      limited to the approved recipient list.

## 3. Build and tests

- [ ] The build was produced from the recorded commit, not an uncommitted tree.
- [ ] `tests/all.sh` passes on the release commit.
- [ ] Release-specific unit and instrumentation tests pass on the reference
      device.
- [ ] No debug build, debug key, test-only exported component, or verbose
      signing log is in the release.
- [ ] The APK/AAB has a monotonic version code and the expected package name.
- [ ] `android:debuggable="false"` and the release backup/permission settings
      are confirmed.
- [ ] The source diff since the prior release was reviewed for permission,
      exported-component, network, and telemetry changes.

## 4. Key custody and configuration

- [ ] `release/signing.example.toml` was copied to a private signing host outside
      the checkout and reviewed for this release.
- [ ] Every key and certificate path resolves outside the repository.
- [ ] Key files are regular files, not group/world readable, in a directory that
      is not group/world writable.
- [ ] Expected key SHA-256 values are pinned in the private configuration and
      match the custodian's record.
- [ ] The key inventory shows all keys active, not expired, and not revoked.
- [ ] The signing host is offline or on the isolated signing network.
- [ ] The signing job has no public inbound access and cannot publish to a public
      host.
- [ ] Configuration validation passes:

      ```sh
      python3 -m release.pipeline validate-config \
        --config /srv/castela-private/signing.toml \
        --require-material
      ```

- [ ] App, OTA, factory-image, and manifest keys are distinct. An app key is not
      used for an OTA or factory image.
- [ ] The manifest key's public certificate fingerprint is recorded:
      `__________`

## 5. Candidate artifacts and checksums

Run `prepare` outside the checkout and record the candidate digest.

- [ ] Candidate release ID: `__________`
- [ ] Candidate `candidate_sha256`: `__________`
- [ ] Previous release ID and manifest digest: `__________`
- [ ] Every artifact in the candidate is the intended build output.
- [ ] The candidate contains no key, keystore, password, `.env`, packet capture,
      tester data, or debug symbol with private paths.
- [ ] Artifact table reviewed:

      | Artifact | Role | SHA-256 | Size |
      | --- | --- | --- | --- |
      | `__________` | app/ota/factory | `__________` | `__________` |
      | `__________` | app/ota/factory | `__________` | `__________` |

- [ ] `previous_release` points at the last known good build, not an arbitrary
      older build.
- [ ] The candidate and configuration digests match the values the approvers
      reviewed.

## 6. Manual security review

- [ ] The security panel still uses public Android APIs only and makes no
      privileged or kernel-level visibility claim.
- [ ] Pcap capture and network inventory still require explicit user action, show
      a persistent indicator where applicable, and store data app-privately.
- [ ] No automatic scanning, hidden service, root path, `sharedUserId`, or
      telemetry was added.
- [ ] The launcher requests no `QUERY_ALL_PACKAGES`; the security panel does not
      request `MANAGE_EXTERNAL_STORAGE`.
- [ ] Sensitive exports warn that packet captures may contain personal data and
      that exports are the user's responsibility.
- [ ] No public screenshot, release note, or test artifact exposes signing
      material, key paths, or private infrastructure.

## 7. Explicit human approval

Approval is mandatory. The `approval.required = true` setting cannot be disabled,
and automation accounts are rejected.

- [ ] Release owner reviewed the checklist and candidate: `__________`
- [ ] Security reviewer reviewed the checklist and candidate: `__________`
- [ ] Both approvers saw the same `candidate_sha256` and checklist digest.
- [ ] The approvers explicitly confirm: "I approve this exact private Castela
      release for signing."
- [ ] The approval record was created with an exact release-ID confirmation:

      ```sh
      python3 -m release.pipeline approve \
        --config /srv/castela-private/signing.toml \
        --candidate /srv/castela-build/out/candidate.json \
        --approver "Release Owner Name" \
        --approver "Security Reviewer Name" \
        --confirm-release-id 2026.11.14-tegu.1 \
        --out /srv/castela-private/approvals/2026.11.14-tegu.1.json
      ```

- [ ] Approval record digest and expiry: `__________`
- [ ] No approval was created by an agent, CI job, bot, or script impersonating a
      human.
- [ ] If the candidate, checklist, configuration, or build output changes, this
      approval is discarded and the review restarts.

## 8. Signing, verification, and private storage

- [ ] Signing ran only after the approval record validated.
- [ ] The signed release has `manifest.json`, `SHA256SUMS`,
      `manifest.json.sha256`, `manifest.sig`, `manifest.sig.sha256`, and
      `release-record.json`.
- [ ] The final manifest digest is recorded: `__________`
- [ ] The manifest signature verifies against the manifest public certificate.
- [ ] `verify` passes with the signed manifest and artifacts.
- [ ] The manifest covers every signed artifact, including the candidate and
      approval records.
- [ ] The release was uploaded to the private store with authenticated access.
- [ ] Store permissions are `0700` for directories and `0600` for files, or the
      private bucket denies public access and anonymous listing.
- [ ] No GitHub Pages, public release page, public package mirror, public bucket,
      or unauthenticated download URL exists for this release.
- [ ] The upload destination and access log entry are recorded: `__________`

## 9. Rollback to the prior build

Do not delete the prior release. A rollback restores the previous build and must
be rehearsed before an incident.

- [ ] The prior release directory, manifest, checksums, and signature are present
      in the private store.
- [ ] The prior manifest passes `verify` and its checksums match.
- [ ] The prior build's signature certificate is still trusted and not revoked.
- [ ] The Android package downgrade behavior is understood. A lower version code
      normally requires uninstalling or a factory reset; document the supported
      path and data-loss risk.
- [ ] The rollback target is recorded: `__________`
- [ ] The rollback command was rehearsed on a non-production channel:

      ```sh
      python3 -m release.pipeline rollback \
        --config /srv/castela-private/signing.toml \
        --to 2026.10.31-tegu.1 \
        --approver "Release Owner Name" \
        --reason "Regression in 2026.11.14-tegu.1" \
        --confirm-release-id 2026.10.31-tegu.1
      ```

- [ ] `channel/current.json` points at the prior release and
      `channel/history/` retains the rollback record.
- [ ] Testers are told which build to install, how to verify its checksum, and
      whether data will be preserved.
- [ ] The failed release is quarantined, not silently overwritten, and its
      artifacts remain available for incident analysis.

## 10. Key rotation and revocation notes

### Rotation

- [ ] App-key rotation has a tested upgrade path from every supported version.
- [ ] OTA/factory-key rotation has a new ADR, a reviewed trust-anchor transition,
      and a recovery plan for devices that cannot receive the new anchor.
- [ ] Old and new public certificates are recorded in the signed release record.
- [ ] The old key remains available for rollback only until the supported upgrade
      window closes, then is revoked.
- [ ] The rotation date, reason, custodian, and new fingerprint are recorded:
      `__________`

### Revocation

- [ ] If a key is suspected compromised, signing stopped immediately.
- [ ] The key is marked revoked in the private inventory and blocked in the
      pipeline configuration.
- [ ] Affected releases signed by the key are identified from the release record
      and manifest signatures.
- [ ] Audit logs and manifests are preserved; evidence was not deleted.
- [ ] A signed private advisory names the affected versions and the replacement
      build.
- [ ] App releases are re-signed and tested from every supported version.
- [ ] OTA/factory trust-anchor recovery follows the new ADR and explicitly warns
      about a possible wipe.
- [ ] Revocation date, incident owner, notification list, and verification result
      are recorded: `__________`

## 11. Release record and sign-off

Attach or link the following in the private release record:

- [ ] Candidate manifest and approval record.
- [ ] Final manifest, `SHA256SUMS`, manifest signature, and signature digest.
- [ ] Test output and device smoke-test result.
- [ ] SBOM, license notices, privacy notice, and asset provenance changes.
- [ ] Private store location, access log, and recipient list.
- [ ] Prior release and rollback verification result.
- [ ] Key fingerprints, rotation/revocation status, and incident notes.

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Release owner | `__________` | `__________` | approve / reject |
| Security reviewer | `__________` | `__________` | approve / reject |
| Key custodian | `__________` | `__________` | keys verified / blocked |

**Do not sign, upload, distribute, or call this release final until every
required box is checked and both named humans have approved the exact candidate.
Automation cannot approve a release.**
