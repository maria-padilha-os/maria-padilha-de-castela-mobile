# Private release tooling

This directory contains the source for the private Castela release pipeline. It
never stores a signing key and it has no public publishing path.

- [`signing.example.toml`](signing.example.toml): copy to a private signing host
  outside the checkout and replace the sample paths.
- [`config.py`](config.py): rejects keys, certificates, and stores inside the
  repository; rejects public/anonymous stores and disabled approval.
- [`approval.py`](approval.py): named-human approval bound to one candidate,
  checklist version, and configuration digest.
- [`checksums.py`](checksums.py): deterministic SHA-256 manifest and verification.
- [`pipeline.py`](pipeline.py): `prepare`, `approve`, `sign`, `verify`, `upload`,
  and `rollback` commands.
- [`../docs/release-pipeline.md`](../docs/release-pipeline.md): the trust model,
  key custody, store policy, rotation, and revocation procedure.
- [`../docs/release-checklist.md`](../docs/release-checklist.md): the mandatory
  human checklist before signing.

Quick commands, from the repository root:

```sh
python3 -m release.pipeline validate-config \
  --config /srv/castela-private/signing.toml --require-material

python3 -m release.pipeline prepare \
  --config /srv/castela-private/signing.toml \
  --release-id 2026.11.14-tegu.1 \
  --artifact /srv/castela-build/out/Castela.apk \
  --artifact /srv/castela-build/out/castela-ota-tegu.zip \
  --artifact /srv/castela-build/out/factory-tegu.zip \
  --candidate /srv/castela-build/out/candidate.json
```

See the documentation before running `approve`, `sign`, or `upload`. Build
artifacts, candidates, approvals, and signed releases must stay outside this
checkout. Use the separate [`tools/release_manifest.py`](../tools/release_manifest.py)
only when a directory of already-built artifacts needs a standalone checksum
manifest; it does not sign anything and it does not upload.
