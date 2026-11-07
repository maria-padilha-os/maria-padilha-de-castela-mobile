# Manifest pin

The upstream manifest is not copied into this repository. GrapheneOS stable
manifests already pin every project to a commit hash, and the release tag is
SSH-signed. Copying the full `default.xml` would duplicate thousands of lines,
invite drift, and make the signed upstream tag harder to audit.

What is pinned here:

- Upstream manifest: `https://github.com/GrapheneOS/platform_manifest.git`
- Ref: `refs/tags/2026110200`
- Signed tag object: `433433b931eeb4a33613a52acc545c08835e5f94`
- Commit: `abed042a17e948a9734e4c3927ce936b5648129f`
- AOSP baseline: `android-17.0.0_r1`
- Allowed-signers SHA-256:
  `344f59c6f058699e63fea68e35953b341c14e3bf1fbc1256f6baa84aa2aca1d0`

`config/release.env` is the machine-readable source of truth.
`config/grapheneos-allowed-signers` is the public key used to verify the tag;
its hash is pinned so a changed trust file cannot be substituted silently.

## Local manifest

`castela-local.xml` is copied to `.repo/local_manifests/castela.xml` by
`scripts/sync.sh`. It adds no projects yet. Castela-specific overlay projects,
when they exist, are added there and pinned to commits in the same change. The
file must never contain vendor blobs, firmware, release artifacts, or public
update metadata.

## Updating the pin

1. Pick a specific GrapheneOS stable release. Do not use the `17` development
   branch for this private build.
2. Update `config/release.env` with the new tag, tag object, commit and AOSP
   baseline after verifying the signature.
3. Run `./scripts/verify-pin.sh --network` and `./tests/all.sh`.
4. Update `docs/BUILD.md` and any test expectations that mention the old pin.
5. Re-sync into a fresh `.scratch/grapheneos` (or re-run `repo init` with
   `--force-sync` if the repository set changed).

The stable manifest points at commit hashes rather than per-repository tags, so
only the manifest tag needs signature verification.
